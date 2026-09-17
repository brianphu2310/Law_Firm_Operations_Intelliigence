import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (load_all, money, sidebar_filters, filter_transactions,
                    inject_theme, kpi_card, insight_card, flow_kpi, PALETTE)

st.set_page_config(page_title="Office Account and Cards", layout="wide")
inject_theme()

st.title("Office Account and Cards")
st.caption("The firm's own money: fee income, operating expenses, and Amex/Visa card activity.")

data = load_all()
matters = data["matters"]

st.sidebar.header("Filters")
loc, mtype, status, date_range = sidebar_filters(data, key_prefix="office")

office_f = filter_transactions(data["office"], matters, loc, mtype, status, date_range)
cards_f = filter_transactions(data["cards"], matters, loc, mtype, status, date_range)

fee_income = office_f[office_f.type == "Fee income"]
expenses = office_f[office_f.type == "Expense"]

# ---------------------------------------------------------------- KPI row
c1, c2, c3 = st.columns(3)
with c1:
    flow_kpi(fee_income, "date", "amount", "Fee income", spark_color=PALETTE[0])
with c2:
    flow_kpi(expenses, "date", "amount", "Operating expenses",
              spark_color=PALETTE[2], magnitude=True, invert_color=True)
with c3:
    flow_kpi(cards_f, "date", "amount", "Total card spend",
              spark_color=PALETTE[4], magnitude=False, invert_color=True)

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
        by_cat = cards_f.groupby("charged_to")["amount"].sum()
        insight_card("Largest card spend category", by_cat.idxmax(), f"{money(by_cat.max())} charged")
    if len(expenses):
        by_exp = expenses.groupby("category")["amount"].sum().abs()
        insight_card("Top expense category", by_exp.idxmax(), f"{money(by_exp.max())} spent")
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
