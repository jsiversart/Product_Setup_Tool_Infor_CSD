# app/step2_processor.py
import pandas as pd
import sqlite3
from datetime import datetime
import os

def process_step2(db, output_folder):
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
WITH PRICING AS 
(SELECT PRODUCT as prod, 
CASE
	WHEN PRODLINE like '%CORE' THEN "REPL COST"
	WHEN "REPL COST" < 1.5 THEN ROUND("REPL COST"*p."B-0.01-1.49",2)
	WHEN "REPL COST" < 5 THEN ROUND("REPL COST"*p."B-1.5-4.99",2)
	WHEN "REPL COST" < 50 THEN ROUND("REPL COST"*p."B-5-49.99",2)
	WHEN "REPL COST" < 75 THEN ROUND("REPL COST"*p."B-50-74.99",2)
	WHEN "REPL COST" < 100 THEN ROUND("REPL COST"*p."B-75-99.99",2)
	WHEN "REPL COST" < 500 THEN ROUND("REPL COST"*p."B-100-499.99",2)
	WHEN "REPL COST" < 1000 THEN ROUND("REPL COST"*p."B-500-999.99",2)
	ELSE ROUND("REPL COST"*p."B-1000-999999",2)
END AS baseprice,
CASE
	WHEN PRODLINE like '%CORE' THEN "REPL COST"
	WHEN "REPL COST" < 5 THEN ROUND("REPL COST"*p."L-0.01-4.99",2)
	WHEN "REPL COST" < 50 THEN ROUND("REPL COST"*p."L-5-49.99.1",2)
	WHEN "REPL COST" < 75 THEN ROUND("REPL COST"*p."L-50-74.99.1",2)
	ELSE ROUND("REPL COST"*p."L-75-99999",2)
	END AS listprice,
	"Vendor List Handling" as vendlisthandling
	from rawicswdata r 
	LEFT JOIN pricing_map p ON 
		CASE WHEN r."VENDOR NO" in (select distinct vendor from pricing_map) THEN p.Vendor = r."VENDOR NO"
		ELSE p.Vendor = 'Standard' END)
SELECT
PRODUCT AS prod,
printf('%02d', warehouse) AS whse,
strftime('%m/%d', CURRENT_DATE) || '/' || substr(strftime('%Y', CURRENT_DATE), 3, 2) AS enterdt,
'O' AS statustype,
'' AS serlottype,
'' AS snpocd,
'' AS reservety,
'' AS reservedays,
'' AS prodpreference,
'DEAL' AS pricetype,
p.baseprice AS baseprice,
CASE
	WHEN PRODLINE like '%CORE' THEN p.listprice
	WHEN p.vendlisthandling is NULL then p.listprice
	WHEN p.vendlisthandling = 'list_or_base1.1' then
		CASE
			WHEN r."LIST PRICE" is null THEN p.listprice
			WHEN r."LIST PRICE" < p.baseprice THEN p.baseprice*1.1
			ELSE r."LIST PRICE"
		END
	WHEN p.vendlisthandling = 'take_min' THEN 
		CASE WHEN r."LIST PRICE" is null THEN p.listprice
			ELSE MIN(r."LIST PRICE",p.listprice)
		END
	ELSE 'UNKNOWN LIST HANDLING!'
END AS listprice,
'' AS smanalfl,
'' AS autofillfl,
'' AS boshortfl,
'' AS countfl,
CASE 
	WHEN w.Type = 'D' THEN 'V'
	ELSE 'W'
END AS arptype,
'' AS arppushfl,
r."VENDOR NO" AS arpvendno,
CAST(
    CASE 
        WHEN w.Arpwhse IS NULL OR TRIM(w.Arpwhse) = '' THEN NULL
        ELSE w.Arpwhse
    END 
AS INT) AS arpwhse,
r.PRODLINE AS prodline,
'' AS vendprod,
'' AS famgrptype,
'' AS ncnr,
'' AS rebatety,
'' AS rebsubty,
'' AS autoesrcbofl,
'' AS binloc1,
'' AS binloc2,
'' AS wmfl,
'' AS wmallocty,
'' AS bintype,
'' AS wmpriority,
'' AS wmrestrict,
'' AS frtfreefl,
'' AS frtextra1,
'' AS frtextra2,
'' AS unitbuy,
'' AS unitconv1,
'' AS unitediuom1,
'' AS unitstnd,
'' AS unitconv2,
'' AS unitediuom2,
'' AS unitwt,
'' AS unitconv3,
'' AS unitediuom3,
'D' AS safeallty,
0 AS safeallamt,
'' AS safetyfrzfl,
'' AS usagerate,
CASE WHEN r.SEASONAL = 'y' THEN 3
	ELSE 6
END AS usgmths,
'yes' AS usmthsfrzfl,
CASE WHEN r.SEASONAL = 'y' THEN 'f'
	ELSE 'b'
END AS usagectrl,
'' AS excludemovefl,
'' AS orderpt,
'' AS linept,
'' AS ordqtyin,
CASE 
	WHEN w.Type = 'D' THEN 'E'
	ELSE 'M'
