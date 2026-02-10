# app/step2_processor.py
# Produces ICSW record upload using pure functional approach
import pandas as pd
import numpy as np
from datetime import datetime
import os


# ============================================================================
# PURE FUNCTIONS - No side effects, return new data
# ============================================================================

def calculate_base_price(repl_cost, prodline, pricing_rule):
    """Pure function: Calculate base price for a single product"""
    # CORE products use repl cost
    if "CORE" in (prodline or ""):
        return round(repl_cost, 2)
    
    # Tiered pricing based on replacement cost
    if repl_cost < 1.5:
        return round(repl_cost * pricing_rule["B-0.01-1.49"], 2)
    elif repl_cost < 5:
        return round(repl_cost * pricing_rule["B-1.5-4.99"], 2)
    elif repl_cost < 50:
        return round(repl_cost * pricing_rule["B-5-49.99"], 2)
    elif repl_cost < 75:
        return round(repl_cost * pricing_rule["B-50-74.99"], 2)
    elif repl_cost < 100:
        return round(repl_cost * pricing_rule["B-75-99.99"], 2)
    elif repl_cost < 500:
        return round(repl_cost * pricing_rule["B-100-499.99"], 2)
    elif repl_cost < 1000:
        return round(repl_cost * pricing_rule["B-500-999.99"], 2)
    else:
        return round(repl_cost * pricing_rule["B-1000-999999"], 2)


def calculate_list_price_calc(repl_cost, prodline, pricing_rule):
    """Pure function: Calculate theoretical list price"""
    if "CORE" in (prodline or ""):
        return round(repl_cost, 2)
    
    if repl_cost < 5:
        return round(repl_cost * pricing_rule["L-0.01-4.99"], 2)
    elif repl_cost < 50:
        return round(repl_cost * pricing_rule["L-5-49.99.1"], 2)
    elif repl_cost < 75:
        return round(repl_cost * pricing_rule["L-50-74.99.1"], 2)
    else:
        return round(repl_cost * pricing_rule["L-75-99999"], 2)


def resolve_final_list_price(list_price_calc, vendor_list_price, base_price, 
                              list_handling, prodline):
    """Pure function: Determine final list price based on vendor rules"""
    # CORE products always use calculated
    if "CORE" in (prodline or ""):
        return list_price_calc
    
    # No handling rule → use calculated
    if pd.isna(list_handling):
        return list_price_calc
    
    # list_or_base1.1: use vendor list unless it's below base price, then floor at base*1.1
    if list_handling == "list_or_base1.1":
        if pd.isna(vendor_list_price):
            return list_price_calc
        if vendor_list_price < base_price:
            return round(base_price * 1.1, 2)
        return vendor_list_price
    
    # take_min: use minimum of vendor list or calculated
    if list_handling == "take_min":
        if pd.isna(vendor_list_price):
            return list_price_calc
        return min(vendor_list_price, list_price_calc)
    
        # Unknown handling → prefer vendor list if available
    if not pd.isna(vendor_list_price):
        return vendor_list_price
    
    return list_price_calc

def calculate_usage_months(seasonal_flag):
    """Pure function: Calculate usage months based on seasonal flag"""
    return 3 if seasonal_flag == 'y' else 6


def calculate_usage_control(seasonal_flag):
    """Pure function: Calculate usage control based on seasonal flag"""
    return 'f' if seasonal_flag == 'y' else 'b'


def calculate_warehouse_fields(warehouse_type):
    """Pure function: Calculate warehouse-specific fields"""
    if warehouse_type == 'D':
        return {
            'arptype': 'V',
            'ordcalcty': 'E',
            'leadtmavg': 21
        }
    else:
        return {
            'arptype': 'W',
            'ordcalcty': 'M',
            'leadtmavg': 2
        }


# ============================================================================
# DATA TRANSFORMATION FUNCTIONS
# ============================================================================

