import FreeSimpleGUI as sg
import pandas as pd
import sqlite3
import os
import json
import re
import unicodedata
import shutil
from datetime import datetime
from pathlib import Path

# =============================================================================
# DATABASE MANAGEMENT
# =============================================================================

class AppDatabase:
    """Manage self-contained application database"""
    
    def __init__(self, db_path='app_data.db'):
        self.db_path = db_path
        self.conn = None
        self.initialize_database()
    
    def initialize_database(self):
        """Create database and tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # Vendor defaults table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vendor_defaults (
                vendor_no INTEGER PRIMARY KEY,
                default_brandcode TEXT,
                default_prodcat TEXT,
                default_webcat TEXT,
                default_prodline TEXT,
                seasonal_flag TEXT,
                created_date TEXT,
                modified_date TEXT
            )
        ''')
        
        # Warehouse info table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warehouse_info (
                warehouse INTEGER PRIMARY KEY,
                type TEXT,
                arpwhse INTEGER,
                description TEXT,
                active INTEGER DEFAULT 1
            )
        ''')
        
        # Pricing multipliers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pricing_multipliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor TEXT,
                vendor_list_handling TEXT,
                base_0_01_1_49 REAL,
                base_1_5_4_99 REAL,
                base_5_49_99 REAL,
                base_50_74_99 REAL,
                base_75_99_99 REAL,
                base_100_499_99 REAL,
                base_500_999_99 REAL,
                base_1000_999999 REAL,
                list_0_01_4_99 REAL,
                list_5_49_99 REAL,
                list_50_74_99 REAL,
                list_75_99999 REAL
            )
        ''')
        
        # Upload log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS upload_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                file_creation_ts TEXT,
                update_count INTEGER,
                notes TEXT
            )
        ''')
        
        # Product staging table (for batch processing)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_staging (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product TEXT,
                vendor_no INTEGER,
                description TEXT,
                core_flag TEXT,
                repl_cost REAL,
                base_price REAL,
                list_price REAL,
                length REAL,
                width REAL,
                height REAL,
                weight REAL,
                brand_code TEXT,
                product_cat TEXT,
                website_cat TEXT,
                wp_wise TEXT,
                tr_returnable TEXT,
                created_date TEXT
            )
        ''')
        
        self.conn.commit()
        
        # Insert default warehouses if table is empty
        cursor.execute('SELECT COUNT(*) FROM warehouse_info')
        if cursor.fetchone()[0] == 0:
            default_warehouses = [
                (25, 'D', 15, 'Main Distribution Center'),
                (50, 'D', 16, 'Secondary Distribution Center'),
                (10, 'B', None, 'Branch 10'),
                (20, 'B', None, 'Branch 20')
            ]
            cursor.executemany(
                'INSERT INTO warehouse_info (warehouse, type, arpwhse, description) VALUES (?, ?, ?, ?)',
                default_warehouses
            )
            self.conn.commit()
    
    def get_vendor_defaults(self, vendor_no):
        """Get vendor defaults from database"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM vendor_defaults WHERE vendor_no = ?', (vendor_no,))
        row = cursor.fetchone()
        if row:
            return {
                'default_brandcode': row[1],
                'default_prodcat': row[2],
                'default_webcat': row[3],
                'default_prodline': row[4],
                'seasonal_flag': row[5]
            }
        return None
    
    def save_vendor_defaults(self, vendor_no, defaults):
        """Save or update vendor defaults"""
        cursor = self.conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('SELECT vendor_no FROM vendor_defaults WHERE vendor_no = ?', (vendor_no,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute('''
                UPDATE vendor_defaults 
                SET default_brandcode=?, default_prodcat=?, default_webcat=?, 
                    default_prodline=?, seasonal_flag=?, modified_date=?
                WHERE vendor_no=?
            ''', (defaults['default_brandcode'], defaults['default_prodcat'], 
                  defaults['default_webcat'], defaults['default_prodline'],
                  defaults['seasonal_flag'], now, vendor_no))
        else:
            cursor.execute('''
                INSERT INTO vendor_defaults 
                (vendor_no, default_brandcode, default_prodcat, default_webcat, 
                 default_prodline, seasonal_flag, created_date, modified_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (vendor_no, defaults['default_brandcode'], defaults['default_prodcat'],
                  defaults['default_webcat'], defaults['default_prodline'],
                  defaults['seasonal_flag'], now, now))
        
        self.conn.commit()
    
    def get_all_vendors(self):
        """Get list of all vendors"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT vendor_no, default_brandcode FROM vendor_defaults ORDER BY vendor_no')
        return cursor.fetchall()
    
    def delete_vendor(self, vendor_no):
        """Delete vendor defaults"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM vendor_defaults WHERE vendor_no = ?', (vendor_no,))
        self.conn.commit()
    
    def get_warehouses(self):
        """Get all active warehouses"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM warehouse_info WHERE active = 1 ORDER BY warehouse')
        return cursor.fetchall()
    
    def get_pricing_multipliers(self):
        """Get pricing multipliers"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM pricing_multipliers')
        return pd.read_sql_query('SELECT * FROM pricing_multipliers', self.conn)
    
    def import_pricing_from_excel(self, file_path, sheet_name='PRICING MULTIPLIERS'):
        """Import pricing multipliers from Excel"""
        try:
            pricing_df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Normalize column names
            cols = ["" if pd.isna(c) else str(c) for c in pricing_df.columns]
            for idx in range(len(cols)):
                name = cols[idx].strip()
                if 1 <= idx <= 8:
                    cols[idx] = "B-" + name if not name.upper().startswith("B-") else name
                elif 9 <= idx <= 12:
                    cols[idx] = "L-" + name if not name.upper().startswith("L-") else name
            
            pricing_df.columns = cols
            
            # Clear and reload pricing table
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM pricing_multipliers')
            pricing_df.to_sql('pricing_multipliers', self.conn, if_exists='append', index=False)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error importing pricing: {e}")
            return False
    
    def log_upload(self, file_name, update_count, notes=''):
        """Add entry to upload log"""
        cursor = self.conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO upload_log (file_name, file_creation_ts, update_count, notes)
            VALUES (?, ?, ?, ?)
        ''', (file_name, now, update_count, notes))
        self.conn.commit()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

# =============================================================================
# CONFIGURATION & SETTINGS MANAGEMENT
# =============================================================================

class Settings:
    """Manage application settings"""
    
    def __init__(self, settings_file='app_settings.json'):
        self.settings_file = settings_file
        self.defaults = {
            'folders': {
                'prodadds': '',
                'output_folder': ''
            },
            'use_internal_db': True
        }
        self.load()
    
    def load(self):
        """Load settings from file"""
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = self.defaults.copy()
    
    def save(self):
        """Save settings to file"""
        with open(self.settings_file, 'w') as f:
            json.dump(self.data, f, indent=4)
    
    def get(self, key, default=None):
        """Get a setting value"""
        keys = key.split('.')
        value = self.data
        for k in keys:
            value = value.get(k, default)
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

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

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

def get_vendor_default(db, vendor_no, field_name):
    """Get vendor default from database"""
    defaults = db.get_vendor_defaults(vendor_no)
    if defaults:
        return defaults.get(field_name)
    return None

# =============================================================================
# SETTINGS WINDOW
# =============================================================================

def create_settings_window(settings, db):
    """Create settings configuration window"""
    
    # Folder settings layout
    folder_layout = [
        [sg.Text('Folder Paths', font='Any 12 bold')],
        [sg.Text('Product Adds Folder:'), sg.Input(settings.get('folders.prodadds', ''), key='folder_prodadds', size=(50,1)), 
         sg.FolderBrowse()],
        [sg.Text('Output Folder:'), sg.Input(settings.get('folders.output_folder', ''), key='folder_output', size=(50,1)), 
         sg.FolderBrowse()],
        [sg.HorizontalSeparator()],
        [sg.Checkbox('Use internal database (recommended)', key='use_internal_db', 
                     default=settings.get('use_internal_db', True))],
        [sg.Text('Internal database location: app_data.db', font='Any 9 italic')],
    ]
    
    # Vendor defaults layout
    vendor_layout = [
        [sg.Text('Vendor Defaults Management', font='Any 12 bold')],
        [sg.Text('Vendor Number:'), sg.Input(key='vendor_no', size=(10,1)), 
         sg.Button('Load Vendor'), sg.Button('New Vendor')],
        [sg.HorizontalSeparator()],
        [sg.Text('Brand Code:'), sg.Input(key='vendor_brandcode', size=(20,1))],
        [sg.Text('Product Category:'), sg.Input(key='vendor_prodcat', size=(20,1))],
        [sg.Text('Website Category:'), sg.Input(key='vendor_webcat', size=(20,1))],
        [sg.Text('Product Line:'), sg.Input(key='vendor_prodline', size=(20,1))],
        [sg.Text('Seasonal (y/n):'), sg.Input(key='vendor_seasonal', size=(5,1))],
        [sg.Button('Save Vendor Defaults'), sg.Button('Delete Vendor')],
        [sg.HorizontalSeparator()],
        [sg.Text('Existing Vendors:')],
        [sg.Listbox(values=[], key='vendor_list', size=(60, 10), enable_events=True)]
    ]
    
    # Warehouse management layout
    warehouse_layout = [
        [sg.Text('Warehouse Configuration', font='Any 12 bold')],
        [sg.Table(values=[], headings=['Warehouse', 'Type', 'ARP Whse', 'Description', 'Active'],
                 key='warehouse_table', size=(None, 15), enable_events=True)],
        [sg.Button('Add Warehouse'), sg.Button('Edit Warehouse'), sg.Button('Refresh Warehouses')]
    ]
    
    # Pricing layout
    pricing_layout = [
        [sg.Text('Pricing Multipliers', font='Any 12 bold')],
        [sg.Text('Import pricing rules from Excel:')],
        [sg.Input(key='pricing_import_file', size=(50,1)), sg.FileBrowse(file_types=(("Excel Files", "*.xlsx"),))],
        [sg.Text('Sheet Name:'), sg.Input('PRICING MULTIPLIERS', key='pricing_sheet', size=(30,1))],
        [sg.Button('Import Pricing Rules')],
        [sg.HorizontalSeparator()],
        [sg.Text('Current Pricing Rules:')],
        [sg.Table(values=[], headings=['Vendor', 'List Handling'], key='pricing_table', 
                 size=(None, 10), auto_size_columns=False, col_widths=[15, 30])]
    ]
    
    # Main layout
    layout = [
        [sg.TabGroup([
            [sg.Tab('Folders', folder_layout)],
            [sg.Tab('Vendor Defaults', vendor_layout)],
            [sg.Tab('Warehouses', warehouse_layout)],
            [sg.Tab('Pricing Rules', pricing_layout)]
        ])],
        [sg.Button('Save All Settings'), sg.Button('Export Database'), sg.Button('Cancel')]
    ]
    
    window = sg.Window('Settings', layout, modal=True, finalize=True)
    
    # Load initial data
    update_vendor_list(window, db)
    update_warehouse_table(window, db)
    update_pricing_table(window, db)
    
    return window

def update_vendor_list(window, db):
    """Update the vendor list display"""
    vendors = db.get_all_vendors()
    vendor_list = [f"Vendor {v[0]}: {v[1] or 'N/A'}" for v in vendors]
    window['vendor_list'].update(values=vendor_list)

def update_warehouse_table(window, db):
    """Update warehouse table display"""
    warehouses = db.get_warehouses()
    table_data = [[w[0], w[1], w[2] or '', w[3], 'Yes' if w[4] else 'No'] for w in warehouses]
    window['warehouse_table'].update(values=table_data)

def update_pricing_table(window, db):
    """Update pricing table display"""
    pricing_df = db.get_pricing_multipliers()
    if not pricing_df.empty:
        table_data = [[row['vendor'], row.get('vendor_list_handling', '')] 
                     for _, row in pricing_df.iterrows()]
        window['pricing_table'].update(values=table_data)

def handle_settings_window(settings, db):
    """Handle settings window events"""
    window = create_settings_window(settings, db)
    
    while True:
        event, values = window.read()
        
        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        
        if event == 'Save All Settings':
            # Save folder settings
            settings.set('folders.prodadds', values['folder_prodadds'])
            settings.set('folders.output_folder', values['folder_output'])
            settings.set('use_internal_db', values['use_internal_db'])
            sg.popup('Settings saved successfully!')
        
        elif event == 'Load Vendor':
            vendor_no = values['vendor_no'].strip()
            if vendor_no:
                vendor_data = db.get_vendor_defaults(int(vendor_no))
                if vendor_data:
                    window['vendor_brandcode'].update(vendor_data.get('default_brandcode', ''))
                    window['vendor_prodcat'].update(vendor_data.get('default_prodcat', ''))
                    window['vendor_webcat'].update(vendor_data.get('default_webcat', ''))
                    window['vendor_prodline'].update(vendor_data.get('default_prodline', ''))
                    window['vendor_seasonal'].update(vendor_data.get('seasonal_flag', ''))
                else:
                    sg.popup(f'Vendor {vendor_no} not found')
        
        elif event == 'New Vendor':
            window['vendor_brandcode'].update('')
            window['vendor_prodcat'].update('')
            window['vendor_webcat'].update('')
            window['vendor_prodline'].update('')
            window['vendor_seasonal'].update('')
        
        elif event == 'Save Vendor Defaults':
            vendor_no = values['vendor_no'].strip()
            if vendor_no:
                vendor_data = {
                    'default_brandcode': values['vendor_brandcode'],
                    'default_prodcat': values['vendor_prodcat'],
                    'default_webcat': values['vendor_webcat'],
                    'default_prodline': values['vendor_prodline'],
                    'seasonal_flag': values['vendor_seasonal']
                }
                db.save_vendor_defaults(int(vendor_no), vendor_data)
                update_vendor_list(window, db)
                sg.popup(f'Vendor {vendor_no} saved successfully!')
            else:
                sg.popup('Please enter a vendor number')
        
        elif event == 'Delete Vendor':
            vendor_no = values['vendor_no'].strip()
            if vendor_no:
                db.delete_vendor(int(vendor_no))
                update_vendor_list(window, db)
                sg.popup(f'Vendor {vendor_no} deleted')
        
        elif event == 'Import Pricing Rules':
            if values['pricing_import_file']:
                success = db.import_pricing_from_excel(
                    values['pricing_import_file'], 
                    values['pricing_sheet']
                )
                if success:
                    update_pricing_table(window, db)
                    sg.popup('Pricing rules imported successfully!')
                else:
                    sg.popup_error('Failed to import pricing rules')
        
        elif event == 'Refresh Warehouses':
            update_warehouse_table(window, db)
        
        elif event == 'Export Database':
            backup_path = f"app_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy(db.db_path, backup_path)
            sg.popup(f'Database exported to:\n{backup_path}')
        
        elif event == 'vendor_list':
            if values['vendor_list']:
                vendor_str = values['vendor_list'][0]
                vendor_no = vendor_str.split(':')[0].replace('Vendor ', '').strip()
                window['vendor_no'].update(vendor_no)
                window.write_event_value('Load Vendor', '')
    
    window.close()

# =============================================================================
# MAIN APPLICATION WINDOW
# =============================================================================

def create_main_window():
    """Create the main application window"""
    
    # Set theme - try different methods for compatibility
    try:
        sg.theme('LightBlue2')
    except AttributeError:
        try:
            sg.ChangeLookAndFeel('LightBlue2')
        except:
            pass  # Use default theme
    
    # Input method selection
    input_tab = [
        [sg.Text('Choose Input Method:', font='Any 12 bold')],
        [sg.Radio('Upload Excel/CSV File', 'INPUT', key='input_file', default=True, enable_events=True)],
        [sg.Input(key='file_path', size=(50,1)), sg.FileBrowse(file_types=(("Excel Files", "*.xlsx"), ("CSV Files", "*.csv")))],
        [sg.Radio('Manual Form Entry', 'INPUT', key='input_form', enable_events=True)],
        [sg.HorizontalSeparator()],
        [sg.Text('Or add single product manually:', font='Any 11 bold')],
        [sg.Column([
            [sg.Text('Product:'), sg.Input(key='prod', size=(15,1))],
            [sg.Text('Vendor No:'), sg.Input(key='vendor_no', size=(15,1))],
            [sg.Text('Description:'), sg.Input(key='description', size=(40,1))],
            [sg.Text('Core Flag (Y):'), sg.Input(key='core_flag', size=(5,1))],
            [sg.Text('Repl Cost:'), sg.Input(key='repl_cost', size=(10,1))],
            [sg.Text('Base Price:'), sg.Input(key='base_price', size=(10,1))],
            [sg.Text('List Price:'), sg.Input(key='list_price', size=(10,1))],
        ], key='form_column', visible=False),
        sg.Column([
            [sg.Text('Length:'), sg.Input(key='length', size=(10,1))],
            [sg.Text('Width:'), sg.Input(key='width', size=(10,1))],
            [sg.Text('Height:'), sg.Input(key='height', size=(10,1))],
            [sg.Text('Weight:'), sg.Input(key='weight', size=(10,1))],
            [sg.Text('Brand Code:'), sg.Input(key='brand_code', size=(15,1))],
            [sg.Text('Product Cat:'), sg.Input(key='prod_cat', size=(15,1))],
            [sg.Text('Website Cat:'), sg.Input(key='web_cat', size=(15,1))],
        ], key='form_column2', visible=False)],
        [sg.Button('Add to Batch', key='add_manual', visible=False)]
    ]
    
    # Batch view
    batch_tab = [
        [sg.Text('Products in Current Batch:', font='Any 12 bold')],
        [sg.Table(values=[], headings=['Product', 'Vendor', 'Description', 'Core', 'Repl Cost', 'Base Price', 'List Price'],
                  key='batch_table', size=(None, 15), auto_size_columns=True, justification='left')],
        [sg.Button('Remove Selected'), sg.Button('Clear Batch'), sg.Button('Export Batch to Excel')]
    ]
    
    # Output settings
    output_tab = [
        [sg.Text('Output Options:', font='Any 12 bold')],
        [sg.Checkbox('Generate Step 1 Output (cp*.csv)', key='gen_step1', default=True)],
        [sg.Checkbox('Generate Step 2 Output (cw*.csv)', key='gen_step2', default=True)],
        [sg.Checkbox('Create Archive of Input Files', key='do_archive', default=True)],
        [sg.Checkbox('Update Upload Log', key='update_log', default=True)],
        [sg.Text('Notes for Log:'), sg.Input(key='log_notes', size=(50,1))],
    ]
    
    # Main layout
    layout = [
        [sg.MenuBar([['File', ['Settings', 'Exit']], ['Help', ['About']]])],
        [sg.TabGroup([
            [sg.Tab('Input', input_tab)],
            [sg.Tab('Batch', batch_tab)],
            [sg.Tab('Output', output_tab)]
        ])],
        [sg.HorizontalSeparator()],
        [sg.Button('Process', size=(15,1), button_color=('white', 'green')), 
         sg.Button('Clear All', size=(15,1)), 
         sg.Button('Exit', size=(15,1))],
        [sg.Multiline(size=(100, 10), key='output_log', autoscroll=True, disabled=True)]
    ]
    
    window = sg.Window('Product Adds Management System', layout, finalize=True)
    return window

# =============================================================================
# PROCESSING FUNCTIONS
# =============================================================================

def process_step1(df, db, output_folder):
    """Process Step 1 - Product adds"""
    
    log_messages = []
    records = []
    
    for _, row in df.iterrows():
        try:
            prod = str(row['PRODUCT']).strip()
            vendor_no = int(float(row['VENDOR NO']))
            core_flag = str(row.get('CORE FLAG (Y)', '')).strip().upper()
            prodtype = 'r' if core_flag == 'Y' else ''
            
            # Get defaults from database
            prodline = get_vendor_default(db, vendor_no, 'default_prodline')
            repl_cost = row.get('REPL COST', None)
            base_price = row.get('BASE PRICE', None)
            list_price = row.get('LIST PRICE', None)
            
            # Clean descriptions
            description1 = clean_description(row['DESCRIPTION'])
            description3 = clean_description3(row['DESCRIPTION'])
            
            # Dimensions
            length = default_1(row.get('LENGTH', 1))
            width = default_1(row.get('WIDTH', 1))
            height = default_1(row.get('HEIGHT', 1))
            weight = default_1(row.get('WEIGHT', 1))
            cubes = length * width * height
            
            # Get vendor defaults
            brandcode = row.get('BRAND CODE') or get_vendor_default(db, vendor_no, 'default_brandcode')
            prodcat = row.get('PRODUCT CAT') or get_vendor_default(db, vendor_no, 'default_prodcat')
            webcat = row.get('WEBSITE CAT') or get_vendor_default(db, vendor_no, 'default_webcat')
            seasonal = get_vendor_default(db, vendor_no, 'seasonal_flag')
            
            # Core handling
            impliedcoreprod = dirtycoreprod = impliedqty = graceperiod = ''
            if core_flag == 'Y':
                prodtype = 'r'
                impliedcoreprod = "IC" + prod
                dirtycoreprod = "DC" + prod
                impliedqty = '1'
                graceperiod = '36'
                if vendor_no == 360:
                    description1 = "CONTROL - ADD 55.00 CORE"
                elif vendor_no == 825:
                    description1 = "CONTROL - ADD 60.00 CORE"
            
            slchgdt = datetime.today().strftime("%m/%d/%y")
            
            # Build record (simplified - full 166 columns in actual implementation)
            base_record = [prod, description1, "", description3, "", "", "", "", "",
                          weight, cubes, length, width, height, 'EA']
            # ... add remaining columns
            
            records.append(base_record)
            
            # IC/DC records if core
            if core_flag == 'Y':
                # Add IC and DC records (simplified)
                pass
            
            log_messages.append(f"✓ Processed: {prod}")
            
        except Exception as e:
            log_messages.append(f"✗ Error processing row: {str(e)}")
    
    # Export
    day_of_year = datetime.today().timetuple().tm_yday
    seconds = datetime.today().second + datetime.today().minute * 60
    hash_part = format(seconds % (36**3), '03x')
    output_filename = f"cp{day_of_year:03}{hash_part}.csv"
    output_path = os.path.join(output_folder, output_filename)
    
    export_df = pd.DataFrame(records)
    export_df.to_csv(output_path, index=False, header=False)
    
    log_messages.append(f"\n✓ Step 1 output saved: {output_filename}")
    return output_path, log_messages

# =============================================================================
# MAIN APPLICATION LOGIC
# =============================================================================

def main():
    """Main application entry point"""
    
    settings = Settings()
    db = AppDatabase()
    window = create_main_window()
    batch_data = []
    
    while True:
        event, values = window.read()
        
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        
        # Toggle form visibility
        if event == 'input_form':
            window['form_column'].update(visible=True)
            window['form_column2'].update(visible=True)
            window['add_manual'].update(visible=True)
        elif event == 'input_file':
            window['form_column'].update(visible=False)
            window['form_column2'].update(visible=False)
            window['add_manual'].update(visible=False)
        
        # Settings menu
        if event == 'Settings':
            handle_settings_window(settings, db)
        
        # Add manual entry to batch
        if event == 'add_manual':
            try:
                product_data = {
                    'PRODUCT': values['prod'],
                    'VENDOR NO': values['vendor_no'],
                    'DESCRIPTION': values['description'],
                    'CORE FLAG (Y)': values['core_flag'],
                    'REPL COST': values['repl_cost'],
                    'BASE PRICE': values['base_price'],
                    'LIST PRICE': values['list_price'],
                    'LENGTH': values['length'] or 1,
                    'WIDTH': values['width'] or 1,
                    'HEIGHT': values['height'] or 1,
                    'WEIGHT': values['weight'] or 1,
                    'BRAND CODE': values['brand_code'],
                    'PRODUCT CAT': values['prod_cat'],
                    'WEBSITE CAT': values['web_cat']
                }
                batch_data.append(product_data)
                
                # Update table
                table_data = [[p['PRODUCT'], p['VENDOR NO'], p['DESCRIPTION'], 
                              p.get('CORE FLAG (Y)', ''), p.get('REPL COST', ''),
                              p.get('BASE PRICE', ''), p.get('LIST PRICE', '')] 
                             for p in batch_data]
                window['batch_table'].update(values=table_data)
                
                window['output_log'].update(f"Added {values['prod']} to batch\n", append=True)
            except Exception as e:
                sg.popup_error(f"Error adding to batch: {str(e)}")
        
        # Process button
        if event == 'Process':
            try:
                window['output_log'].update("Starting processing...\n")
                
                # Determine input source
                if values['input_file'] and values['file_path']:
                    # Load from file
                    if values['file_path'].endswith('.xlsx'):
                        df = pd.read_excel(values['file_path'])
                    else:
                        df = pd.read_csv(values['file_path'])
                    window['output_log'].update(f"Loaded {len(df)} rows from file\n", append=True)
                
                elif batch_data:
                    # Use batch data
                    df = pd.DataFrame(batch_data)
                    window['output_log'].update(f"Using {len(df)} products from batch\n", append=True)
                
                else:
                    sg.popup_error("No input data selected!")
                    continue
                
                output_folder = settings.get('folders.prodadds', '.')
                
                # Process Step 1
                if values['gen_step1']:
                    output_path, messages = process_step1(df, db, output_folder)
                    for msg in messages:
                        window['output_log'].update(msg + "\n", append=True)
                
                # Process Step 2 (simplified)
                if values['gen_step2']:
                    window['output_log'].update("Step 2 processing would run here...\n", append=True)
                
                window['output_log'].update("\n✓ Processing complete!\n", append=True)
                sg.popup('Processing complete!', 'Check the output log for details.')
                
            except Exception as e:
                error_msg = f"Error during processing: {str(e)}"
                window['output_log'].update(error_msg + "\n", append=True)
                sg.popup_error(error_msg)
        
        # Clear batch
        if event == 'Clear Batch':
            batch_data = []
            window['batch_table'].update(values=[])
            window['output_log'].update("Batch cleared\n", append=True)
        
        # About
        if event == 'About':
            sg.popup('Product Adds Management System', 'Version 1.0', 
                    'Automates product addition workflows')
    
    db.close()
    window.close()

if __name__ == '__main__':
    main()