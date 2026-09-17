import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import load_all, money, inject_theme, kpi_card, insight_card, monthly_series, PALETTE

st.set_page_config(page_title="Relationships and Locations", layout="wide")
inject_theme()

st.title("Relationships and Locations")
st.caption(
    "How office account, trust account, cards, InfoTrack, LEAP, RapidPay, CommBiz and commission "
    "relate to each other, and how it all rolls up by matter location. This page shows the whole "
    "firm (no filters) - use the other pages to drill into a specific office or practice area."
)

data = load_all()
matters = data["matters"]
locations = data["locations"]

# ---------------------------------------------------------------- KPI row
c1, c2, c3 = st.columns(3)
with c1:
    kpi_card("Offices", str(len(locations)), monthly_series(matters, "open_date", "matter_id", "count").values,
              None, spark_color=PALETTE[0])
with c2:
    kpi_card("Total matters", str(len(matters)),
              monthly_series(matters, "open_date", "matter_id", "count").values, None, spark_color=PALETTE[1])
with c3:
    kpi_card("Trust net movement", money(data["trust"]["amount"].sum()),
              monthly_series(data["trust"], "date", "amount").values, None, spark_color=PALETTE[4])

st.markdown("")

# ================================================================== 3D RELATIONSHIP NETWORK
st.markdown("**How the pieces connect (interactive 3D)**")

with st.expander("How to use this diagram", expanded=False):
    st.markdown(
        "- **Rotate**: click and drag anywhere on the diagram.\n"
        "- **Zoom**: scroll, or pinch on a trackpad.\n"
        "- **Highlight one thing's connections**: click any node, or pick one from the dropdown "
        "below it - its direct relationships light up and everything else fades out.\n"
        "- **Keep exploring**: once a node is highlighted, click one of its newly-lit neighbours "
        "to jump the highlight to that node next - so you can walk the chain, e.g. "
        "MATTER to TRUST ACCOUNT to COMMBIZ.\n"
        "- **Hover** any node for a one-line description of what it is.\n"
        "- Pick **Show all connections** to reset the view."
    )

NODE_META = {
    "MATTER": ("MATTER", "An individual client matter or case", PALETTE[1]),
    "LOCATION": ("LOCATION", "Liverpool or Camden office", PALETTE[0]),
    "CLIENT": ("CLIENT", "The person or entity the firm acts for", PALETTE[0]),
    "COUNSEL": ("COUNSEL", "External barrister briefed on litigation-heavy matters", PALETTE[0]),
    "INFOTRACK": ("INFOTRACK", "Disbursement platform: searches, settlements, lodgements", PALETTE[2]),
    "COMMISSION": ("COMMISSION", "Referral commission and RapidPay merchant fees, tracked as costs", PALETTE[0]),
    "TRUST_ACCOUNT": ("TRUST ACCOUNT", "Client funds held on statutory trust", PALETTE[4]),
    "OFFICE_ACCOUNT": ("OFFICE ACCOUNT", "The firm's own operating account", PALETTE[4]),
    "CREDIT_CARD": ("CREDIT CARD", "Amex / Visa - firm expenses and disbursement pre-payments", PALETTE[2]),
    "LEAP": ("LEAP", "Practice management system - system of record for both ledgers", PALETTE[2]),
    "RAPIDPAY": ("RAPIDPAY", "Client card payment collection - charges a merchant fee", PALETTE[2]),
    "COMMBIZ": ("COMMBIZ", "CommBank business banking portal - where the real balances live", PALETTE[2]),
}

EDGES = [
    ("LOCATION", "MATTER", "hosts"),
    ("CLIENT", "MATTER", "owns"),
    ("MATTER", "COUNSEL", "briefs"),
    ("MATTER", "TRUST_ACCOUNT", "holds client funds"),
    ("MATTER", "OFFICE_ACCOUNT", "generates fees to"),
    ("CREDIT_CARD", "OFFICE_ACCOUNT", "charges firm expenses"),
    ("CREDIT_CARD", "TRUST_ACCOUNT", "pays disbursement, reimbursed"),
    ("INFOTRACK", "MATTER", "settlement and search fees"),
    ("LEAP", "OFFICE_ACCOUNT", "system of record"),
    ("LEAP", "TRUST_ACCOUNT", "system of record"),
    ("RAPIDPAY", "OFFICE_ACCOUNT", "client card payment in"),
    ("RAPIDPAY", "COMMISSION", "merchant fee charged"),
    ("COMMBIZ", "OFFICE_ACCOUNT", "bank portal"),
    ("COMMBIZ", "TRUST_ACCOUNT", "bank portal"),
    ("COMMISSION", "MATTER", "earned on referral or type"),
]

