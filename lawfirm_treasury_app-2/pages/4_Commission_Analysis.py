import streamlit as st
import pandas as pd
import plotly.express as px
from utils import load_all, money, sidebar_filters, apply_matter_filters

st.set_page_config(page_title="Commission Analysis", page_icon="📊", layout="wide")
st.title("📊 Commission Analysis")
st.caption(
    "Tracked separately: **Referral commission** (paid/earned on matters sourced via referral partners) "
    "and **Merchant fee commission** (RapidPay's processing cut on card-collected invoices)."
)

data = load_all()
matters = data["matters"]

st.sidebar.header("Filters")
loc, mtype, date_range = sidebar_filters(data, key_prefix="comm")

commission_f = apply_matter_filters(data["commission"], matters, loc, mtype, date_range)

c1, c2, c3 = st.columns(3)
referral = commission_f[commission_f.commission_type == "Referral"]["amount"].sum()
merchant = commission_f[commission_f.commission_type == "Merchant fee (RapidPay)"]["amount"].sum()
c1.metric("Referral commission", money(referral))
c2.metric("Merchant fee commission", money(merchant))
c3.metric("Combined total", money(referral + merchant))

st.divider()
left, right = st.columns(2)

with left:
    st.subheader("Commission by month and type")
    cm = commission_f.copy()
    cm["month"] = cm["date"].dt.to_period("M").dt.to_timestamp()
    cm_month = cm.groupby(["month", "commission_type"])["amount"].sum().reset_index()
    fig = px.bar(cm_month, x="month", y="amount", color="commission_type", barmode="stack")
    fig.update_layout(xaxis_title="", height=380)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Referral commission by source")
    ref = commission_f[commission_f.commission_type == "Referral"]
    if len(ref):
        by_source = ref.groupby("source")["amount"].sum().sort_values(ascending=False).reset_index()
        fig2 = px.bar(by_source, x="source", y="amount")
        fig2.update_layout(xaxis_title="", height=380)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No referral commission for this selection.")

st.subheader("Commission by location")
by_loc = commission_f.merge(data["locations"], on="location_id", how="left")
by_loc = by_loc.groupby(["location_name", "commission_type"])["amount"].sum().reset_index()
fig3 = px.bar(by_loc, x="location_name", y="amount", color="commission_type", barmode="group")
fig3.update_layout(xaxis_title="", height=340)
st.plotly_chart(fig3, use_container_width=True)

st.subheader("Commission detail")
st.dataframe(commission_f.sort_values("date", ascending=False), use_container_width=True, height=320)
