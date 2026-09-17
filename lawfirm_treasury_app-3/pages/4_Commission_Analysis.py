import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (load_all, money, sidebar_filters, apply_matter_filters,
                    inject_theme, kpi_card, insight_card, PALETTE)

st.set_page_config(page_title="Commission Analysis", page_icon="📊", layout="wide")
inject_theme()

st.title("📊 Commission Analysis")
st.caption(
    "Tracked separately: **Referral commission** (matters sourced via referral partners) and "
    "**Merchant fee commission** (RapidPay's processing cut on card-collected invoices)."
)

data = load_all()
matters = data["matters"]

st.sidebar.header("Filters")
loc, mtype, date_range = sidebar_filters(data, key_prefix="comm")

commission_f = apply_matter_filters(data["commission"], matters, loc, mtype, date_range)


def monthly_series(df, date_col, value_col):
    d = df.copy()
    d["month"] = d[date_col].dt.to_period("M").dt.to_timestamp()
    return d.groupby("month")[value_col].sum().sort_index()


def yoy(df, date_col, value_col):
    d = df.copy()
    d["year"] = d[date_col].dt.year
    g = d.groupby("year")[value_col].sum()
    if 2024 in g.index and 2025 in g.index and g[2024] != 0:
        return (g[2025] - g[2024]) / abs(g[2024]) * 100
    return None


referral_df = commission_f[commission_f.commission_type == "Referral"]
merchant_df = commission_f[commission_f.commission_type == "Merchant fee (RapidPay)"]

c1, c2, c3 = st.columns(3)
with c1:
    kpi_card("Referral commission", money(referral_df["amount"].sum()),
              monthly_series(referral_df, "date", "amount").values if len(referral_df) else [0, 0],
              yoy(referral_df, "date", "amount"), spark_color=PALETTE[0])
with c2:
    kpi_card("Merchant fee commission", money(merchant_df["amount"].sum()),
              monthly_series(merchant_df, "date", "amount").values if len(merchant_df) else [0, 0],
              yoy(merchant_df, "date", "amount"), spark_color=PALETTE[1])
with c3:
    kpi_card("Combined commission", money(commission_f["amount"].sum()),
              monthly_series(commission_f, "date", "amount").values if len(commission_f) else [0, 0],
              yoy(commission_f, "date", "amount"), spark_color=PALETTE[4])

st.markdown("")
left, mid, right = st.columns([2, 1.4, 1.4])

with left:
    st.markdown("**Commission by month and type**")
    cm = commission_f.copy()
    cm["month"] = cm["date"].dt.to_period("M").dt.to_timestamp()
    cm_month = cm.groupby(["month", "commission_type"])["amount"].sum().reset_index()
    fig = px.bar(cm_month, x="month", y="amount", color="commission_type",
                 color_discrete_sequence=PALETTE, barmode="stack")
    fig.update_layout(xaxis_title="", height=340, legend_title="", plot_bgcolor="white",
                       paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

with mid:
    st.markdown("**Split by type**")
    cm2 = commission_f.groupby("commission_type")["amount"].sum().reset_index()
    fig2 = go.Figure(data=[go.Pie(labels=cm2.commission_type, values=cm2["amount"], hole=0.6,
                                    marker=dict(colors=PALETTE))])
    fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig2, use_container_width=True)

with right:
    if len(referral_df):
        top_src = referral_df.groupby("source")["amount"].sum().idxmax()
        top_src_amt = referral_df.groupby("source")["amount"].sum().max()
        insight_card("Top referral partner", top_src,
                     f"{money(top_src_amt)} in referral commission generated")
    by_loc_top = commission_f.merge(data["locations"], on="location_id", how="left")
    if len(by_loc_top):
        top_loc = by_loc_top.groupby("location_name")["amount"].sum().idxmax()
        top_loc_amt = by_loc_top.groupby("location_name")["amount"].sum().max()
        insight_card("Top office by commission", top_loc, f"{money(top_loc_amt)} total commission")
    if len(merchant_df):
        avg_rate = (merchant_df["amount"].sum() /
                    data["rapidpay"].loc[data["rapidpay"].matter_id.isin(merchant_df.matter_id), "gross_amount"].sum() * 100)
        insight_card("Avg RapidPay merchant fee rate", f"{avg_rate:.2f}%",
                     "Blended across Visa, Amex & Mastercard collections")

st.markdown("")
st.markdown("**Commission by location**")
by_loc = commission_f.merge(data["locations"], on="location_id", how="left")
by_loc = by_loc.groupby(["location_name", "commission_type"])["amount"].sum().reset_index()
fig3 = px.bar(by_loc, x="location_name", y="amount", color="commission_type",
              color_discrete_sequence=PALETTE, barmode="group")
fig3.update_layout(xaxis_title="", height=320, legend_title="", plot_bgcolor="white",
                    paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=10, l=0, r=0, b=0))
st.plotly_chart(fig3, use_container_width=True)

st.markdown("**Commission detail**")
st.dataframe(commission_f.sort_values("date", ascending=False), use_container_width=True, height=320)
