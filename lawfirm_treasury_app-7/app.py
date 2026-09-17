import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from utils import (load_all, money, inject_theme, kpi_card, insight_card, flow_kpi,
                    top_slicers, filter_matters, filter_transactions,
                    monthly_series, yoy_delta, PALETTE)

st.set_page_config(page_title="Treasury and Credit Strategy Dashboard", layout="wide")
inject_theme()

data = load_all()
matters = data["matters"]

# ================================================================== FROZEN HEADER
# Title, slicers, and the top-tier KPIs stay pinned to the top of the viewport while the rest
# of the dashboard scrolls beneath them - so the headline numbers are always visible.
with st.container(key="dash_header"):
    st.title("D'Agostino Treasury and Credit Strategy Dashboard")
    st.caption(
        "Interactive overview of office account, trust account, credit cards, InfoTrack, LEAP, "
        "RapidPay, CommBiz and commission across both offices and all practice areas."
    )

    loc, mtype, status, date_range = top_slicers(data, key_prefix="home")

    m_f = filter_matters(matters, loc, mtype, status, date_range)
    trust_f = filter_transactions(data["trust"], matters, loc, mtype, status, date_range)
    office_f = filter_transactions(data["office"], matters, loc, mtype, status, date_range)
    cards_f = filter_transactions(data["cards"], matters, loc, mtype, status, date_range)
    rapidpay_f = filter_transactions(data["rapidpay"], matters, loc, mtype, status, date_range)
    commission_f = filter_transactions(data["commission"], matters, loc, mtype, status, date_range)
    infotrack_f = filter_transactions(data["infotrack"], matters, loc, mtype, status, date_range)

    trust_deposits = trust_f[trust_f.type == "Deposit"]
    disbursements = trust_f[trust_f.type == "Disbursement payment"]
    transfers = trust_f[trust_f.type == "Transfer to office (billing)"]
    office_fees = office_f[office_f.type == "Fee income"]
    expenses = office_f[office_f.type == "Expense"]

    st.markdown("**Core financial KPIs**")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        flow_kpi(trust_deposits, "date", "amount", "Trust deposits", spark_color=PALETTE[0])
    with c2:
        flow_kpi(office_fees, "date", "amount", "Fee income", spark_color=PALETTE[1])
    with c3:
        flow_kpi(expenses, "date", "amount", "Operating expenses",
                  spark_color=PALETTE[2], magnitude=True, invert_color=True)
    with c4:
        open_m = m_f[m_f.status == "Open"]
        kpi_card("Open matters", str(len(open_m)),
                  monthly_series(open_m, "open_date", "matter_id", "count").values,
                  yoy_delta(m_f, "open_date", "matter_id", "count"), spark_color=PALETTE[3])
    with c5:
        flow_kpi(rapidpay_f, "date", "gross_amount", "RapidPay collected", spark_color=PALETTE[4])

st.markdown("")

# ================================================================== EXECUTIVE SUMMARY
scope_bits = []
scope_bits.append(loc if loc != "All" else "both offices")
scope_bits.append(mtype if mtype != "All" else "all practice areas")
scope_bits.append(f"{status.lower()} matters" if status != "All" else "all matter statuses")
scope_text = ", ".join(scope_bits)

realization = (office_fees.merge(
    m_f[["matter_id", "fee_estimate"]], on="matter_id", how="left")
    .assign(rate=lambda d: d.amount / d.fee_estimate.replace(0, np.nan)))
realization_rate = realization["rate"].mean() * 100 if len(realization) else None

expense_ratio = (abs(expenses.amount.sum()) / office_fees.amount.sum() * 100
                  if office_fees.amount.sum() else None)

expense_ratio_text = f"{expense_ratio:.1f}% expense ratio" if expense_ratio is not None else "no expense ratio available (no fee income in this selection)"
realization_text = f"{realization_rate:.1f}%" if realization_rate is not None else "not available"