END AS ordcalcty,
'' AS ordptadjty,
'' AS overreasin,
'' AS surplusty,
'' AS inclunavqty,
'' AS rolloanusagefl,
'' AS companyrank,
'' AS whserank,
'' AS rankfreezefl,
'' AS threshrefer,
'' AS minthreshold,
'' AS minthreshexpdt,
'' AS asqfl,
'' AS asqdifffl,
'' AS asqdiff,
'' AS hi5fl,
'' AS hi5difffl,
'' AS hi5diff,
CASE 
	WHEN w.Type = 'D' THEN 21
	ELSE 2
END AS leadtmavg,
'' AS avgltdt,
'' AS leadtmlast,
'' AS lastltdt,
'' AS leadtmprio,
'' AS priorltdt,
999 AS frozenltty,
'' AS class,
'' AS classfrzfl,
'' AS abcgmroiclass,
'' AS abcsalesclass,
'' AS abcqtyclass,
'' AS abccustclass,
'' AS abcoverexpdt,
'' AS abcfinalclass,
'' AS abcclassdt,
'' AS seasbegmm,
'' AS seasendmm,
'' AS nodaysseas,
'' AS ordqtyout,
'' AS overreasout,
'' AS seastrendmax,
'' AS seastrendmin,
'' AS seastrendexpdt,
'' AS seastrendtyu,
'' AS seastrendlyu,
'' AS seasonfrzfl,
'' AS taxtype,
1 AS taxgroup,
'V' AS taxablety,
'' AS nontaxtype,
'' AS tariffcd,
'' AS countryoforigin,
'' AS gststatus,
'' AS frozenmmyy,
'' AS frozentype,
'' AS frozenmos,
'' AS acquiredt,
'' AS so15fl,
'' AS lastsodt,
'' AS nodaysso,
'' AS notimesso,
'' AS availsodt,
"REPL COST" AS avgcost,
'' AS lastcost,
"REPL COST" AS replcost,
strftime('%m/%d', CURRENT_DATE) || '/' || substr(strftime('%Y', CURRENT_DATE), 3, 2) AS replcostdt,
'' AS stndcost,
'' AS stndcostdt,
'' AS rebatecost,
'' AS addoncost,
'' AS datccost,
'' AS baseyrcost,
'' AS lastcostfor,
'' AS replcostfor,
'' AS qtyonhand,
'' AS qtyunavail,
'' AS reasunavty,
'' AS custavgcost,
'' AS custlastcost,
'' AS custfixedcost,
'' AS custqtyonhand,
'' AS custqtyonorder,
'' AS custqtyunavail,
'' AS custqtyrcvd,
'' AS custqtyburnoff,
'' AS custavgcostburnoff,
'' AS issueunytd,
'' AS rcptunytd,
'' AS retinunytd,
'' AS retouunytd,
'' AS rpt852dt,
'' AS lastinvdt,
'' AS lastrcptdt,
'' AS lastpowtdt,
'' AS priceupddt,
'' AS lastcntdt,
'' AS slchgdt,
'' AS buyer,
'' AS user1,
'' AS user2,
'' AS user3,
'' AS user4,
'' AS user5,
'' AS user6,
'' AS user7,
'' AS user8,
'' AS user9,
'' AS user10,
'' AS user11,
'' AS user12,
'' AS user13,
'' AS user14,
'' AS user15,
'' AS user16,
'' AS user17,
'' AS user18,
'' AS user19,
'' AS user20,
'' AS user21,
'' AS user22,
'' AS user23,
'' AS user24,
'' AS boxqty,
'' AS caseqty,
'' AS palletqty,
'' AS whzone,
'' AS bincntr,
'' AS kitbuild,
'' AS srcommcode1,
'' AS srcommcode2,
'' AS srmachine,
'' AS srunitcnt,
'' AS unitconv4,
'' AS unitediuom4,
'' AS regrindfl,
'' AS laborprod,
'' AS linkedprod,
'' AS billonrcptfl,
'' AS custonlyfl,
'' AS rcvunavailfl,
'' AS criticalfl,
'' AS shelflifefl,
'' AS edi852statuschgfl,
'' AS suppwarrallowfl,
'' AS recalcprodcostinv,
'' AS recalcommcostinv,
'' AS cutminlength,
'' AS cutminty,
'' AS cutminoutput
from rawicswdata r
cross join warehouse_info w
left join PRICING p on p.prod = r.PRODUCT
WHERE w.active = 1
ORDER BY
    CASE warehouse
        WHEN 25 THEN 1
        WHEN 50 THEN 2
        ELSE 3
    END,
    CASE 
        WHEN PRODUCT LIKE 'IC%' THEN 1
        WHEN PRODUCT LIKE 'DC%' THEN 2
        ELSE 3
    END;
"""
        
        log_messages.append("✓ Executing warehouse query...")
        
        # Execute query
        result_df = pd.read_sql_query(query, db.conn)
        
        # Convert integer columns
        int_cols = ["arpwhse", "arpvendno", "leadtmavg", "usgmths"]
        for c in int_cols:
            if c in result_df.columns:
                result_df[c] = result_df[c].astype("Int64")
        
        log_messages.append(f"✓ Generated {len(result_df)} warehouse records")
        
        # Export to CSV
        result_df.to_csv(output_path, index=False)
        log_messages.append(f"✓ Step 2 output saved: {output_filename}")
        
        return output_path, log_messages
        
    except Exception as e:
        log_messages.append(f"✗ Error in Step 2 processing: {str(e)}")
        return None, log_messages