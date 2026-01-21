# app/template_generator.py
import pandas as pd
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill

class TemplateGenerator:
    """Generate Excel templates for various uploads"""
    
    def __init__(self):
        self.template_dir = Path('app/templates')
        self.template_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_product_input_template(self):
        """Generate product input template"""
        # Create sample data
        sample_data = pd.DataFrame([{
            'PRODUCT': 'SAMPLE123',
            'VENDOR NO': 100,
            'DESCRIPTION': 'Sample Product Description',
            'CORE FLAG (Y)': '',
            'REPL COST': 10.00,
            'BASE PRICE': 15.00,
            'LIST PRICE': 20.00,
            'LENGTH': 1,
            'WIDTH': 1,
            'HEIGHT': 1,
            'WEIGHT': 1,
            'BRAND CODE': 'BRANDX',
            'PRODUCT CAT': 'CATEG1',
            'WEBSITE CAT': 'WEBCAT1',
            'PRODLINE': 'LINE1',
            'SEASONAL': 'n'
        }])
        
        instructions = pd.DataFrame({
            'Field': ['PRODUCT', 'VENDOR NO', 'DESCRIPTION', 'CORE FLAG (Y)', 
                     'REPL COST', 'BASE PRICE', 'LIST PRICE', 'SEASONAL'],
            'Required': ['Yes', 'Yes', 'Yes', 'No', 'Yes', 'No', 'No', 'No'],
            'Description': [
                'Product SKU/Part Number (unique identifier)',
                'Vendor number (must match vendor defaults)',
                'Product description (will be cleaned to 24 chars)',
                'Enter Y if this is a core product, leave blank otherwise',
                'Replacement cost from vendor',
                'Optional: Override calculated base price',
                'Optional: Override calculated list price',
                'Enter y for seasonal products, n for standard'
            ]
        })
        
        output_path = self.template_dir / 'product_input_template.xlsx'
        
        # Write using openpyxl for better control
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            sample_data.to_excel(writer, sheet_name='Products', index=False)
            instructions.to_excel(writer, sheet_name='Instructions', index=False)
            
            # Auto-adjust column widths
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        return str(output_path)
    
    def generate_vendor_bulk_template(self):
        """Generate vendor bulk upload template"""
        sample_data = pd.DataFrame([
            {
                'vendor_no': 100,
                'default_brandcode': 'BRAND1',
                'default_prodcat': 'CATEGORY1',
                'default_webcat': 'WEBCAT1',
                'default_prodline': 'PRODUCTLINE1',
                'seasonal_flag': 'n'
            },
            {
                'vendor_no': 200,
                'default_brandcode': 'BRAND2',
                'default_prodcat': 'CATEGORY2',
                'default_webcat': 'WEBCAT2',
                'default_prodline': 'PRODUCTLINE2',
                'seasonal_flag': 'y'
            }
        ])
        
        instructions = pd.DataFrame({
            'Field': ['vendor_no', 'default_brandcode', 'default_prodcat', 
                     'default_webcat', 'default_prodline', 'seasonal_flag'],
            'Description': [
                'Unique vendor number',
                'Default brand code for this vendor',
                'Default product category',
                'Default website category',
                'Default product line',
                'Enter y for seasonal, n for standard'
            ]
        })
        
        output_path = self.template_dir / 'vendor_bulk_upload.xlsx'
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            sample_data.to_excel(writer, sheet_name='Vendors', index=False)
            instructions.to_excel(writer, sheet_name='Instructions', index=False)
            
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        return str(output_path)
    
    def generate_warehouse_bulk_template(self):
        """Generate warehouse bulk upload template"""
        sample_data = pd.DataFrame([
            {
                'warehouse': 25,
                'type': 'D',
                'arpwhse': 15,
                'description': 'Main Distribution Center',
                'active': 1
            },
            {
                'warehouse': 50,
                'type': 'D',
                'arpwhse': 16,
                'description': 'Secondary Distribution Center',
                'active': 1
            },
            {
                'warehouse': 10,
                'type': 'B',
                'arpwhse': None,
                'description': 'Branch 10',
                'active': 1
            }
        ])
        
        instructions = pd.DataFrame({
            'Field': ['warehouse', 'type', 'arpwhse', 'description', 'active'],
            'Description': [
                'Unique warehouse number',
                'D for Distribution Center, B for Branch',
                'ARP warehouse number (for D type only)',
                'Warehouse description',
                '1 for active, 0 for inactive'
            ]
        })
        
        output_path = self.template_dir / 'warehouse_bulk_upload.xlsx'
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            sample_data.to_excel(writer, sheet_name='Warehouses', index=False)
            instructions.to_excel(writer, sheet_name='Instructions', index=False)
            
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        return str(output_path)
    
    def generate_pricing_bulk_template(self):
        """Generate pricing rules bulk upload template"""
        sample_data = pd.DataFrame([
            {
                'vendor': 'Standard',
                'Vendor List Handling': 'list_or_base1.1',
                'B-0.01-1.49': 1.75,
                'B-1.5-4.99': 1.65,
                'B-5-49.99': 1.55,
                'B-50-74.99': 1.45,
                'B-75-99.99': 1.40,
                'B-100-499.99': 1.35,
                'B-500-999.99': 1.30,
                'B-1000-999999': 1.25,
                'L-0.01-4.99': 2.00,
                'L-5-49.99.1': 1.85,
                'L-50-74.99.1': 1.70,
                'L-75-99999': 1.60
            },
            {
                'vendor': '360',
                'Vendor List Handling': 'take_min',
                'B-0.01-1.49': 1.80,
                'B-1.5-4.99': 1.70,
                'B-5-49.99': 1.60,
                'B-50-74.99': 1.50,
                'B-75-99.99': 1.45,
                'B-100-499.99': 1.40,
                'B-500-999.99': 1.35,
                'B-1000-999999': 1.30,
                'L-0.01-4.99': 2.10,
                'L-5-49.99.1': 1.95,
                'L-50-74.99.1': 1.80,
                'L-75-99999': 1.70
            }
        ])
        
        instructions = pd.DataFrame({
            'Field': ['vendor', 'Vendor List Handling', 'B-* columns', 'L-* columns'],
            'Description': [
                'Vendor number or "Standard" for default rules',
                'Options: list_or_base1.1 (use list or base*1.1) or take_min (use minimum of list or calculated)',
                'Base price multipliers for different cost ranges (multiply repl cost by these)',
                'List price multipliers for different cost ranges'
            ]
        })
        
        output_path = self.template_dir / 'pricing_bulk_upload.xlsx'
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            sample_data.to_excel(writer, sheet_name='PRICING MULTIPLIERS', index=False)
            instructions.to_excel(writer, sheet_name='Instructions', index=False)
            
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        return str(output_path)
    
    def generate_all_templates(self):
        """Generate all templates and return paths"""
        templates = {}
        try:
            templates['product_input'] = self.generate_product_input_template()
            templates['vendor_bulk'] = self.generate_vendor_bulk_template()
            templates['warehouse_bulk'] = self.generate_warehouse_bulk_template()
            templates['pricing_bulk'] = self.generate_pricing_bulk_template()
        except Exception as e:
            print(f"Error generating templates: {str(e)}")
        return templates