"""
Meridian & Cole — Firm Financial Overview
A Streamlit dashboard styled to match the "HealthCare Dashboard" reference
mockup: soft mint background, rounded white cards, teal accent palette.

Run:
    pip install -r requirements.txt
    streamlit run app.py

All figures below are SAMPLE DATA generated with a fixed random seed so the
KPI cards, chart, and table numbers stay internally consistent every time
the app runs. Swap `build_sample_data()` for a real data source when ready.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Firm Financial Overview",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TEAL_DARK = "#136d72"
TEAL = "#17888e"
TEAL_MID = "#6fb8bd"
TEAL_LIGHT = "#9fd6da"
TEAL_PALE = "#dff0f1"
GREEN = "#2e9b5f"
RED = "#e2665a"
INK = "#123338"
SUBTLE = "#6b8288"
FAINT = "#93a4a9"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class^="css"], .stMarkdown, .stMetric {{
    font-family: 'Plus Jakarta Sans', sans-serif;
}}

.stApp {{
    background:
        radial-gradient(1200px 500px at 10% -10%, #d3eef0 0%, rgba(211,238,240,0) 60%),
        radial-gradient(900px 500px at 100% 0%, #cdeef1 0%, rgba(205,238,241,0) 55%),
        #eef8f9;
}}

.block-container {{
    padding-top: 1.6rem;
    padding-bottom: 3rem;
    max-width: 1360px;
}}

#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; }}

/* ---- top identity row ---- */
.brand-row {{ display:flex; align-items:center; gap:12px; margin-bottom: 4px; }}
.brand-badge {{
    width:44px; height:44px; border-radius:999px; background:{TEAL};
    display:flex; align-items:center; justify-content:center; flex-shrink:0;
}}
.brand-welcome {{ font-size:13px; color:{SUBTLE}; font-weight:500; line-height:1.1; }}
.brand-title {{ font-size:20px; color:{INK}; font-weight:800; line-height:1.2; }}

/* ---- native tabs, restyled to look like the pill bar ---- */
div[data-testid="stTabs"] button[data-baseweb="tab"] {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 600;
    font-size: 14px;
    color: {SUBTLE};
    border-radius: 999px !important;
    padding: 6px 18px;
    margin-right: 4px;
}}
div[data-testid="stTabs"] button[aria-selected="true"] {{
    background: {TEAL} !important;
    color: #ffffff !important;
}}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ display:none; }}
div[data-testid="stTabs"] [data-baseweb="tab-border"] {{ display:none; }}
div[data-testid="stTabs"] {{
    background:#ffffff; border-radius:999px; padding:6px; width:fit-content;
    box-shadow: 0 6px 18px rgba(20,60,65,0.06);
}}

/* ---- KPI cards ---- */
.kpi-card {{
    background:#ffffff; border-radius:18px; padding:18px 20px;
    box-shadow:0 8px 22px rgba(20,60,65,0.06);
    display:flex; flex-direction:column; gap:10px; height:100%;
}}
.kpi-label {{ font-size:13px; color:{SUBTLE}; font-weight:600; }}
.kpi-row {{ display:flex; align-items:center; justify-content:space-between; gap:8px; }}
.kpi-value {{ font-size:25px; font-weight:800; color:{INK}; white-space:nowrap; }}
.kpi-delta {{ font-size:12px; font-weight:700; display:flex; align-items:center; gap:4px; }}
.kpi-vs {{ color:{FAINT}; font-weight:500; }}

/* ---- chart panel titles / legend row ---- */
.panel-title {{ font-size:15px; font-weight:700; color:{INK}; }}
.legend-row {{ display:flex; align-items:center; gap:14px; font-size:12px; color:{SUBTLE}; font-weight:600; flex-wrap:wrap; }}
.legend-dot {{ width:9px; height:9px; border-radius:999px; display:inline-block; margin-right:5px; }}
.legend-caption {{ color:{FAINT}; font-weight:500; }}

/* ---- donut center labels ---- */
.donut-wrap {{ position:relative; display:flex; align-items:center; justify-content:center; }}
.donut-label {{ position:absolute; font-size:11px; color:{SUBTLE}; font-weight:600; line-height:1.3; }}
.donut-label b {{ display:block; font-size:13px; font-weight:800; }}

/* ---- insight cards ---- */
.insight-card {{
    background:#ffffff; border-radius:18px; padding:18px;
    box-shadow:0 8px 22px rgba(20,60,65,0.06);
}}
.insight-label {{ font-size:13px; color:{SUBTLE}; font-weight:600; }}
.insight-value {{ font-size:17px; font-weight:800; color:{TEAL}; margin:3px 0; }}
.insight-desc {{ font-size:12px; color:{SUBTLE}; line-height:1.5; }}

/* ---- panel wrapper for st.container(border=True) ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 18px !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"] > div {{
    background:#ffffff;
    border-radius: 18px !important;
    box-shadow: 0 8px 22px rgba(20,60,65,0.06);
    border: none !important;
}}

/* ---- billable-hours table ---- */
table.lawtable {{ width:100%; font-size:13px; border-collapse:collapse; }}
table.lawtable th {{ color:{SUBTLE}; font-weight:600; text-align:left; padding:8px 10px; }}
table.lawtable td {{ padding:8px 10px; border-top:1px solid #f0f4f4; color:#253c42; }}
table.lawtable tr.alt td {{ background:#f3fafa; }}
table.lawtable tr.total td {{ border-top:2px solid #d9eceb; font-weight:800; color:{TEAL_DARK}; padding:10px 10px; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Sample data (seeded — swap this out for real data later)
# ----------------------------------------------------------------------
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PRACTICE_AREAS = ["Litigation", "Corporate", "Family Law", "IP", "Real Estate", "Trust & Estates"]
ATTORNEYS = ["A. Sinclair", "M. Chen", "R. Alvarez", "J. Whitfield",
             "S. Okafor", "D. Park", "L. Mercer", "K. Bennett"]


@st.cache_data
def build_sample_data():
    rng = np.random.default_rng(42)

    # Monthly revenue trend, by matter type ($ thousands)
    litigation = 210 + rng.normal(0, 18, 12).cumsum() * 0.3 + np.linspace(0, 40, 12)
    corporate = 260 + rng.normal(0, 22, 12).cumsum() * 0.35 + np.linspace(0, 60, 12)
    family_law = 90 + rng.normal(0, 14, 12).cumsum() * 0.25
    trend = pd.DataFrame({
        "month": MONTHS,
        "Litigation": litigation.round(0),
        "Corporate": corporate.round(0),
        "Family Law": family_law.round(0),
    })
    trend_prior_year_total = trend[["Litigation", "Corporate", "Family Law"]].sum().sum() * 0.89

    # Billable hours matrix: attorney x practice area
    hours = rng.integers(20, 260, size=(len(ATTORNEYS), len(PRACTICE_AREAS)))
    hours_df = pd.DataFrame(hours, index=ATTORNEYS, columns=PRACTICE_AREAS)

    # Revenue share by client type
    client_mix = {"Corporate Clients": 52.4, "Individual Clients": 31.2, "Government Contracts": 16.4}

    total_revenue = trend[["Litigation", "Corporate", "Family Law"]].sum().sum() * 1000
    prior_total_revenue = trend_prior_year_total * 1000

    invoices_this_year = 542
    avg_invoice = total_revenue / invoices_this_year
    prior_avg_invoice = avg_invoice * 0.912

    avg_duration = 46.5
    prior_duration = 43.8

    active_attorneys = 42
    prior_attorneys = 37

    open_matters = 128
    prior_open_matters = 115

    kpis = {
        "Total Revenue": {"value": total_revenue, "prior": prior_total_revenue, "fmt": "money"},
        "Avg Matter Duration": {"value": avg_duration, "prior": prior_duration, "fmt": "days"},
        "Avg Invoice Amount": {"value": avg_invoice, "prior": prior_avg_invoice, "fmt": "money"},
        "Active Attorneys": {"value": active_attorneys, "prior": prior_attorneys, "fmt": "int"},
        "Open Matters": {"value": open_matters, "prior": prior_open_matters, "fmt": "int"},
    }

    sparks = {
        "Total Revenue": (trend["Litigation"] + trend["Corporate"] + trend["Family Law"]).values,
        "Avg Matter Duration": 46.5 + rng.normal(0, 3, 12).cumsum() * 0.2,
        "Avg Invoice Amount": avg_invoice * (0.85 + rng.random(12) * 0.3),
        "Active Attorneys": np.linspace(35, 42, 12) + rng.normal(0, 0.6, 12),
        "Open Matters": np.linspace(100, 128, 12) + rng.normal(0, 3, 12),
    }

    insights = {
        "Top Practice Area": ("Corporate Law", "$1.42M billed this year — 34% of total firm revenue"),
        "Top Client": ("Meridian Holdings Ltd.", "$612K billed across 14 active matters this year"),
        "Most Profitable Matter Type": ("M&A Advisory", "41% realised margin, the highest of any matter type"),
    }

    return trend, hours_df, client_mix, kpis, sparks, insights


trend, hours_df, client_mix, kpis, sparks, insights = build_sample_data()


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------
def fmt_money(v):
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f} M"
    if v >= 1_000:
        return f"${v/1_000:.0f} K"
    return f"${v:.0f}"


def fmt_kpi(fmt, v):
    if fmt == "money":
        return fmt_money(v)
    if fmt == "days":
        return f"{v:.1f} days"
    return f"{v:,.0f}"


def sparkline_svg(values, color=TEAL, width=60, height=24):
    values = np.asarray(values, dtype=float)
    lo, hi = values.min(), values.max()
    rng_span = (hi - lo) or 1.0
    n = len(values)
    step = width / (n - 1) if n > 1 else width
    pts = []
    for i, v in enumerate(values):
        x = i * step
        y = height - ((v - lo) / rng_span) * height
        pts.append(f"{x:.1f},{y:.1f}")
    points = " ".join(pts)
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def delta_arrow(up):
    stroke = GREEN if up else RED
    d = "M12 19V5M5 12l7-7 7 7" if up else "M12 5v14M5 12l7 7 7-7"
    return (f'<svg width="10" height="10" viewBox="0 0 24 24" fill="none">'
            f'<path d="{d}" stroke="{stroke}" stroke-width="3" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def kpi_card_html(label, value_str, pct, spark_values):
    up = pct >= 0
    color = GREEN if up else RED
    return f"""
    <div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-row">
        <div class="kpi-value">{value_str}</div>
        {sparkline_svg(spark_values)}
      </div>
      <div class="kpi-delta" style="color:{color}">
        {delta_arrow(up)} {abs(pct):.2f}% <span class="kpi-vs">Vs PY</span>
      </div>
    </div>
    """


def insight_card_html(label, headline, desc):
    return f"""
    <div class="insight-card">
      <div class="insight-label">{label}</div>
      <div class="insight-value">{headline}</div>
      <div class="insight-desc">{desc}</div>
    </div>
    """


def plotly_base_layout(height=230):
    return dict(
        margin=dict(l=8, r=8, t=8, b=8),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font=dict(family="Plus Jakarta Sans, sans-serif", color=SUBTLE, size=11),
    )


# ----------------------------------------------------------------------
# Top bar
# ----------------------------------------------------------------------
left, right = st.columns([2.4, 1], vertical_alignment="center")
with left:
    tabs = st.tabs(["Financial Overview", "Billing & Trust", "Matters"])
with right:
    st.markdown(
        f"""
        <div class="brand-row" style="justify-content:flex-end;">
          <div class="brand-badge">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 5v14M5 12h14" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round"/>
            </svg>
          </div>
          <div>
            <div class="brand-welcome">Welcome to</div>
            <div class="brand-title">Firm Financial Overview</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with tabs[1]:
    st.info("Billing & Trust is a placeholder tab — say the word and I'll build it out next.")
