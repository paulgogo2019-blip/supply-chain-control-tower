# ══════════════════════════════════════════════════ 
# DuckDB SQL Queries — SAP Edition 
# ══════════════════════════════════════════════════ 
import duckdb, boto3, pandas as pd, io 
import streamlit as st

# Secure credentials loaded dynamically from Streamlit Secrets
BUCKET     = st.secrets["BUCKET_NAME"]
ACCESS_KEY = st.secrets["AWS_ACCESS_KEY_ID"]
SECRET_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
REGION     = st.secrets["AWS_REGION"]

s3 = boto3.client( 
    's3', 
    region_name           = REGION, 
    aws_access_key_id     = ACCESS_KEY, 
    aws_secret_access_key = SECRET_KEY
) 

def load(key): 
    obj = s3.get_object(Bucket=BUCKET, Key=key) 
    return pd.read_csv(io.BytesIO(obj['Body'].read())) 

results   = load('gold/inventory_metrics/latest_results.csv') 
carriers  = load('gold/supplier_metrics/carrier_scorecard.csv') 
suppliers = load('gold/supplier_metrics/supplier_scorecard.csv') 
abc_xyz   = load('gold/inventory_metrics/abc_xyz.csv') 

con = duckdb.connect() 
con.register('results',   results) 
con.register('carriers',  carriers) 
con.register('suppliers', suppliers) 
con.register('abc_xyz',   abc_xyz) 

# Q1: SAP Inventory Health Summary 
print("\n[Q1] SAP Inventory Health") 
print(con.execute(""" 
SELECT 
Action_Required, 
COUNT(*)                         AS sku_count, 
SUM(Current_Stock)             AS total_avail, 
SUM(Backorder_Qty)             AS total_backorder, 
SUM(Short_Qty)                 AS total_short, 
SUM(Unavailable_Qty)           AS total_unavail, 
ROUND(SUM(Inventory_Value), 0) AS total_value 
FROM results 
GROUP BY Action_Required 
ORDER BY 
CASE Action_Required 
WHEN 'URGENT: STOCKOUT'         THEN 1 
WHEN 'ORDER NOW'                THEN 2 
WHEN 'ALLOCATION SHORTAGE'      THEN 3 
WHEN 'APPROACHING ROP'          THEN 4 
WHEN 'OVERSTOCK: REDUCE ORDERS' THEN 5 
ELSE 6 
END 
""").df().to_string(index=False)) 

# Q2: Backorder Analysis 
print("\n[Q2] Active Backorders & Shortages") 
print(con.execute(""" 
SELECT 
SKU, Segment, Supplier_Name, 
Current_Stock, Backorder_Qty, 
Short_Qty, Unavailable_Qty, 
Forecast_M1, Avg_Lead_Time, MOQ 
FROM results 
WHERE Backorder_Qty > 0 
OR Short_Qty     > 0 
ORDER BY Backorder_Qty DESC 
LIMIT 20 
""").df().to_string(index=False)) 

# Q3: Supplier Scorecard 
print("\n[Q3] Supplier Performance") 
print(con.execute(""" 
SELECT 
Supplier_ID, Supplier_Name, 
COUNT(*)                        AS sku_count, 
ROUND(AVG(Lead_Time_Days), 1)  AS avg_lead_days, 
ROUND(AVG(OTD_Rate_Pct), 1)    AS avg_otd_pct, 
ROUND(AVG(Quality_Score), 2)   AS avg_quality, 
ROUND(AVG(Unit_Cost), 2)       AS avg_unit_cost, 
MIN(Lead_Time_Days)            AS min_lt, 
MAX(Lead_Time_Days)            AS max_lt 
FROM suppliers 
GROUP BY Supplier_ID, Supplier_Name 
ORDER BY avg_otd_pct DESC 
""").df().to_string(index=False)) 

# Q4: Carrier Performance 
print("\n[Q4] Carrier OTD Performance") 
print(con.execute(""" 
SELECT 
Carrier_Name, 
Total_Loads, 
ROUND(OTD_Rate * 100, 1)       AS otd_pct, 
ROUND(Avg_Lead_Time, 1)        AS avg_lead_days, 
Weather_Delays, 
Op_Delays, 
Capacity_Shortages, 
Expedited_Count, 
ROUND(Avg_Delay_Days, 1)       AS avg_delay_days, 
Carrier_Grade 
FROM carriers 
ORDER BY OTD_Rate DESC 
""").df().to_string(index=False)) 

