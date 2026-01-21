# app/step1_processor.py
#generates ICSP upload
import pandas as pd
import re
import unicodedata
from datetime import datetime
import os

def clean_description(desc):
    """Clean description to 24 chars"""
    if pd.isna(desc):
        return ""
    text = str(desc)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r'(?<!\s)[\'\",/;\\](?!\s)', ' ', text)
    text = re.sub(r'[\'\",/;\\]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip().upper()[:24]

def clean_description3(desc):
    """Clean description (full length)"""
    if pd.isna(desc):
        return ""
    text = str(desc)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r'(?<!\s)[\'\",/;\\](?!\s)', ' ', text)
    text = re.sub(r'[\'\",/;\\]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip().upper()

def build_core_record(
    product,
    status,
    core_type,
    *,
    base_prod,
    prodcat,
    brandcode,
    webcat,
    slchgdt
):
    core_desc = f"CORE {base_prod}"

    core_record = [
        product,                 # 1  PRODUCT
        core_desc,               # 2  DESCRIPTION
        '',                       # 3  DESCRIPTION2
        core_desc,               # 4  DESCRIPTION3
        '', '', '', status, '',   # 5–9
        1, 1, 1, 1, 1, 'EA',       # 10–15
    ]

    core_record += [''] * 20      # blank columns

    core_record += [
        prodcat, '', '', brandcode, webcat
    ]

    core_record += [''] * 14

    core_record += ['', '', '', slchgdt]

    core_record += [''] * 10

    core_record += [
        core_type,                # PRODTYPE ('i' or 'd')
        '',                        # IMPLIEDCOREPROD
        '',                        # IMPLIEDQTY
        '',                        # DIRTYCOREPROD
        ''
    ]

    core_record += ['', '', '']   # grace placeholders

    core_record += [''] * 38

    core_record += [
        "NA",
        "NA"
    ]

    core_record += [''] * (166 - len(core_record))

    return core_record



def default_1(val):
    """Return val or 1 if NA"""
    return val if pd.notna(val) else 1

def process_step1(db, output_folder):
    """
    Process Step 1 - Product master data (cp*.csv)
    Generates the 166-column product master file
    """
    
    log_messages = []
    records = []
    
    try:
        # Get data from staging
        staging_df = db.get_staging_data()
        
        if staging_df.empty:
            raise Exception("No products in staging table")
        
        log_messages.append(f"Processing {len(staging_df)} products...")
        
        for _, row in staging_df.iterrows():
            try:
                prod = str(row['PRODUCT']).strip()
                vendor_no = int(float(row['VENDOR NO']))
                core_flag = str(row.get('CORE FLAG (Y)', '')).strip().upper()
                
                # Product type
                prodtype = 'r' if core_flag == 'Y' else ''
                
                # Get vendor defaults
                vendor_defaults = db.get_vendor_defaults(vendor_no)
                prodline = vendor_defaults.get('default_prodline', '') if vendor_defaults else ''
                seasonal = vendor_defaults.get('seasonal_flag', 'n') if vendor_defaults else 'n'
                brandcode = row.get('BRAND CODE') or (vendor_defaults.get('default_brandcode', '') if vendor_defaults else '')
                prodcat = row.get('PRODUCT CAT') or (vendor_defaults.get('default_prodcat', '') if vendor_defaults else '')
                webcat = row.get('WEBSITE CAT') or (vendor_defaults.get('default_webcat', '') if vendor_defaults else '')
                
                # Costs and prices
                repl_cost = float(row['REPL COST'])
                base_price = float(row['BASE PRICE']) if pd.notna(row.get('BASE PRICE')) else None
                list_price = float(row['LIST PRICE']) if pd.notna(row.get('LIST PRICE')) else None
                
                # Clean descriptions
                description1 = clean_description(row['DESCRIPTION'])
                description3 = clean_description3(row['DESCRIPTION'])
                
                # Dimensions
                length = default_1(row.get('LENGTH', 1))
                width = default_1(row.get('WIDTH', 1))
                height = default_1(row.get('HEIGHT', 1))
                weight = default_1(row.get('WEIGHT', 1))
                cubes = length * width * height
                
                # Core handling
                impliedcoreprod = dirtycoreprod = impliedqty = graceperiod = ''
                core_description_override = ''
                
                if core_flag == 'Y':
                    prodtype = 'r'
                    impliedcoreprod = "IC" + prod
                    dirtycoreprod = "DC" + prod
                    impliedqty = '1'
                    graceperiod = '36'
                    
                    # Vendor-specific core descriptions
                    if vendor_no == 360:
                        core_description_override = "CONTROL - ADD 55.00 CORE"
                    elif vendor_no == 825:
                        core_description_override = "CONTROL - ADD 60.00 CORE"
                
                slchgdt = datetime.today().strftime("%m/%d/%y")
                
                # Build 166-column record

                def blank(n):
                    return [''] * n

                record = [
                    prod,
                    core_description_override or description1,
                    '',
                    description3,
                    '', '', '', '', '',
                    weight, cubes, length, width, height, 'EA',
                ]

                record += blank(20)                      # blank columns

                record += [
                    prodcat, '', '', brandcode, webcat   # matches old placement
                ]

                record += blank(14)

                record += [
                    '', '', '',                          # placeholders
                    slchgdt
                ]

                record += blank(10)

                record += [
                    prodtype,
                    impliedcoreprod,
                    impliedqty,
                    dirtycoreprod,
                    ''
                ]

                record += [
                    graceperiod, '', graceperiod
                ]

                record += blank(38)

                record += [
                    'NA',
                    'NA'
                ]

                record += blank(166 - len(record))

                records.append(record)

                
                # Create IC and DC records if this is a core product
                # Create IC and DC records if this is a core product
                
                if core_flag == 'Y':
                        records.append(
                            build_core_record(
                                impliedcoreprod,
                                status='L',
                                core_type='i',
                                base_prod=prod,
                                prodcat=prodcat,
                                brandcode=brandcode,
                                webcat=webcat,
                                slchgdt=slchgdt
                            )
                        )

                        records.append(
                            build_core_record(
                                dirtycoreprod,
                                status='A',
                                core_type='d',
                                base_prod=prod,
                                prodcat=prodcat,
                                brandcode=brandcode,
                                webcat=webcat,
                                slchgdt=slchgdt
                            )
                        )
                        log_messages.append(f"✓ Processed core product: {prod} (with IC/DC)")
                else:
                    log_messages.append(f"✓ Processed: {prod}")
                
            except Exception as e:
                log_messages.append(f"✗ Error processing {row.get('PRODUCT', 'unknown')}: {str(e)}")
        
        # Generate hashed output filename
        day_of_year = datetime.today().timetuple().tm_yday
        seconds = datetime.today().second + datetime.today().minute * 60
        hash_part = format(seconds % (36**3), '03x')
        output_filename = f"cp{day_of_year:03}{hash_part}.csv"
        output_path = os.path.join(output_folder, output_filename)
        
        # Create DataFrame and export
        export_df = pd.DataFrame(records)
        export_df.to_csv(output_path, index=False, header=False)
        
        log_messages.append(f"\n✓ Step 1 output saved: {output_filename}")
        log_messages.append(f"✓ Total records: {len(records)} ({len(staging_df)} products + cores)")
        
        return export_df, output_path, log_messages
        
    except Exception as e:
        log_messages.append(f"✗ Error in Step 1 processing: {str(e)}")
        return None, None, log_messages