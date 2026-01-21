# app/main.py - Enhanced Main Application
import FreeSimpleGUI as sg
import pandas as pd
import os
from pathlib import Path

# Import our modules
from database import AppDatabase
from settings import Settings
from step1_processor import process_step1
from step2_processor import process_step2
from template_generator import TemplateGenerator

def validate_required_fields(values):
    """Validate that required fields are filled"""
    required = ['prod', 'vendor_no', 'description', 'repl_cost']
    missing = []
    
    for field in required:
        if not values.get(field) or str(values[field]).strip() == '':
            missing.append(field.replace('_', ' ').title())
    
    return missing

def validate_vendors_against_pricing(db, staging_df):
    pricing_vendors = set(
        v[0] for v in db.conn.execute(
            "SELECT DISTINCT vendor FROM pricing_map"
        ).fetchall()
    )

    product_vendors = set(
        str(v) for v in staging_df['VENDOR NO'].dropna().unique()
    )

    missing = sorted(product_vendors - pricing_vendors)

    if missing:
        raise ValueError(
            "Pricing rules missing for vendor(s): "
            + ", ".join(missing)
            + "\n\nPlease add pricing rules under Settings → Pricing Rules."
        )
    
def vendor_has_pricing(db, vendor_no):
    row = db.conn.execute(
        "SELECT 1 FROM pricing_map WHERE vendor = ? LIMIT 1",
        (str(vendor_no),)
    ).fetchone()

    return row is not None