with tabs[2]:
    st.info("Matters is a placeholder tab — say the word and I'll build it out next.")

with tabs[0]:
    # ------------------------------------------------------------------
    # KPI row
    # ------------------------------------------------------------------
    kpi_cols = st.columns(5)
    for col, (label, d) in zip(kpi_cols, kpis.items()):
        pct = (d["value"] - d["prior"]) / d["prior"] * 100
        with col:
            st.markdown(
                kpi_card_html(label, fmt_kpi(d["fmt"], d["value"]), pct, sparks[label]),
                unsafe_allow_html=True,
            )

    st.write("")

    # ------------------------------------------------------------------
    # Chart row: trend line | donut | insight cards
    # ------------------------------------------------------------------
    col_trend, col_donut, col_insights = st.columns([1.7, 1, 0.9])

    with col_trend:
        with st.container(border=True):
            top1, top2 = st.columns([1.4, 2], vertical_alignment="center")
            with top1:
                st.markdown('<div class="panel-title">Revenue Trend By Matter Type</div>', unsafe_allow_html=True)
            with top2:
                st.markdown(
                    f"""
                    <div class="legend-row" style="justify-content:flex-end;">
                      <span class="legend-caption">$ thousands</span>
                      <span><span class="legend-dot" style="background:{TEAL_LIGHT}"></span>Litigation</span>
                      <span><span class="legend-dot" style="background:#1f7a4d"></span>Corporate</span>
                      <span><span class="legend-dot" style="background:{RED}"></span>Family Law</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=trend["month"], y=trend["Litigation"], mode="lines",
                                      line=dict(color=TEAL_LIGHT, width=2.6, shape="spline")))
            fig.add_trace(go.Scatter(x=trend["month"], y=trend["Corporate"], mode="lines",
                                      line=dict(color="#1f7a4d", width=2.6, shape="spline")))
            fig.add_trace(go.Scatter(x=trend["month"], y=trend["Family Law"], mode="lines",
                                      line=dict(color=RED, width=2.6, shape="spline")))
            fig.update_layout(**plotly_base_layout(230))
            fig.update_xaxes(showgrid=False, tickfont=dict(size=10))
            fig.update_yaxes(showgrid=True, gridcolor="#f4f7f7", tickfont=dict(size=10))
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})

    with col_donut:
        with st.container(border=True):
            st.markdown('<div class="panel-title">Revenue by Client Type</div>', unsafe_allow_html=True)
            labels = list(client_mix.keys())
            values = list(client_mix.values())
            colors = [TEAL_LIGHT, TEAL_MID, TEAL_DARK]
            fig2 = go.Figure(data=[go.Pie(
                labels=labels, values=values, hole=0.62,
                marker=dict(colors=colors, line=dict(color="#ffffff", width=2)),
                textinfo="none", sort=False,
            )])
            fig2.update_layout(**plotly_base_layout(190))
            st.plotly_chart(fig2, width='stretch', config={"displayModeBar": False})
            st.markdown(
                f"""
                <div class="legend-row" style="justify-content:center;">
                  <span><span class="legend-dot" style="background:{TEAL_LIGHT}"></span>Corporate {client_mix['Corporate Clients']:.1f}%</span>
                </div>
                <div class="legend-row" style="justify-content:center; margin-top:6px;">
                  <span><span class="legend-dot" style="background:{TEAL_MID}"></span>Individual {client_mix['Individual Clients']:.1f}%</span>
                  <span><span class="legend-dot" style="background:{TEAL_DARK}"></span>Government {client_mix['Government Contracts']:.1f}%</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_insights:
        for label, (headline, desc) in insights.items():
            st.markdown(insight_card_html(label, headline, desc), unsafe_allow_html=True)

    st.write("")

    # ------------------------------------------------------------------
    # Bottom row: billable-hours table | bar chart
    # ------------------------------------------------------------------
    col_table, col_bar = st.columns([1.7, 1])

    with col_table:
        with st.container(border=True):
            st.markdown('<div class="panel-title">Billable Hours by Attorney &amp; Practice Area</div>',
                        unsafe_allow_html=True)
            st.write("")
            totals = hours_df.sum()
            rows_html = []
            for i, (attorney, row) in enumerate(hours_df.iterrows()):
                cls = "alt" if i % 3 == 1 else ""
                cells = "".join(f"<td>{v}</td>" for v in row.values)
                rows_html.append(f'<tr class="{cls}"><td>{attorney}</td>{cells}</tr>')
            total_cells = "".join(f"<td>{v}</td>" for v in totals.values)
            rows_html.append(f'<tr class="total"><td>Total</td>{total_cells}</tr>')

            table_html = f"""
            <table class="lawtable">
              <thead>
                <tr><th>Attorney</th>{''.join(f'<th>{c}</th>' for c in PRACTICE_AREAS)}</tr>
              </thead>
              <tbody>
                {''.join(rows_html)}
              </tbody>
            </table>
            """
            st.markdown(table_html, unsafe_allow_html=True)

    with col_bar:
        with st.container(border=True):
            st.markdown('<div class="panel-title">Billable Hours by Practice Area</div>', unsafe_allow_html=True)
            area_totals = hours_df.sum().sort_values(ascending=True)
            fig3 = go.Figure(go.Bar(
                x=area_totals.values, y=area_totals.index, orientation="h",
                marker=dict(color=TEAL_MID),
                text=area_totals.values, textposition="outside",
                textfont=dict(size=11, color=SUBTLE),
            ))
            layout = plotly_base_layout(260)
            layout["margin"] = dict(l=8, r=30, t=8, b=8)
            fig3.update_layout(**layout)
            fig3.update_xaxes(visible=False)
            fig3.update_yaxes(tickfont=dict(size=11, color=SUBTLE))
            st.plotly_chart(fig3, width='stretch', config={"displayModeBar": False})

st.caption("Sample data for layout preview — connect a real data source in `build_sample_data()` when ready.")
