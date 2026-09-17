"""
Apex Legal — Operations Dashboard
Streamlit implementation of the Figma design at:
https://www.figma.com/design/v2XzNdUJW2v3tcIcR28sCf/Untitled?node-id=3-4

All numbers below are the SAMPLE DATA that shipped in the Figma design
itself (142 Case Files, Harvey Specter's 184 hrs, the Oct 12 / Oct 15
court dates, etc.) — kept exactly as designed so the layout, colors and
proportions match. Swap `DATA` near the top for a real data source when
ready; the rest of the app reads from it and updates automatically.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------
st.set_page_config(page_title="Apex Legal — Operations", layout="wide",
                    initial_sidebar_state="collapsed")

BG = "#ebf1f6"
CARD = "#ffffff"
BORDER = "#e2e8f0"
TEAL = "#0a8496"
TEAL_TINT = "#ecfeff"
INK = "#0f172a"
MUTED = "#475569"
FAINT = "#94a3b8"
GREEN = "#10b981"
RED = "#ef4444"
AMBER = "#f59e0b"
GREEN_TINT = "#f0fdf4"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class^="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {BG}; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1440px; }}
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; }}

/* top bar */
.topbar {{
    background:{CARD}; border:1px solid {BORDER}; border-radius:24px;
    padding:16px 24px; display:flex; align-items:center; justify-content:space-between;
    margin-bottom: 20px;
}}
.brand {{ display:flex; align-items:center; gap:8px; }}
.brand-badge {{
    background:{TEAL}; width:28px; height:28px; border-radius:8px;
    display:flex; align-items:center; justify-content:center;
    color:#fff; font-weight:800; font-size:16px;
}}
.brand-name {{ font-weight:700; font-size:16px; color:{INK}; }}
.nav-pills {{ display:flex; gap:8px; margin-left:24px; }}
.nav-pill {{ padding:8px 16px; border-radius:99px; font-size:13px; font-weight:500; color:{MUTED}; border:1px solid transparent; }}
.nav-pill.active {{ background:{TEAL_TINT}; border:1px solid {TEAL}; color:{TEAL}; font-weight:600; }}
.nav-left {{ display:flex; align-items:center; }}
.user-row {{ display:flex; align-items:center; gap:10px; }}
.avatar-initials {{
    width:36px; height:36px; border-radius:18px; background:{TEAL};
    color:#fff; font-weight:700; font-size:13px;
    display:flex; align-items:center; justify-content:center; flex-shrink:0;
}}
.user-name {{ font-weight:600; font-size:13px; color:{INK}; }}
.user-role {{ font-size:10px; color:{MUTED}; }}

/* kpi cards */
.kpi-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:16px; padding:16px; height:100%; }}
.kpi-label {{ font-size:12px; font-weight:500; color:{MUTED}; margin-bottom:8px; }}
.kpi-bottom {{ display:flex; align-items:flex-end; justify-content:space-between; gap:8px; }}
.kpi-value {{ font-size:22px; font-weight:700; color:{INK}; white-space:nowrap; }}
.kpi-trend {{ display:flex; align-items:center; gap:4px; margin-top:4px; }}
.kpi-trend .pct {{ font-size:11px; font-weight:600; }}
.kpi-trend .vs {{ font-size:10px; color:{FAINT}; }}

/* generic card */
.card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:20px; padding:20px; height:100%; }}
.card-title {{ font-size:14px; font-weight:600; color:{INK}; margin-bottom:4px; }}
.legend-row {{ display:flex; gap:12px; align-items:center; }}
.legend-item {{ display:flex; gap:6px; align-items:center; font-size:11px; color:{MUTED}; }}
.legend-dot {{ width:8px; height:8px; border-radius:99px; display:inline-block; }}

/* donut */
.donut-center {{ position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center; }}
.donut-center .num {{ font-size:22px; font-weight:700; color:{INK}; line-height:1.1; }}
.donut-center .cap {{ font-size:10px; color:{FAINT}; }}
.donut-legend-item {{ display:flex; gap:6px; align-items:center; font-size:11px; font-weight:600; color:{INK}; margin-bottom:8px; }}

/* insight card */
.insight-kicker {{ font-size:11px; font-weight:600; color:{TEAL}; letter-spacing:0.02em; }}
.insight-headline {{ font-size:14px; font-weight:700; color:{INK}; margin:2px 0; }}
.insight-desc {{ font-size:12px; color:{MUTED}; }}

/* attorney matrix */
table.matrix {{ width:100%; border-collapse:collapse; font-size:12px; }}
table.matrix th {{ background:{BG}; font-weight:600; color:{MUTED}; padding:8px 4px; text-align:center; font-size:11px; }}
table.matrix td {{ border:0.5px solid {BORDER}; height:36px; text-align:center; font-weight:500; color:{INK}; }}
table.matrix td.name {{ text-align:center; font-weight:500; }}
table.matrix td.total {{ background:transparent; }}

/* billing bars */
.bar-row {{ margin-bottom: 14px; }}
.bar-head {{ display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px; }}
.bar-head .lbl {{ color:{MUTED}; }}
.bar-head .val {{ color:{INK}; font-weight:700; }}
.bar-track {{ background:{BG}; height:8px; border-radius:4px; overflow:hidden; }}
.bar-fill {{ height:100%; border-radius:4px; }}

/* deadlines */
.deadline-item {{ display:flex; gap:12px; align-items:center; margin-bottom:14px; }}
.date-badge {{
    width:42px; height:42px; border-radius:10px; display:flex; align-items:center;
    justify-content:center; font-weight:700; font-size:13px; flex-shrink:0;
}}
.deadline-title {{ font-weight:700; font-size:12px; color:{INK}; }}
.deadline-sub {{ font-size:10px; color:{MUTED}; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Data — mirrors the sample data shipped in the Figma design
# ----------------------------------------------------------------------
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

NAV_ITEMS = ["Overview", "Matters", "Clients", "Calendar", "Billing", "Team"]

KPIS = [
    {"label": "Active Matters", "value": "142 Case Files", "pct": 8.3, "up": True,
     "spark": [100, 106, 103, 112, 118, 115, 124, 130, 127, 136, 133, 142]},
    {"label": "Billable Hours (MTD)", "value": "1,840.5 hrs", "pct": 5.1, "up": True,
     "spark": [1550, 1610, 1580, 1660, 1700, 1650, 1720, 1690, 1760, 1730, 1800, 1840]},
    {"label": "Collected Revenue", "value": "$1.48 M", "pct": 12.4, "up": True,
     "spark": [0.95, 1.02, 0.98, 1.10, 1.15, 1.08, 1.20, 1.18, 1.28, 1.32, 1.40, 1.48]},
    {"label": "Utilization Rate", "value": "84.2 %", "pct": -2.1, "up": False,
     "spark": [88, 87, 89, 86, 87, 85, 86, 84, 85, 83, 84, 84.2]},
    {"label": "Upcoming Deadlines", "value": "18 Matters", "pct": 15.3, "up": True,
     "spark": [10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 17, 18]},
]

TREND = pd.DataFrame({
    "month": MONTHS,
    "Litigation": [58, 62, 60, 68, 72, 70, 76, 74, 66, 72, 78, 82],
    "Corporate":  [48, 52, 55, 58, 62, 66, 64, 70, 68, 74, 78, 80],
})

WORKLOAD = {"Corporate": 33, "Litigation": 25, "IP Portfolio": 25, "Employment": 17}
TOTAL_ACTIVE = 142

INSIGHTS = [
    ("TOP BILLING ASSOCIATE", "Harvey Specter, JD", "184 billable hours logged MTD (104% of target)"),
    ("LARGEST RECENT WIN", "Acme Corp vs. Zenith Labs", "Full defense verdict + $2.1M counter-claim won"),
]

PRACTICE_COLS = ["Corporate", "Litigation", "IP Portfolio", "Advisory"]
MATRIX_ROWS = [
    {"name": "Sterling, C.", "vals": [(45, 0.6), (20, 0.1), (80, 0.9), (15, 0.1)], "total": 160},
    {"name": "Specter, H.", "vals": [(10, 0.1), (140, 0.9), (5, 0.1), (25, 0.3)], "total": 180},
    {"name": "Zane, R.", "vals": [(85, 0.9), (40, 0.3), (15, 0.1), (10, 0.1)], "total": 150},
    {"name": "Litt, L.", "vals": [(30, 0.3), (15, 0.1), (95, 0.9), (5, 0.1)], "total": 145},
]

BILLING_BARS = [
    {"label": "Retainer Deposited (Trust)", "value": "$420K", "pct": 76, "color": TEAL},
    {"label": "Work-in-Progress (Unbilled)", "value": "$280K", "pct": 50, "color": "rgba(10,132,150,0.6)"},
    {"label": "Outstanding Invoices", "value": "$110K", "pct": 20, "color": AMBER},
]

DEADLINES = [
    {"date": "Oct 12", "badge_bg": TEAL_TINT, "badge_fg": TEAL,
     "title": "Acme vs. Zenith Trial Brief Filing", "sub": "Appellate Court · Assigned: Zane, R."},
    {"date": "Oct 15", "badge_bg": GREEN_TINT, "badge_fg": GREEN,
     "title": "Global Trust M&A Preliminary Hearing", "sub": "Chancery Court · Assigned: Specter, H."},
]

USER_NAME = "Clara Sterling"
USER_ROLE = "Senior Managing Partner"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def sparkline_svg(values, color, width=60, height=30):
    values = np.asarray(values, dtype=float)
    lo, hi = values.min(), values.max()
    span = (hi - lo) or 1.0
    n = len(values)
    step = width / (n - 1) if n > 1 else width
    pts = []
    for i, v in enumerate(values):
        x = i * step
        y = height - ((v - lo) / span) * height
        pts.append(f"{x:.1f},{y:.1f}")
    points = " ".join(pts)
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def trend_arrow(up):
    color = GREEN if up else RED
    d = "M6 2v8M2.5 6.5 6 10l3.5-3.5" if up else "M6 10V2M2.5 5.5 6 2l3.5 3.5"
    return (f'<svg width="12" height="12" viewBox="0 0 12 12" fill="none">'
            f'<path d="{d}" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def kpi_html(k):
    color = GREEN if k["up"] else RED
    return f"""
    <div class="kpi-card">
      <div class="kpi-label">{k['label']}</div>
      <div class="kpi-bottom">
        <div>
          <div class="kpi-value">{k['value']}</div>
          <div class="kpi-trend">
            {trend_arrow(k['up'])}
            <span class="pct" style="color:{color}">{'+' if k['up'] else ''}{k['pct']}%</span>
            <span class="vs">vs LY</span>
          </div>
        </div>
        {sparkline_svg(k['spark'], TEAL)}
      </div>
    </div>
    """


def plotly_base(height):
    return dict(
        margin=dict(l=8, r=8, t=4, b=4), height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False, font=dict(family="Inter, sans-serif", color=MUTED, size=10),
    )


# ----------------------------------------------------------------------
# Top bar
# ----------------------------------------------------------------------
pills_html = "".join(
    f'<div class="nav-pill{" active" if item == "Overview" else ""}">{item}</div>'
    for item in NAV_ITEMS
)
initials = "".join(part[0] for part in USER_NAME.split()[:2]).upper()

st.markdown(
    f"""
    <div class="topbar">
      <div class="nav-left">
        <div class="brand">
          <div class="brand-badge">&Lambda;</div>
          <div class="brand-name">Apex Legal</div>
        </div>
        <div class="nav-pills">{pills_html}</div>
      </div>
      <div class="user-row">
        <div class="avatar-initials">{initials}</div>
        <div>
          <div class="user-name">Welcome, {USER_NAME}</div>
          <div class="user-role">{USER_ROLE}</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# KPI row
