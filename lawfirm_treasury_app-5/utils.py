"""Shared helpers: data loading, filters, formatting, and the pastel dashboard theme.

Filtering convention
--------------------
Every transaction-level table either:
  (a) belongs to a specific matter (matter_id set) - filtered by looking up that matter's
      location / practice area / status, or
  (b) is a firm-level row with no matter (e.g. firm overhead expenses, non-disbursement card
      charges) - it still carries its own location_id, but has no practice area or matter status
      of its own.
`filter_transactions` is the single function used everywhere to apply the location / practice
area / matter status / date slicers correctly to both kinds of row. Older per-page workarounds
that tried to patch this by hand have been removed in favour of this one function.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"

# ---------------------------------------------------------------- pastel theme
PALETTE = ["#6EC6E8", "#5DCAA5", "#F2A6B0", "#F7C873", "#A6B6E8", "#8FD8C6"]
ACCENT = "#5DCAA5"
GOOD = "#2FAE7C"
BAD = "#E2745B"


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
            min-height: 108px;
        }
        .kpi-title { color: #7A8A99; font-size: 0.85rem; margin-bottom: 4px; }
        .kpi-row { display: flex; align-items: center; justify-content: space-between; }
        .kpi-value { font-size: 1.7rem; font-weight: 700; color: #1F3B4D; }
        .kpi-delta-up { color: #2FAE7C; font-size: 0.82rem; margin-top: 4px; }
        .kpi-delta-down { color: #E2745B; font-size: 0.82rem; margin-top: 4px; }
        .kpi-delta-flat { color: #9AA7B2; font-size: 0.82rem; margin-top: 4px; }
        .insight-card {
            background: #FFFFFF;
            border-radius: 16px;
            padding: 18px 20px;
            box-shadow: 0 6px 18px rgba(110, 198, 232, 0.18);
            border: 1px solid #E4F3FA;
            margin-bottom: 14px;
            min-height: 108px;
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
    values = [float(v) for v in values]
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


def kpi_card(title, value, spark_values, delta_pct=None, spark_color=ACCENT, invert_color=False):
    """Render one KPI card.

    delta_pct is the signed percentage change (can be negative). invert_color=True means an
    increase is UNFAVOURABLE (e.g. expenses, disbursements, merchant fees) so the colour (not
    the sign) flips: a positive delta shows in red, a negative delta shows in green. The sign
    printed always matches the arithmetic sign of delta_pct.
    """
    delta_html = ""
    if delta_pct is not None:
        rising = delta_pct >= 0
        sign = "+" if rising else "-"
        favourable = rising if not invert_color else not rising
        if abs(delta_pct) < 0.005:
            cls = "kpi-delta-flat"
        else:
            cls = "kpi-delta-up" if favourable else "kpi-delta-down"
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
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "$0"
    return f"${x:,.0f}"


def sidebar_filters(data, key_prefix=""):
    """Sidebar slicers used on every detail page: location, practice area, matter status, date."""
    locs = ["All"] + sorted(data["locations"]["location_name"].unique().tolist())
    mtypes = ["All"] + sorted(data["matters"]["matter_type"].unique().tolist())
    statuses = ["All"] + sorted(data["matters"]["status"].unique().tolist())
    loc = st.sidebar.selectbox("Location", locs, key=f"{key_prefix}_loc")
    mtype = st.sidebar.selectbox("Practice area", mtypes, key=f"{key_prefix}_mtype")
    status = st.sidebar.selectbox("Matter status", statuses, key=f"{key_prefix}_status")
    date_range = st.sidebar.date_input(
        "Date range",
        value=(pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")),
        key=f"{key_prefix}_dates",
    )
    return loc, mtype, status, date_range


def top_slicers(data, key_prefix=""):
    """Horizontal slicer bar for the Power BI-style home dashboard. Same fields as sidebar_filters."""
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


def filter_matters(matters, loc, mtype, status, date_range):
    """Filter the matters table itself by location / practice area / status / open date."""
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


def filter_transactions(df, matters_all, loc, mtype, status, date_range, date_col="date"):
    """The single filtering function for every transaction-level table.

    Correctly keeps firm-level rows (matter_id is null) whenever no practice-area or matter-status
    slicer is active, filtering them only by their own location_id and date. Matter-linked rows are
    filtered by looking up the matching matters. Without this split, every firm-level row (overhead
    expenses, non-disbursement card charges) would be silently dropped under any filter, including
    the default "All" view.
    """
    df = df.copy()
    if len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        df = df[(df[date_col] >= start) & (df[date_col] <= end)]

    if "matter_id" not in df.columns:
        return df

    m = matters_all.copy()
    if loc != "All":
        m = m[m.location_name == loc]
    if mtype != "All":
        m = m[m.matter_type == mtype]
    if status != "All":
        m = m[m.status == status]

    linked = df[df.matter_id.notna()]
    linked_f = linked[linked.matter_id.isin(m.matter_id)]

    if mtype != "All" or status != "All":
        # firm-level rows have no practice area or matter status of their own
        return linked_f

    unlinked = df[df.matter_id.isna()]
    if loc != "All" and "location_id" in unlinked.columns:
        loc_ids = matters_all.loc[matters_all.location_name == loc, "location_id"].unique()
        unlinked = unlinked[unlinked.location_id.isin(loc_ids)]

    return pd.concat([linked_f, unlinked]).sort_index()


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


def flow_kpi(df, date_col, value_col, title, spark_color=ACCENT, magnitude=False,
             invert_color=False, agg="sum"):
    """Build and render one KPI card for a signed money flow, handling sign consistently.

    magnitude=True takes the absolute value before totalling/charting (use this whenever the
    underlying ledger amount is negative, e.g. expenses or disbursements, so the KPI displays a
    positive number). invert_color controls colour only: True means a rising value is shown in
    red (unfavourable, e.g. expenses, merchant fees); False means rising is green (favourable,
    e.g. revenue, deposits, billed amounts). These are independent - a disbursement is both a
    magnitude flip and colour-inverted; a "transferred to office" amount is a magnitude flip but
    NOT colour-inverted, since more billing is good news even though the trust-ledger amount is
    negative.
    """
    d = df.copy()
    if magnitude and len(d):
        d[value_col] = d[value_col].abs()
    total = d[value_col].agg(agg) if len(d) else 0
    spark = monthly_series(d, date_col, value_col, agg).values
    delta = yoy_delta(d, date_col, value_col, agg)
    kpi_card(title, money(total), spark, delta, spark_color=spark_color, invert_color=invert_color)