st.markdown(
    f"""
    <div class="insight-card" style="margin-top:8px;">
        <div class="insight-label">Executive summary - {scope_text}</div>
        <div class="insight-detail" style="font-size:0.95rem; line-height:1.6;">
            {len(m_f)} matters generated {money(office_fees.amount.sum())} in fee income against
            {money(abs(expenses.amount.sum()))} in operating expenses ({expense_ratio_text}).
            Trust deposits totalled {money(trust_deposits.amount.sum())}, of which
            {money(abs(disbursements.amount.sum()))} was paid out in disbursements.
            Average fee realisation against original estimates was {realization_text}.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("")

# ================================================================== TIER 2: RATIOS
st.markdown("**Efficiency and collection ratios**")
r1, r2, r3, r4 = st.columns(4)

with r1:
    val = f"{realization_rate:.1f}%" if realization_rate is not None else "n/a"
    rate_vals = realization["rate"].dropna().values * 100 if len(realization) else np.array([])
    kpi_card("Fee realisation rate", val, rate_vals if len(rate_vals) else [0, 0],
              None, spark_color=PALETTE[0])

with r2:
    val = f"{expense_ratio:.1f}%" if expense_ratio is not None else "n/a"
    monthly_ratio = pd.Series(dtype=float)
    if len(office_f):
        o = office_f.copy()
        o["month"] = o["date"].dt.to_period("M").dt.to_timestamp()
        fee_m = o[o.type == "Fee income"].groupby("month")["amount"].sum()
        exp_m = o[o.type == "Expense"].groupby("month")["amount"].sum().abs()
        monthly_ratio = (exp_m / fee_m.replace(0, np.nan) * 100).dropna()
    kpi_card("Expense ratio (opex / fees)", val,
              monthly_ratio.values if len(monthly_ratio) else [0, 0], None, spark_color=PALETTE[2])

with r3:
    days_to_cash = pd.Series(dtype=float)
    if len(rapidpay_f):
        merged = rapidpay_f.merge(matters[["matter_id", "open_date"]], on="matter_id", how="left")
        merged["days"] = (merged["date"] - merged["open_date"]).dt.days
        merged = merged[merged["days"] >= 0]
        days_to_cash = merged["days"]
    avg_days = days_to_cash.mean() if len(days_to_cash) else 0
    kpi_card("Avg days: open to cash collected", f"{avg_days:.0f} days",
              monthly_series(merged.assign(month=merged["date"]), "month", "days", "mean").values
              if len(days_to_cash) else [0, 0], None, spark_color=PALETTE[3])

with r4:
    merchant_rate = (rapidpay_f["merchant_fee"].sum() / rapidpay_f["gross_amount"].sum() * 100
                      if len(rapidpay_f) and rapidpay_f["gross_amount"].sum() else None)
    val = f"{merchant_rate:.2f}%" if merchant_rate is not None else "n/a"
    rp_rate_series = pd.Series(dtype=float)
    if len(rapidpay_f):
        rp = rapidpay_f.copy()
        rp["month"] = rp["date"].dt.to_period("M").dt.to_timestamp()
        g = rp.groupby("month").apply(lambda d: d.merchant_fee.sum() / d.gross_amount.sum() * 100
                                        if d.gross_amount.sum() else np.nan)
        rp_rate_series = g.dropna()
    kpi_card("RapidPay merchant fee rate", val,
              rp_rate_series.values if len(rp_rate_series) else [0, 0],
              None, spark_color=PALETTE[4], invert_color=True)

st.markdown("")

# ================================================================== MONTHLY FINANCIAL TREND
st.markdown("**Monthly financial trend: fee income, expenses and net**")
trend_src = office_f.copy()
if len(trend_src):
    trend_src["month"] = trend_src["date"].dt.to_period("M").dt.to_timestamp()
    fee_m = trend_src[trend_src.type == "Fee income"].groupby("month")["amount"].sum()
    exp_m = trend_src[trend_src.type == "Expense"].groupby("month")["amount"].sum().abs()
    trend_df = pd.DataFrame({"Fee income": fee_m, "Operating expenses": exp_m}).fillna(0.0)
    trend_df["Net"] = trend_df["Fee income"] - trend_df["Operating expenses"]
    trend_long = trend_df.reset_index().melt(id_vars="month", var_name="Metric", value_name="Amount")
    fig_trend = px.line(trend_long, x="month", y="Amount", color="Metric", markers=True,
                         color_discrete_sequence=[PALETTE[1], PALETTE[2], PALETTE[0]])
    fig_trend.update_layout(xaxis_title="", yaxis_title="", height=320, legend_title="",
                             plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                             margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("No office transactions for this filter selection.")

st.markdown("")

# ================================================================== PRACTICE AREA PROFITABILITY
st.markdown("**Practice area profitability (estimated)**")
st.caption(
    "Fee income by practice area, less operating expenses allocated proportionally by matter "
    "count. This is an allocation estimate for directional comparison, not a true cost-accounting figure."
)
fee_by_type = (office_fees.merge(matters[["matter_id", "matter_type"]], on="matter_id", how="left")
               .groupby("matter_type")["amount"].sum())
matter_count_by_type = m_f.groupby("matter_type").size()
total_matters_n = matter_count_by_type.sum()
total_expenses_abs = abs(expenses.amount.sum())
allocated_expense = (matter_count_by_type / total_matters_n * total_expenses_abs
                      if total_matters_n else pd.Series(dtype=float))

profit_df = pd.DataFrame({"Fee income": fee_by_type, "Allocated expenses": allocated_expense}).fillna(0.0)
if len(profit_df):
    profit_df["Estimated margin"] = profit_df["Fee income"] - profit_df["Allocated expenses"]
    profit_df = profit_df.reset_index().rename(columns={"matter_type": "Practice area"})
    profit_df["Result"] = np.where(profit_df["Estimated margin"] >= 0, "Profitable (est.)", "Loss-making (est.)")
    fig_profit = px.bar(profit_df.sort_values("Estimated margin"), x="Estimated margin", y="Practice area",
                         orientation="h", color="Result",
                         color_discrete_map={"Profitable (est.)": PALETTE[1], "Loss-making (est.)": PALETTE[2]})
    fig_profit.update_layout(xaxis_title="", yaxis_title="", height=300, legend_title="",
                              plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                              margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig_profit, use_container_width=True)
else:
    st.info("No matters for this filter selection.")

st.markdown("")

# ================================================================== CASH FLOW BRIDGE
st.markdown("**Cash flow bridge: trust to office**")
st.caption(
    "Illustrative bridge across the four ledgers - not a formal accounting reconciliation, since "
    "trust transfers and office fee income are recorded as separate events in this dataset."
)
bridge_labels = ["Trust deposits", "Disbursements", "Transferred to office",
                  "Trust closing position", "Fee income (direct)", "Operating expenses",
                  "Net financial result"]
bridge_values = [
    trust_deposits.amount.sum(),
    disbursements.amount.sum(),
    transfers.amount.sum(),
    0,
    office_fees.amount.sum(),
    expenses.amount.sum(),
    0,
]
bridge_measure = ["absolute", "relative", "relative", "total", "relative", "relative", "total"]

fig_bridge = go.Figure(go.Waterfall(
    orientation="v",
    measure=bridge_measure,
    x=bridge_labels,
    y=bridge_values,
    connector={"line": {"color": "#B9D8E6", "width": 1}},
    increasing={"marker": {"color": PALETTE[1]}},
    decreasing={"marker": {"color": PALETTE[2]}},
    totals={"marker": {"color": PALETTE[0]}},
    text=[money(v) if m != "total" else "" for v, m in zip(bridge_values, bridge_measure)],
    textposition="outside",
))
fig_bridge.update_layout(height=380, showlegend=False, plot_bgcolor="white",
                          paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, l=0, r=0, b=0))
st.plotly_chart(fig_bridge, use_container_width=True)

st.markdown("")

# ================================================================== YoY COMPARISON
st.markdown("**Year-over-year comparison**")


def year_totals(df, date_col, value_col, magnitude=False):
    if not len(df):
        return {2024: 0, 2025: 0}
    d = df.copy()
    if magnitude:
        d[value_col] = d[value_col].abs()
    g = d.groupby(d[date_col].dt.year)[value_col].sum()
    return {2024: g.get(2024, 0), 2025: g.get(2025, 0)}


yoy_rows = []
for label, series in [
    ("Trust deposits", year_totals(trust_deposits, "date", "amount")),
    ("Fee income", year_totals(office_fees, "date", "amount")),
    ("Operating expenses", year_totals(expenses, "date", "amount", magnitude=True)),
    ("RapidPay collected", year_totals(rapidpay_f, "date", "gross_amount")),
]:
    yoy_rows.append({"Metric": label, "Year": "2024", "Amount": series[2024]})
    yoy_rows.append({"Metric": label, "Year": "2025", "Amount": series[2025]})
yoy_df = pd.DataFrame(yoy_rows)

fig_yoy = px.bar(yoy_df, x="Metric", y="Amount", color="Year", barmode="group",
                  color_discrete_sequence=[PALETTE[3], PALETTE[0]])
fig_yoy.update_layout(xaxis_title="", yaxis_title="", height=340, legend_title="",
                       plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                       margin=dict(t=10, l=0, r=0, b=0))
st.plotly_chart(fig_yoy, use_container_width=True)

st.markdown("")

# ================================================================== LOCATION SCORECARD
st.markdown("**Location scorecard**")

scorecard_rows = []
for _, loc_row in data["locations"].iterrows():
    lid, lname = loc_row.location_id, loc_row.location_name
    loc_matters = m_f[m_f.location_id == lid]
    loc_fees = office_fees[office_fees.matter_id.isin(loc_matters.matter_id)]
    loc_expenses = expenses[expenses.location_id == lid]
    loc_trust = trust_f[trust_f.location_id == lid]
    loc_realization = loc_fees.merge(loc_matters[["matter_id", "fee_estimate"]], on="matter_id", how="left")
    loc_realization_rate = (
        (loc_realization.amount / loc_realization.fee_estimate.replace(0, np.nan)).mean() * 100
        if len(loc_realization) else np.nan
    )
    scorecard_rows.append({
        "Location": lname,
        "Matters": len(loc_matters),
        "Fee income": loc_fees.amount.sum(),
        "Operating expenses": abs(loc_expenses.amount.sum()),
        "Trust net movement": loc_trust.amount.sum(),
        "Realisation rate %": loc_realization_rate,
    })
scorecard_df = pd.DataFrame(scorecard_rows).set_index("Location")

styled = (
    scorecard_df.style
    .format({
        "Matters": "{:.0f}",
        "Fee income": "${:,.0f}",
        "Operating expenses": "${:,.0f}",
        "Trust net movement": "${:,.0f}",
        "Realisation rate %": "{:.1f}%",
    })
    .background_gradient(subset=["Fee income"], cmap="Greens")
    .background_gradient(subset=["Operating expenses"], cmap="Reds")
    .background_gradient(subset=["Realisation rate %"], cmap="RdYlGn")
)
st.dataframe(styled, use_container_width=True)

st.markdown("")

# ================================================================== RECONCILIATION ANOMALIES
recon_all = data["commbiz"]
if loc != "All":
    loc_ids = matters.loc[matters.location_name == loc, "location_id"].unique()
    recon_all = recon_all[recon_all.location_id.isin(loc_ids)]
flagged = recon_all[recon_all.status == "Investigate"]
if len(flagged):
    st.markdown("**Reconciliation exceptions flagged for review**")
    st.dataframe(
        flagged[["account_type", "location_id", "period_end", "bank_balance", "ledger_balance", "variance"]]
        .sort_values("period_end", ascending=False),
        use_container_width=True, height=200,
    )
    st.markdown("")

# ================================================================== DETAIL TABS
tab1, tab2, tab3 = st.tabs(["Treasury Overview", "Matters and Practice Areas", "Billing and Cards"])

# ======================================================================== TAB 1
with tab1:
    left, mid, right = st.columns([2.2, 1.6, 1.4])

    with left:
        st.markdown("**Matters opened by month, by practice area**")
        if len(m_f):
            m = m_f.copy()
            m["month"] = m["open_date"].dt.to_period("M").dt.to_timestamp()
            trend = m.groupby(["month", "matter_type"]).size().reset_index(name="count")
            fig = px.line(trend, x="month", y="count", color="matter_type",
                          color_discrete_sequence=PALETTE, markers=True)
            fig.update_layout(xaxis_title="", yaxis_title="", height=320, legend_title="",
                               plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                               margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No matters for this filter selection.")

    with mid:
        st.markdown("**Matters by client type**")
        if len(m_f):
            ct = m_f.client_type.value_counts().reset_index()
            ct.columns = ["client_type", "count"]
            fig2 = go.Figure(data=[go.Pie(labels=ct.client_type, values=ct["count"], hole=0.6,
                                            marker=dict(colors=PALETTE))])
            fig2.update_layout(height=320, margin=dict(t=10, l=0, r=0, b=0),
                                paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No data.")

    with right:
        if len(m_f):
            by_type = m_f.matter_type.value_counts()
            insight_card("Top practice area", by_type.idxmax(),
                         f"{by_type.max()} matters ({by_type.max()/len(m_f)*100:.1f}%)")
            by_loc = m_f.location_name.value_counts()
            insight_card("Top office", by_loc.idxmax(),
                         f"{by_loc.max()} matters ({by_loc.max()/len(m_f)*100:.1f}%)")
        ref = m_f[m_f.referred_matter]
        if len(ref):
            by_ref = ref.referral_source.value_counts()
            insight_card("Top referral source", by_ref.idxmax(),
                         f"{by_ref.max()} matters ({by_ref.max()/len(ref)*100:.1f}%)")

    st.markdown("")
    left2, right2 = st.columns([2, 1.4])
    with left2:
        st.markdown("**Matters by location and practice area**")
        if len(m_f):
            pivot = m_f.pivot_table(index="location_name", columns="matter_type",
                                     values="matter_id", aggfunc="count", fill_value=0)
            pivot["Total"] = pivot.sum(axis=1)
            pivot.loc["Total"] = pivot.sum()
            st.dataframe(pivot, use_container_width=True, height=180)
        else:
            st.info("No data.")

    with right2:
        st.markdown("**Trust disbursements by practice area**")
        t = trust_f[trust_f.type == "Disbursement payment"].merge(
            matters[["matter_id", "matter_type"]], on="matter_id", how="left")
        if len(t):
            by_type = t.groupby("matter_type")["amount"].sum().abs().sort_values().reset_index()
            fig3 = px.bar(by_type, x="amount", y="matter_type", orientation="h",
                          color="matter_type", color_discrete_sequence=PALETTE)
            fig3.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=220,
                                plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                                margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No disbursements for this filter selection.")

# ======================================================================== TAB 2
with tab2:
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Total matters", str(len(m_f)),
                  monthly_series(m_f, "open_date", "matter_id", "count").values,
                  yoy_delta(m_f, "open_date", "matter_id", "count"), spark_color=PALETTE[0])
    with c2:
        closed_m = m_f[m_f.status == "Closed"]
        kpi_card("Closed matters", str(len(closed_m)),
                  monthly_series(closed_m, "open_date", "matter_id", "count").values,
                  None, spark_color=PALETTE[1])
    with c3:
        ref_m = m_f[m_f.referred_matter]
        kpi_card("Referred matters", str(len(ref_m)),
                  monthly_series(ref_m, "open_date", "matter_id", "count").values,
                  None, spark_color=PALETTE[4])

    st.markdown("")
    left, right = st.columns(2)
    with left:
        st.markdown("**Practice area mix**")
        if len(m_f):
            by_type = m_f.matter_type.value_counts().reset_index()
            by_type.columns = ["matter_type", "count"]
            fig = px.bar(by_type, x="matter_type", y="count", color="matter_type",
                         color_discrete_sequence=PALETTE)
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=340,
                               plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                               margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No matters for this filter selection.")
    with right:
        st.markdown("**Matter status split**")
        if len(m_f):
            status_ct = m_f.status.value_counts().reset_index()
            status_ct.columns = ["status", "count"]
            fig2 = go.Figure(data=[go.Pie(labels=status_ct.status, values=status_ct["count"], hole=0.6,
                                            marker=dict(colors=PALETTE))])
            fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                                paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No data.")

    st.markdown("")
    st.markdown("**Matter detail**")
    st.dataframe(m_f[["matter_id", "client_name", "location_name", "matter_type", "status",
                       "open_date", "close_date", "fee_estimate"]].sort_values(
        "open_date", ascending=False), use_container_width=True, height=300)

# ======================================================================== TAB 3
with tab3:
    c1, c2, c3 = st.columns(3)
    with c1:
        flow_kpi(cards_f, "date", "amount", "Total card spend", spark_color=PALETTE[0], invert_color=True)
    with c2:
        flow_kpi(commission_f, "date", "amount", "Total commission", spark_color=PALETTE[1], invert_color=True)
    with c3:
        flow_kpi(rapidpay_f, "date", "net_amount", "RapidPay net to firm", spark_color=PALETTE[4])

    st.markdown("")
    left, right = st.columns(2)
    with left:
        st.markdown("**Amex vs Visa spend**")
        if len(cards_f):
            by_card = cards_f.groupby("card_type")["amount"].sum().reset_index()
            fig = px.bar(by_card, x="card_type", y="amount", color="card_type",
                         color_discrete_sequence=[PALETTE[0], PALETTE[2]])
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=340,
                               plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                               margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No card transactions for this filter selection.")
    with right:
        st.markdown("**Commission split by type**")
        if len(commission_f):
            cm = commission_f.groupby("commission_type")["amount"].sum().reset_index()
            fig2 = go.Figure(data=[go.Pie(labels=cm.commission_type, values=cm["amount"], hole=0.6,
                                            marker=dict(colors=PALETTE))])
            fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                                paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No commission for this filter selection.")

    st.markdown("")
    st.markdown("**Credit card transaction detail**")
    st.dataframe(cards_f.sort_values("date", ascending=False), use_container_width=True, height=300)

st.caption(
    "Use the pages in the left navigation for Trust, Office and Cards, Payments and Rails, "
    "Commission, Matters and Clients, and the Relationships and Locations map."
)
