# ===== FILE: app/database.py =====
# Enhanced Database Management
import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
import shutil

class AppDatabase:
    """Manage self-contained application database"""
    
    def __init__(self, db_path='data/app_data.db'):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
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
        
        # Pricing multipliers table (matches your pricing_map structure)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pricing_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor TEXT,
                "Vendor List Handling" TEXT,
                "B-0.01-1.49" REAL,
                "B-1.5-4.99" REAL,
                "B-5-49.99" REAL,
                "B-50-74.99" REAL,
                "B-75-99.99" REAL,
                "B-100-499.99" REAL,
                "B-500-999.99" REAL,
                "B-1000-999999" REAL,
                "L-0.01-4.99" REAL,
                "L-5-49.99.1" REAL,
                "L-50-74.99.1" REAL,
                "L-75-99999" REAL
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
        
        # Product staging table (rawicswdata equivalent)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rawicswdata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                PRODUCT TEXT NOT NULL,
                "VENDOR NO" INTEGER NOT NULL,
                DESCRIPTION TEXT NOT NULL,
                "CORE FLAG (Y)" TEXT,
                "REPL COST" REAL NOT NULL,
                "BASE PRICE" REAL,
                "LIST PRICE" REAL,
                LENGTH REAL,
                WIDTH REAL,
                HEIGHT REAL,
                WEIGHT REAL,
                "BRAND CODE" TEXT,
                "PRODUCT CAT" TEXT,
                "WEBSITE CAT" TEXT,
                PRODLINE TEXT,
                SEASONAL TEXT,
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
        
        # Insert default pricing if empty
        cursor.execute('SELECT COUNT(*) FROM pricing_map')
        if cursor.fetchone()[0] == 0:
            default_pricing = {
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
            }
            df = pd.DataFrame([default_pricing])
            df.to_sql('pricing_map', self.conn, if_exists='append', index=False)
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
    
    def bulk_upload_vendors(self, df):
        """Bulk upload vendors from DataFrame"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = self.conn.cursor()
        
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO vendor_defaults 
                (vendor_no, default_brandcode, default_prodcat, default_webcat, 
                 default_prodline, seasonal_flag, created_date, modified_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (int(row['vendor_no']), row.get('default_brandcode', ''),
                  row.get('default_prodcat', ''), row.get('default_webcat', ''),
                  row.get('default_prodline', ''), row.get('seasonal_flag', ''),
                  now, now))
        
        self.conn.commit()
    
    def bulk_upload_warehouses(self, df):
        """Bulk upload warehouses from DataFrame"""
        cursor = self.conn.cursor()
        
        for _, row in df.iterrows():
            arpwhse = row.get('arpwhse')
            if pd.notna(arpwhse):
                arpwhse = int(arpwhse)
            else:
                arpwhse = None
                
            cursor.execute('''
                INSERT OR REPLACE INTO warehouse_info 
                (warehouse, type, arpwhse, description, active)
                VALUES (?, ?, ?, ?, ?)
            ''', (int(row['warehouse']), row['type'], arpwhse,
                  row.get('description', ''), int(row.get('active', 1))))
        
        self.conn.commit()
    
    def bulk_upload_pricing(self, df):
        """Bulk upload pricing rules from DataFrame"""
        # Clear existing and reload
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM pricing_map')
        df.to_sql('pricing_map', self.conn, if_exists='append', index=False)
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
        """Get pricing multipliers as DataFrame"""
        return pd.read_sql_query('SELECT * FROM pricing_map', self.conn)
    
    def add_to_staging(self, product_dict):
        """Add a product to staging table (rawicswdata)"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO rawicswdata 
            (PRODUCT, "VENDOR NO", DESCRIPTION, "CORE FLAG (Y)", "REPL COST",
             "BASE PRICE", "LIST PRICE", LENGTH, WIDTH, HEIGHT, WEIGHT,
             "BRAND CODE", "PRODUCT CAT", "WEBSITE CAT", PRODLINE, SEASONAL, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product_dict['PRODUCT'],
            product_dict['VENDOR NO'],
            product_dict['DESCRIPTION'],
            product_dict.get('CORE FLAG (Y)', ''),
            product_dict['REPL COST'],
            product_dict.get('BASE PRICE'),
            product_dict.get('LIST PRICE'),
            product_dict.get('LENGTH', 1),
            product_dict.get('WIDTH', 1),
            product_dict.get('HEIGHT', 1),
            product_dict.get('WEIGHT', 1),
            product_dict.get('BRAND CODE'),
            product_dict.get('PRODUCT CAT'),
            product_dict.get('WEBSITE CAT'),
            product_dict.get('PRODLINE'),
            product_dict.get('SEASONAL'),
            now
        ))
        
        self.conn.commit()
    
    def get_staging_data(self):
        """Get all data from staging table"""
        return pd.read_sql_query('SELECT * FROM rawicswdata', self.conn)
    
    def clear_staging(self):
        """Clear staging table"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM rawicswdata')
        self.conn.commit()
    
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