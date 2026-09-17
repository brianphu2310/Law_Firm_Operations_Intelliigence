"""Shared helpers: data loading, filters, formatting."""
from pathlib import Path
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"


@st.cache_data
def load_all():
    locations = pd.read_csv(DATA / "locations.csv")
    clients = pd.read_csv(DATA / "clients.csv")
    counsel = pd.read_csv(DATA / "counsel.csv")
    matters = pd.read_csv(DATA / "matters.csv", parse_dates=["open_date", "close_date"])
    trust = pd.read_csv(DATA / "trust_transactions.csv", parse_dates=["date"])
    office = pd.read_csv(DATA / "office_transactions.csv", parse_dates=["date"])
    cards = pd.read_csv(DATA / "credit_card_transactions.csv", parse_dates=["date"])
    infotrack = pd.read_csv(DATA / "infotrack_transactions.csv", parse_dates=["date"])
    rapidpay = pd.read_csv(DATA / "rapidpay_transactions.csv", parse_dates=["date"])
    commbiz = pd.read_csv(DATA / "commbiz_reconciliation.csv", parse_dates=["period_end"])
    commission = pd.read_csv(DATA / "commission.csv", parse_dates=["date"])

    matters = matters.merge(locations, on="location_id", how="left")
    matters = matters.merge(clients[["client_id", "client_name", "client_type"]], on="client_id", how="left")

    return {
        "locations": locations, "clients": clients, "counsel": counsel, "matters": matters,
        "trust": trust, "office": office, "cards": cards, "infotrack": infotrack,
        "rapidpay": rapidpay, "commbiz": commbiz, "commission": commission,
    }


def money(x):
    return f"${x:,.0f}"


def sidebar_filters(data, key_prefix=""):
    locs = ["All"] + sorted(data["locations"]["location_name"].unique().tolist())
    mtypes = ["All"] + sorted(data["matters"]["matter_type"].unique().tolist())
    loc = st.sidebar.selectbox("Location", locs, key=f"{key_prefix}_loc")
    mtype = st.sidebar.selectbox("Matter type", mtypes, key=f"{key_prefix}_mtype")
    date_range = st.sidebar.date_input(
        "Date range",
        value=(pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")),
        key=f"{key_prefix}_dates",
    )
    return loc, mtype, date_range


def apply_matter_filters(df, matters, loc, mtype, date_range, date_col="date"):
    """Filter a transaction-level df (with matter_id) by location/matter_type/date via matters table."""
    m = matters.copy()
    if loc != "All":
        m = m[m.location_name == loc]
    if mtype != "All":
        m = m[m.matter_type == mtype]
    out = df[df.matter_id.isin(m.matter_id)] if "matter_id" in df.columns else df.copy()
    if len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        out = out[(out[date_col] >= start) & (out[date_col] <= end)]
    return out
