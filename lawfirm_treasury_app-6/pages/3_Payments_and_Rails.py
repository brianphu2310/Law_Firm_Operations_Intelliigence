import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (load_all, money, sidebar_filters, filter_transactions,
                    inject_theme, kpi_card, insight_card, flow_kpi, PALETTE)

st.set_page_config(page_title="Payments and Rails", layout="wide")
inject_theme()

st.title("Payments and Rails: InfoTrack, RapidPay, CommBiz")
st.caption("How money physically moves: InfoTrack disbursements, RapidPay client collections, and CommBiz bank reconciliation.")

data = load_all()
matters = data["matters"]

st.sidebar.header("Filters")
loc, mtype, status, date_range = sidebar_filters(data, key_prefix="rails")

infotrack_f = filter_transactions(data["infotrack"], matters, loc, mtype, status, date_range)
rapidpay_f = filter_transactions(data["rapidpay"], matters, loc, mtype, status, date_range)

# ---------------------------------------------------------------- KPI row
c1, c2, c3 = st.columns(3)
with c1:
    flow_kpi(infotrack_f, "date", "amount", "InfoTrack disbursements",
              spark_color=PALETTE[0], invert_color=True)
with c2:
    flow_kpi(rapidpay_f, "date", "gross_amount", "RapidPay gross collected", spark_color=PALETTE[1])
with c3:
    flow_kpi(rapidpay_f, "date", "merchant_fee", "RapidPay merchant fees",
              spark_color=PALETTE[2], invert_color=True)

st.markdown("")

# ---------------------------------------------------------------- left / mid / right
left, mid, right = st.columns([2, 1.4, 1.4])

with left:
    st.markdown("**RapidPay collections by month**")
    if len(rapidpay_f):
        rp = rapidpay_f.copy()
        rp["month"] = rp["date"].dt.to_period("M").dt.to_timestamp()
        rp_month = rp.groupby("month")[["net_amount", "merchant_fee"]].sum().reset_index()
        fig = px.bar(rp_month, x="month", y=["net_amount", "merchant_fee"],
                     color_discrete_sequence=PALETTE, barmode="stack")
        fig.update_layout(xaxis_title="", yaxis_title="", height=340, legend_title="",
                           plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                           margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No RapidPay records for this selection.")

with mid:
    st.markdown("**InfoTrack: paid from trust vs office**")
    if len(infotrack_f):
        by_src = infotrack_f.groupby("paid_from")["amount"].sum().reset_index()
        fig2 = go.Figure(data=[go.Pie(labels=by_src.paid_from, values=by_src["amount"], hole=0.6,
                                        marker=dict(colors=PALETTE))])
        fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No InfoTrack records for this selection.")

with right:
    if len(rapidpay_f):
        rp2 = rapidpay_f.copy()
        rp2["fee_rate"] = rp2["merchant_fee"] / rp2["gross_amount"] * 100
        by_method = rp2.groupby("payment_method")["fee_rate"].mean()
        insight_card("Highest merchant fee rate", by_method.idxmax(), f"{by_method.max():.2f}% average fee rate")
    if len(infotrack_f):
        by_service = infotrack_f.groupby("service_type")["amount"].sum()
        insight_card("Top InfoTrack service", by_service.idxmax(), f"{money(by_service.max())} in disbursements")
    recon_all = data["commbiz"]
    if loc != "All":
        loc_id = data["locations"].loc[data["locations"].location_name == loc, "location_id"].iloc[0]
        recon_all = recon_all[recon_all.location_id == loc_id]
    reconciled = recon_all[recon_all.status == "Reconciled"]
    total_recon = len(recon_all)
    rate = len(reconciled) / total_recon * 100 if total_recon else 0
    insight_card("CommBiz reconciliation rate", f"{rate:.1f}%",
                 f"{len(reconciled)} of {total_recon} monthly reconciliations clean")

st.markdown("")

# ---------------------------------------------------------------- breakdown chart
st.markdown("**CommBiz reconciliation: bank balance vs ledger balance by month**")
recon = data["commbiz"]
if loc != "All":
    loc_id = data["locations"].loc[data["locations"].location_name == loc, "location_id"].iloc[0]
    recon = recon[recon.location_id == loc_id]
acct_pick = st.radio("Account", ["Office", "Trust"], horizontal=True, key="rails_acct")
recon_a = recon[recon.account_type == acct_pick]
if len(recon_a):
    recon_month = recon_a.groupby("period_end")[["bank_balance", "ledger_balance"]].mean().reset_index()
    fig3 = px.line(recon_month, x="period_end", y=["bank_balance", "ledger_balance"],
                   markers=True, color_discrete_sequence=PALETTE)
    fig3.update_layout(xaxis_title="", yaxis_title="", height=320, legend_title="",
                        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No reconciliation rows for this selection.")

st.markdown("")

# ---------------------------------------------------------------- detail tables
st.markdown("**InfoTrack detail**")
st.dataframe(infotrack_f.sort_values("date", ascending=False), use_container_width=True, height=280)

st.markdown("**RapidPay detail**")
st.dataframe(rapidpay_f.sort_values("date", ascending=False), use_container_width=True, height=280)
