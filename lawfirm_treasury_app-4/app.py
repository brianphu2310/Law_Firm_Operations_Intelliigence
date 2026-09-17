import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (load_all, money, inject_theme, kpi_card, insight_card,
                    top_slicers, filter_matters_table, filter_by_matters,
                    monthly_series, yoy_delta, PALETTE)

st.set_page_config(page_title="Treasury and Credit Strategy Dashboard", layout="wide")
inject_theme()

st.title("D'Agostino Treasury and Credit Strategy Dashboard")
st.caption(
    "Interactive overview of office account, trust account, credit cards, InfoTrack, LEAP, "
    "RapidPay, CommBiz and commission across both offices and all practice areas."
)

data = load_all()
matters = data["matters"]

# ---------------------------------------------------------------- slicer bar (full width)
loc, mtype, status, date_range = top_slicers(data, key_prefix="home")

m_f = filter_matters_table(matters, loc, mtype, status, date_range)
trust_f = filter_by_matters(data["trust"], m_f, date_range)
office_f = filter_by_matters(data["office"], m_f, date_range)
cards_f = filter_by_matters(data["cards"], m_f, date_range)
rapidpay_f = filter_by_matters(data["rapidpay"], m_f, date_range)
commission_f = filter_by_matters(data["commission"], m_f, date_range)

st.markdown("")

tab1, tab2, tab3 = st.tabs(["Treasury Overview", "Matters and Practice Areas", "Billing and Cards"])