# Q5: ABC-XYZ with SAP metrics 
print("\n[Q5] ABC-XYZ Segment Summary") 
print(con.execute(""" 
SELECT 
r.Segment, 
COUNT(*)                        AS sku_count, 
ROUND(SUM(r.Inventory_Value),0) AS total_value, 
ROUND(AVG(r.MAPE_pct), 1)       AS avg_mape, 
ROUND(AVG(r.Fill_Rate_pct), 1)  AS avg_fill_rate, 
SUM(r.Backorder_Qty)            AS total_backorder, 
SUM(r.Short_Qty)                AS total_short, 
SUM(r.Stockout_Days_History)    AS total_so_days, 
ROUND(AVG(r.Gross_Margin_pct),1)AS avg_margin 
FROM results r 
GROUP BY r.Segment 
ORDER BY r.Segment 
""").df().to_string(index=False)) 

# Q6: Gross Margin Analysis 
print("\n[Q6] Top 10 SKUs by Gross Margin") 
print(con.execute(""" 
SELECT 
SKU, Segment, Supplier_Name, 
Unit_Cost, 
Unit_Selling_Price, 
Gross_Margin_pct, 
Forecast_Monthly_Demand, 
ROUND(Forecast_Monthly_Demand * (Unit_Selling_Price - Unit_Cost), 0) AS monthly_profit, 
Action_Required 
FROM results 
ORDER BY Gross_Margin_pct DESC 
LIMIT 10 
""").df().to_string(index=False)) 

# Q7: Excess and Dead Stock 
print("\n[Q7] Excess and Dead Stock") 
print(con.execute(""" 
SELECT 
SKU, Segment, Supplier_Name, 
Current_Stock, Max_Stock, 
Excess_Units, 
ROUND(Excess_Value, 0)         AS excess_value, 
Unavailable_Qty, 
Dead_Stock_Flag, 
Avg_Lead_Time 
FROM results 
WHERE Excess_Value > 0 
OR Dead_Stock_Flag = 'YES' 
ORDER BY Excess_Value DESC 
LIMIT 15 
""").df().to_string(index=False)) 

# Q8: Forecast Accuracy by Model 
print("\n[Q8] Forecast Accuracy by Model") 
print(con.execute(""" 
SELECT 
Best_Model, 
COUNT(*)                                                        AS sku_count, 
ROUND(AVG(MAPE_pct), 1)                                         AS avg_mape, 
ROUND(MIN(MAPE_pct), 1)                                         AS best_mape, 
ROUND(MAX(MAPE_pct), 1)                                         AS worst_mape, 
SUM(CASE WHEN Accuracy_Grade = 'EXCELLENT' THEN 1 ELSE 0 END)   AS excellent_count, 
SUM(CASE WHEN Accuracy_Grade = 'POOR' THEN 1 ELSE 0 END)        AS poor_count 
FROM results 
GROUP BY Best_Model 
ORDER BY avg_mape ASC 
""").df().to_string(index=False)) 

# Q9: Chronic Stockout Risk 
print("\n[Q9] Chronic Stockout Risk SKUs") 
print(con.execute(""" 
SELECT 
SKU, Segment, Supplier_Name, 
Stockout_Days_History, 
Current_Stock, ROP, 
Safety_Stock, Forecast_M1, 
Avg_Lead_Time, MOQ, 
Action_Required 
FROM results 
WHERE Stockout_Days_History > 3 
ORDER BY Stockout_Days_History DESC 
LIMIT 15 
""").df().to_string(index=False)) 

# Q10: Promotion Impact 
print("\n[Q10] Promotion Impact on Demand") 
print(con.execute(""" 
SELECT 
SKU, Segment, 
Promo_Days, 
Forecast_Monthly_Demand, 
Forecast_M1, 
MAPE_pct, 
Action_Required 
FROM results 
WHERE Promo_Days > 0 
ORDER BY Promo_Days DESC 
LIMIT 15 
""").df().to_string(index=False)) 

print("\nAll queries complete")