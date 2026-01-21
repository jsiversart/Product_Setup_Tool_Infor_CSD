# app/step2_processor.py
# produces ICSW record upload
import pandas as pd
import sqlite3
from datetime import datetime
import os
today = datetime.today().strftime("%Y%m%d")

def validate_pricing_map(db, step1_df):
    pricing_df = pd.read_sql("SELECT * FROM pricing_map", db.conn)

    if pricing_df.empty:
        raise Exception(
            "pricing_map is empty. Upload pricing rules before running Step 2."
        )

    vendors = step1_df["VENDOR NO"].astype(str).unique()
    pricing_vendors = set(pricing_df["vendor"].astype(str)) | {"Standard"}

    missing = sorted(set(vendors) - pricing_vendors)

    if missing:
        raise Exception(
            f"Missing pricing rules for vendor(s): {', '.join(missing)}"
        )

    return pricing_df


def process_step2(db, step1_dataframe, output_folder):
    """
    Process Step 2 - Warehouse data generation (cw*.csv)
    Mirrors the logic from your standalone script
    """
    
    log_messages = []
    
    try:
        # Generate hashed output filename
        day_of_year = datetime.today().timetuple().tm_yday
        seconds = datetime.today().second + datetime.today().minute * 60
        hash_part = format(seconds % (36**3), '03x')
        output_filename = f"cw{day_of_year:03}{hash_part}.csv"
        output_path = os.path.join(output_folder, output_filename)
        
        # Verify pricing_map table exists and has data
        pricing_df = pd.read_sql("SELECT * FROM pricing_map", db.conn)

        if pricing_df.empty:
            raise Exception(
                "pricing_map is empty. Upload pricing rules before running Step 2."
            )
        
        vendors = step1_dataframe['VENDOR NO'].astype(str).unique()
        pricing_vendors = set(pricing_df['vendor'].astype(str)) | {'Standard'}

        missing = sorted(set(vendors) - pricing_vendors)

        if missing:
            raise Exception(
                f"Missing pricing rules for vendor(s): {', '.join(missing)}"
            )


        log_messages.append("✓ Pricing map verified")

        # Verify pricing_map table exists and has data
        whse_df = pd.read_sql("SELECT * FROM warehouse_info", db.conn)

        if whse_df.empty:
            raise Exception(
                "warehouse_info is empty. Add warehouse info in settings before running Step 2."
            )
        
        log_messages.append("✓ Warehouse existence verified")
        
        df = step1_dataframe.copy()

        df["VENDOR NO"] = df["VENDOR NO"].astype(str)
        pricing_df["vendor"] = pricing_df["vendor"].astype(str)

        df = df.merge(
            pricing_df,
            left_on="VENDOR NO",
            right_on="vendor",
            how="left",
            validate="many_to_one"
        )

        if df["vendor"].isna().any():
            missing = df.loc[df["vendor"].isna(), "VENDOR NO"].unique()
            raise ValueError(f"Missing pricing rules for vendors: {missing}")
        
        import numpy as np

        rc = df["REPL COST"]

        df["baseprice"] = np.select(
            [
                df["PRODLINE"].str.contains("CORE", na=False),
                rc < 1.5,
                rc < 5,
                rc < 50,
                rc < 75,
                rc < 100,
                rc < 500,
                rc < 1000,
            ],
            [
                rc,
                rc * df["B-0.01-1.49"],
                rc * df["B-1.5-4.99"],
                rc * df["B-5-49.99"],
                rc * df["B-50-74.99"],
                rc * df["B-75-99.99"],
                rc * df["B-100-499.99"],
                rc * df["B-500-999.99"],
            ],
            default=rc * df["B-1000-999999"]
            ).round(2)
        

        df["listprice_calc"] = np.select(
            [
                df["PRODLINE"].str.contains("CORE", na=False),
                rc < 5,
                rc < 50,
                rc < 75,
            ],
            [
                rc,
                rc * df["L-0.01-4.99"],
                rc * df["L-5-49.99.1"],
                rc * df["L-50-74.99.1"],
            ],
            default=rc * df["L-75-99999"]
            ).round(2)

        def resolve_list_price(row):
            if "CORE" in (row["PRODLINE"] or ""):
                return row["listprice_calc"]

            handling = row["Vendor List Handling"]
            list_price = row["LIST PRICE"]
            base = row["baseprice"]

            if pd.isna(handling):
                return row["listprice_calc"]

            if handling == "list_or_base1.1":
                if pd.isna(list_price):
                    return row["listprice_calc"]
                return max(list_price, base * 1.1)

            if handling == "take_min":
                if pd.isna(list_price):
                    return row["listprice_calc"]
                return min(list_price, row["listprice_calc"])

            raise ValueError(f"Unknown list handling: {handling}")

        df["listprice"] = df.apply(resolve_list_price, axis=1)

        active_whse = whse_df[whse_df["active"] == 1]

        df = df.merge(active_whse, how="cross")

        df["arptype"] = np.where(df["Type"] == "D", "V", "W")
        df["ordcalcty"] = np.where(df["Type"] == "D", "E", "M")
        df["leadtmavg"] = np.where(df["Type"] == "D", 21, 2)
        df["usgmths"] = df["SEASONAL"].map({"y": 3}).fillna(6)
        df["usagectrl"] = df["SEASONAL"].map({"y": "f"}).fillna("b")

        icsw_df = pd.DataFrame({
        # ---- keys / identity ----
        "prod": df["PRODUCT"],
        "whse": df["whse"],
        "enterdt": today,
        "statustype": "O",
        "serlottype": "",
        "snpocd": "",
        "reservety": "",
        "reservedays": "",
        "prodpreference": "",

        # ---- pricing ----
        "pricetype": "DEAL",
        "baseprice": df["baseprice"],
        "listprice": df["listprice"],

        # ---- flags ----
        "smanalfl": "",
        "autofillfl": "",
        "boshortfl": "",
        "countfl": "",

        # ---- ARP ----
        "arptype": df["arptype"],
        "arppushfl": "",
        "arpvendno": df["VENDOR NO"].astype("Int64"),
        "arpwhse": pd.to_numeric(df["Arpwhse"], errors="coerce").astype("Int64"),

        # ---- product attributes ----
        "prodline": df["PRODLINE"],
        "vendprod": "",
        "famgrptype": "",
        "ncnr": "",
        "rebatety": "",
        "rebsubty": "",
        "autoesrcbofl": "",

        # ---- bin / WM ----
        "binloc1": "",
        "binloc2": "",
        "wmfl": "",
        "wmallocty": "",
        "bintype": "",
        "wmpriority": "",
        "wmrestrict": "",

        # ---- freight ----
        "frtfreefl": "",
        "frtextra1": "",
        "frtextra2": "",

        # ---- units ----
        "unitbuy": "",
        "unitconv1": "",
        "unitediuom1": "",
        "unitstnd": "",
        "unitconv2": "",
        "unitediuom2": "",
        "unitwt": "",
        "unitconv3": "",
        "unitediuom3": "",

        # ---- safety / usage ----
        "safeallty": "D",
        "safeallamt": 0,
        "safetyfrzfl": "",
        "usagerate": "",
        "usgmths": df["usgmths"],
        "usmthsfrzfl": "yes",
        "usagectrl": df["usagectrl"],

        # ---- ordering ----
        "excludemovefl": "",
        "orderpt": "",
        "linept": "",
        "ordqtyin": "",
        "ordcalcty": df["ordcalcty"],
        "ordptadjty": "",
        "overreasin": "",
        "surplusty": "",
        "inclunavqty": "",
        "rolloanusagefl": "",

        # ---- ranking ----
        "companyrank": "",
        "whserank": "",
        "rankfreezefl": "",
        "threshrefer": "",
        "minthreshold": "",
        "minthreshexpdt": "",

        # ---- ASQ / HI5 ----
        "asqfl": "",
        "asqdifffl": "",
        "asqdiff": "",
        "hi5fl": "",
        "hi5difffl": "",
        "hi5diff": "",

        # ---- lead time ----
        "leadtmavg": df["leadtmavg"],
        "avgltdt": "",
        "leadtmlast": "",
        "lastltdt": "",
        "leadtmprio": "",
        "priorltdt": "",
        "frozenltty": 999,

        # ---- ABC ----
        "class": "",
        "classfrzfl": "",
        "abcgmroiclass": "",
        "abcsalesclass": "",
        "abcqtyclass": "",
        "abccustclass": "",
        "abcoverexpdt": "",
        "abcfinalclass": "",
        "abcclassdt": "",

        # ---- seasonality ----
        "seasbegmm": "",
        "seasendmm": "",
        "nodaysseas": "",
        "ordqtyout": "",
        "overreasout": "",
        "seastrendmax": "",
        "seastrendmin": "",
        "seastrendexpdt": "",
        "seastrendtyu": "",
        "seastrendlyu": "",
        "seasonfrzfl": "",

        # ---- tax ----
        "taxtype": "",
        "taxgroup": 1,
        "taxablety": "V",
        "nontaxtype": "",
        "tariffcd": "",
        "countryoforigin": "",
        "gststatus": "",

        # ---- cost ----
        "frozenmmyy": "",
        "frozentype": "",
        "frozenmos": "",
        "acquiredt": "",
        "so15fl": "",
        "lastsodt": "",
        "nodaysso": "",
        "notimesso": "",
        "availsodt": "",
        "avgcost": df["REPL COST"],
        "lastcost": "",
        "replcost": df["REPL COST"],
        "replcostdt": today,

        # ---- trailing fields ----
        "stndcost": "",
        "stndcostdt": "",
        "rebatecost": "",
        "addoncost": "",
        "datccost": "",
        "baseyrcost": "",
        "lastcostfor": "",
        "replcostfor": "",
        "qtyonhand": "",
        "qtyunavail": "",
        "reasunavty": "",})


        if icsw_df.isna().any().any():
            raise ValueError("Null values detected in ICSW output")

        expected_cols = icsw_df.shape[1]
        print(f"✓ ICSW columns: {expected_cols}")

            
        log_messages.append(f"✓ Generated {len(icsw_df)} warehouse records")
            
            # Export to CSV
        icsw_df.to_csv(output_path, index=False)
        log_messages.append(f"✓ Step 2 output saved: {output_filename}")
        
        return output_path, log_messages
        
    except Exception as e:
        log_messages.append(f"✗ Error in Step 2 processing: {str(e)}")
        return None, log_messages