ring_a = ["LOCATION", "CLIENT", "COUNSEL", "INFOTRACK", "COMMISSION"]
ring_b = ["TRUST_ACCOUNT", "OFFICE_ACCOUNT"]
ring_c = ["CREDIT_CARD", "LEAP", "RAPIDPAY", "COMMBIZ"]

POSITIONS = {"MATTER": (0.0, 0.0, 0.4)}
for i, n in enumerate(ring_a):
    a = 2 * np.pi * i / len(ring_a)
    POSITIONS[n] = (3 * np.cos(a), 3 * np.sin(a), 1.3)
for i, n in enumerate(ring_b):
    a = 2 * np.pi * i / len(ring_b) + np.pi / 4
    POSITIONS[n] = (1.6 * np.cos(a), 1.6 * np.sin(a), -0.9)
for i, n in enumerate(ring_c):
    a = 2 * np.pi * i / len(ring_c) + np.pi / 6
    POSITIONS[n] = (5 * np.cos(a), 5 * np.sin(a), -1.8)


def neighbors_of(node):
    ns = set()
    for a, b, _ in EDGES:
        if a == node:
            ns.add(b)
        if b == node:
            ns.add(a)
    return ns


def build_network_3d(selected):
    fig = go.Figure()
    highlight = selected != "Show all connections"
    neigh = neighbors_of(selected) if highlight else set()

    for a, b, label in EDGES:
        xs = [POSITIONS[a][0], POSITIONS[b][0]]
        ys = [POSITIONS[a][1], POSITIONS[b][1]]
        zs = [POSITIONS[a][2], POSITIONS[b][2]]
        touches = highlight and (a == selected or b == selected)
        if highlight:
            color = PALETTE[1] if touches else "#DCE6EA"
            width = 7 if touches else 2
            opacity = 0.95 if touches else 0.2
        else:
            color = "#A9CBDC"
            width = 3
            opacity = 0.6
        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs, mode="lines",
            line=dict(color=color, width=width), opacity=opacity,
            hoverinfo="text", text=f"{NODE_META[a][0]} - {NODE_META[b][0]}: {label}",
            showlegend=False,
        ))

    names = list(POSITIONS.keys())
    xs = [POSITIONS[n][0] for n in names]
    ys = [POSITIONS[n][1] for n in names]
    zs = [POSITIONS[n][2] for n in names]
    colors, sizes = [], []
    for n in names:
        _, _, base_color = NODE_META[n]
        if not highlight:
            colors.append(base_color); sizes.append(16 if n == "MATTER" else 12)
        elif n == selected:
            colors.append(base_color); sizes.append(24)
        elif n in neigh:
            colors.append(base_color); sizes.append(16)
        else:
            colors.append("#E4EBEE"); sizes.append(8)
    hover = [f"{NODE_META[n][0]}: {NODE_META[n][1]}" for n in names]

    fig.add_trace(go.Scatter3d(
        x=xs, y=ys, z=zs, mode="markers+text",
        text=[NODE_META[n][0] for n in names],
        textposition="top center",
        textfont=dict(size=10, color="#1F3B4D"),
        marker=dict(size=sizes, color=colors, line=dict(color="white", width=1)),
        customdata=names, hoverinfo="text", hovertext=hover,
        showlegend=False,
    ))

    fig.update_layout(
        height=560, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    return fig


node_options = ["Show all connections"] + list(POSITIONS.keys())
if "rel_node_select" not in st.session_state:
    st.session_state.rel_node_select = "Show all connections"

fig3d = build_network_3d(st.session_state.rel_node_select)
event = st.plotly_chart(fig3d, use_container_width=True, on_select="rerun", key="rel3d_chart")

clicked_points = []
try:
    clicked_points = event.selection.points
except Exception:
    clicked_points = []

if clicked_points:
    clicked = clicked_points[0].get("customdata")
    if isinstance(clicked, list):
        clicked = clicked[0] if clicked else None
    if clicked and clicked in POSITIONS and clicked != st.session_state.rel_node_select:
        st.session_state.rel_node_select = clicked
        st.rerun()

selected_node = st.selectbox("Or choose a node to explore:", node_options, key="rel_node_select")

if selected_node != "Show all connections":
    conns = sorted(neighbors_of(selected_node))
    st.markdown(
        f"**{NODE_META[selected_node][0]}** directly connects to: "
        + ", ".join(NODE_META[c][0] for c in conns)
    )

st.markdown("")

# ================================================================== INTERACTIVE MAP
st.markdown("**Matter locations**")

loc_summary = matters.groupby("location_id").agg(
    matters=("matter_id", "count"),
    open_matters=("status", lambda s: (s == "Open").sum()),
).reset_index().merge(locations, on="location_id", how="right").fillna(0)

trust_by_loc = data["trust"].groupby("location_id")["amount"].sum().rename("trust_net").reset_index()
loc_summary = loc_summary.merge(trust_by_loc, on="location_id", how="left").fillna({"trust_net": 0})

center_lat = loc_summary["latitude"].mean()
center_lon = loc_summary["longitude"].mean()

fig_map = px.scatter_map(
    loc_summary,
    lat="latitude", lon="longitude",
    size="matters", color="location_name",
    hover_name="location_name",
    hover_data={"address": True, "matters": True, "open_matters": True,
                "trust_net": ":.0f", "latitude": False, "longitude": False, "location_name": False},
    custom_data=["location_name"],
    color_discrete_sequence=PALETTE,
    center={"lat": center_lat, "lon": center_lon},
    zoom=9.6, height=460,
)
fig_map.update_traces(marker=dict(size=24))
fig_map.update_layout(
    map_style="open-street-map",
    margin=dict(l=0, r=0, t=0, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    legend_title="Office",
)
map_event = st.plotly_chart(fig_map, use_container_width=True, on_select="rerun", key="rel_map_chart")

map_points = []
try:
    map_points = map_event.selection.points
except Exception:
    map_points = []

if "rel_map_select" not in st.session_state:
    st.session_state.rel_map_select = "All offices"

if map_points:
    clicked_loc = map_points[0].get("customdata")
    if isinstance(clicked_loc, list):
        clicked_loc = clicked_loc[0] if clicked_loc else None
    if clicked_loc and clicked_loc in loc_summary.location_name.values and clicked_loc != st.session_state.rel_map_select:
        st.session_state.rel_map_select = clicked_loc
        st.rerun()

office_options = ["All offices"] + loc_summary.location_name.tolist()
office_pick = st.selectbox("Or choose an office to inspect:", office_options, key="rel_map_select")

st.markdown("")

if office_pick != "All offices":
    row = loc_summary[loc_summary.location_name == office_pick].iloc[0]
    loc_matters = matters[matters.location_id == row.location_id]
    loc_fees = data["office"][(data["office"].type == "Fee income") &
                               (data["office"].matter_id.isin(loc_matters.matter_id))]
    loc_expenses = data["office"][(data["office"].type == "Expense") & (data["office"].location_id == row.location_id)]
    top_types = loc_matters.matter_type.value_counts()

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        insight_card(f"{office_pick}: matters", str(len(loc_matters)),
                     f"{int(row.open_matters)} currently open")
    with cc2:
        insight_card(f"{office_pick}: fee income", money(loc_fees.amount.sum()),
                     f"Operating expenses {money(loc_expenses.amount.sum().__abs__())}")
    with cc3:
        top_label = top_types.idxmax() if len(top_types) else "n/a"
        insight_card(f"{office_pick}: top practice area", top_label,
                     f"{top_types.max() if len(top_types) else 0} matters")
else:
    c1, c2 = st.columns(2)
    for i, row in loc_summary.iterrows():
        with (c1 if i % 2 == 0 else c2):
            insight_card(
                f"{row.location_name} office",
                f"{int(row.matters)} matters",
                f"{row.address} - {int(row.open_matters)} open - trust net {money(row.trust_net)}",
            )

st.markdown("")

# ================================================================== ROLLUP TABLE
st.markdown("**Every side, rolled up by location**")
sides = pd.DataFrame({
    "Location": loc_summary.location_name,
    "Matters": loc_summary.matters.astype(int),
    "Trust net movement": loc_summary.trust_net.map(money),
})
office_by_loc = data["office"].groupby("location_id")["amount"].sum()
card_by_loc = data["cards"].groupby("location_id")["amount"].sum()
commission_by_loc = data["commission"].groupby("location_id")["amount"].sum()
sides["Office net movement"] = loc_summary.location_id.map(office_by_loc).fillna(0).map(money)
sides["Card spend"] = loc_summary.location_id.map(card_by_loc).fillna(0).map(money)
sides["Commission"] = loc_summary.location_id.map(commission_by_loc).fillna(0).map(money)
st.dataframe(sides, use_container_width=True, hide_index=True)