def create_settings_window(settings, db):
    """Create enhanced settings configuration window"""
    
    # Folder settings layout
    folder_layout = [
        [sg.Text('Folder Paths', font='Any 12 bold')],
        [sg.Text('Product Adds Folder:'), 
         sg.Input(settings.get('folders.prodadds', ''), key='folder_prodadds', size=(50,1)), 
         sg.FolderBrowse()],
        [sg.Text('Output Folder:'), 
         sg.Input(settings.get('folders.output_folder', ''), key='folder_output', size=(50,1)), 
         sg.FolderBrowse()],
        [sg.Text('Archive Folder:'), 
         sg.Input(settings.get('folders.archive', ''), key='folder_archive', size=(50,1)), 
         sg.FolderBrowse()],
    ]
    pricing_layout = [
        [sg.Text('Pricing Multipliers', font='Any 12 bold')],

        [sg.Text('Manual Pricing Rule Entry', font='Any 11 bold')],
        [sg.Text('Vendor:'), sg.Input(key='pricing_vendor', size=(15,1))],
        [sg.Text('List Handling:'), sg.Input(key='pricing_vendor_list_handling', size=(30,1))],
        [sg.Text('Base Multiplier, < 1.5:'), sg.Input(key='pricing_b_1', size=(30,1))],
        [sg.Text('Base Multiplier, 1.5-4.99:'), sg.Input(key='pricing_b_2', size=(30,1))],
        [sg.Text('Base Multiplier, 5-49.99:'), sg.Input(key='pricing_b_3', size=(30,1))],
        [sg.Text('Base Multiplier, 50-74.99:'), sg.Input(key='pricing_b_4', size=(30,1))],
        [sg.Text('Base Multiplier, 75-99.99:'), sg.Input(key='pricing_b_5', size=(30,1))],
        [sg.Text('Base Multiplier, 100-499.99:'), sg.Input(key='pricing_b_6', size=(30,1))],
        [sg.Text('Base Multiplier, 500-999.99:'), sg.Input(key='pricing_b_7', size=(30,1))],
        [sg.Text('Base Multiplier, 1000+:'), sg.Input(key='pricing_b_8', size=(30,1))],
        [sg.Text('List Multiplier, < 5:'), sg.Input(key='pricing_l_1', size=(30,1))],
        [sg.Text('List Multiplier, 5-49.99:'), sg.Input(key='pricing_l_2', size=(30,1))],
        [sg.Text('List Multiplier, 50-74.99:'), sg.Input(key='pricing_l_3', size=(30,1))],
        [sg.Text('List Multiplier, 75+:'), sg.Input(key='pricing_l_4', size=(30,1))],
        [sg.Button('Save Pricing Rule'), sg.Button('Delete Pricing Rule')],
        [sg.HorizontalSeparator()],
        [sg.Text('Bulk Upload:', font='Any 11 bold')],
        [sg.Input(key='pricing_bulk_file', size=(50,1)), 
         sg.FileBrowse(file_types=(("Excel Files", "*.xlsx"),))],
        [sg.Button('Upload Pricing Bulk'), sg.Button('Download Pricing Template')],
        [sg.HorizontalSeparator()],
        [sg.Text('Existing Pricing Rules:')],
        [sg.Table(
                values=[],
                headings=[
                    'Vendor','List Handling',
                    'B1','B2','B3','B4','B5','B6','B7','B8',
                    'L1','L2','L3','L4'
                ],
                key='pricing_table',
                enable_events=True,
                auto_size_columns=False,
                col_widths=[10,18] + [6]*12,
                justification='center'
            )]]
    
    # Vendor defaults layout with bulk upload
    vendor_layout = [
        [sg.Text('Vendor Defaults Management', font='Any 12 bold')],
        [sg.Text('Individual Vendor Entry:', font='Any 11 bold')],
        [sg.Text('Vendor Number:'), sg.Input(key='vendor_no', size=(10,1)), 
         sg.Button('Load Vendor'), sg.Button('New Vendor')],
        [sg.Text('Brand Code:'), sg.Input(key='vendor_brandcode', size=(20,1))],
        [sg.Text('Product Category:'), sg.Input(key='vendor_prodcat', size=(20,1))],
        [sg.Text('Website Category:'), sg.Input(key='vendor_webcat', size=(20,1))],
        [sg.Text('Product Line:'), sg.Input(key='vendor_prodline', size=(20,1))],
        [sg.Text('Seasonal (y/n):'), sg.Input(key='vendor_seasonal', size=(5,1))],
        [sg.Button('Save Vendor'), sg.Button('Delete Vendor')],
        [sg.HorizontalSeparator()],
        [sg.Text('Bulk Upload:', font='Any 11 bold')],
        [sg.Input(key='vendor_bulk_file', size=(50,1)), 
         sg.FileBrowse(file_types=(("Excel Files", "*.xlsx"),))],
        [sg.Button('Upload Vendor Bulk'), sg.Button('Download Vendor Template')],
        [sg.HorizontalSeparator()],
        [sg.Text('Existing Vendors:')],
        [sg.Listbox(values=[], key='vendor_list', size=(60, 10), enable_events=True)]
    ]
    
    # Warehouse management layout with bulk upload
    warehouse_layout = [
            [sg.Text('Warehouse Configuration', font='Any 12 bold')],
            [sg.Text('Individual Warehouse Entry:', font='Any 11 bold')],
            [sg.Text('Warehouse Number:'), sg.Input(key='wh_number', size=(10,1)), 
            sg.Button('Load Warehouse'), sg.Button('New Warehouse')],
            [sg.Text('Type:'), sg.Combo(['D', 'B'], key='wh_type', size=(5,1), readonly=True),
            sg.Text('(D=Distribution, B=Branch)')],
            [sg.Text('ARP Whse:'), sg.Input(key='wh_arpwhse', size=(10,1)),
            sg.Text('(Only for Distribution centers)')],
            [sg.Text('Description:'), sg.Input(key='wh_description', size=(40,1))],
            [sg.Checkbox('Active', key='wh_active', default=True)],
            [sg.Button('Save Warehouse'), sg.Button('Delete Warehouse')],
            [sg.HorizontalSeparator()],
            [sg.Text('Existing Warehouses:')],
            [sg.Table(
                values=[], 
                headings=['Warehouse', 'Type', 'ARP Whse', 'Description', 'Active'],
                key='warehouse_table', 
                size=(None, 10), 
                enable_events=True,
                auto_size_columns=False,
                col_widths=[10, 8, 10, 30, 8]
            )],
            [sg.Button('Refresh Warehouses')],
            [sg.HorizontalSeparator()],
            [sg.Text('Bulk Upload:', font='Any 11 bold')],
            [sg.Input(key='warehouse_bulk_file', size=(50,1)), 
            sg.FileBrowse(file_types=(("Excel Files", "*.xlsx"),))],
            [sg.Button('Upload Warehouse Bulk'), sg.Button('Download Warehouse Template')]
        ]

    # # Pricing layout with bulk upload
    # pricing_layout = [
    #     [sg.Text('Pricing Multipliers', font='Any 12 bold')],
    #     [sg.Text('Import pricing rules from Excel:')],
    #     [sg.Input(key='pricing_import_file', size=(50,1)), 
    #      sg.FileBrowse(file_types=(("Excel Files", "*.xlsx"),))],
    #     [sg.Text('Sheet Name:'), sg.Input('PRICING MULTIPLIERS', key='pricing_sheet', size=(30,1))],
    #     [sg.Button('Import Pricing Rules'), sg.Button('Download Pricing Template')],
    #     [sg.HorizontalSeparator()],
    #     [sg.Text('Current Pricing Rules:')],
    #     [sg.Table(values=[], headings=['Vendor', 'List Handling'], key='pricing_table', 
    #              size=(None, 10), auto_size_columns=False, col_widths=[15, 30])]
    # ]
    
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
    rows = db.get_pricing_multipliers()  # must return tuples
    window['pricing_table'].update(values=rows)