def validate_pricing_map(db, staging_df):
    """Validate pricing map has all required vendors"""
    pricing_df = pd.read_sql("SELECT * FROM pricing_map", db.conn)
    
    if pricing_df.empty:
        raise Exception(
            "pricing_map is empty. Upload pricing rules before running Step 2."
        )
    
    # CORE-prodline products use repl_cost directly, no pricing rule needed
    non_core = staging_df[~staging_df["PRODLINE"].str.contains("CORE", na=False, case=False)]
    vendors = non_core["VENDOR NO"].astype(str).unique()
    pricing_vendors = set(pricing_df["vendor"].astype(str))
    
    missing = sorted(set(vendors) - pricing_vendors)
    
    if missing:
        raise Exception(
            f"Missing pricing rules for vendor(s): {', '.join(missing)}\n"
            f"Add these vendors to pricing rules ."
        )
    
    return pricing_df


def validate_warehouses(db):
    """Get active warehouses"""
    whse_df = pd.read_sql("SELECT * FROM warehouse_info WHERE active = 1", db.conn)
    
    if whse_df.empty:
        raise Exception(
            "warehouse_info is empty. Add warehouse info in settings."
        )
    
    return whse_df


def apply_pricing(staging_df, pricing_df):
    """Apply pricing rules to products"""
    df = staging_df.copy()
    
    # Ensure vendor columns are strings for merge
    df["VENDOR NO"] = df["VENDOR NO"].astype(str)
    pricing_df = pricing_df.copy()
    pricing_df["vendor"] = pricing_df["vendor"].astype(str)
    
    # Merge pricing rules (left join to keep all products)
    df = df.merge(
        pricing_df,
        left_on="VENDOR NO",
        right_on="vendor",
        how="left",
        validate="many_to_one"
    )
    
    # For vendors without specific rules, use 'Standard'
    standard_pricing = pricing_df[pricing_df["vendor"] == "Standard"]
    if not standard_pricing.empty:
        mask = df["vendor"].isna()
        for col in pricing_df.columns:
            if col not in ["vendor", "id"]:
                df.loc[mask, col] = standard_pricing[col].iloc[0]
    
    # Apply pure pricing functions using vectorized operations
    df["baseprice"] = df.apply(
        lambda row: calculate_base_price(
            row["REPL COST"], 
            row.get("PRODLINE"),
            row
        ),
        axis=1
    )
    
    df["listprice_calc"] = df.apply(
        lambda row: calculate_list_price_calc(
            row["REPL COST"],
            row.get("PRODLINE"),
            row
        ),
        axis=1
    )
    
    df["listprice"] = df.apply(
        lambda row: resolve_final_list_price(
            row["listprice_calc"],
            row.get("LIST PRICE"),
            row["baseprice"],
            row.get("Vendor List Handling"),
            row.get("PRODLINE")
        ),
        axis=1
    )
    
    # Calculate usage fields
    df["usgmths"] = df.get("SEASONAL", "n").apply(calculate_usage_months)
    df["usagectrl"] = df.get("SEASONAL", "n").apply(calculate_usage_control)
    
    return df


def expand_warehouses(priced_df, whse_df):
    """Cross join products with warehouses"""
    df = priced_df.copy()
    wh = whse_df.copy()
    
    # Create merge key for cross join
    df['_key'] = 1
    wh['_key'] = 1
    
    # Cross join
    expanded = df.merge(wh, on='_key', how='outer').drop('_key', axis=1)
    
    # Apply warehouse-specific calculations
    wh_fields = expanded['type'].apply(calculate_warehouse_fields)
    expanded['arptype'] = wh_fields.apply(lambda x: x['arptype'])
    expanded['ordcalcty'] = wh_fields.apply(lambda x: x['ordcalcty'])
    expanded['leadtmavg'] = wh_fields.apply(lambda x: x['leadtmavg'])
    
    return expanded


