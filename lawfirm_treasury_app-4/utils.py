"""Shared helpers: data loading, filters, formatting, and the pastel dashboard theme."""
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"

# ---------------------------------------------------------------- pastel theme
PALETTE = ["#6EC6E8", "#5DCAA5", "#F2A6B0", "#F7C873", "#A6B6E8", "#8FD8C6"]
ACCENT = "#5DCAA5"
DANGER = "#E2745B"


def inject_theme():
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #EAF6FB 0%, #F5FBFD 55%, #FDFEFF 100%);
        }
        section[data-testid="stSidebar"] {
            background: #E4F3FA;
        }
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border-radius: 16px;
            padding: 14px 18px 10px 18px;
            box-shadow: 0 6px 18px rgba(110, 198, 232, 0.18);
            border: 1px solid #E4F3FA;
        }
        .kpi-card {
            background: #FFFFFF;
            border-radius: 16px;
            padding: 16px 18px;
            box-shadow: 0 6px 18px rgba(110, 198, 232, 0.18);
            border: 1px solid #E4F3FA;
            margin-bottom: 14px;
        }
        .kpi-title { color: #7A8A99; font-size: 0.85rem; margin-bottom: 4px; }
        .kpi-row { display: flex; align-items: center; justify-content: space-between; }
        .kpi-value { font-size: 1.7rem; font-weight: 700; color: #1F3B4D; }
        .kpi-delta-up { color: #2FAE7C; font-size: 0.82rem; margin-top: 4px; }
        .kpi-delta-down { color: #E2745B; font-size: 0.82rem; margin-top: 4px; }
        .insight-card {
            background: #FFFFFF;
            border-radius: 16px;
            padding: 18px 20px;
            box-shadow: 0 6px 18px rgba(110, 198, 232, 0.18);
            border: 1px solid #E4F3FA;
            margin-bottom: 14px;
        }
        .insight-label { color: #7A8A99; font-size: 0.82rem; margin-bottom: 2px; }
        .insight-value { color: #2E88B0; font-size: 1.15rem; font-weight: 700; margin-bottom: 4px; }
        .insight-detail { color: #4A5A68; font-size: 0.85rem; }
        .stTabs [data-baseweb="tab"] {
            background-color: #FFFFFF;
            border-radius: 999px;
            padding: 6px 18px;
            margin-right: 6px;
            border: 1px solid #E4F3FA;
        }
        .stTabs [aria-selected="true"] {
            background-color: #CDECF7 !important;
            color: #1F3B4D !important;
        }
        h1, h2, h3 { color: #1F3B4D; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def svg_sparkline(values, color=ACCENT, width=90, height=30):
    """Tiny inline SVG sparkline, no external deps."""
    values = list(values)
    if len(values) < 2:
        values = values * 2
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    pad = 3
    xs = np.linspace(pad, width - pad, len(values))
    ys = [height - pad - (v - lo) / span * (height - 2 * pad) for v in values]
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{points}"/>'
        f'</svg>'
    )


def kpi_card(title, value, spark_values, delta_pct=None, spark_color=ACCENT):
    up = delta_pct is not None and delta_pct >= 0
    delta_html = ""
    if delta_pct is not None:
        sign = "+" if up else "-"
        cls = "kpi-delta-up" if up else "kpi-delta-down"
        delta_html = f'<div class="{cls}">{sign}{abs(delta_pct):.2f}% vs PY</div>'
    spark = svg_sparkline(spark_values, color=spark_color)
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-row">
                <span class="kpi-value">{value}</span>
                <span>{spark}</span>
            </div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def insight_card(label, value, detail):
    st.markdown(
        f"""
        <div class="insight-card">
            <div class="insight-label">{label}</div>
            <div class="insight-value">{value}</div>
            <div class="insight-detail">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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


def top_slicers(data, key_prefix=""):
    """Horizontal slicer bar for the Power BI-style home dashboard."""
    locs = ["All"] + sorted(data["locations"]["location_name"].unique().tolist())
    mtypes = ["All"] + sorted(data["matters"]["matter_type"].unique().tolist())
    statuses = ["All"] + sorted(data["matters"]["status"].unique().tolist())
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        loc = st.selectbox("Location", locs, key=f"{key_prefix}_loc")
    with c2:
        mtype = st.selectbox("Practice area", mtypes, key=f"{key_prefix}_mtype")
    with c3:
        status = st.selectbox("Matter status", statuses, key=f"{key_prefix}_status")
    with c4:
        date_range = st.date_input(
            "Date range",
            value=(pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")),
            key=f"{key_prefix}_dates",
        )
    return loc, mtype, status, date_range


def filter_matters_table(matters, loc, mtype, status, date_range):
    m = matters.copy()
    if loc != "All":
        m = m[m.location_name == loc]
    if mtype != "All":
        m = m[m.matter_type == mtype]
    if status != "All":
        m = m[m.status == status]
    if len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        m = m[(m.open_date >= start) & (m.open_date <= end)]
    return m


def filter_by_matters(df, filtered_matters, date_range, date_col="date"):
    """Filter a transaction-level df (with matter_id) to only rows for the given filtered matters set,
    then clip to the date range on its own date column."""
    out = df[df.matter_id.isin(filtered_matters.matter_id)] if "matter_id" in df.columns else df.copy()
    if len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        out = out[(out[date_col] >= start) & (out[date_col] <= end)]
    return out


def monthly_series(df, date_col, value_col, agg="sum"):
    d = df.copy()
    if not len(d):
        return pd.Series([0, 0])
    d["month"] = d[date_col].dt.to_period("M").dt.to_timestamp()
    s = d.groupby("month")[value_col].agg(agg).sort_index()
    return s if len(s) >= 2 else pd.Series(list(s.values) * 2)


def yoy_delta(df, date_col, value_col, agg="sum"):
    if not len(df):
        return None
    d = df.copy()
    d["year"] = d[date_col].dt.year
    g = d.groupby("year")[value_col].agg(agg)
    if 2024 in g.index and 2025 in g.index and g[2024] != 0:
        return (g[2025] - g[2024]) / abs(g[2024]) * 100
    return None


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
