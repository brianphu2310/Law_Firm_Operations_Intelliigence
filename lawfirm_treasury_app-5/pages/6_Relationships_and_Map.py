import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
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

# ---------------------------------------------------------------- relationship diagram
st.markdown("**How the pieces connect**")
mermaid_src = """
erDiagram
  LOCATION ||--o{ MATTER : hosts
  CLIENT ||--o{ MATTER : owns
  MATTER }o--o{ COUNSEL : briefs
  MATTER ||--o{ TRUST_ACCOUNT : "holds client funds"
  MATTER ||--o{ OFFICE_ACCOUNT : "generates fees to"
  CREDIT_CARD ||--o{ OFFICE_ACCOUNT : "charges firm expenses"
  CREDIT_CARD ||--o{ TRUST_ACCOUNT : "pays disbursement, reimbursed"
  INFOTRACK ||--o{ MATTER : "settlement and search fees"
  LEAP ||--|| OFFICE_ACCOUNT : "system of record"
  LEAP ||--|| TRUST_ACCOUNT : "system of record"
  RAPIDPAY ||--o{ OFFICE_ACCOUNT : "client card payment in"
  RAPIDPAY ||--o{ COMMISSION : "merchant fee charged"
  COMMBIZ ||--|| OFFICE_ACCOUNT : "bank portal"
  COMMBIZ ||--|| TRUST_ACCOUNT : "bank portal"
  COMMISSION ||--o{ MATTER : "earned on referral or type"
"""
components.html(
    f"""
    <div style="background:#FFFFFF; border-radius:16px; padding:12px;
                box-shadow:0 6px 18px rgba(110,198,232,0.18); border:1px solid #E4F3FA;">
      <div id="erd"></div>
    </div>
    <script type="module">
      import mermaid from 'https://esm.sh/mermaid@11/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{
        startOnLoad: false, theme: 'base',
        themeVariables: {{
          primaryColor: '#EAF6FB', primaryTextColor: '#1F3B4D', primaryBorderColor: '#6EC6E8',
          lineColor: '#7A8A99', tertiaryColor: '#FFFFFF', fontFamily: 'sans-serif'
        }}
      }});
      const src = `{mermaid_src}`;
      const {{ svg }} = await mermaid.render('erd-svg', src);
      document.getElementById('erd').innerHTML = svg;
    </script>
    """,
    height=520,
)

st.markdown("")

# ---------------------------------------------------------------- interactive map
st.markdown("**Matter locations**")

loc_summary = matters.groupby("location_id").agg(
    matters=("matter_id", "count"),
    open_matters=("status", lambda s: (s == "Open").sum()),
).reset_index().merge(locations, on="location_id", how="right").fillna(0)

trust_by_loc = data["trust"].groupby("location_id")["amount"].sum().rename("trust_net").reset_index()
loc_summary = loc_summary.merge(trust_by_loc, on="location_id", how="left").fillna({"trust_net": 0})

fig = px.scatter_map(
    loc_summary,
    lat="latitude", lon="longitude",
    size="matters", color="location_name",
    hover_name="location_name",
    hover_data={"address": True, "matters": True, "open_matters": True,
                "trust_net": ":.0f", "latitude": False, "longitude": False, "location_name": False},
    color_discrete_sequence=PALETTE,
    zoom=9.2, height=440,
)
fig.update_traces(marker=dict(size=22))
fig.update_layout(
    map_style="open-street-map",
    margin=dict(l=0, r=0, t=0, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    legend_title="Office",
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("")

c1, c2 = st.columns(2)
for i, row in loc_summary.iterrows():
    with (c1 if i % 2 == 0 else c2):
        insight_card(
            f"{row.location_name} office",
            f"{int(row.matters)} matters",
            f"{row.address} - {int(row.open_matters)} open - trust net {money(row.trust_net)}",
        )

st.markdown("")

# ---------------------------------------------------------------- rollup table
st.markdown("**Every side, rolled up by location**")
sides = pd.DataFrame({
    "Location": loc_summary.location_name,
    "Matters": loc_summary.matters.astype(int),
    "Trust net movement": loc_summary.trust_net.map(money),
})
# Office spend / commission attribute a row to a location either via its own location_id (firm-level
# rows) or via the matter it's linked to; group directly on the raw tables' own location_id, which
# every row carries regardless of whether it's matter-linked.
office_by_loc = data["office"].groupby("location_id")["amount"].sum()
card_by_loc = data["cards"].groupby("location_id")["amount"].sum()
commission_by_loc = data["commission"].groupby("location_id")["amount"].sum()
sides["Office net movement"] = loc_summary.location_id.map(office_by_loc).fillna(0).map(money)
sides["Card spend"] = loc_summary.location_id.map(card_by_loc).fillna(0).map(money)
sides["Commission"] = loc_summary.location_id.map(commission_by_loc).fillna(0).map(money)
st.dataframe(sides, use_container_width=True, hide_index=True)
