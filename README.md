# Product Adds Management System

Last edit 3/7/26 by Julian Sivers

A desktop tool for generating ICSP (product master) and ICSW (warehouse/pricing) upload files for new product additions in Infor Cloudsuite Distribution (CSD). Built for internal use on Windows.

# The Problem

Managing 30+ warehouse locations with strict product setup rules created a bottleneck. Setting up a new vendor with thousands of items required manual data entry across multiple pages for initial ICSP and ICSW records, with copies needing manual adjustment for each warehouse—highly error-prone and slow.

Previous Excel-based solutions broke with large catalogs and didn’t scale after a company merger increased warehouse count. The process was manual, fragile, and time-consuming.

This tool automates and standardizes the entire product setup workflow, making it fast, reliable, and portable; anyone with data conversion access across the company can now complete tasks that previously took hours in minutes, reducing errors and scaling to thousands of items effortlessly.

---

## What It Does

Given a list of new products, the tool:

1. **Step 1 — ICSP** (`cp*.csv`): Builds the 166-column product master upload file. Applies vendor defaults, cleans descriptions, calculates dimensions/cubes, and generates IC/DC core records for supported core vendors (Whirlpool 825, GE 360).
2. **Step 2 — ICSW** (`cw*.csv`): Builds the warehouse/pricing upload file. Cross-joins every product against all active warehouses, applies tiered pricing multipliers, resolves list price per vendor rules, and sets seasonal/usage parameters.

Both outputs use hashed filenames (`cp{day}{hash}.csv` / `cw{day}{hash}.csv`) to avoid collisions.

---

## File Structure

```
ProductAddsManager/
├── ProductAddsManager.exe   ← compiled executable
├── data/
│   └── app_data.db          ← SQLite database (auto-created on first run)
├── config/
│   └── app_settings.json    ← folder path settings (auto-created on first run)
├── output/                  ← default output folder for generated CSVs
└── archive/                 ← default archive folder for processed input files
```

The `data/` and `config/` folders are created automatically on first launch if they don't exist. The database self-initializes with a Standard pricing rule and three default warehouses (25, 50, 13).

---

## First-Time Setup

### 1. Configure Folder Paths
Go to **File → Settings → Folders** and set:
- **Output Folder** — where `cp*.csv` and `cw*.csv` files are written
- **Product Adds Folder** — source folder watched for input files (informational)
- **Archive Folder** — where processed input files are moved

### 2. Configure Vendor Defaults
Go to **Settings → Vendor Defaults**. For each vendor number used in product adds, set:

| Field | Description |
|---|---|
| Brand Code | Default brand code applied if not specified per-product |
| Product Category | Default PRODCAT |
| Website Category | Default WEBCAT |
| Product Line | Default PRODLINE (used in ICSW) |
| Seasonal (y/n) | Drives `usgmths` (3 for seasonal, 6 for standard) and `usagectrl` |

Use **Download Vendor Template** → fill in bulk → **Upload Vendor Bulk** to load multiple vendors at once.

### 3. Configure Warehouses
Go to **Settings → Warehouses**. Each warehouse needs:

| Field | Values |
|---|---|
| Type | `D` = Distribution Center, `B` = Branch |
| ARP Whse | Required for type `B` only |
| Active | Checked = included in every ICSW run |

Default warehouses are pre-loaded. Edit or delete as needed.

### 4. Configure Pricing Rules
Go to **Settings → Pricing Rules**. Rules are looked up by vendor number; if no vendor-specific rule exists, `Standard` is used as fallback.

**List Handling options:**
- `list_or_base1.1` — use vendor list price as-is, unless it's below base price (floor at `base × 1.1`)
- `take_min` — use the lower of vendor list or calculated list

Multiplier columns cover cost tiers for both base price (`B-*`) and list price (`L-*`). Use **Download Pricing Template** to get a pre-formatted Excel file.

---

## Adding Products

### Option A — Upload a File
1. Select **Upload Excel/CSV File** on the Input tab
2. Click **Download Template** to get the correct column layout if needed
3. Browse to your filled-in file and click **Process**

**Required columns:** `PRODUCT`, `VENDOR NO`, `DESCRIPTION`, `REPL COST`

**Optional columns:** `CORE FLAG (Y)`, `LIST PRICE`, `LENGTH`, `WIDTH`, `HEIGHT`, `WEIGHT`, `BRAND CODE`, `PRODUCT CAT`, `WEBSITE CAT`

### Option B — Manual Entry
1. Select **Manual Form Entry**
2. Fill required fields (marked `*`) and click **Add to Batch**
3. Review products on the **Batch** tab; remove any unwanted rows
4. Click **Process**

---

## Core Products

Setting `CORE FLAG (Y)` = `Y` triggers automatic IC/DC record generation.

**Supported vendors only:**
- **Vendor 825 (Whirlpool):** prodline `WPCORE`, cost `$60.00`, description `CONTROL - ADD 60.00 CORE`
- **Vendor 360 (GE):** prodline `GECORE`, cost `$55.00`, description `CONTROL - ADD 55.00 CORE`

Core products for any other vendor will error with a clear message and must be set up manually. The rest of the batch will continue processing.

---

## Output Files

| File | Contents |
|---|---|
| `cp{day}{hash}.csv` | 166-column ICSP product master — upload via ICSP import |
| `cw{day}{hash}.csv` | ICSW warehouse/pricing records — upload via ICSW import |

Both files are written to the configured Output Folder. The Upload Log (File → View Upload Log) records every run with timestamp and record count.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| "No products in staging table" | No file loaded or batch is empty | Load a file or add products manually |
| "Pricing rules missing for vendor X" | Vendor has no pricing rule and no Standard fallback | Add rule under Settings → Pricing Rules |
| "Core products are only supported for Whirlpool (825) and GE (360)" | Core flag set for unsupported vendor | Set up that vendor's cores manually; remove the Y flag |
| Vendor defaults not applying | Vendor not configured | Add vendor under Settings → Vendor Defaults |
| Output folder not writable | Permissions or path doesn't exist | Update path under Settings → Folders |

---

## Deployment Notes

- **Single machine:** Copy the entire folder to the target machine and run `ProductAddsManager.exe`. No Python or other software required.
- **Pre-loaded deployment:** To ship with vendors, warehouses, and pricing rules already configured, run the tool once on a setup machine, configure everything, then copy the resulting `data/app_data.db` alongside the executable.
- **Empty deployment:** Delete `data/app_data.db` before distributing; the app recreates it with defaults on first launch.
