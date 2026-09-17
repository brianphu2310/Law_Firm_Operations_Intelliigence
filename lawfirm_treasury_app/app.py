import streamlit as st
import pandas as pd
import plotly.express as px
from utils import load_all, money, sidebar_filters, apply_matter_filters

st.set_page_config(page_title="Treasury & Credit Strategy Dashboard", page_icon="⚖️", layout="wide")

st.title("⚖️ Law Firm Treasury & Credit Strategy Dashboard")
st.caption(
    "Synthetic demo data modelling the relationship between office account, trust account, "
    "credit cards (Amex/Visa), InfoTrack, LEAP, RapidPay, CommBiz, commission, locations, "
    "matter types, clients and counsel."
)

data = load_all()
matters = data["matters"]

st.sidebar.header("Filters")
loc, mtype, date_range = sidebar_filters(data, key_prefix="home")

trust_f = apply_matter_filters(data["trust"], matters, loc, mtype, date_range)
office_f = apply_matter_filters(data["office"], matters, loc, mtype, date_range)
cards_f = apply_matter_filters(data["cards"], matters, loc, mtype, date_range)
rapidpay_f = apply_matter_filters(data["rapidpay"], matters, loc, mtype, date_range)
commission_f = apply_matter_filters(data["commission"], matters, loc, mtype, date_range)

m_f = matters.copy()
if loc != "All":
    m_f = m_f[m_f.location_name == loc]
if mtype != "All":
    m_f = m_f[m_f.matter_type == mtype]

# ---------------------------------------------------------------- KPIs
c1, c2, c3, c4, c5 = st.columns(5)
trust_net = trust_f["amount"].sum()
office_net = office_f["amount"].sum()
card_spend = cards_f["amount"].sum()
rp_gross = rapidpay_f["gross_amount"].sum() if len(rapidpay_f) else 0
commission_total = commission_f["amount"].sum()

c1.metric("Trust account net movement", money(trust_net))
c2.metric("Office account net movement", money(office_net))
c3.metric("Credit card spend (Amex+Visa)", money(card_spend))
c4.metric("RapidPay collections (gross)", money(rp_gross))
c5.metric("Commission (referral + merchant fee)", money(commission_total))

st.divider()

# ---------------------------------------------------------------- charts row 1
left, right = st.columns(2)

with left:
    st.subheader("Trust vs office movement by matter type")
    t = trust_f.merge(matters[["matter_id", "matter_type"]], on="matter_id", how="left")
    o = office_f.merge(matters[["matter_id", "matter_type"]], on="matter_id", how="left")
    t_sum = t.groupby("matter_type")["amount"].sum().rename("Trust")
    o_sum = o.groupby("matter_type")["amount"].sum().rename("Office")
    combo = pd.concat([t_sum, o_sum], axis=1).fillna(0).reset_index()
    combo_long = combo.melt(id_vars="matter_type", var_name="Account", value_name="Net amount")
    fig = px.bar(combo_long, x="matter_type", y="Net amount", color="Account", barmode="group")
    fig.update_layout(xaxis_title="", height=380)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Credit card spend: Amex vs Visa over time")
    cc = cards_f.copy()
    cc["month"] = cc["date"].dt.to_period("M").dt.to_timestamp()
    cc_month = cc.groupby(["month", "card_type"])["amount"].sum().reset_index()
    fig2 = px.line(cc_month, x="month", y="amount", color="card_type", markers=True)
    fig2.update_layout(xaxis_title="", yaxis_title="Spend", height=380)
    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------- charts row 2
left2, right2 = st.columns(2)

with left2:
    st.subheader("Commission split by type")
    if len(commission_f):
        cm = commission_f.groupby("commission_type")["amount"].sum().reset_index()
        fig3 = px.pie(cm, names="commission_type", values="amount", hole=0.45)
        fig3.update_layout(height=360)
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No commission records for this filter selection.")

with right2:
    st.subheader("Matters by location")
    mloc = m_f.groupby("location_name").size().reset_index(name="matters")
    fig4 = px.bar(mloc, x="location_name", y="matters")
    fig4.update_layout(xaxis_title="", height=360)
    st.plotly_chart(fig4, use_container_width=True)

st.divider()
st.subheader("Matter list (filtered)")
show_cols = ["matter_id", "client_name", "location_name", "matter_type", "status",
             "open_date", "close_date", "fee_estimate", "referred_matter", "referral_source"]
st.dataframe(m_f[show_cols].sort_values("open_date", ascending=False), use_container_width=True, height=320)

st.caption(
    "Use the sidebar to filter by location, matter type and date range — every chart and table "
    "on this page updates together. See the pages in the left navigation for Trust, Office & Cards, "
    "Payments & Rails, Commission, and Matters & Clients detail views."
)