# ----------------------------------------------------------------------
kpi_cols = st.columns(5)
for col, k in zip(kpi_cols, KPIS):
    with col:
        st.markdown(kpi_html(k), unsafe_allow_html=True)

st.write("")

# ----------------------------------------------------------------------
# Middle row: trend | donut | insights
# ----------------------------------------------------------------------
col_trend, col_donut, col_insights = st.columns([1.6, 1, 1])

with col_trend:
    with st.container(border=True):
        top1, top2 = st.columns([1.6, 1], vertical_alignment="center")
        with top1:
            st.markdown('<div class="card-title">Matter Activity Trend By Practice Group</div>',
                        unsafe_allow_html=True)
        with top2:
            st.markdown(
                f"""
                <div class="legend-row" style="justify-content:flex-end;">
                  <span class="legend-item"><span class="legend-dot" style="background:{TEAL}"></span>Litigation</span>
                  <span class="legend-item"><span class="legend-dot" style="background:#67c1cb"></span>Corporate</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=TREND["month"], y=TREND["Litigation"], mode="lines",
                                  line=dict(color=TEAL, width=2.4, shape="spline")))
        fig.add_trace(go.Scatter(x=TREND["month"], y=TREND["Corporate"], mode="lines",
                                  line=dict(color="#67c1cb", width=2.4, shape="spline")))
        fig.update_layout(**plotly_base(200))
        fig.update_xaxes(showgrid=False, tickfont=dict(size=9))
        fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9", tickfont=dict(size=9))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

with col_donut:
    with st.container(border=True):
        st.markdown('<div class="card-title">Workload By Practice Area</div>', unsafe_allow_html=True)
        labels = list(WORKLOAD.keys())
        values = list(WORKLOAD.values())
        colors = [TEAL, "#3ba7b3", "#7bc4cd", "#b7dee2"]
        donut_col, legend_col = st.columns([1, 1], vertical_alignment="center")
        with donut_col:
            fig2 = go.Figure(data=[go.Pie(
                labels=labels, values=values, hole=0.68,
                marker=dict(colors=colors, line=dict(color="#ffffff", width=2)),
                textinfo="none", sort=False,
            )])
            fig2.update_layout(**plotly_base(150))
            st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})
            st.markdown(
                f"""
                <div style="text-align:center; margin-top:-95px; pointer-events:none;">
                  <div style="font-size:20px; font-weight:700; color:{INK};">{TOTAL_ACTIVE}</div>
                  <div style="font-size:9px; color:{FAINT};">Total Active</div>
                </div>
                <div style="height:60px;"></div>
                """,
                unsafe_allow_html=True,
            )
        with legend_col:
            for label, color in zip(labels, colors):
                st.markdown(
                    f'<div class="donut-legend-item"><span class="legend-dot" '
                    f'style="background:{color}"></span>{label} ({WORKLOAD[label]}%)</div>',
                    unsafe_allow_html=True,
                )

with col_insights:
    with st.container(border=True):
        st.markdown('<div class="card-title">Critical Partner Metrics</div>', unsafe_allow_html=True)
        for kicker, headline, desc in INSIGHTS:
            st.markdown(
                f"""
                <div style="margin-top:12px;">
                  <div class="insight-kicker">{kicker}</div>
                  <div class="insight-headline">{headline}</div>
                  <div class="insight-desc">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.write("")

# ----------------------------------------------------------------------
# Bottom row: attorney matrix | billing + deadlines
# ----------------------------------------------------------------------
col_matrix, col_right = st.columns([1.6, 1])

with col_matrix:
    with st.container(border=True):
        st.markdown('<div class="card-title">Attorney Utilization Matrix (Hours MTD)</div>',
                     unsafe_allow_html=True)
        st.write("")
        header_cells = "".join(f"<th>{c}</th>" for c in PRACTICE_COLS)
        rows_html = []
        for row in MATRIX_ROWS:
            cells = "".join(
                f'<td style="background:rgba(10,132,150,{alpha})">{v} hrs</td>'
                for v, alpha in row["vals"]
            )
            rows_html.append(
                f'<tr><td class="name">{row["name"]}</td>{cells}<td class="total">{row["total"]} hrs</td></tr>'
            )
        table_html = f"""
        <table class="matrix">
          <thead><tr><th>Attorney</th>{header_cells}<th>Total Hrs</th></tr></thead>
          <tbody>{''.join(rows_html)}</tbody>
        </table>
        """
        st.markdown(table_html, unsafe_allow_html=True)

with col_right:
    with st.container(border=True):
        st.markdown('<div class="card-title">Billing &amp; Trust Account Status (K$)</div>',
                     unsafe_allow_html=True)
        st.write("")
        for bar in BILLING_BARS:
            st.markdown(
                f"""
                <div class="bar-row">
                  <div class="bar-head">
                    <span class="lbl">{bar['label']}</span>
                    <span class="val">{bar['value']}</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill" style="width:{bar['pct']}%; background:{bar['color']};"></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.write("")

    with st.container(border=True):
        st.markdown('<div class="card-title">Upcoming Court Appearances &amp; Filings</div>',
                     unsafe_allow_html=True)
        st.write("")
        for d in DEADLINES:
            month, day = d["date"].split(" ")
            st.markdown(
                f"""
                <div class="deadline-item">
                  <div class="date-badge" style="background:{d['badge_bg']}; color:{d['badge_fg']};">{d['date']}</div>
                  <div>
                    <div class="deadline-title">{d['title']}</div>
                    <div class="deadline-sub">{d['sub']}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.caption("Sample data mirrors the Figma design — connect a real source in the DATA section near the top when ready.")
