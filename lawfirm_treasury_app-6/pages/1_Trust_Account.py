import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (load_all, money, sidebar_filters, filter_transactions,
                    inject_theme, kpi_card, insight_card, flow_kpi, PALETTE)

st.set_page_config(page_title="Trust Account", layout="wide")
inject_theme()

st.title("Trust Account")
st.caption("Client money held on statutory trust - separate from the firm's own funds, reconciled against CommBiz.")

data = load_all()
matters = data["matters"]

st.sidebar.header("Filters")
loc, mtype, status, date_range = sidebar_filters(data, key_prefix="trust")

trust_f = filter_transactions(data["trust"], matters, loc, mtype, status, date_range)
deposits = trust_f[trust_f.type == "Deposit"]
disbursements = trust_f[trust_f.type == "Disbursement payment"]
transfers = trust_f[trust_f.type == "Transfer to office (billing)"]

recon = data["commbiz"]
recon_t = recon[recon.account_type == "Trust"]
if loc != "All":
    loc_id = data["locations"].loc[data["locations"].location_name == loc, "location_id"].iloc[0]
    recon_t = recon_t[recon_t.location_id == loc_id]

# ---------------------------------------------------------------- KPI row
c1, c2, c3 = st.columns(3)
with c1:
    flow_kpi(deposits, "date", "amount", "Trust deposits", spark_color=PALETTE[0])
with c2:
    flow_kpi(disbursements, "date", "amount", "Disbursement payments",
              spark_color=PALETTE[2], magnitude=True, invert_color=True)
with c3:
    flow_kpi(transfers, "date", "amount", "Transferred to office (billed)",
              spark_color=PALETTE[4], magnitude=True, invert_color=False)

st.markdown("")

# ---------------------------------------------------------------- left / mid / right
left, mid, right = st.columns([2, 1.4, 1.4])

with left:
    st.markdown("**Trust movement by month**")
    if len(trust_f):
        t = trust_f.copy()
        t["month"] = t["date"].dt.to_period("M").dt.to_timestamp()
        t_month = t.groupby(["month", "type"])["amount"].sum().reset_index()
        fig = px.bar(t_month, x="month", y="amount", color="type",
                     color_discrete_sequence=PALETTE, barmode="relative")
        fig.update_layout(xaxis_title="", yaxis_title="", height=340, legend_title="",
                           plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                           margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trust transactions for this filter selection.")

with mid:
    st.markdown("**Reconciliation status**")
    if len(recon_t):
        status_counts = recon_t["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig2 = go.Figure(data=[go.Pie(labels=status_counts.status, values=status_counts["count"], hole=0.6,
                                        marker=dict(colors=[PALETTE[1], PALETTE[2]]))])
        fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No reconciliation rows for this selection.")

with right:
    if len(trust_f):
        by_src = trust_f.groupby("source_system")["amount"].sum().abs()
        insight_card("Busiest source system", by_src.idxmax(), f"{money(by_src.max())} moved through this system")
    invest = recon_t[recon_t.status == "Investigate"]
    total_recon = len(recon_t)
    rate = (1 - len(invest) / total_recon) * 100 if total_recon else 0
    insight_card("Reconciliation exceptions", str(len(invest)),
                 f"Out of {total_recon} monthly checks ({rate:.1f}% clean)")
    if len(disbursements):
        insight_card("Avg disbursement size", money(disbursements["amount"].abs().mean()),
                     "Average trust disbursement payment")

st.markdown("")

# ---------------------------------------------------------------- breakdown chart
st.markdown("**Trust transactions by source system**")
if len(trust_f):
    src = trust_f.groupby("source_system")["amount"].sum().abs().reset_index()
    fig3 = px.bar(src, x="source_system", y="amount", color="source_system",
                  color_discrete_sequence=PALETTE)
    fig3.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=300,
                        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No trust transactions for this filter selection.")

st.markdown("")

# ---------------------------------------------------------------- detail tables
st.markdown("**Trust transaction detail**")
st.dataframe(trust_f.sort_values("date", ascending=False), use_container_width=True, height=300)

st.markdown("**Monthly reconciliation detail (bank vs ledger)**")
st.dataframe(recon_t.sort_values("period_end", ascending=False), use_container_width=True, height=280)
