# ===== FILE: app/settings.py =====
import json
import os
from pathlib import Path

class Settings:
    """Manage application settings"""
    
    def __init__(self, settings_file='config/app_settings.json'):
        self.settings_file = settings_file
        Path(settings_file).parent.mkdir(parents=True, exist_ok=True)
        self.defaults = {
            'folders': {
                'prodadds': './output',
                'output_folder': './output',
                'archive': './archive'
            },
            'use_internal_db': True
        }
        self.load()
    
    def load(self):
        """Load settings from file"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    self.data = json.load(f)
            except:
                self.data = self.defaults.copy()
        else:
            self.data = self.defaults.copy()
            self.save()
    
    def save(self):
        """Save settings to file"""
        with open(self.settings_file, 'w') as f:
            json.dump(self.data, f, indent=4)
    
    def get(self, key, default=None):
        """Get a setting value"""
        keys = key.split('.')
        value = self.data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
            if value is None:
                return default
        return value
    
    def set(self, key, value):
        """Set a setting value"""
        keys = key.split('.')
        data = self.data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value
        self.save()

# ===== FILE: app/step1_processor.py =====
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
                # Columns 1-15: Basic product info
                record = [
                    prod,                                    # 1: PRODUCT
                    core_description_override or description1,  # 2: DESCRIPTION
                    '',                                      # 3: DESCRIPTION2
                    description3,                            # 4: DESCRIPTION3
                    '',                                      # 5: FOREIGNDESC
                    '',                                      # 6: FOREIGNDESC2
                    '',                                      # 7: FOREIGNDESC3
                    '',                                      # 8: SHORTDESC
                    '',                                      # 9: SHORTDESC2
                    weight,                                  # 10: WEIGHT
                    cubes,                                   # 11: CUBES
                    length,                                  # 12: LENGTH
                    width,                                   # 13: WIDTH
                    height,                                  # 14: HEIGHT
                    'EA',                                    # 15: UNITSIZE
                ]
                
                # Columns 16-30: Product classification
                record.extend([
                    brandcode,                               # 16: BRANDCODE
                    prodcat,                                 # 17: PRODCAT
                    '',                                      # 18: PRODCAT2
                    '',                                      # 19: PRODCAT3
                    '',                                      # 20: PRODCAT4
                    '',                                      # 21: PRODCAT5
                    '',                                      # 22: ALTPRODGROUP
                    webcat,                                  # 23: WEBCAT
                    prodline,                                # 24: PRODLINE
                    '',                                      # 25: VENDORGROUP
                    prodtype,                                # 26: PRODTYPE
                    '',                                      # 27: KEYWORDS
                    '',                                      # 28: MODELNO
                    '',                                      # 29: SERIALCODE
                    '',                                      # 30: LOTCODE
                ])
                
                # Columns 31-45: Product attributes
                record.extend([
                    '',                                      # 31: SPECNSTYPE
                    '',                                      # 32: STATUSTYPE
                    '',                                      # 33: RESTRICTTYPES
                    '',                                      # 34: RESTRICTTYPE2
                    '',                                      # 35: EXCLWEBTY
                    '',                                      # 36: ABCCODE
                    '',                                      # 37: COUNTRYOFORIGIN
                    '',                                      # 38: TARIFFCODE
                    '',                                      # 39: NMORCODE
                    '',                                      # 40: ECOSCODE
                    '',                                      # 41: NMFCCODE
                    '',                                      # 42: NMFCSUBCODE
                    '',                                      # 43: HAZMATCLASS
                    '',                                      # 44: UNNACODE
                    '',                                      # 45: FREIGHTCLASS
                ])
                
                # Columns 46-60: Pricing and costs
                record.extend([
                    '',                                      # 46: STKGACCT
                    '',                                      # 47: INUSETYPE
                    '',                                      # 48: WARRDAYS
                    '',                                      # 49: RETURNFL
                    seasonal,                                # 50: SEASONFL
                    '',                                      # 51: COMPFL
                    '',                                      # 52: CONMGFL
                    '',                                      # 53: DROPSHIPTYPE
                    '',                                      # 54: PHANTOMFL
                    'N',                                     # 55: LOANERFL
                    '',                                      # 56: MACHSPECFL
                    '',                                      # 57: CAPEQUIPFL
                    '',                                      # 58: STAGEFL
                    '',                                      # 59: ONETIMEFL
                    '',                                      # 60: RECYCLEFL
                ])
                
                # Columns 61-75: Core and kit info
                record.extend([
                    impliedcoreprod,                         # 61: IMPLIEDCOREPROD
                    dirtycoreprod,                           # 62: DIRTYCOREPROD
                    impliedqty,                              # 63: IMPLIEDQTY
                    graceperiod,                             # 64: GRACEPERIOD
                    '',                                      # 65: KITMEMBERFL
                    '',                                      # 66: KITITEMFL
                    '',                                      # 67: KITALLOWCHGFL
                    '',                                      # 68: BOMMEMBERFL
                    '',                                      # 69: COMPONENTFL
                    '',                                      # 70: BOMCOST
                    '',                                      # 71: BOMOUTPUT
                    '',                                      # 72: BOMUOM
                    '',                                      # 73: SERVICEFL
                    '',                                      # 74: SERVICEUNITS
                    '',                                      # 75: SERVICEPRINTER
                ])
                
                # Columns 76-90: Additional product info
                record.extend([
                    '',                                      # 76: IMAGEFI LE
                    '',                                      # 77: IMAGETYPE
                    '',                                      # 78: IMAGEPATH
                    '',                                      # 79: PRODVOLUME
                    '',                                      # 80: PRODVOLUOM
                    '',                                      # 81: MIXEDFL
                    '',                                      # 82: QTYINCR
                    '',                                      # 83: PALLETQTY
                    '',                                      # 84: PALLETTIED
                    '',                                      # 85: TIERED
                    '',                                      # 86: ENTERDT
                    slchgdt,                                 # 87: SLCHGDT
                    '',                                      # 88: STATUSDT
                    '',                                      # 89: NETAVAILFL
                    '',                                      # 90: NETAVAILTYPE
                ])
                
                # Columns 91-105: Empty fields
                record.extend([''] * 15)                     # 91-105
                
                # Columns 106-120: More empty fields
                record.extend([''] * 15)                     # 106-120
                
                # Columns 121-135: Additional empty fields
                record.extend([''] * 15)                     # 121-135
                
                # Columns 136-150: More empty fields
                record.extend([''] * 15)                     # 136-150
                
                # Columns 151-166: Final empty fields
                record.extend([''] * 16)                     # 151-166
                
                records.append(record)
                
                # Create IC and DC records if this is a core product
                if core_flag == 'Y':
                    # IC (Implied Core) record
                    ic_record = record.copy()
                    ic_record[0] = impliedcoreprod           # PRODUCT
                    ic_record[1] = 'IMPLIED CORE'            # DESCRIPTION
                    ic_record[3] = 'IMPLIED CORE FOR ' + prod  # DESCRIPTION3
                    ic_record[25] = ''                       # PRODTYPE (blank for core)
                    ic_record[60] = ''                       # IMPLIEDCOREPROD (blank for IC)
                    ic_record[61] = ''                       # DIRTYCOREPROD (blank for IC)
                    records.append(ic_record)
                    
                    # DC (Dirty Core) record  
                    dc_record = record.copy()
                    dc_record[0] = dirtycoreprod             # PRODUCT
                    dc_record[1] = 'DIRTY CORE'              # DESCRIPTION
                    dc_record[3] = 'DIRTY CORE FOR ' + prod  # DESCRIPTION3
                    dc_record[25] = ''                       # PRODTYPE (blank for core)
                    dc_record[60] = ''                       # IMPLIEDCOREPROD (blank for DC)
                    dc_record[61] = ''                       # DIRTYCOREPROD (blank for DC)
                    records.append(dc_record)
                    
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
        
        return output_path, log_messages
        
    except Exception as e:
        log_messages.append(f"✗ Error in Step 1 processing: {str(e)}")
        return None, log_messages

# ===== FILE: app/__init__.py =====
# Empty init file to make app a package