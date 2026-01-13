
# process_step1# app/step1_processor.py
import pandas as pd
import sqlite3
from datetime import datetime
import os

def process_step1(db, output_folder):
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
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(1) FROM pricing_map")
        if cursor.fetchone()[0] == 0:
            raise Exception("pricing_map table is empty. Please upload pricing rules first.")
        
        log_messages.append("✓ Pricing map verified")
        
        # Main query - exactly as in your script
        query = """
        SELECT * FROM {db}"""
        
        log_messages.append("✓ Executing warehouse query...")
        
        # Execute query
        result_df = pd.read_sql_query(query, db.conn)
        
        # Convert integer columns
        int_cols = ["arpwhse", "arpvendno", "leadtmavg", "usgmths"]
        for c in int_cols:
            if c in result_df.columns:
                result_df[c] = result_df[c].astype("Int64")
        
        log_messages.append(f"✓ Generated {len(result_df)} product records")
        
        # Export to CSV
        result_df.to_csv(output_path, index=False)
        log_messages.append(f"✓ Step 1 output saved: {output_filename}")
        
        return output_path, log_messages
        
    except Exception as e:
        log_messages.append(f"✗ Error in Step 1 processing: {str(e)}")
        return None, log_messages