def handle_settings_window(settings, db, template_gen):
    """Handle settings window events"""
    window = create_settings_window(settings, db)
    
    while True:
        event, values = window.read()
        
        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        
        if event == 'Save All Settings':
            settings.set('folders.prodadds', values['folder_prodadds'])
            settings.set('folders.output_folder', values['folder_output'])
            settings.set('folders.archive', values['folder_archive'])
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
        
        elif event == 'Save Vendor':
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

       
        
        elif event == 'Save Pricing Rule':
            vendor = values['pricing_vendor'].strip()
            list_handling = values['pricing_vendor_list_handling'].strip()

            if not vendor:
                sg.popup_error('Vendor is required')
                continue

            def safe_float(val):
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return None

            base_mults = [safe_float(values[f'pricing_b_{i}']) for i in range(1, 9)]
            list_mults = [safe_float(values[f'pricing_l_{i}']) for i in range(1, 5)]

            if any(v is None for v in base_mults + list_mults):
                sg.popup_error('All multiplier fields must be numeric')
                continue

            db.save_pricing_rule(
                vendor,
                list_handling,
                *base_mults,
                *list_mults
            )

            update_pricing_table(window, db)
            sg.popup(f'Pricing rule saved for {vendor}')


        elif event == 'Delete Pricing Rule':

            vendor = values['pricing_vendor'].strip()

            if not vendor:
                sg.popup_error('Vendor is required to delete')
                continue

            if sg.popup_yes_no(f'Delete pricing rule for {vendor}?') != 'Yes':
                continue

            db.delete_pricing_rule(vendor)
            update_pricing_table(window, db)

            for key in values:
                if key.startswith('pricing_'):
                    window[key].update('')

            sg.popup(f'Pricing rule deleted for {vendor}')

        elif event == 'pricing_table' and values['pricing_table']:
            row = values['pricing_table'][0]

            vendor = row[0]
            list_handling = row[1]
            base_mults = row[2:10]   # b1–b8
            list_mults = row[10:14] # l1–l4

            window['pricing_vendor'].update(vendor)
            window['pricing_vendor_list_handling'].update(list_handling)

            for i, val in enumerate(base_mults, start=1):
                window[f'pricing_b_{i}'].update(val)

            for i, val in enumerate(list_mults, start=1):
                window[f'pricing_l_{i}'].update(val)

           
        
        elif event == 'Download Vendor Template':
            path = template_gen.generate_vendor_bulk_template()
            sg.popup(f'Template saved to:\n{path}')
        
        elif event == 'Upload Vendor Bulk':
            if values['vendor_bulk_file']:
                try:
                    df = pd.read_excel(values['vendor_bulk_file'], sheet_name='Vendors')
                    db.bulk_upload_vendors(df)
                    update_vendor_list(window, db)
                    sg.popup(f'Uploaded {len(df)} vendors successfully!')
                except Exception as e:
                    sg.popup_error(f'Error uploading vendors: {str(e)}')
        
        elif event == 'Download Warehouse Template':
            path = template_gen.generate_warehouse_bulk_template()
            sg.popup(f'Template saved to:\n{path}')
        
        elif event == 'Upload Warehouse Bulk':
            if values['warehouse_bulk_file']:
                try:
                    df = pd.read_excel(values['warehouse_bulk_file'], sheet_name='Warehouses')
                    db.bulk_upload_warehouses(df)
                    update_warehouse_table(window, db)
                    sg.popup(f'Uploaded {len(df)} warehouses successfully!')
                except Exception as e:
                    sg.popup_error(f'Error uploading warehouses: {str(e)}')
        
        elif event == 'Download Pricing Template':
            path = template_gen.generate_pricing_bulk_template()
            sg.popup(f'Template saved to:\n{path}')
        
        elif event == 'Import Pricing Rules':
            if values['pricing_import_file']:
                try:
                    df = pd.read_excel(values['pricing_import_file'], 
                                      sheet_name=values['pricing_sheet'])
                    db.bulk_upload_pricing(df)
                    update_pricing_table(window, db)
                    sg.popup('Pricing rules imported successfully!')
                except Exception as e:
                    sg.popup_error(f'Failed to import pricing rules: {str(e)}')
        
        elif event == 'Refresh Warehouses':
            update_warehouse_table(window, db)
        
        elif event == 'Export Database':
            from datetime import datetime
            import shutil
            backup_path = f"app_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy(db.db_path, backup_path)
            sg.popup(f'Database exported to:\n{backup_path}')
        
        elif event == 'vendor_list':
            if values['vendor_list']:
                vendor_str = values['vendor_list'][0]
                vendor_no = vendor_str.split(':')[0].replace('Vendor ', '').strip()
                window['vendor_no'].update(vendor_no)
                window.write_event_value('Load Vendor', '')
        
        elif event == 'Load Warehouse':
            wh_num = values['wh_number'].strip()
            if wh_num:
                try:
                    warehouses = db.get_warehouses()
                    wh_data = [w for w in warehouses if w[0] == int(wh_num)]
                    if wh_data:
                        wh = wh_data[0]
                        window['wh_type'].update(wh[1])
                        window['wh_arpwhse'].update(wh[2] if wh[2] else '')
                        window['wh_description'].update(wh[3])
                        window['wh_active'].update(bool(wh[4]))
                    else:
                        sg.popup(f'Warehouse {wh_num} not found')
                except ValueError:
                    sg.popup_error('Invalid warehouse number')

        elif event == 'New Warehouse':
            window['wh_number'].update('')
            window['wh_type'].update('D')
            window['wh_arpwhse'].update('')
            window['wh_description'].update('')
            window['wh_active'].update(True)

        elif event == 'Save Warehouse':
            wh_num = values['wh_number'].strip()
            wh_type = values['wh_type']
            
            if not wh_num or not wh_type:
                sg.popup_error('Warehouse number and type are required')
                continue
            
            try:
                wh_number = int(wh_num)
                arpwhse = None
                
                # Validate ARP warehouse for Distribution centers
                if wh_type == 'D':
                    arpwhse_str = values['wh_arpwhse'].strip()
                    if arpwhse_str:
                        try:
                            arpwhse = int(arpwhse_str)
                        except ValueError:
                            sg.popup_error('ARP Whse must be a number')
                            continue
                
                description = values['wh_description'].strip()
                active = 1 if values['wh_active'] else 0
                
                db.save_warehouse(wh_number, wh_type, arpwhse, description, active)
                update_warehouse_table(window, db)
                sg.popup(f'Warehouse {wh_number} saved successfully!')
                
            except ValueError:
                sg.popup_error('Invalid warehouse number - must be numeric')
            except Exception as e:
                sg.popup_error(f'Error saving warehouse: {str(e)}')

        elif event == 'Delete Warehouse':
            wh_num = values['wh_number'].strip()
            if wh_num:
                try:
                    if sg.popup_yes_no(f'Delete warehouse {wh_num}?') == 'Yes':
                        db.delete_warehouse(int(wh_num))
                        update_warehouse_table(window, db)
                        sg.popup(f'Warehouse {wh_num} deleted')
                        
                        # Clear form
                        window['wh_number'].update('')
                        window['wh_type'].update('D')
                        window['wh_arpwhse'].update('')
                        window['wh_description'].update('')
                        window['wh_active'].update(True)
                except Exception as e:
                    sg.popup_error(f'Error deleting warehouse: {str(e)}')
            else:
                sg.popup_error('Please enter a warehouse number to delete')

        elif event == 'warehouse_table' and values['warehouse_table']:
            # Load selected warehouse into form
            selected_row = values['warehouse_table'][0]
            table_data = window['warehouse_table'].get()
            if selected_row < len(table_data):
                row = table_data[selected_row]
                window['wh_number'].update(str(row[0]))
                window['wh_type'].update(row[1])
                window['wh_arpwhse'].update(str(row[2]) if row[2] else '')
                window['wh_description'].update(row[3])
                window['wh_active'].update(row[4] == 'Yes')

        elif event == 'Upload Pricing Bulk':
            if values['pricing_bulk_file']:
                try:
                    df = pd.read_excel(values['pricing_bulk_file'], sheet_name='PRICING MULTIPLIERS')
                    
                    # Validate columns
                    required_cols = ['vendor', 'Vendor List Handling', 
                                'B-0.01-1.49', 'B-1.5-4.99', 'B-5-49.99', 'B-50-74.99',
                                'B-75-99.99', 'B-100-499.99', 'B-500-999.99', 'B-1000-999999',
                                'L-0.01-4.99', 'L-5-49.99.1', 'L-50-74.99.1', 'L-75-99999']
                    
                    missing = [c for c in required_cols if c not in df.columns]
                    if missing:
                        sg.popup_error(f'Missing required columns:\n' + '\n'.join(missing))
                        continue
                    
                    db.bulk_upload_pricing(df)
                    update_pricing_table(window, db)
                    sg.popup(f'Uploaded {len(df)} pricing rules successfully!')
                except Exception as e:
                    sg.popup_error(f'Error uploading pricing rules: {str(e)}')
        
    window.close()

