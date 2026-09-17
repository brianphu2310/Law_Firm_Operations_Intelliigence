import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import load_all, sidebar_filters, filter_matters, inject_theme, kpi_card, insight_card, monthly_series, yoy_delta, PALETTE

st.set_page_config(page_title="Matters and Clients", layout="wide")
inject_theme()

st.title("Matters, Clients and Counsel")
st.caption("The dimensions everything else is sliced by: who the client is, what kind of matter it is, where it sits, and which counsel is briefed.")

data = load_all()
matters = data["matters"]
counsel = data["counsel"]

st.sidebar.header("Filters")
loc, mtype, status, date_range = sidebar_filters(data, key_prefix="matters")

m_f = filter_matters(matters, loc, mtype, status, date_range)

# ---------------------------------------------------------------- KPI row
c1, c2, c3 = st.columns(3)
with c1:
    kpi_card("Total matters", str(len(m_f)),
              monthly_series(m_f, "open_date", "matter_id", "count").values,
              yoy_delta(m_f, "open_date", "matter_id", "count"), spark_color=PALETTE[0])
with c2:
    open_m = m_f[m_f.status == "Open"]
    kpi_card("Open matters", str(len(open_m)),
              monthly_series(open_m, "open_date", "matter_id", "count").values, None, spark_color=PALETTE[1])
with c3:
    ref_m = m_f[m_f.referred_matter]
    kpi_card("Referred matters", str(len(ref_m)),
              monthly_series(ref_m, "open_date", "matter_id", "count").values, None, spark_color=PALETTE[4])

st.markdown("")

# ---------------------------------------------------------------- left / mid / right
left, mid, right = st.columns([2, 1.4, 1.4])

with left:
    st.markdown("**Practice area mix**")
    if len(m_f):
        mt = m_f.matter_type.value_counts().reset_index()
        mt.columns = ["matter_type", "count"]
        fig = px.bar(mt, x="matter_type", y="count", color_discrete_sequence=PALETTE)
        fig.update_layout(xaxis_title="", yaxis_title="", height=340,
                           plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                           margin=dict(t=10, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No matters for this filter selection.")

with mid:
    st.markdown("**Client type mix**")
    if len(m_f):
        ct = m_f.client_type.value_counts().reset_index()
        ct.columns = ["client_type", "count"]
        fig2 = go.Figure(data=[go.Pie(labels=ct.client_type, values=ct["count"], hole=0.6,
                                        marker=dict(colors=PALETTE))])
        fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No data.")

with right:
    if len(m_f):
        by_type = m_f.matter_type.value_counts()
        insight_card("Top practice area", by_type.idxmax(), f"{by_type.max()} matters ({by_type.max()/len(m_f)*100:.1f}%)")
        by_loc = m_f.location_name.value_counts()
        insight_card("Top office", by_loc.idxmax(), f"{by_loc.max()} matters ({by_loc.max()/len(m_f)*100:.1f}%)")
    ref = m_f[m_f.referred_matter]
    if len(ref):
        by_ref = ref.referral_source.value_counts()
        insight_card("Top referral source", by_ref.idxmax(), f"{by_ref.max()} matters ({by_ref.max()/len(ref)*100:.1f}%)")

st.markdown("")

# ---------------------------------------------------------------- breakdown chart
st.markdown("**Counsel briefed on filtered matters**")
briefed = m_f.dropna(subset=["counsel_id"]).merge(counsel, on="counsel_id", how="left")
if len(briefed):
    by_counsel = briefed.groupby(["counsel_name", "specialty"]).size().reset_index(name="matters")
    fig3 = px.bar(by_counsel.sort_values("matters", ascending=False), x="counsel_name", y="matters",
                  color="specialty", color_discrete_sequence=PALETTE)
    fig3.update_layout(xaxis_title="", yaxis_title="", height=320, legend_title="",
                        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No counsel briefed on matters in this filter selection.")

st.markdown("")

# ---------------------------------------------------------------- detail table
st.markdown("**Matter detail**")
st.dataframe(
    m_f[["matter_id", "client_name", "client_type", "location_name", "matter_type", "status",
         "open_date", "close_date", "responsible_lawyer", "fee_estimate",
         "referred_matter", "referral_source"]].sort_values("open_date", ascending=False),
    use_container_width=True, height=360,
)
