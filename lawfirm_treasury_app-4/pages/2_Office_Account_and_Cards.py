import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (load_all, money, sidebar_filters, apply_matter_filters,
                    inject_theme, kpi_card, insight_card, monthly_series, yoy_delta, PALETTE)

st.set_page_config(page_title="Office Account and Cards", layout="wide")
inject_theme()

st.title("Office Account and Cards")
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

fee_income = office_f[office_f.type == "Fee income"]
expenses = office_f[office_f.type == "Expense"]

# ---------------------------------------------------------------- KPI row
c1, c2, c3 = st.columns(3)
with c1:
    kpi_card("Fee income", money(fee_income["amount"].sum()),
              monthly_series(fee_income, "date", "amount").values,
              yoy_delta(fee_income, "date", "amount"), spark_color=PALETTE[0])
with c2:
    kpi_card("Operating expenses", money(-expenses["amount"].sum()),
              monthly_series(expenses, "date", "amount").abs().values,
              yoy_delta(expenses, "date", "amount"), spark_color=PALETTE[2])
with c3:
    kpi_card("Total card spend", money(cards_f["amount"].sum()),
              monthly_series(cards_f, "date", "amount").values,
              yoy_delta(cards_f, "date", "amount"), spark_color=PALETTE[4])

st.markdown("")

# ---------------------------------------------------------------- left / mid / right
left, mid, right = st.columns([2, 1.4, 1.4])

with left:
    st.markdown("**Fee income vs expenses by month**")
    if len(office_f):
        o = office_f.copy()
        o["month"] = o["date"].dt.to_period("M").dt.to_timestamp()
        o_month = o.groupby(["month", "type"])["amount"].sum().reset_index()
        fig = px.bar(o_month, x="month", y="amount", color="type",
                     color_discrete_sequence=PALETTE, barmode="relative")
        fig.update_layout(xaxis_title="", yaxis_title="", height=340, legend_title="",
                           plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                           margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No office transactions for this filter selection.")

with mid:
    st.markdown("**Amex vs Visa split**")
    if len(cards_f):
        by_card = cards_f.groupby("card_type")["amount"].sum().reset_index()
        fig2 = go.Figure(data=[go.Pie(labels=by_card.card_type, values=by_card["amount"], hole=0.6,
                                        marker=dict(colors=[PALETTE[0], PALETTE[2]]))])
        fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No card transactions for this selection.")

with right:
    if len(cards_f):
        top_cat = cards_f.groupby("charged_to")["amount"].sum().idxmax()
        top_cat_amt = cards_f.groupby("charged_to")["amount"].sum().max()
        insight_card("Largest card spend category", top_cat, f"{money(top_cat_amt)} charged")
    if len(expenses):
        top_exp = expenses.groupby("category")["amount"].sum().abs().idxmax()
        top_exp_amt = expenses.groupby("category")["amount"].sum().abs().max()
        insight_card("Top expense category", top_exp, f"{money(top_exp_amt)} spent")
    if len(fee_income):
        insight_card("Avg fee per matter", money(fee_income["amount"].mean()),
                     f"Across {len(fee_income)} billed matters")

st.markdown("")

# ---------------------------------------------------------------- breakdown chart
st.markdown("**Expense category breakdown**")
if len(expenses):
    exp = expenses.groupby("category")["amount"].sum().abs().sort_values(ascending=False).reset_index()
    fig3 = px.bar(exp, x="category", y="amount", color_discrete_sequence=PALETTE)
    fig3.update_layout(xaxis_title="", yaxis_title="", height=300,
                        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No expense transactions for this filter selection.")

st.markdown("")

# ---------------------------------------------------------------- detail tables
st.markdown("**Office transaction detail**")
st.dataframe(office_f.sort_values("date", ascending=False), use_container_width=True, height=300)

st.markdown("**Credit card transaction detail**")
st.dataframe(cards_f.sort_values("date", ascending=False), use_container_width=True, height=300)