def create_main_window():
    """Create the main application window with all enhancements"""
    
    try:
        sg.theme('LightBlue2')
    except:
        pass
    
    # Input tab with template download
    input_tab = [
        [sg.Text('Choose Input Method:', font='Any 12 bold')],
        [sg.Radio('Upload Excel/CSV File', 'INPUT', key='input_file', default=True, enable_events=True)],
        [sg.Input(key='file_path', size=(45,1)), 
         sg.FileBrowse(file_types=(("Excel Files", "*.xlsx"), ("CSV Files", "*.csv"))),
         sg.Button('Download Template', key='download_input_template')],
        [sg.Radio('Manual Form Entry', 'INPUT', key='input_form', enable_events=True)],
        [sg.HorizontalSeparator()],
        [sg.Text('Manual Product Entry (Required: Product, Vendor No, Description, Repl Cost)', 
                 font='Any 10 italic', key='required_notice', visible=False)],
        [sg.Column([
            [sg.Text('*Product:'), sg.Input(key='prod', size=(15,1))],
            [sg.Text('*Vendor No:'), sg.Input(key='vendor_no', size=(15,1))],
            [sg.Text('*Description:'), sg.Input(key='description', size=(40,1))],
            [sg.Text(' Core Flag (Y):'), sg.Input(key='core_flag', size=(5,1))],
            [sg.Text('*Repl Cost:'), sg.Input(key='repl_cost', size=(10,1))],
            [sg.Text(' Base Price:'), sg.Input(key='base_price', size=(10,1))],
            [sg.Text(' List Price:'), sg.Input(key='list_price', size=(10,1))],
        ], key='form_column', visible=False),
        sg.Column([
            [sg.Text('Length:'), sg.Input(key='length', size=(10,1), default_text='1')],
            [sg.Text('Width:'), sg.Input(key='width', size=(10,1), default_text='1')],
            [sg.Text('Height:'), sg.Input(key='height', size=(10,1), default_text='1')],
            [sg.Text('Weight:'), sg.Input(key='weight', size=(10,1), default_text='1')],
            [sg.Text('Brand Code:'), sg.Input(key='brand_code', size=(15,1))],
            [sg.Text('Product Cat:'), sg.Input(key='prod_cat', size=(15,1))],
            [sg.Text('Website Cat:'), sg.Input(key='web_cat', size=(15,1))],
        ], key='form_column2', visible=False)],
        [sg.Button('Add to Batch', key='add_manual', visible=False),
         sg.Button('Clear Form', key='clear_form', visible=False)],
        [sg.Text('* = Required Field', font='Any 9 italic', key='required_legend', visible=False)]
    ]
    
    # Batch view
    batch_tab = [
        [sg.Text('Products in Current Batch:', font='Any 12 bold')],
        [sg.Table(values=[], 
                  headings=['Product', 'Vendor', 'Description', 'Core', 'Repl Cost', 'Base Price', 'List Price'],
                  key='batch_table', size=(None, 15), auto_size_columns=True, 
                  justification='left', enable_events=True)],
        [sg.Button('Remove Selected'), sg.Button('Clear Batch'), sg.Button('Export Batch to Excel')]
    ]
    
    # Output settings
    output_tab = [
        [sg.Text('Output Options:', font='Any 12 bold')],
        [sg.Checkbox('Generate Step 1 Output (cp*.csv) - Product Master', 
                     key='gen_step1', default=True)],
        [sg.Checkbox('Generate Step 2 Output (cw*.csv) - Warehouse Data', 
                     key='gen_step2', default=True)],
        [sg.Checkbox('Create Archive of Input Files', key='do_archive', default=True)],
        [sg.Checkbox('Update Upload Log', key='update_log', default=True)],
        [sg.Text('Notes for Log:'), sg.Input(key='log_notes', size=(60,1))],
        [sg.HorizontalSeparator()],
        [sg.Text('Processing will:', font='Any 10 italic')],
        [sg.Text('  • Apply vendor defaults to products', font='Any 9')],
        [sg.Text('  • Calculate pricing based on rules', font='Any 9')],
        [sg.Text('  • Generate warehouse records for active warehouses', font='Any 9')],
        [sg.Text('  • Create hashed output filenames', font='Any 9')],
    ]
    
    # Main layout
    layout = [
        [sg.MenuBar([['File', ['Settings', 'Exit']], ['Help', ['About', 'User Guide']]])],
        [sg.TabGroup([
            [sg.Tab('Input', input_tab)],
            [sg.Tab('Batch', batch_tab)],
            [sg.Tab('Output', output_tab)]
        ])],
        [sg.HorizontalSeparator()],
        [sg.Button('Process', size=(15,1), button_color=('white', 'green')), 
         sg.Button('Clear All', size=(15,1)), 
         sg.Button('Exit', size=(15,1))],
        [sg.Multiline(size=(120, 12), key='output_log', autoscroll=True, disabled=True,
                     font='Courier 9')]
    ]
    
    window = sg.Window('Product Adds Management System', layout, finalize=True, 
                      resizable=True, size=(1000, 700))
    return window

