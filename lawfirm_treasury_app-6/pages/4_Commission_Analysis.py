import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (load_all, money, sidebar_filters, filter_transactions,
                    inject_theme, kpi_card, insight_card, flow_kpi, PALETTE)

st.set_page_config(page_title="Commission Analysis", layout="wide")
inject_theme()

st.title("Commission Analysis")
st.caption(
    "Tracked separately: referral commission (paid out to referral partners on sourced matters) and "
    "merchant fee commission (RapidPay's processing cut on card-collected invoices). Both are shown "
    "as costs to the firm - a rise is flagged in red, a fall in green."
)

data = load_all()
matters = data["matters"]

st.sidebar.header("Filters")
loc, mtype, status, date_range = sidebar_filters(data, key_prefix="comm")

commission_f = filter_transactions(data["commission"], matters, loc, mtype, status, date_range)
referral_df = commission_f[commission_f.commission_type == "Referral"]
merchant_df = commission_f[commission_f.commission_type == "Merchant fee (RapidPay)"]

# ---------------------------------------------------------------- KPI row
c1, c2, c3 = st.columns(3)
with c1:
    flow_kpi(referral_df, "date", "amount", "Referral commission", spark_color=PALETTE[0], invert_color=True)
with c2:
    flow_kpi(merchant_df, "date", "amount", "Merchant fee commission", spark_color=PALETTE[1], invert_color=True)
with c3:
    flow_kpi(commission_f, "date", "amount", "Combined commission", spark_color=PALETTE[4], invert_color=True)

st.markdown("")

# ---------------------------------------------------------------- left / mid / right
left, mid, right = st.columns([2, 1.4, 1.4])

with left:
    st.markdown("**Commission by month and type**")
    if len(commission_f):
        cm = commission_f.copy()
        cm["month"] = cm["date"].dt.to_period("M").dt.to_timestamp()
        cm_month = cm.groupby(["month", "commission_type"])["amount"].sum().reset_index()
        fig = px.bar(cm_month, x="month", y="amount", color="commission_type",
                     color_discrete_sequence=PALETTE, barmode="stack")
        fig.update_layout(xaxis_title="", yaxis_title="", height=340, legend_title="",
                           plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                           margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No commission records for this filter selection.")

with mid:
    st.markdown("**Split by type**")
    if len(commission_f):
        cm2 = commission_f.groupby("commission_type")["amount"].sum().reset_index()
        fig2 = go.Figure(data=[go.Pie(labels=cm2.commission_type, values=cm2["amount"], hole=0.6,
                                        marker=dict(colors=PALETTE))])
        fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No data.")

with right:
    if len(referral_df):
        by_src = referral_df.groupby("source")["amount"].sum()
        insight_card("Top referral partner", by_src.idxmax(), f"{money(by_src.max())} in referral commission paid")
    else:
        insight_card("Top referral partner", "None", "No referral commission for this selection")

    by_loc_top = commission_f.merge(data["locations"], on="location_id", how="left")
    if len(by_loc_top):
        by_loc = by_loc_top.groupby("location_name")["amount"].sum()
        insight_card("Top office by commission", by_loc.idxmax(), f"{money(by_loc.max())} total commission")

    if len(merchant_df):
        gross_total = data["rapidpay"].loc[
            data["rapidpay"].matter_id.isin(merchant_df.matter_id), "gross_amount"].sum()
        avg_rate = (merchant_df["amount"].sum() / gross_total * 100) if gross_total else 0
        insight_card("Avg RapidPay merchant fee rate", f"{avg_rate:.2f}%",
                     "Blended across Visa, Amex and Mastercard collections")

st.markdown("")

# ---------------------------------------------------------------- breakdown chart
st.markdown("**Commission by location**")
by_loc = commission_f.merge(data["locations"], on="location_id", how="left")
if len(by_loc):
    by_loc = by_loc.groupby(["location_name", "commission_type"])["amount"].sum().reset_index()
    fig3 = px.bar(by_loc, x="location_name", y="amount", color="commission_type",
                  color_discrete_sequence=PALETTE, barmode="group")
    fig3.update_layout(xaxis_title="", yaxis_title="", height=320, legend_title="",
                        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No commission records for this filter selection.")

st.markdown("")

# ---------------------------------------------------------------- detail table
st.markdown("**Commission detail**")
st.dataframe(commission_f.sort_values("date", ascending=False), use_container_width=True, height=320)