def build_icsw(expanded_df, today_str):
    """Build final ICSW output dataframe - matches SQL column order exactly"""
    df = expanded_df.copy()
    
    # Format warehouse number as 2-digit string
    df['whse_formatted'] = df['warehouse'].apply(lambda x: f"{int(x):02d}")
    
    # Build ICSW structure with columns in exact SQL SELECT order
    icsw_df = pd.DataFrame({
        "prod": df["PRODUCT"],
        "whse": df["whse_formatted"],
        "enterdt": today_str,
        "statustype": "O",
        "serlottype": "",
        "snpocd": "",
        "reservety": "",
        "reservedays": "",
        "prodpreference": "",
        "pricetype": "DEAL",
        "baseprice": df["baseprice"],
        "listprice": df["listprice"],
        "smanalfl": "",
        "autofillfl": "",
        "boshortfl": "",
        "countfl": "",
        "arptype": df["arptype"],
        "arppushfl": "",
        "arpvendno": df["VENDOR NO"].astype("Int64"),
        "arpwhse": pd.to_numeric(df["arpwhse"], errors="coerce").astype("Int64"),
        "prodline": df.get("PRODLINE", ""), 
        "vendprod": "",
        "famgrptype": "",
        "ncnr": "",
        "rebatety": "",
        "rebsubty": "",
        "autoesrcbofl": "",
        "binloc1": "",
        "binloc2": "",
        "wmfl": "",
        "wmallocty": "",
        "bintype": "",
        "wmpriority": "",
        "wmrestrict": "",
        "frtfreefl": "",
        "frtextra1": "",
        "frtextra2": "",
        "unitbuy": "",
        "unitconv1": "",
        "unitediuom1": "",
        "unitstnd": "",
        "unitconv2": "",
        "unitediuom2": "",
        "unitwt": "",
        "unitconv3": "",
        "unitediuom3": "",
        "safeallty": "D",
        "safeallamt": 0,
        "safetyfrzfl": "",
        "usagerate": "",
        "usgmths": df["usgmths"],
        "usmthsfrzfl": "yes",
        "usagectrl": df["usagectrl"],
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
        "companyrank": "",
        "whserank": "",
        "rankfreezefl": "",
        "threshrefer": "",
        "minthreshold": "",
        "minthreshexpdt": "",
        "asqfl": "",
        "asqdifffl": "",
        "asqdiff": "",
        "hi5fl": "",
        "hi5difffl": "",
        "hi5diff": "",
        "leadtmavg": df["leadtmavg"],
        "avgltdt": "",
        "leadtmlast": "",
        "lastltdt": "",
        "leadtmprio": "",
        "priorltdt": "",
        "frozenltty": 999,
        "class": "",
        "classfrzfl": "",
        "abcgmroiclass": "",
        "abcsalesclass": "",
        "abcqtyclass": "",
        "abccustclass": "",
        "abcoverexpdt": "",
        "abcfinalclass": "",
        "abcclassdt": "",
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
        "taxtype": "",
        "taxgroup": 1,
        "taxablety": "V",
        "nontaxtype": "",
        "tariffcd": "",
        "countryoforigin": "",
        "gststatus": "",
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
        "replcostdt": today_str,
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
        "reasunavty": "",
        "custavgcost": "",
        "custlastcost": "",
        "custfixedcost": "",
        "custqtyonhand": "",
        "custqtyonorder": "",
        "custqtyunavail": "",
        "custqtyrcvd": "",
        "custqtyburnoff": "",
        "custavgcostburnoff": "",
        "issueunytd": "",
        "rcptunytd": "",
        "retinunytd": "",
        "retouunytd": "",
        "rpt852dt": "",
        "lastinvdt": "",
        "lastrcptdt": "",
        "lastpowtdt": "",
        "priceupddt": "",
        "lastcntdt": "",
        "slchgdt": "",
        "buyer": "",
        "user1": "",
        "user2": "",
        "user3": "",
        "user4": "",
        "user5": "",
        "user6": "",
        "user7": "",
        "user8": "",
        "user9": "",
        "user10": "",
        "user11": "",
        "user12": "",
        "user13": "",
        "user14": "",
        "user15": "",
        "user16": "",
        "user17": "",
        "user18": "",
        "user19": "",
        "user20": "",
        "user21": "",
        "user22": "",
        "user23": "",
        "user24": "",
        "boxqty": "",
        "caseqty": "",
        "palletqty": "",
        "whzone": "",
        "bincntr": "",
        "kitbuild": "",
        "srcommcode1": "",
        "srcommcode2": "",
        "srmachine": "",
        "srunitcnt": "",
        "unitconv4": "",
        "unitediuom4": "",
        "regrindfl": "",
        "laborprod": "",
        "linkedprod": "",
        "billonrcptfl": "",
        "custonlyfl": "",
        "rcvunavailfl": "",
        "criticalfl": "",
        "shelflifefl": "",
        "edi852statuschgfl": "",
        "suppwarrallowfl": "",
        "recalcprodcostinv": "",
        "recalcommcostinv": "",
        "cutminlength": "",
        "cutminty": "",
        "cutminoutput": ""
    })
    
    # Sort: warehouses 25, 50, then others; IC, DC, then regular products
    icsw_df['_sort_whse'] = icsw_df['whse'].astype(int).map({25: 1, 50: 2}).fillna(3)
    icsw_df['_sort_prod'] = icsw_df['prod'].apply(
        lambda x: 1 if str(x).startswith('IC') else (2 if str(x).startswith('DC') else 3)
    )
    
    icsw_df = icsw_df.sort_values(['_sort_whse', '_sort_prod', 'prod'])
    icsw_df = icsw_df.drop(['_sort_whse', '_sort_prod'], axis=1)
    
    return icsw_df


