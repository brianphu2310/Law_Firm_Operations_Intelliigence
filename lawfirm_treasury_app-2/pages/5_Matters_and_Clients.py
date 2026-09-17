import streamlit as st
import pandas as pd
import plotly.express as px
from utils import load_all, sidebar_filters

st.set_page_config(page_title="Matters & Clients", page_icon="📁", layout="wide")
st.title("📁 Matters, Clients & Counsel")
st.caption("The dimensions everything else is sliced by: who the client is, what kind of matter it is, where it sits, and which counsel is briefed.")

data = load_all()
matters = data["matters"]
counsel = data["counsel"]

st.sidebar.header("Filters")
loc, mtype, date_range = sidebar_filters(data, key_prefix="matters")

m_f = matters.copy()
if loc != "All":
    m_f = m_f[m_f.location_name == loc]
if mtype != "All":
    m_f = m_f[m_f.matter_type == mtype]
if len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    m_f = m_f[(m_f.open_date >= start) & (m_f.open_date <= end)]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Matters", len(m_f))
c2.metric("Open", (m_f.status == "Open").sum())
c3.metric("Closed", (m_f.status == "Closed").sum())
c4.metric("Referred matters", int(m_f.referred_matter.sum()))

st.divider()
left, right = st.columns(2)

with left:
    st.subheader("Matter type mix")
    mt = m_f.matter_type.value_counts().reset_index()
    mt.columns = ["matter_type", "count"]
    fig = px.bar(mt, x="matter_type", y="count")
    fig.update_layout(xaxis_title="", height=380)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Client type mix")
    ct = m_f.client_type.value_counts().reset_index()
    ct.columns = ["client_type", "count"]
    fig2 = px.pie(ct, names="client_type", values="count", hole=0.45)
    fig2.update_layout(height=380)
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Counsel briefed on filtered matters")
briefed = m_f.dropna(subset=["counsel_id"]).merge(counsel, on="counsel_id", how="left")
if len(briefed):
    by_counsel = briefed.groupby(["counsel_name", "specialty"]).size().reset_index(name="matters")
    fig3 = px.bar(by_counsel.sort_values("matters", ascending=False), x="counsel_name", y="matters", color="specialty")
    fig3.update_layout(xaxis_title="", height=360)
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No counsel briefed on matters in this filter selection.")

st.subheader("Matter detail")
st.dataframe(
    m_f[["matter_id", "client_name", "client_type", "location_name", "matter_type", "status",
         "open_date", "close_date", "responsible_lawyer", "fee_estimate",
         "referred_matter", "referral_source"]].sort_values("open_date", ascending=False),
    use_container_width=True, height=400,
)
