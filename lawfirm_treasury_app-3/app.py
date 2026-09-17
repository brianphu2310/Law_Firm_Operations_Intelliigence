import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from utils import load_all, money, inject_theme, kpi_card, insight_card, PALETTE, ACCENT

st.set_page_config(page_title="Treasury & Credit Strategy Dashboard", page_icon="⚖️", layout="wide")
inject_theme()

data = load_all()
matters = data["matters"]
trust = data["trust"]
office = data["office"]
commission = data["commission"]

# ---------------------------------------------------------------- top bar / tabs
top_l, top_r = st.columns([3, 2])
with top_l:
    tab = st.tabs(["🏦 Treasury Overview", "📁 Matters & Practice Areas", "🧾 Billing & Cards"])
with top_r:
    st.markdown(
        """
        <div style="text-align:right; padding-top:6px;">
            <span style="color:#7A8A99;">Welcome to</span><br/>
            <span style="font-size:1.3rem; font-weight:700; color:#1F3B4D;">
                D'Agostino Treasury Dashboard
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------- YoY helper
def yoy_delta(df, date_col, value_col, agg="sum"):
    df = df.copy()
    df["year"] = df[date_col].dt.year
    g = df.groupby("year")[value_col].agg(agg)
    if 2024 in g.index and 2025 in g.index and g[2024] != 0:
        return (g[2025] - g[2024]) / abs(g[2024]) * 100
    return None


def monthly_series(df, date_col, value_col, agg="sum"):
    df = df.copy()
    df["month"] = df[date_col].dt.to_period("M").dt.to_timestamp()
    return df.groupby("month")[value_col].agg(agg).sort_index()


with tab[0]:
    st.markdown("#### Treasury Overview")

    trust_deposits = trust[trust.type == "Deposit"]
    office_fees = office[office.type == "Fee income"]
    card_spend = data["cards"]["amount"]
    rp = data["rapidpay"]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        s = monthly_series(trust_deposits, "date", "amount")
        kpi_card("Trust Deposits", money(trust_deposits["amount"].sum()), s.values,
                  yoy_delta(trust_deposits, "date", "amount"))
    with c2:
        avg_matter_days = (matters.close_date - matters.open_date).dt.days.dropna()
        s = monthly_series(matters.dropna(subset=["close_date"]).assign(
            days=(matters.close_date - matters.open_date).dt.days), "close_date", "days", "mean")
        kpi_card("Avg Matter Duration", f"{avg_matter_days.mean():.1f} days", s.values, None, spark_color=PALETTE[1])
    with c3:
        s = monthly_series(office_fees, "date", "amount")
        kpi_card("Avg Fee per Matter", money(office_fees["amount"].mean()), s.values,
                  yoy_delta(office_fees, "date", "amount", "mean"), spark_color=PALETTE[2])
    with c4:
        s = monthly_series(matters, "open_date", "matter_id", "count")
        kpi_card("Open Matters", str((matters.status == "Open").sum()), s.values, None, spark_color=PALETTE[3])
    with c5:
        s = monthly_series(rp, "date", "gross_amount")
        kpi_card("RapidPay Collected", money(rp["gross_amount"].sum()), s.values,
                  yoy_delta(rp, "date", "gross_amount"), spark_color=PALETTE[4])

    st.markdown("")
    left, mid, right = st.columns([2.2, 1.6, 1.4])

    with left:
        st.markdown("**Matters Opened Trend by Month**")
        m = matters.copy()
        m["month"] = m["open_date"].dt.to_period("M").dt.to_timestamp()
        m["month_label"] = m["month"].dt.strftime("%b")
        trend = m.groupby(["month_label", "matter_type"]).size().reset_index(name="count")
        month_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        fig = px.line(trend, x="month_label", y="count", color="matter_type",
                       category_orders={"month_label": month_order},
                       color_discrete_sequence=PALETTE, markers=True)
        fig.update_layout(xaxis_title="", yaxis_title="", height=300, legend_title="",
                           plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                           margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with mid:
        st.markdown("**Matters by Client Type**")
        ct = matters.client_type.value_counts().reset_index()
        ct.columns = ["client_type", "count"]
        fig2 = go.Figure(data=[go.Pie(labels=ct.client_type, values=ct["count"], hole=0.6,
                                        marker=dict(colors=PALETTE))])
        fig2.update_layout(height=300, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)

    with right:
        top_mtype = matters.matter_type.value_counts().idxmax()
        top_mtype_n = matters.matter_type.value_counts().max()
        insight_card("Top Practice Area", top_mtype,
                     f"{top_mtype_n} matters ({top_mtype_n/len(matters)*100:.1f}%) were {top_mtype}")

        top_loc = matters.location_name.value_counts().idxmax()
        top_loc_n = matters.location_name.value_counts().max()
        insight_card("Top Office", top_loc,
                     f"{top_loc_n} matters ({top_loc_n/len(matters)*100:.1f}%) opened at {top_loc}")

        ref = matters[matters.referred_matter]
        if len(ref):
            top_ref = ref.referral_source.value_counts().idxmax()
            top_ref_n = ref.referral_source.value_counts().max()
            insight_card("Top Referral Source", top_ref,
                         f"{top_ref_n} matters ({top_ref_n/len(ref)*100:.1f}%) referred by {top_ref}")

    st.markdown("")
    left2, right2 = st.columns([2, 1.4])
    with left2:
        st.markdown("**Matters by Location & Practice Area**")
        pivot = matters.pivot_table(index="location_name", columns="matter_type",
                                     values="matter_id", aggfunc="count", fill_value=0)
        pivot["Total"] = pivot.sum(axis=1)
        pivot.loc["Total"] = pivot.sum()
        st.dataframe(pivot, use_container_width=True, height=180)

    with right2:
        st.markdown("**Trust Disbursements by Practice Area**")
        t = trust[trust.type == "Disbursement payment"].merge(
            matters[["matter_id", "matter_type"]], on="matter_id", how="left")
        by_type = t.groupby("matter_type")["amount"].sum().abs().sort_values().reset_index()
        fig3 = px.bar(by_type, x="amount", y="matter_type", orientation="h",
                       color="matter_type", color_discrete_sequence=PALETTE)
        fig3.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=220,
                            plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig3, use_container_width=True)

with tab[1]:
    st.markdown("#### Matters & Practice Areas")
    c1, c2 = st.columns(2)
    with c1:
        by_type = matters.matter_type.value_counts().reset_index()
        by_type.columns = ["matter_type", "count"]
        fig = px.bar(by_type, x="matter_type", y="count", color="matter_type",
                     color_discrete_sequence=PALETTE)
        fig.update_layout(showlegend=False, xaxis_title="", height=340,
                           plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        status_ct = matters.status.value_counts().reset_index()
        status_ct.columns = ["status", "count"]
        fig2 = px.pie(status_ct, names="status", values="count", hole=0.5,
                      color_discrete_sequence=PALETTE)
        fig2.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(matters[["matter_id", "client_name", "location_name", "matter_type", "status",
                           "open_date", "close_date", "fee_estimate"]].sort_values(
        "open_date", ascending=False), use_container_width=True, height=320)

with tab[2]:
    st.markdown("#### Billing & Cards")
    c1, c2 = st.columns(2)
    with c1:
        cc = data["cards"].copy()
        by_card = cc.groupby("card_type")["amount"].sum().reset_index()
        fig = px.bar(by_card, x="card_type", y="amount", color="card_type",
                     color_discrete_sequence=[PALETTE[0], PALETTE[2]])
        fig.update_layout(showlegend=False, xaxis_title="", height=340,
                           plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        cm = commission.groupby("commission_type")["amount"].sum().reset_index()
        fig2 = px.pie(cm, names="commission_type", values="amount", hole=0.5,
                      color_discrete_sequence=PALETTE)
        fig2.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(data["cards"].sort_values("date", ascending=False), use_container_width=True, height=320)

st.caption(
    "Use the pages in the left navigation for Trust, Office & Cards, Payments & Rails, Commission, "
    "Matters & Clients, and the Relationships & Locations map."
)
