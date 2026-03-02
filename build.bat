@echo off
setlocal enabledelayedexpansion

:: ============================================================
::  ProductAddsManager — Build Script
::  Builds a standalone Windows EXE using PyInstaller.
::  Optionally signs the output with an internal code-signing cert.
::
::  Prerequisites (developer machine only — not needed on target):
::    - Python 3.9-3.12 on PATH  (python.org, add to PATH during install)
::    - Internet access for first run (pip downloads packages)
::
::  Usage:
::    build.bat              — build only
::    build.bat /sign        — build then sign with internal cert
::    build.bat /sign /pack  — build, sign, then create a zip for distribution
:: ============================================================

set APP_NAME=ProductAddsManager
set DIST_DIR=dist\%APP_NAME%
set VENV_DIR=build_venv
set SIGN=0
set PACK=0

:: Parse arguments
for %%A in (%*) do (
    if /I "%%A"=="/sign" set SIGN=1
    if /I "%%A"=="/pack" set PACK=1
)

echo.
echo ============================================================
echo  %APP_NAME% Build Script
echo ============================================================
echo.

:: ----------------------------------------------------------
:: 1. Check Python
:: ----------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo         Install Python 3.9-3.12 from python.org
    echo         and check "Add Python to PATH" during install.
    pause & exit /b 1
)
for /f "tokens=*" %%V in ('python --version') do echo [OK] Found %%V

:: ----------------------------------------------------------
:: 2. Create virtual environment
:: ----------------------------------------------------------
if not exist %VENV_DIR% (
    echo [..] Creating virtual environment...
    "C:\Users\jsivers\AppData\Local\Programs\Python\Python313\python.exe" -m venv %VENV_DIR%
    if errorlevel 1 ( echo [ERROR] venv creation failed & pause & exit /b 1 )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

:: Activate venv
call %VENV_DIR%\Scripts\activate.bat

:: ----------------------------------------------------------
:: 3. Install / upgrade dependencies
:: ----------------------------------------------------------
echo [..] Installing dependencies...
pip install --quiet --upgrade pip
pip install --quiet ^
    FreeSimpleGUI ^
    pandas ^
    numpy ^
    openpyxl ^
    pyinstaller

if errorlevel 1 ( echo [ERROR] pip install failed & pause & exit /b 1 )
echo [OK] Dependencies installed.

:: ----------------------------------------------------------
:: 4. Create required folders if missing
:: ----------------------------------------------------------
if not exist app\templates mkdir app\templates

:: ----------------------------------------------------------
:: 5. Run PyInstaller
:: ----------------------------------------------------------
echo [..] Building with PyInstaller...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

pyinstaller ProductAddsManager.spec --noconfirm

if errorlevel 1 ( echo [ERROR] PyInstaller build failed & pause & exit /b 1 )
if not exist "%DIST_DIR%\%APP_NAME%.exe" (
    echo [ERROR] EXE not found after build — check PyInstaller output above.
    pause & exit /b 1
)
echo [OK] Build complete: %DIST_DIR%\%APP_NAME%.exe

:: ----------------------------------------------------------
:: 6. Copy runtime folders into the dist folder
:: ----------------------------------------------------------
echo [..] Copying runtime folders...

:: output/ — where CSVs are written; must exist but be empty
if not exist "%DIST_DIR%\output" mkdir "%DIST_DIR%\output"

:: archive/ — empty placeholder
if not exist "%DIST_DIR%\archive" mkdir "%DIST_DIR%\archive"

:: data/ — copy pre-loaded DB if one exists, otherwise create empty placeholder
:: To ship with vendors/pricing/warehouses pre-configured:
::   Run the app once, configure everything, then place the resulting
::   data\app_data.db next to this build script before building.
if exist data\app_data.db (
    if not exist "%DIST_DIR%\data" mkdir "%DIST_DIR%\data"
    copy /Y data\app_data.db "%DIST_DIR%\data\app_data.db" >nul
    echo [OK] Pre-loaded app_data.db included.
) else (
    if not exist "%DIST_DIR%\data" mkdir "%DIST_DIR%\data"
    echo [NOTE] No pre-loaded database found. App will create a fresh one on first launch.
)

:: config/ — empty; app creates app_settings.json on first run
if not exist "%DIST_DIR%\config" mkdir "%DIST_DIR%\config"

echo [OK] Runtime folders ready.

:: ----------------------------------------------------------
:: 7. Optional: Sign the EXE
:: ----------------------------------------------------------
if "%SIGN%"=="1" (
    echo.
    echo [..] Signing executable...

    :: Locate signtool — part of Windows SDK
    :: Adjust this path if your SDK is installed elsewhere
    set SIGNTOOL=
    for %%P in (
        "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
        "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe"
        "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"
    ) do (
        if exist %%P set SIGNTOOL=%%P
    )

    if "!SIGNTOOL!"=="" (
        echo [WARN] signtool.exe not found. Install Windows SDK or adjust the path in this script.
        echo        Skipping signing step.
        goto :skip_sign
    )

    :: The .pfx certificate file — generated by CERT_SETUP.md instructions
    set PFX_FILE=certs\internal_codesign.pfx

    if not exist "%PFX_FILE%" (
        echo [WARN] Certificate not found at %PFX_FILE%
        echo        Run the steps in CERT_SETUP.md to generate it first.
        echo        Skipping signing step.
        goto :skip_sign
    )

    :: Prompt for PFX password (set as env var or type here)
    if "%PFX_PASSWORD%"=="" (
        set /p PFX_PASSWORD=Enter PFX certificate password: 
    )

    "!SIGNTOOL!" sign ^
        /fd SHA256 ^
        /f "%PFX_FILE%" ^
        /p "!PFX_PASSWORD!" ^
        /tr http://timestamp.digicert.com ^
        /td SHA256 ^
        /d "%APP_NAME% Internal Build" ^
        "%DIST_DIR%\%APP_NAME%.exe"

    if errorlevel 1 (
        echo [ERROR] Signing failed. Check certificate and password.
        pause & exit /b 1
    )
    echo [OK] Executable signed successfully.

    :: Verify the signature
    "!SIGNTOOL!" verify /pa /v "%DIST_DIR%\%APP_NAME%.exe" >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Signature verification failed — cert may not yet be trusted on this machine.
        echo        See CERT_SETUP.md for how to install the cert on target machines.
    ) else (
        echo [OK] Signature verified.
    )
)
:skip_sign

:: ----------------------------------------------------------
:: 8. Optional: Package into a zip
:: ----------------------------------------------------------
if "%PACK%"=="1" (
    echo.
    echo [..] Packaging into zip...
    set ZIP_NAME=%APP_NAME%_v%DATE:~10,4%%DATE:~4,2%%DATE:~7,2%.zip

    :: Use PowerShell to zip (no 7-zip needed)
    powershell -Command ^
        "Compress-Archive -Path '%DIST_DIR%\*' -DestinationPath 'dist\!ZIP_NAME!' -Force"

    if errorlevel 1 (
        echo [WARN] Zip packaging failed. Distribute the dist\%APP_NAME% folder directly.
    ) else (
        echo [OK] Package ready: dist\!ZIP_NAME!
    )
)

:: ----------------------------------------------------------
:: Done
:: ----------------------------------------------------------
echo.
echo ============================================================
echo  Build complete!
echo.
echo  Distribute the entire folder:
echo    %DIST_DIR%\
echo.
echo  Users run:
echo    %APP_NAME%.exe
echo.
echo  No Python or other software needed on target machines.
echo ============================================================
echo.

call %VENV_DIR%\Scripts\deactivate.bat
pause
