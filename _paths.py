# _paths.py
# Resolves runtime paths correctly whether running as:
#   - a plain Python script (development)
#   - a PyInstaller --onedir EXE (production)
#
# Import and use BASE_DIR instead of relying on os.getcwd():
#
#   from _paths import BASE_DIR
#   db_path = BASE_DIR / 'data' / 'app_data.db'

import sys
from pathlib import Path


def _get_base_dir() -> Path:
    """Return the directory that should be treated as the app root."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller EXE — use the folder containing the .exe
        return Path(sys.executable).parent
    else:
        # Running as a script — use the folder containing this file
        return Path(__file__).parent


BASE_DIR = _get_base_dir()
