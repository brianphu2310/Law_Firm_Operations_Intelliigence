import streamlit as st
import pandas as pd
import plotly.express as px
from utils import inject_theme, PALETTE, load_all, money, sidebar_filters, apply_matter_filters

st.set_page_config(page_title="Trust Account", page_icon="🏦", layout="wide")
inject_theme()
st.title("🏦 Trust Account")
st.caption("Client money held on statutory trust — separate from the firm's own funds, reconciled against CommBiz.")

data = load_all()
matters = data["matters"]

st.sidebar.header("Filters")
loc, mtype, date_range = sidebar_filters(data, key_prefix="trust")

trust_f = apply_matter_filters(data["trust"], matters, loc, mtype, date_range)
recon = data["commbiz"]
recon_t = recon[recon.account_type == "Trust"]
if loc != "All":
    loc_id = data["locations"].loc[data["locations"].location_name == loc, "location_id"].iloc[0]
    recon_t = recon_t[recon_t.location_id == loc_id]

c1, c2, c3 = st.columns(3)
c1.metric("Deposits", money(trust_f.loc[trust_f.type == "Deposit", "amount"].sum()))
c2.metric("Disbursement payments", money(-trust_f.loc[trust_f.type == "Disbursement payment", "amount"].sum()))
c3.metric("Transferred to office (billed)", money(-trust_f.loc[trust_f.type == "Transfer to office (billing)", "amount"].sum()))

st.divider()
left, right = st.columns([3, 2])

with left:
    st.subheader("Trust movement over time")
    t = trust_f.copy()
    t["month"] = t["date"].dt.to_period("M").dt.to_timestamp()
    t_month = t.groupby(["month", "type"])["amount"].sum().reset_index()
    fig = px.bar(t_month, x="month", y="amount", color="type", barmode="relative", color_discrete_sequence=PALETTE)
    fig.update_layout(xaxis_title="", yaxis_title="Amount", height=400)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Reconciliation status (CommBiz)")
    if len(recon_t):
        status_counts = recon_t["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig2 = px.pie(status_counts, names="status", values="count", hole=0.5,
                      color="status", color_discrete_map={"Reconciled": "#5DCAA5", "Investigate": "#E24B4A"})
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No reconciliation rows for this selection.")

st.subheader("Source system of trust transactions")
src = trust_f.groupby("source_system")["amount"].sum().abs().reset_index()
fig3 = px.bar(src, x="source_system", y="amount", color="source_system", color_discrete_sequence=PALETTE)
fig3.update_layout(showlegend=False, xaxis_title="", yaxis_title="Total absolute amount", height=320)
st.plotly_chart(fig3, use_container_width=True)

st.subheader("Trust transaction detail")
st.dataframe(trust_f.sort_values("date", ascending=False), use_container_width=True, height=350)

st.subheader("Monthly reconciliation detail (bank vs ledger)")
st.dataframe(recon_t.sort_values("period_end", ascending=False), use_container_width=True, height=300)
