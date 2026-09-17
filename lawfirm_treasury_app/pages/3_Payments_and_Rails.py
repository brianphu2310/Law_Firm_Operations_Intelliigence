import streamlit as st
import pandas as pd
import plotly.express as px
from utils import load_all, money, sidebar_filters, apply_matter_filters

st.set_page_config(page_title="Payments & Rails", page_icon="🔄", layout="wide")
st.title("🔄 Payments & Rails: InfoTrack · RapidPay · CommBiz")
st.caption("How money physically moves: InfoTrack disbursements, RapidPay client collections, and CommBiz bank reconciliation.")

data = load_all()
matters = data["matters"]

st.sidebar.header("Filters")
loc, mtype, date_range = sidebar_filters(data, key_prefix="rails")

infotrack_f = apply_matter_filters(data["infotrack"], matters, loc, mtype, date_range)
rapidpay_f = apply_matter_filters(data["rapidpay"], matters, loc, mtype, date_range)

c1, c2, c3, c4 = st.columns(4)
c1.metric("InfoTrack disbursements", money(infotrack_f["amount"].sum()))
c2.metric("RapidPay gross collected", money(rapidpay_f["gross_amount"].sum()))
c3.metric("RapidPay merchant fees", money(rapidpay_f["merchant_fee"].sum()))
c4.metric("RapidPay net to firm", money(rapidpay_f["net_amount"].sum()))

st.divider()
left, right = st.columns(2)

with left:
    st.subheader("InfoTrack disbursements: paid from trust vs office")
    if len(infotrack_f):
        by_src = infotrack_f.groupby("paid_from")["amount"].sum().reset_index()
        fig = px.pie(by_src, names="paid_from", values="amount", hole=0.45)
        fig.update_layout(height=360)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No InfoTrack records for this selection.")

with right:
    st.subheader("RapidPay merchant fee rate by payment method")
    if len(rapidpay_f):
        rp = rapidpay_f.copy()
        rp["fee_rate_%"] = (rp["merchant_fee"] / rp["gross_amount"] * 100).round(2)
        fig2 = px.box(rp, x="payment_method", y="fee_rate_%", points="all")
        fig2.update_layout(xaxis_title="", height=360)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No RapidPay records for this selection.")

st.subheader("CommBiz reconciliation: bank balance vs ledger balance over time")
recon = data["commbiz"]
if loc != "All":
    loc_id = data["locations"].loc[data["locations"].location_name == loc, "location_id"].iloc[0]
    recon = recon[recon.location_id == loc_id]
acct_pick = st.radio("Account", ["Office", "Trust"], horizontal=True)
recon_a = recon[recon.account_type == acct_pick]
recon_month = recon_a.groupby("period_end")[["bank_balance", "ledger_balance"]].mean().reset_index()
fig3 = px.line(recon_month, x="period_end", y=["bank_balance", "ledger_balance"], markers=True)
fig3.update_layout(xaxis_title="", yaxis_title="Balance", height=380)
st.plotly_chart(fig3, use_container_width=True)

st.subheader("InfoTrack detail")
st.dataframe(infotrack_f.sort_values("date", ascending=False), use_container_width=True, height=280)

st.subheader("RapidPay detail")
st.dataframe(rapidpay_f.sort_values("date", ascending=False), use_container_width=True, height=280)
