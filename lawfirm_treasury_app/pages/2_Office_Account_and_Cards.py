import streamlit as st
import pandas as pd
import plotly.express as px
from utils import load_all, money, sidebar_filters, apply_matter_filters

st.set_page_config(page_title="Office Account & Cards", page_icon="💳", layout="wide")
st.title("💳 Office Account & Credit Cards")
st.caption("The firm's own money: fee income, operating expenses, and Amex/Visa card activity.")

data = load_all()
matters = data["matters"]

st.sidebar.header("Filters")
loc, mtype, date_range = sidebar_filters(data, key_prefix="office")

office_f = apply_matter_filters(data["office"], matters, loc, mtype, date_range)
cards_f = apply_matter_filters(data["cards"], matters, loc, mtype, date_range)
if mtype == "All":
    unmatter_cards = data["cards"][data["cards"].matter_id.isna()]
    if loc != "All":
        loc_id = data["locations"].loc[data["locations"].location_name == loc, "location_id"].iloc[0]
        unmatter_cards = unmatter_cards[unmatter_cards.location_id == loc_id]
    if len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        unmatter_cards = unmatter_cards[(unmatter_cards.date >= start) & (unmatter_cards.date <= end)]
    cards_f = pd.concat([cards_f, unmatter_cards]).drop_duplicates(subset="txn_id")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Fee income", money(office_f.loc[office_f.type == "Fee income", "amount"].sum()))
c2.metric("Operating expenses", money(-office_f.loc[office_f.type == "Expense", "amount"].sum()))
c3.metric("Amex spend", money(cards_f.loc[cards_f.card_type == "Amex", "amount"].sum()))
c4.metric("Visa spend", money(cards_f.loc[cards_f.card_type == "Visa", "amount"].sum()))

st.divider()
left, right = st.columns(2)

with left:
    st.subheader("Fee income vs expenses by month")
    o = office_f.copy()
    o["month"] = o["date"].dt.to_period("M").dt.to_timestamp()
    o_month = o.groupby(["month", "type"])["amount"].sum().reset_index()
    fig = px.bar(o_month, x="month", y="amount", color="type", barmode="relative")
    fig.update_layout(xaxis_title="", height=380)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Card spend: office expense vs trust-reimbursable disbursement")
    if len(cards_f):
        by_charge = cards_f.groupby(["card_type", "charged_to"])["amount"].sum().reset_index()
        fig2 = px.bar(by_charge, x="card_type", y="amount", color="charged_to", barmode="group")
        fig2.update_layout(xaxis_title="", height=380)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No card transactions for this selection.")

st.subheader("Expense category breakdown")
exp = office_f[office_f.type == "Expense"].groupby("category")["amount"].sum().abs().sort_values(ascending=False).reset_index()
fig3 = px.bar(exp, x="category", y="amount")
fig3.update_layout(xaxis_title="", yaxis_title="Total spend", height=320)
st.plotly_chart(fig3, use_container_width=True)

st.subheader("Office transaction detail")
st.dataframe(office_f.sort_values("date", ascending=False), use_container_width=True, height=320)

st.subheader("Credit card transaction detail")
st.dataframe(cards_f.sort_values("date", ascending=False), use_container_width=True, height=320)
