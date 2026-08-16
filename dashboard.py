# ══════════════════════════════════════════════════
# Supply Chain Control Tower — Streamlit Dashboard
# SAP-Format Data Edition
# Run: streamlit run dashboard.py
# ══════════════════════════════════════════════════
import streamlit as st
import pandas as pd
import numpy as np
import boto3
import io
import json
from datetime import datetime

st.set_page_config(
    page_title = "Supply Chain Control Tower",
    page_icon  = "      ",
    layout     = "wide"
)

@st.cache_resource
def get_s3():
    return boto3.client(
        's3',
        region_name           = st.secrets.get("AWS_REGION", "us-east-1"),
        aws_access_key_id     = st.secrets.get("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key = st.secrets.get("AWS_SECRET_ACCESS_KEY", "")
    )

BUCKET = st.secrets.get("BUCKET_NAME", "sc-control-tower-ogola")

@st.cache_data(ttl=3600)
def load_csv(key):
    try:
        s3  = get_s3()
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        return pd.read_csv(io.BytesIO(obj['Body'].read()))
    except Exception as e:
        st.error(f"Cannot load {key}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_kpi():
    try:
        s3  = get_s3()
        pag = s3.get_paginator('list_objects_v2')
        pages = pag.paginate(Bucket=BUCKET, Prefix='gold/alerts/kpi_summary_')
        keys = []
        for page in pages:
            if 'Contents' in page:
                keys.extend([o['Key'] for o in page['Contents'] if o['Key'].endswith('.json')])
        if not keys:
            return {}
        obj = s3.get_object(Bucket=BUCKET, Key=sorted(keys)[-1])
        return json.loads(obj['Body'].read())
    except Exception:
        return {}

# ── MAIN APP ──────────────────────────────────────
st.title("Supply Chain Control Tower")
st.caption(f"SAP Edition | Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

with st.sidebar:
    st.header("Filters")
    st.button("Refresh", on_click=st.cache_data.clear)

with st.spinner("Loading from S3..."):
    results_df   = load_csv('gold/inventory_metrics/latest_results.csv')
    carriers_df  = load_csv('gold/supplier_metrics/carrier_scorecard.csv')
    suppliers_df = load_csv('gold/supplier_metrics/supplier_scorecard.csv')
    kpi          = load_kpi()

if results_df.empty:
    st.error("No data. Run Colab notebook first.")
    st.stop()

# Sidebar filters
with st.sidebar:
    seg_filter = st.selectbox("Segment", ['All'] + sorted(results_df['Segment'].dropna().unique().tolist()))
    act_filter = st.selectbox("Action Required", ['All'] + sorted(results_df['Action_Required'].dropna().unique().tolist()))
    sup_filter = st.selectbox("Supplier", ['All'] + sorted(results_df['Supplier_Name'].dropna().unique().tolist()))
    st.divider()
    st.markdown("**SAP Filters**")
    show_bo = st.checkbox("Backorders Only", False)
    show_sh = st.checkbox("Shortages Only", False)

filtered = results_df.copy()
if seg_filter != 'All':
    filtered = filtered[filtered['Segment'] == seg_filter]
if act_filter != 'All':
    filtered = filtered[filtered['Action_Required'] == act_filter]
if sup_filter != 'All':
    filtered = filtered[filtered['Supplier_Name'] == sup_filter]
if show_bo:
    filtered = filtered[filtered['Backorder_Qty'] > 0]
if show_sh:
    filtered = filtered[filtered['Short_Qty'] > 0]

# ── KPI Row ───────────────────────────────────────
st.subheader("Portfolio KPIs")

# Row 1: Stock & Inventory Counts (Updated to use 'filtered')
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total SKUs", len(filtered))
k2.metric("Stockouts", int(len(filtered[filtered['Action_Required'] == 'URGENT: STOCKOUT'])))
k3.metric("Order Now", int(len(filtered[filtered['Action_Required'] == 'ORDER NOW'])))
k4.metric("Backorder Qty", f"{int(filtered['Backorder_Qty'].sum()):,}" if not filtered.empty else "0")

# Row 2: Quantities, Accuracy & Value Metrics (Updated to use 'filtered')
k5, k6, k7, k8 = st.columns(4)
k5.metric("Short Qty", f"{int(filtered['Short_Qty'].sum()):,}" if not filtered.empty else "0")
k6.metric("Avg MAPE", f"{filtered['MAPE_pct'].mean():.1f}%" if not filtered.empty else "0.0%")
k7.metric("Total Inv Value", f"${filtered['Inventory_Value'].sum():,.0f}" if not filtered.empty else "$0")
k8.metric("Avg Gross Margin", f"{filtered['Gross_Margin_pct'].mean():.1f}%" if not filtered.empty else "0.0%")

st.divider()

# ── Tabs ──────────────────────────────────────────
tabs = st.tabs([
    "Alerts",
    "Inventory",
    "Forecasts",
    "Carriers",
    "Suppliers",
    "ABC-XYZ"
])
tab1,tab2,tab3,tab4,tab5,tab6 = tabs

# ── Tab 1: Alerts ─────────────────────────────────
with tab1:
    st.subheader("Exception Dashboard")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Critical — Act Immediately")
        crit = filtered[filtered['Action_Required'].isin(['URGENT: STOCKOUT', 'ORDER NOW'])][[
            'SKU', 'Segment', 'Supplier_Name', 'Current_Stock', 'Backorder_Qty', 'ROP', 'Forecast_M1', 'Action_Required', 'MAPE_pct', 'Avg_Lead_Time', 'MOQ'
        ]]
        if len(crit) > 0:
            st.dataframe(crit, use_container_width=True, height=280)
        else:
            st.success("No critical alerts")

    with c2:
        st.markdown("#### SAP — Backorders & Shortages")
        sap = filtered[(filtered['Backorder_Qty'] > 0) | (filtered['Short_Qty'] > 0)][[
            'SKU', 'Segment', 'Current_Stock', 'Backorder_Qty', 'Short_Qty', 'Unavailable_Qty', 'Allocated_Stock', 'Supplier_Name', 'Action_Required'
        ]]
        if len(sap) > 0:
            st.dataframe(sap, use_container_width=True, height=280)
            st.warning(f"Backorder: {sap['Backorder_Qty'].sum():,} | Short: {sap['Short_Qty'].sum():,}")
        else:
            st.success("No backorders/shortages")

    st.markdown("#### Warnings — Act This Week")
    warn = filtered[filtered['Action_Required'].isin(['APPROACHING ROP', 'OVERSTOCK: REDUCE ORDERS', 'ALLOCATION SHORTAGE'])][[
        'SKU', 'Segment', 'Current_Stock', 'ROP', 'Max_Stock', 'Short_Qty', 'Action_Required', 'Excess_Value'
    ]]
    if len(warn) > 0:
        st.dataframe(warn, use_container_width=True)
    else:
        st.success("No warnings")

    st.markdown("#### Dead Stock")
    dead = filtered[filtered['Dead_Stock_Flag'] == 'YES'][[
        'SKU', 'Segment', 'Current_Stock', 'Unavailable_Qty', 'Backorder_Qty', 'Unit_Cost', 'Inventory_Value', 'Supplier_Name'
    ]]
    if len(dead) > 0:
        st.dataframe(dead, use_container_width=True)
        st.warning(f"Dead stock at risk: ${dead['Inventory_Value'].sum():,.0f}")
    else:
        st.success("No dead stock")

# ── Tab 2: Inventory ──────────────────────────────
with tab2:
    st.subheader("SAP Inventory Position")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Value", f"${filtered['Inventory_Value'].sum():,.0f}" if not filtered.empty else "$0")
    c2.metric("Excess Capital", f"${filtered['Excess_Value'].sum():,.0f}" if not filtered.empty else "$0")
    c3.metric("Avg Days of Supply", f"{filtered['DOS_on_Hand'].mean():.0f}d" if not filtered.empty else "0d")
    c4.metric("Avg Allocation Rate", f"{filtered['Allocation_Rate_pct'].mean():.1f}%" if not filtered.empty else "0.0%")
    cols = [
        'SKU', 'Segment', 'Current_Stock', 'On_Hand_Stock', 'Reserved_Stock', 'Allocated_Stock', 'Backorder_Qty', 'Short_Qty', 'Unavailable_Qty', 'ROP', 'Max_Stock', 'Safety_Stock', 'DOS_on_Hand', 'Inventory_Value', 'Stock_Status', 'Action_Required'
    ]
    ok = [c for c in cols if c in filtered.columns]
    st.dataframe(filtered[ok].sort_values('Action_Required'), use_container_width=True, height=450)
    st.download_button("Download Report", data=filtered.to_csv(index=False), file_name=f"inventory_{datetime.now().strftime('%Y%m%d')}.csv", mime='text/csv')

# ── Tab 3: Forecasts ──────────────────────────────
with tab3:
    st.subheader("Demand Forecasts")
    c1,c2,c3 = st.columns(3)
    c1.metric("Avg MAPE", f"{filtered['MAPE_pct'].mean():.1f}%" if not filtered.empty else "0.0%")
    c2.metric("SKUs MAPE < 15%", len(filtered[filtered['MAPE_pct'] < 15]))
    c3.metric("Avg Gross Margin", f"{filtered['Gross_Margin_pct'].mean():.1f}%" if not filtered.empty else "0.0%")
    st.markdown("#### Model Selection")
    mc = (filtered['Best_Model'].value_counts().reset_index())
    if not mc.empty:
        mc.columns = ['Model', 'SKU_Count']
    st.dataframe(mc, use_container_width=True)
    st.markdown("#### All Forecasts")
    fc = [
        'SKU', 'Segment', 'Best_Model', 'Forecast_M1', 'Forecast_M2', 'Forecast_M3', 'MAPE_pct', 'Accuracy_Grade', 'Stockout_Days_History', 'Promo_Days'
    ]
    fc_ok = [c for c in fc if c in filtered.columns]
    st.dataframe(filtered[fc_ok].sort_values('MAPE_pct'), use_container_width=True, height=400)

# ── Tab 4: Carriers ───────────────────────────────
with tab4:
    st.subheader("Carrier Scorecards")
    if not carriers_df.empty:
        c1,c2,c3 = st.columns(3)
        c1.metric("Overall OTD", f"{carriers_df['OTD_Rate'].mean():.1%}")
        c2.metric("Avg Delay Days", f"{carriers_df['Avg_Delay_Days'].mean():.1f}")
        c3.metric("Total Loads", f"{carriers_df['Total_Loads'].sum():,}")
        cc = [
            'Carrier_Name', 'Total_Loads', 'Avg_Lead_Time', 'Lead_Time_Std', 'OTD_Rate', 'Weather_Delays', 'Op_Delays', 'Avg_Delay_Days', 'Expedited_Count', 'Capacity_Shortages', 'Reliability_Score', 'Carrier_Grade'
        ]
        cc_ok = [c for c in cc if c in carriers_df.columns]
        st.dataframe(carriers_df[cc_ok].sort_values('Reliability_Score', ascending=False), use_container_width=True)
        poor = carriers_df[carriers_df['Carrier_Grade'].isin(['C', 'D'])]
        if len(poor) > 0:
            st.warning(f"{len(poor)} carrier(s) Grade C/D — review contracts")
    else:
        st.info("Carrier data not available yet.")

# ── Tab 5: Suppliers ──────────────────────────────
with tab5:
    st.subheader("Supplier Scorecards")
    if not suppliers_df.empty:
        # Filter suppliers list if supplier filter is active
        sup_filtered = suppliers_df.copy()
        if sup_filter != 'All':
            sup_filtered = sup_filtered[sup_filtered['Supplier_Name'] == sup_filter]
            
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total Suppliers", sup_filtered['Supplier_ID'].nunique())
        c2.metric("Avg Lead Time", f"{sup_filtered['Lead_Time_Days'].mean():.1f}d" if not sup_filtered.empty else "0d")
        c3.metric("Avg OTD Rate", f"{sup_filtered['OTD_Rate_Pct'].mean():.1f}%" if not sup_filtered.empty else "0.0%")
        c4.metric("Avg Quality", f"{sup_filtered['Quality_Score'].mean():.2f}/5" if not sup_filtered.empty else "0/5")
        sc = [
            'SKU', 'Supplier_ID', 'Supplier_Name', 'Lead_Time_Days', 'MOQ', 'Unit_Cost', 'OTD_Rate_Pct', 'Quality_Score', 'Ship_Mode', 'Status', 'Supplier_Score', 'Num_Suppliers'
        ]
        sc_ok = [c for c in sc if c in sup_filtered.columns]
        st.dataframe(sup_filtered[sc_ok].sort_values('Supplier_Score', ascending=False), use_container_width=True)
        ur = sup_filtered[sup_filtered['Status'] == 'Under Review']
        if len(ur) > 0:
            st.warning(f"{ur['Supplier_ID'].nunique()} supplier(s) Under Review — affects {len(ur)} SKUs")
    else:
        st.info("Supplier data not available yet.")

# ── Tab 6: ABC-XYZ ────────────────────────────────
with tab6:
    st.subheader("ABC-XYZ Inventory Segmentation")
    if 'Segment' in filtered.columns and not filtered.empty:
        seg_sum = (
            filtered.groupby('Segment').agg(
                SKU_Count        = ('SKU', 'count'),
                Total_Value      = ('Inventory_Value', 'sum'),
                Avg_MAPE         = ('MAPE_pct', 'mean'),
                Avg_Fill_Rate    = ('Fill_Rate_pct', 'mean'),
                Avg_Lead_Time    = ('Avg_Lead_Time', 'mean'),
                Backorder_SKUs   = ('Backorder_Qty', lambda x: (x > 0).sum()),
                Stockout_History = ('Stockout_Days_History', 'sum')
            ).reset_index().sort_values('Segment')
        )
        st.dataframe(seg_sum, use_container_width=True)
    else:
        st.info("No segment data available for current filter selection.")
        
    st.markdown("#### Strategy Recommendations")
    strategy_map = {
        'AX': 'Holt-Winters + Tight Safety Stock',
        'AY': 'Holt-Winters + Higher Safety Stock',
        'AZ': 'Amazon Forecast + Manual Review',
        'BX': 'Simple Exponential Smoothing',
        'BY': 'Exp Smoothing + Safety Stock',
        'BZ': 'Reorder Point + High Safety Stock',
        'CX': 'Min/Max Policy',
        'CY': 'Min/Max with Buffer',
        'CZ': 'Discontinuation or VMI'
    }
    strat_df = pd.DataFrame([
        {'Segment': k, 'Strategy': v}
        for k, v in strategy_map.items()
    ])
    st.dataframe(strat_df, use_container_width=True)