import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (load_all, money, inject_theme, kpi_card, insight_card, flow_kpi,
                    top_slicers, filter_matters, filter_transactions,
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

m_f = filter_matters(matters, loc, mtype, status, date_range)
trust_f = filter_transactions(data["trust"], matters, loc, mtype, status, date_range)
office_f = filter_transactions(data["office"], matters, loc, mtype, status, date_range)
cards_f = filter_transactions(data["cards"], matters, loc, mtype, status, date_range)
rapidpay_f = filter_transactions(data["rapidpay"], matters, loc, mtype, status, date_range)
commission_f = filter_transactions(data["commission"], matters, loc, mtype, status, date_range)

st.markdown("")

tab1, tab2, tab3 = st.tabs(["Treasury Overview", "Matters and Practice Areas", "Billing and Cards"])

# ======================================================================== TAB 1
with tab1:
    trust_deposits = trust_f[trust_f.type == "Deposit"]
    office_fees = office_f[office_f.type == "Fee income"]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        flow_kpi(trust_deposits, "date", "amount", "Trust deposits", spark_color=PALETTE[0])
    with c2:
        durations = m_f.dropna(subset=["close_date"]).assign(
            days=lambda d: (d.close_date - d.open_date).dt.days)
        avg_days = durations["days"].mean() if len(durations) else 0
        kpi_card("Avg matter duration", f"{avg_days:.1f} days",
                  monthly_series(durations, "close_date", "days", "mean").values,
                  None, spark_color=PALETTE[1])
    with c3:
        flow_kpi(office_fees, "date", "amount", "Avg fee per matter",
                  spark_color=PALETTE[2], agg="mean")
    with c4:
        open_m = m_f[m_f.status == "Open"]
        kpi_card("Open matters", str(len(open_m)),
                  monthly_series(open_m, "open_date", "matter_id", "count").values,
                  None, spark_color=PALETTE[3])
    with c5:
        flow_kpi(rapidpay_f, "date", "gross_amount", "RapidPay collected", spark_color=PALETTE[4])

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
            by_type = m_f.matter_type.value_counts()
            insight_card("Top practice area", by_type.idxmax(),
                         f"{by_type.max()} matters ({by_type.max()/len(m_f)*100:.1f}%)")
            by_loc = m_f.location_name.value_counts()
            insight_card("Top office", by_loc.idxmax(),
                         f"{by_loc.max()} matters ({by_loc.max()/len(m_f)*100:.1f}%)")
        ref = m_f[m_f.referred_matter]
        if len(ref):
            by_ref = ref.referral_source.value_counts()
            insight_card("Top referral source", by_ref.idxmax(),
                         f"{by_ref.max()} matters ({by_ref.max()/len(ref)*100:.1f}%)")

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
                  monthly_series(m_f, "open_date", "matter_id", "count").values,
                  yoy_delta(m_f, "open_date", "matter_id", "count"), spark_color=PALETTE[0])
    with c2:
        closed_m = m_f[m_f.status == "Closed"]
        kpi_card("Closed matters", str(len(closed_m)),
                  monthly_series(closed_m, "open_date", "matter_id", "count").values,
                  None, spark_color=PALETTE[1])
    with c3:
        ref_m = m_f[m_f.referred_matter]
        kpi_card("Referred matters", str(len(ref_m)),
                  monthly_series(ref_m, "open_date", "matter_id", "count").values,
                  None, spark_color=PALETTE[4])

    st.markdown("")
    left, right = st.columns(2)
    with left:
        st.markdown("**Practice area mix**")
        if len(m_f):
            by_type = m_f.matter_type.value_counts().reset_index()
            by_type.columns = ["matter_type", "count"]
            fig = px.bar(by_type, x="matter_type", y="count", color="matter_type",
                         color_discrete_sequence=PALETTE)
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="", height=340,
                               plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                               margin=dict(t=10, l=0, r=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No matters for this filter selection.")
    with right:
        st.markdown("**Matter status split**")
        if len(m_f):
            status_ct = m_f.status.value_counts().reset_index()
            status_ct.columns = ["status", "count"]
            fig2 = go.Figure(data=[go.Pie(labels=status_ct.status, values=status_ct["count"], hole=0.6,
                                            marker=dict(colors=PALETTE))])
            fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                                paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No data.")

    st.markdown("")
    st.markdown("**Matter detail**")
    st.dataframe(m_f[["matter_id", "client_name", "location_name", "matter_type", "status",
                       "open_date", "close_date", "fee_estimate"]].sort_values(
        "open_date", ascending=False), use_container_width=True, height=300)

# ======================================================================== TAB 3
with tab3:
    c1, c2, c3 = st.columns(3)
    with c1:
        flow_kpi(cards_f, "date", "amount", "Total card spend", spark_color=PALETTE[0], invert_color=True)
    with c2:
        flow_kpi(commission_f, "date", "amount", "Total commission", spark_color=PALETTE[1], invert_color=True)
    with c3:
        flow_kpi(rapidpay_f, "date", "net_amount", "RapidPay net to firm", spark_color=PALETTE[4])

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
