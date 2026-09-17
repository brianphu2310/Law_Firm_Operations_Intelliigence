import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import load_all, sidebar_filters, inject_theme, kpi_card, insight_card, monthly_series, PALETTE

st.set_page_config(page_title="Matters and Clients", layout="wide")
inject_theme()

st.title("Matters, Clients and Counsel")
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

# ---------------------------------------------------------------- KPI row
c1, c2, c3 = st.columns(3)
with c1:
    kpi_card("Total matters", str(len(m_f)),
              monthly_series(m_f, "open_date", "matter_id", "count").values, None, spark_color=PALETTE[0])
with c2:
    kpi_card("Open matters", str((m_f.status == "Open").sum()),
              monthly_series(m_f[m_f.status == "Open"], "open_date", "matter_id", "count").values,
              None, spark_color=PALETTE[1])
with c3:
    kpi_card("Referred matters", str(int(m_f.referred_matter.sum())),
              monthly_series(m_f[m_f.referred_matter], "open_date", "matter_id", "count").values,
              None, spark_color=PALETTE[4])

st.markdown("")

# ---------------------------------------------------------------- left / mid / right
left, mid, right = st.columns([2, 1.4, 1.4])

with left:
    st.markdown("**Practice area mix**")
    mt = m_f.matter_type.value_counts().reset_index()
    mt.columns = ["matter_type", "count"]
    fig = px.bar(mt, x="matter_type", y="count", color_discrete_sequence=PALETTE)
    fig.update_layout(xaxis_title="", yaxis_title="", height=340,
                       plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                       margin=dict(t=10, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

with mid:
    st.markdown("**Client type mix**")
    ct = m_f.client_type.value_counts().reset_index()
    ct.columns = ["client_type", "count"]
    fig2 = go.Figure(data=[go.Pie(labels=ct.client_type, values=ct["count"], hole=0.6,
                                    marker=dict(colors=PALETTE))])
    fig2.update_layout(height=340, margin=dict(t=10, l=0, r=0, b=0),
                        paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
    st.plotly_chart(fig2, use_container_width=True)

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
