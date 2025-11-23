import requests
import pandas as pd
import streamlit as st
from datetime import datetime

API_BASE = "http://127.0.0.1:8000"

def fetch_expenses():
    res = requests.get(f"{API_BASE}/expenses")
    res.raise_for_status()
    data = res.json()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if "expense_date" in df.columns and df["expense_date"].notna().any():
        df["expense_date"] = pd.to_datetime(df["expense_date"])
    return df
def fetch_summary_by_category(start_date=None, end_date=None):
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    res = requests.get(f"{API_BASE}/expenses/summary/by-category", params=params)
    res.raise_for_status()
    data = res.json()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)


# ---------- Streamlit UI ----------

st.set_page_config(page_title="Currency Expense Tracker", layout="wide")

st.title("💸 Multi-Currency Expense Dashboard")

st.markdown("Data coming from your FastAPI backend + SQLite database.")

# Load data
with st.spinner("Loading expenses from API..."):
    df = fetch_expenses()

if df.empty:
    st.warning("No expenses found yet. Add some via /docs first.")
    st.stop()

# Sidebar filters
st.sidebar.header("Filters")

# Date range filter (based on expense_date)
min_date = df["expense_date"].min()
max_date = df["expense_date"].max()

start_date = st.sidebar.date_input("Start date", value=min_date.date() if pd.notna(min_date) else None)
end_date = st.sidebar.date_input("End date", value=max_date.date() if pd.notna(max_date) else None)

# Category filter
all_categories = sorted(df["category"].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect("Categories", all_categories, default=all_categories)

# Currency filter (original currency)
all_currencies = sorted(df["currency_original"].dropna().unique().tolist())
selected_currencies = st.sidebar.multiselect("Original Currency", all_currencies, default=all_currencies)

# Apply filters to main dataframe
mask = pd.Series([True] * len(df))

if min_date is not None:
    mask &= df["expense_date"].dt.date >= start_date
if max_date is not None:
    mask &= df["expense_date"].dt.date <= end_date

if selected_categories:
    mask &= df["category"].isin(selected_categories)

if selected_currencies:
    mask &= df["currency_original"].isin(selected_currencies)

filtered_df = df[mask].copy()

st.subheader("Filtered Expenses")
st.dataframe(filtered_df)

# Summary metrics
total_base = filtered_df["amount_base"].sum()
st.metric("Total Spend (Base Currency - USD)", f"${total_base:,.2f}")

# Category summary (using your /summary endpoint)
with st.spinner("Loading category summary..."):
    cat_summary_df = fetch_summary_by_category(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat()
    )

st.subheader("Total Spend by Category (USD)")
if not cat_summary_df.empty:
    st.bar_chart(
        cat_summary_df.set_index("category")["total_base_usd"]
    )
else:
    st.info("No summary data available for the selected range.")