def main():
    """Main application entry point"""
    
    # Initialize components
    settings = Settings()
    db = AppDatabase()
    template_gen = TemplateGenerator()
    window = create_main_window()
    batch_data = []
    
    # Generate templates on first run
    template_gen.generate_all_templates()
    
    while True:
        event, values = window.read()
        
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        
        # Toggle form visibility
        if event == 'input_form':
            window['form_column'].update(visible=True)
            window['form_column2'].update(visible=True)
            window['add_manual'].update(visible=True)
            window['clear_form'].update(visible=True)
            window['required_notice'].update(visible=True)
            window['required_legend'].update(visible=True)
        elif event == 'input_file':
            window['form_column'].update(visible=False)
            window['form_column2'].update(visible=False)
            window['add_manual'].update(visible=False)
            window['clear_form'].update(visible=False)
            window['required_notice'].update(visible=False)
            window['required_legend'].update(visible=False)
        
        # Settings menu
        if event == 'Settings':
            handle_settings_window(settings, db, template_gen)
        
        # Download input template
        if event == 'download_input_template':
            path = template_gen.generate_product_input_template()
            sg.popup(f'Product input template saved to:\n{path}')
            window['output_log'].update(f"Template saved: {path}\n", append=True)
        
        # Clear form
        if event == 'clear_form':
            for key in ['prod', 'vendor_no', 'description', 'core_flag', 'repl_cost',
                       'base_price', 'list_price', 'brand_code', 'prod_cat', 'web_cat']:
                window[key].update('')
            window['length'].update('1')
            window['width'].update('1')
            window['height'].update('1')
            window['weight'].update('1')
        
        # Add manual entry to batch
        if event == 'add_manual':
            missing = validate_required_fields(values)
            if missing:
                sg.popup_error(
                    "Missing required fields:\n" + "\n".join(missing)
                )
                continue

            try:
                vendor_no = int(values['vendor_no'])

                # 🔴 HARD STOP — pricing validation
                if not vendor_has_pricing(db, vendor_no):
                    sg.popup_error(
                        f"Vendor {vendor_no} has no Pricing Rules configured.\n\n"
                        "Go to Settings → Pricing Rules to set up pricing rules for vendor, then try again."
                    )
                    continue   # ⬅ DO NOT ADD TO BATCH
                product_data = {
                        'PRODUCT': values['prod'].strip(),
                        'VENDOR NO': int(values['vendor_no']),
                        'DESCRIPTION': values['description'].strip(),
                        'CORE FLAG (Y)': values['core_flag'].strip().upper(),
                        'REPL COST': float(values['repl_cost']),
                        'BASE PRICE': float(values['base_price']) if values['base_price'] else None,
                        'LIST PRICE': float(values['list_price']) if values['list_price'] else None,
                        'LENGTH': float(values['length']) if values['length'] else 1,
                        'WIDTH': float(values['width']) if values['width'] else 1,
                        'HEIGHT': float(values['height']) if values['height'] else 1,
                        'WEIGHT': float(values['weight']) if values['weight'] else 1,
                        'BRAND CODE': values['brand_code'].strip(),
                        'PRODUCT CAT': values['prod_cat'].strip(),
                        'WEBSITE CAT': values['web_cat'].strip()
                }        
                # Get vendor defaults
                vendor_defaults = db.get_vendor_defaults(product_data['VENDOR NO'])
                if vendor_defaults:
                    if not product_data['BRAND CODE']:
                        product_data['BRAND CODE'] = vendor_defaults.get('default_brandcode', '')
                    if not product_data['PRODUCT CAT']:
                        product_data['PRODUCT CAT'] = vendor_defaults.get('default_prodcat', '')
                    if not product_data['WEBSITE CAT']:
                        product_data['WEBSITE CAT'] = vendor_defaults.get('default_webcat', '')
                    product_data['PRODLINE'] = vendor_defaults.get('default_prodline', '')
                    product_data['SEASONAL'] = vendor_defaults.get('seasonal_flag', '')
                
                batch_data.append(product_data)
                sg.popup("Product added to batch.")
                # Update table
                table_data = [[p['PRODUCT'], p['VENDOR NO'], p['DESCRIPTION'][:30], 
                              p.get('CORE FLAG (Y)', ''), f"${p.get('REPL COST', 0):.2f}",
                              f"${p.get('BASE PRICE') or 0:.2f}", 
                              f"${p.get('LIST PRICE') or 0:.2f}"] 
                             for p in batch_data]
                window['batch_table'].update(values=table_data)
                
                window['output_log'].update(f"✓ Added {values['prod']} to batch\n", append=True)
                
                # Clear form after successful add
                window.write_event_value('clear_form', '')

            except ValueError as e:
                sg.popup_error(f"Invalid input: {str(e)}\nPlease check numeric fields.")
            except Exception as e:
                sg.popup_error(f"Error adding to batch: {str(e)}")
        
        # Process button
        if event == 'Process':
            try:
                if not batch_data and not (values['input_file'] and values['file_path']):
                    sg.popup_error("No input data! Either upload a file or add products manually.")
                    continue
                
                window['output_log'].update("=" * 80 + "\nStarting processing...\n")
                
                # Load data into staging table
                if values['input_file'] and values['file_path']:
                    # Load from file
                    if values['file_path'].endswith('.xlsx'):
                        df = pd.read_excel(values['file_path'])
                    else:
                        df = pd.read_csv(values['file_path'])
                    
                    window['output_log'].update(f"Loaded {len(df)} rows from file\n", append=True)
                    
                    # Validate required columns
                    required_cols = ['PRODUCT', 'VENDOR NO', 'DESCRIPTION', 'REPL COST']
                    missing_cols = [c for c in required_cols if c not in df.columns]
                    if missing_cols:
                        sg.popup_error(f'Missing required columns in file:\n' + 
                                      '\n'.join(f'  • {c}' for c in missing_cols))
                        continue
                    
                    # Add to staging
                    for _, row in df.iterrows():
                        product_dict = row.to_dict()
                        db.add_to_staging(product_dict)
                
                elif batch_data:
                    # Use batch data
                    window['output_log'].update(f"Using {len(batch_data)} products from batch\n", 
                                               append=True)
                    for product in batch_data:
                        db.add_to_staging(product)
                
                output_folder = settings.get('folders.output_folder') or '.'
                
                # Process Step 1
                if values['gen_step1']:
                    window['output_log'].update("\n--- Step 1: Product Master ---\n", append=True)
                    step1_df, output_path, messages = process_step1(db, output_folder)
                    for msg in messages:
                        window['output_log'].update(msg + "\n", append=True)
                
                # Process Step 2
                if values['gen_step2']:
                    window['output_log'].update("\n--- Step 2: Warehouse Data ---\n", append=True)
                    output_path, messages = process_step2(db, step1_df, output_folder)
                    for msg in messages:
                        window['output_log'].update(msg + "\n", append=True)
                
                # Update log
                if values['update_log']:
                    staging_df = db.get_staging_data()
                    validate_vendors_against_pricing(db, staging_df)
                    db.log_upload(
                        f"Processed {len(staging_df)} products",
                        len(staging_df),
                        values['log_notes']
                    )
                    window['output_log'].update("✓ Upload log updated\n", append=True)
                
                # Clear staging
                db.clear_staging()
                batch_data = []
                window['batch_table'].update(values=[])
                
                window['output_log'].update("\n" + "=" * 80 + "\n✓ Processing complete!\n", 
                                           append=True)
                sg.popup('Processing Complete!', 'Check the output log for details.')
                
            except Exception as e:
                error_msg = f"✗ Error during processing: {str(e)}"
                window['output_log'].update(error_msg + "\n", append=True)
                sg.popup_error(error_msg)
        
        # Clear batch
        if event == 'Clear Batch':
            batch_data = []
            window['batch_table'].update(values=[])
            window['output_log'].update("Batch cleared\n", append=True)
        
        # Clear all
        if event == 'Clear All':
            batch_data = []
            window['batch_table'].update(values=[])
            window['output_log'].update('')
            window['file_path'].update('')
        
        # Remove selected from batch
        if event == 'Remove Selected':
            if values['batch_table']:
                selected_rows = values['batch_table']
                for row_idx in sorted(selected_rows, reverse=True):
                    if 0 <= row_idx < len(batch_data):
                        removed = batch_data.pop(row_idx)
                        window['output_log'].update(f"Removed {removed['PRODUCT']} from batch\n", 
                                                   append=True)
                
                # Update table
                table_data = [[p['PRODUCT'], p['VENDOR NO'], p['DESCRIPTION'][:30], 
                              p.get('CORE FLAG (Y)', ''), f"${p.get('REPL COST', 0):.2f}",
                              f"${p.get('BASE PRICE') or 0:.2f}", 
                              f"${p.get('LIST PRICE') or 0:.2f}"] 
                             for p in batch_data]
                window['batch_table'].update(values=table_data)
        
        # About
        if event == 'About':
            sg.popup('Product Adds Management System', 
                    'Version 2.0',
                    'Automated product addition with pricing and warehouse management',
                    'Docker-ready application')
        
        # User Guide
        if event == 'User Guide':
            guide = """
Quick Start Guide:

1. Settings Setup (File → Settings):
   • Configure folder paths
   • Set up vendor defaults (or bulk upload)
   • Configure warehouses
   • Import pricing rules

2. Adding Products:
   • Option A: Upload Excel/CSV (download template first)
   • Option B: Manual entry (fill required fields: Product, Vendor No, Description, Repl Cost)

3. Processing:
   • Review batch
   • Select output options
   • Click Process

4. Output:
   • cp*.csv: Product master data (Step 1)
   • cw*.csv: Warehouse data (Step 2)

Required Fields:
  • Product
  • Vendor No
  • Description  
  • Repl Cost

For detailed instructions, see README.md
"""
            sg.popup_scrolled(guide, title='User Guide', size=(60, 30))
    
    db.close()
    window.close()

if __name__ == '__main__':
    main()