# ============================================================================
# MAIN ORCHESTRATOR FUNCTION
# ============================================================================

def process_step2(db, step_2_df, output_folder):
    """
    Main orchestrator for Step 2 processing
    """
    log_messages = []
    
    try:
        # Generate output filename
        day_of_year = datetime.today().timetuple().tm_yday
        seconds = datetime.today().second + datetime.today().minute * 60
        hash_part = format(seconds % (36**3), '03x')
        output_filename = f"cw{day_of_year:03}{hash_part}.csv"
        output_path = os.path.join(output_folder, output_filename)
        
        today_str = datetime.today().strftime("%m/%d/%y")
        
        # Get staging data
        staging_df = step_2_df
        if staging_df.empty:
            raise Exception("No products in staging table")
        log_messages.append(f"✓ Loaded {len(staging_df)} products from staging")
        
        # Validate and get pricing rules
        pricing_df = validate_pricing_map(db, staging_df)
        log_messages.append("✓ Pricing map verified")
        
        # Validate and get warehouses
        whse_df = validate_warehouses(db)
        log_messages.append(f"✓ {len(whse_df)} active warehouses verified")
        
        # Apply pricing calculations
        priced_df = apply_pricing(staging_df, pricing_df)
        log_messages.append("✓ Pricing calculated")
        
        # Expand to warehouses
        expanded_df = expand_warehouses(priced_df, whse_df)
        log_messages.append(f"✓ Expanded to {len(expanded_df)} warehouse records")
        
        # Build ICSW output
        icsw_df = build_icsw(expanded_df, today_str)
        log_messages.append(f"✓ Built ICSW with {icsw_df.shape[1]} columns")
        
        # Validate output
        if icsw_df.isna().any().any():
            null_cols = icsw_df.columns[icsw_df.isna().any()].tolist()
            log_messages.append(f"⚠ Warning: Null values in columns: {null_cols}")
        
        # Export
        icsw_df.to_csv(output_path, index=False)
        log_messages.append(f"✓ Step 2 output saved: {output_filename}")
        log_messages.append(f"✓ Total records: {len(icsw_df)}")

        #clear staging table
     
        
        return output_path, log_messages
        
    except Exception as e:
        log_messages.append(f"✗ Error in Step 2 processing: {str(e)}")
        import traceback
        log_messages.append(f"Traceback: {traceback.format_exc()}")
        return None, log_messages