# ======================================================================== TAB 1
with tab1:
    trust_deposits = trust_f[trust_f.type == "Deposit"]
    office_fees = office_f[office_f.type == "Fee income"]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("Trust deposits", money(trust_deposits["amount"].sum()),
                  monthly_series(trust_deposits, "date", "amount").values,
                  yoy_delta(trust_deposits, "date", "amount"), spark_color=PALETTE[0])
    with c2:
        durations = m_f.dropna(subset=["close_date"]).assign(
            days=lambda d: (d.close_date - d.open_date).dt.days)
        avg_days = durations["days"].mean() if len(durations) else 0
        kpi_card("Avg matter duration", f"{avg_days:.1f} days",
                  monthly_series(durations, "close_date", "days", "mean").values,
                  None, spark_color=PALETTE[1])
    with c3:
        kpi_card("Avg fee per matter", money(office_fees["amount"].mean() if len(office_fees) else 0),
                  monthly_series(office_fees, "date", "amount").values,
                  yoy_delta(office_fees, "date", "amount", "mean"), spark_color=PALETTE[2])
    with c4:
        kpi_card("Open matters", str((m_f.status == "Open").sum()),
                  monthly_series(m_f, "open_date", "matter_id", "count").values,
                  None, spark_color=PALETTE[3])
    with c5:
        kpi_card("RapidPay collected", money(rapidpay_f["gross_amount"].sum()),
                  monthly_series(rapidpay_f, "date", "gross_amount").values,
                  yoy_delta(rapidpay_f, "date", "gross_amount"), spark_color=PALETTE[4])

    st.markdown("")
    left, mid, right = st.columns([2.2, 1.6, 1.4])

    with left:
        st.markdown("**Matters opened by month, by practice area**")
        if len(m_f):
            m = m_f.copy()
            m["month"] = m["open_date"].dt.to_period("M").dt.to_timestamp()
            trend = m.groupby(["month", "matter_type"]).size().reset_index(name="count")
            fig = px.line(trend, x="month", y="count", color="matter_type",
                          color_discrete_sequence=PALETTE, markers=True)
            fig.update_layout(xaxis_title="", yaxis_title="", height=320, legend_title="",
                               plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                               margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No matters for this filter selection.")

    with mid:
        st.markdown("**Matters by client type**")
        if len(m_f):
            ct = m_f.client_type.value_counts().reset_index()
            ct.columns = ["client_type", "count"]
            fig2 = go.Figure(data=[go.Pie(labels=ct.client_type, values=ct["count"], hole=0.6,
                                            marker=dict(colors=PALETTE))])
            fig2.update_layout(height=320, margin=dict(t=10, l=0, r=0, b=0),
                                paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No data.")

    with right:
        if len(m_f):
            top_mtype = m_f.matter_type.value_counts().idxmax()
            top_mtype_n = m_f.matter_type.value_counts().max()
            insight_card("Top practice area", top_mtype, f"{top_mtype_n} matters ({top_mtype_n/len(m_f)*100:.1f}%)")
            top_loc = m_f.location_name.value_counts().idxmax()
            top_loc_n = m_f.location_name.value_counts().max()
            insight_card("Top office", top_loc, f"{top_loc_n} matters ({top_loc_n/len(m_f)*100:.1f}%)")
        ref = m_f[m_f.referred_matter]
        if len(ref):
            top_ref = ref.referral_source.value_counts().idxmax()
            top_ref_n = ref.referral_source.value_counts().max()
            insight_card("Top referral source", top_ref, f"{top_ref_n} matters ({top_ref_n/len(ref)*100:.1f}%)")

    st.markdown("")
    left2, right2 = st.columns([2, 1.4])
    with left2:
        st.markdown("**Matters by location and practice area**")
        if len(m_f):
            pivot = m_f.pivot_table(index="location_name", columns="matter_type",
                                     values="matter_id", aggfunc="count", fill_value=0)
            pivot["Total"] = pivot.sum(axis=1)
            pivot.loc["Total"] = pivot.sum()
            st.dataframe(pivot, use_container_width=True, height=180)
        else:
            st.info("No data.")

    with right2:
        st.markdown("**Trust disbursements by practice area**")
        t = trust_f[trust_f.type == "Disbursement payment"].merge(
            matters[["matter_id", "matter_type"]], on="matter_id", how="left")
        if len(t):
            by_type = t.groupby("matter_type")["amount"].sum().abs().sort_values().reset_index()
            fig3 = px.bar(by_type, x="amount", y="matter_type", orientation="h",
                          color="matter_type", color_discrete_sequence=PALETTE)
            fig3.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=220,
                                plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                                margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No disbursements for this filter selection.")

# ======================================================================== TAB 2
with tab2:
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Total matters", str(len(m_f)),
                  monthly_series(m_f, "open_date", "matter_id", "count").values, None, spark_color=PALETTE[0])
    with c2:
        kpi_card("Closed matters", str((m_f.status == "Closed").sum()),
                  monthly_series(m_f[m_f.status == "Closed"], "open_date", "matter_id", "count").values,
                  None, spark_color=PALETTE[1])
    with c3:
        kpi_card("Referred matters", str(int(m_f.referred_matter.sum())),
                  monthly_series(m_f[m_f.referred_matter], "open_date", "matter_id", "count").values,
                  None, spark_color=PALETTE[4])

    st.markdown("")
    left, right = st.columns(2)
    with left:
        st.markdown("**Practice area mix**")
        by_type = m_f.matter_type.value_counts().reset_index()
        by_type.columns = ["matter_type", "count"]
        fig = px.bar(by_type, x="matter_type", y="count", color="matter_type",
                     color_discrete_sequence=PALETTE)
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=340,
                           plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                           margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.markdown("**Matter status split**")
        status_ct = m_f.status.value_counts().reset_index()
        status_ct.columns = ["status", "count"]
        fig2 = go.Figure(data=[go.Pie(labels=status_ct.status, values=status_ct["count"], hole=0.6,
                                        marker=dict(colors=PALETTE))])
        fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("")
    st.markdown("**Matter detail**")
    st.dataframe(m_f[["matter_id", "client_name", "location_name", "matter_type", "status",
                       "open_date", "close_date", "fee_estimate"]].sort_values(
        "open_date", ascending=False), use_container_width=True, height=300)

# ======================================================================== TAB 3
with tab3:
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Total card spend", money(cards_f["amount"].sum()),
                  monthly_series(cards_f, "date", "amount").values,
                  yoy_delta(cards_f, "date", "amount"), spark_color=PALETTE[0])
    with c2:
        kpi_card("Total commission", money(commission_f["amount"].sum()),
                  monthly_series(commission_f, "date", "amount").values,
                  yoy_delta(commission_f, "date", "amount"), spark_color=PALETTE[1])
    with c3:
        kpi_card("RapidPay net to firm", money(rapidpay_f["net_amount"].sum()),
                  monthly_series(rapidpay_f, "date", "net_amount").values,
                  yoy_delta(rapidpay_f, "date", "net_amount"), spark_color=PALETTE[4])

    st.markdown("")
    left, right = st.columns(2)
    with left:
        st.markdown("**Amex vs Visa spend**")
        if len(cards_f):
            by_card = cards_f.groupby("card_type")["amount"].sum().reset_index()
            fig = px.bar(by_card, x="card_type", y="amount", color="card_type",
                         color_discrete_sequence=[PALETTE[0], PALETTE[2]])
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=340,
                               plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                               margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No card transactions for this filter selection.")
    with right:
        st.markdown("**Commission split by type**")
        if len(commission_f):
            cm = commission_f.groupby("commission_type")["amount"].sum().reset_index()
            fig2 = go.Figure(data=[go.Pie(labels=cm.commission_type, values=cm["amount"], hole=0.6,
                                            marker=dict(colors=PALETTE))])
            fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                                paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No commission for this filter selection.")

    st.markdown("")
    st.markdown("**Credit card transaction detail**")
    st.dataframe(cards_f.sort_values("date", ascending=False), use_container_width=True, height=300)

st.caption(
    "Use the pages in the left navigation for Trust, Office and Cards, Payments and Rails, "
    "Commission, Matters and Clients, and the Relationships and Locations map."
)
