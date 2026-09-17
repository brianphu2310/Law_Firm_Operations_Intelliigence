"""
D'Agostino Legal — Operations Dashboard (full practice-management build)

Built from the Figma design at:
https://www.figma.com/design/v2XzNdUJW2v3tcIcR28sCf/Untitled?node-id=3-4
and extended per follow-up requirements into a full multi-section app:
Office Account, Trust Account, CommBiz, MYOB, Billing & Invoices,
Commission, RapidPay, InfoTrack, Council searches, Card Expenses
(Amex/Visa), Matter Types, a branch map (Richmond / Camden / Liverpool),
editable pay rates, and a hiring / branch-acquisition simulator.

All data is SAMPLE DATA, defined in one place near the top, built to be
internally consistent across every section (same attorneys, clients,
matters, and branches everywhere). Swap it for a real source when ready —
every section function reads from it, so the rest of the app updates
automatically.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------
st.set_page_config(page_title="D'Agostino Legal — Operations", layout="wide",
                    initial_sidebar_state="collapsed")

BG = "#ebf1f6"
CARD = "#ffffff"
BORDER = "#e2e8f0"
TEAL = "#0a8496"
TEAL_TINT = "#ecfeff"
INK = "#0f172a"
MUTED = "#475569"
FAINT = "#94a3b8"
GREEN = "#10b981"
RED = "#ef4444"
AMBER = "#f59e0b"
GREEN_TINT = "#f0fdf4"
RED_TINT = "#fef2f2"
AMBER_TINT = "#fffbeb"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class^="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {BG}; }}
.block-container {{ padding-top: 1rem; padding-bottom: 1.6rem; max-width: 1440px; }}
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; }}
div[data-testid="stVerticalBlock"] {{ gap: 0.6rem; }}

div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 16px !important; }}
div[data-testid="stVerticalBlockBorderWrapper"] > div {{
    background:{CARD}; border-radius: 16px !important;
    box-shadow: 0 1px 3px rgba(15,23,42,0.06); border: 1px solid {BORDER} !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {{
    gap: 0.5rem; padding: 2px 2px;
}}

.brand {{ display:flex; align-items:center; gap:8px; height:38px; }}
.brand-badge {{
    background:{TEAL}; width:28px; height:28px; border-radius:8px;
    display:flex; align-items:center; justify-content:center;
    color:#fff; font-weight:800; font-size:16px; flex-shrink:0;
}}
.brand-name {{ font-weight:700; font-size:16px; color:{INK}; }}
.user-row {{ display:flex; align-items:center; gap:10px; justify-content:flex-end; height:38px; }}
.avatar-initials {{
    width:34px; height:34px; border-radius:17px; background:{TEAL};
    color:#fff; font-weight:700; font-size:12px;
    display:flex; align-items:center; justify-content:center; flex-shrink:0;
}}
.user-name {{ font-weight:600; font-size:13px; color:{INK}; line-height:1.2; }}
.user-role {{ font-size:10px; color:{MUTED}; line-height:1.2; }}

div[data-testid="stButton"] button {{
    border-radius: 999px !important; font-weight: 600 !important; font-size: 13px !important;
    padding: 6px 4px !important; border: 1px solid transparent !important;
    background: transparent !important; color: {MUTED} !important; box-shadow: none !important;
}}
div[data-testid="stButton"] button:hover {{ color:{TEAL} !important; border-color:{BORDER} !important; }}
div[data-testid="stButton"] button[kind="primary"] {{
    background:{TEAL_TINT} !important; color:{TEAL} !important; border:1px solid {TEAL} !important;
}}

.kpi-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:14px; padding:12px 14px; height:100%; }}
.kpi-label {{ font-size:11.5px; font-weight:500; color:{MUTED}; margin-bottom:6px; }}
.kpi-bottom {{ display:flex; align-items:flex-end; justify-content:space-between; gap:8px; }}
.kpi-value {{ font-size:20px; font-weight:700; color:{INK}; white-space:nowrap; }}
.kpi-trend {{ display:flex; align-items:center; gap:4px; margin-top:3px; }}
.kpi-trend .pct {{ font-size:11px; font-weight:600; }}
.kpi-trend .vs {{ font-size:10px; color:{FAINT}; }}

.card-title {{ font-size:13.5px; font-weight:700; color:{INK}; margin-bottom:2px; }}
.section-title {{ font-size:19px; font-weight:800; color:{INK}; margin: 2px 0 0 0; }}
.section-sub {{ font-size:12.5px; color:{MUTED}; margin-bottom: 8px; }}
.spacer {{ height: 10px; }}
.legend-row {{ display:flex; gap:12px; align-items:center; }}
.legend-item {{ display:flex; gap:6px; align-items:center; font-size:11px; color:{MUTED}; }}
.legend-dot {{ width:8px; height:8px; border-radius:99px; display:inline-block; }}

.donut-legend-item {{ display:flex; gap:6px; align-items:center; font-size:11px; font-weight:600; color:{INK}; margin-bottom:8px; }}

.insight-kicker {{ font-size:11px; font-weight:600; color:{TEAL}; letter-spacing:0.02em; }}
.insight-headline {{ font-size:14px; font-weight:700; color:{INK}; margin:2px 0; }}
.insight-desc {{ font-size:12px; color:{MUTED}; }}

table.matrix {{ width:100%; border-collapse:collapse; font-size:12px; }}
table.matrix th {{ background:{BG}; font-weight:600; color:{MUTED}; padding:8px 4px; text-align:center; font-size:11px; }}
table.matrix td {{ border:0.5px solid {BORDER}; height:36px; text-align:center; font-weight:500; color:{INK}; }}

table.simple {{ width:100%; border-collapse:collapse; font-size:12px; }}
table.simple th {{ text-align:left; color:{MUTED}; font-weight:600; padding:6px 8px; font-size:11px; border-bottom:1px solid {BORDER}; }}
table.simple td {{ padding:6px 8px; border-bottom:1px solid #f1f5f9; color:{INK}; }}

.bar-row {{ margin-bottom: 14px; }}
.bar-head {{ display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px; }}
.bar-head .lbl {{ color:{MUTED}; }}
.bar-head .val {{ color:{INK}; font-weight:700; }}
.bar-track {{ background:{BG}; height:8px; border-radius:4px; overflow:hidden; }}
.bar-fill {{ height:100%; border-radius:4px; }}

.deadline-item {{ display:flex; gap:12px; align-items:center; margin-bottom:14px; }}
.date-badge {{
    width:48px; height:42px; border-radius:10px; display:flex; align-items:center;
    justify-content:center; font-weight:700; font-size:12px; flex-shrink:0; text-align:center;
}}
.deadline-title {{ font-weight:700; font-size:12px; color:{INK}; }}
.deadline-sub {{ font-size:10px; color:{MUTED}; }}

.status-pill {{ padding:3px 10px; border-radius:999px; font-size:11px; font-weight:600; display:inline-block; }}
.chip {{ padding:3px 10px; border-radius:999px; font-size:11px; font-weight:600; background:{BG}; color:{MUTED}; display:inline-block; margin:2px 4px 2px 0; }}

.attorney-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:14px; padding:14px; text-align:center; }}
.attorney-avatar {{
    width:42px; height:42px; border-radius:21px; background:{TEAL}; color:#fff;
    font-weight:700; font-size:14px; display:flex; align-items:center; justify-content:center;
    margin: 0 auto 8px auto;
}}

.branch-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:14px; padding:14px; }}
.branch-name {{ font-size:14px; font-weight:700; color:{INK}; }}
.branch-council {{ font-size:11px; color:{MUTED}; margin-bottom:8px; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# DATA — sample data, internally consistent across all sections.
# ----------------------------------------------------------------------
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_6 = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
NAV_ITEMS = ["Overview", "Matters", "Clients", "Calendar", "Finance", "Team", "Simulator"]
PRACTICE_AREAS = ["Corporate", "Litigation", "IP Portfolio", "Employment", "Advisory"]

USER_NAME = "Brian Phu"
USER_ROLE = "Financial Analyst"

BRANCHES = [
    {"name": "Richmond", "lat": -33.6003, "lon": 150.7514, "council": "Hawkesbury City Council",
     "headcount": 7, "active_matters": 16, "monthly_revenue": 182000, "monthly_cost": 128000},
    {"name": "Camden", "lat": -34.0489, "lon": 150.6993, "council": "Camden Council",
     "headcount": 8, "active_matters": 21, "monthly_revenue": 224000, "monthly_cost": 158000},
    {"name": "Liverpool", "lat": -33.9209, "lon": 150.8809, "council": "Liverpool City Council",
     "headcount": 10, "active_matters": 27, "monthly_revenue": 256000, "monthly_cost": 182000},
]
BRANCH_NAMES = [b["name"] for b in BRANCHES]
BRANCH_COUNCIL = {b["name"]: b["council"] for b in BRANCHES}

ROLE_PRESETS = {
    "Associate": {"bill_rate": 380, "pay_rate": 120, "target_hours": 190},
    "Senior Associate": {"bill_rate": 520, "pay_rate": 170, "target_hours": 190},
    "Partner": {"bill_rate": 650, "pay_rate": 210, "target_hours": 190},
}

ATTORNEYS = [
    {"name": "Clara Sterling", "short": "Sterling, C.", "role": "Senior Managing Partner", "branch": "Richmond",
     "hours": {"Corporate": 45, "Litigation": 20, "IP Portfolio": 80, "Advisory": 15},
     "target": 190, "bill_rate": 650, "pay_rate": 210},
    {"name": "Harvey Specter", "short": "Specter, H.", "role": "Senior Associate", "branch": "Camden",
     "hours": {"Corporate": 10, "Litigation": 140, "IP Portfolio": 5, "Advisory": 25},
     "target": 190, "bill_rate": 520, "pay_rate": 170},
    {"name": "Rachel Zane", "short": "Zane, R.", "role": "Associate", "branch": "Liverpool",
     "hours": {"Corporate": 85, "Litigation": 40, "IP Portfolio": 15, "Advisory": 10},
     "target": 190, "bill_rate": 380, "pay_rate": 120},
    {"name": "Louis Litt", "short": "Litt, L.", "role": "Senior Partner", "branch": "Liverpool",
     "hours": {"Corporate": 30, "Litigation": 15, "IP Portfolio": 95, "Advisory": 5},
     "target": 190, "bill_rate": 560, "pay_rate": 175},
    {"name": "Katrina Bennett", "short": "Bennett, K.", "role": "Associate", "branch": "Camden",
     "hours": {"Corporate": 60, "Litigation": 25, "IP Portfolio": 30, "Advisory": 40},
     "target": 190, "bill_rate": 400, "pay_rate": 130},
    {"name": "Mike Ross", "short": "Ross, M.", "role": "Senior Associate", "branch": "Richmond",
     "hours": {"Corporate": 70, "Litigation": 60, "IP Portfolio": 20, "Advisory": 15},
     "target": 190, "bill_rate": 500, "pay_rate": 160},
    {"name": "Jessica Pearson", "short": "Pearson, J.", "role": "Senior Partner", "branch": "Liverpool",
     "hours": {"Corporate": 100, "Litigation": 30, "IP Portfolio": 20, "Advisory": 10},
     "target": 190, "bill_rate": 700, "pay_rate": 230},
    {"name": "Donna Paulsen", "short": "Paulsen, D.", "role": "Associate", "branch": "Richmond",
     "hours": {"Corporate": 40, "Litigation": 35, "IP Portfolio": 45, "Advisory": 55},
     "target": 190, "bill_rate": 360, "pay_rate": 115},
]
for a in ATTORNEYS:
    a["total"] = sum(a["hours"].values())
    a["utilization"] = round(a["total"] / a["target"] * 100, 1)

MATRIX_ALPHA = {
    "Sterling, C.": {"Corporate": 0.6, "Litigation": 0.1, "IP Portfolio": 0.9, "Advisory": 0.1},
    "Specter, H.": {"Corporate": 0.1, "Litigation": 0.9, "IP Portfolio": 0.1, "Advisory": 0.3},
    "Zane, R.": {"Corporate": 0.9, "Litigation": 0.3, "IP Portfolio": 0.1, "Advisory": 0.1},
    "Litt, L.": {"Corporate": 0.3, "Litigation": 0.1, "IP Portfolio": 0.9, "Advisory": 0.1},
    "Bennett, K.": {"Corporate": 0.4, "Litigation": 0.15, "IP Portfolio": 0.2, "Advisory": 0.3},
    "Ross, M.": {"Corporate": 0.5, "Litigation": 0.45, "IP Portfolio": 0.15, "Advisory": 0.1},
    "Pearson, J.": {"Corporate": 0.8, "Litigation": 0.25, "IP Portfolio": 0.15, "Advisory": 0.1},
    "Paulsen, D.": {"Corporate": 0.3, "Litigation": 0.25, "IP Portfolio": 0.35, "Advisory": 0.5},
}

CLIENTS = [
    {"name": "Acme Corp", "practice": "Litigation", "attorney": "Zane, R.", "billed": 612000, "matters": 5, "since": 2019},
    {"name": "Zenith Labs", "practice": "Litigation", "attorney": "Specter, H.", "billed": 390000, "matters": 2, "since": 2021},
    {"name": "Meridian Holdings Ltd.", "practice": "Corporate", "attorney": "Sterling, C.", "billed": 540000, "matters": 6, "since": 2017},
    {"name": "Global Trust Bank", "practice": "Corporate", "attorney": "Specter, H.", "billed": 475000, "matters": 4, "since": 2020},
    {"name": "Vertex Industries", "practice": "IP Portfolio", "attorney": "Litt, L.", "billed": 268000, "matters": 6, "since": 2018},
    {"name": "Harlow & Co.", "practice": "Employment", "attorney": "Sterling, C.", "billed": 142000, "matters": 3, "since": 2022},
    {"name": "Nova Materials", "practice": "IP Portfolio", "attorney": "Litt, L.", "billed": 198000, "matters": 4, "since": 2020},
    {"name": "Bright Path Foundation", "practice": "Advisory", "attorney": "Sterling, C.", "billed": 86000, "matters": 2, "since": 2023},
    {"name": "Halcyon Systems", "practice": "IP Portfolio", "attorney": "Pearson, J.", "billed": 315000, "matters": 3, "since": 2016},
    {"name": "Blackwood Realty", "practice": "Corporate", "attorney": "Ross, M.", "billed": 220000, "matters": 4, "since": 2021},
    {"name": "Sunrise Logistics", "practice": "Employment", "attorney": "Bennett, K.", "billed": 98000, "matters": 2, "since": 2022},
    {"name": "Fentonville Council", "practice": "Advisory", "attorney": "Paulsen, D.", "billed": 64000, "matters": 2, "since": 2023},
    {"name": "Okafor Mining Co.", "practice": "Litigation", "attorney": "Ross, M.", "billed": 445000, "matters": 3, "since": 2019},
    {"name": "Delacroix & Sons", "practice": "Corporate", "attorney": "Pearson, J.", "billed": 288000, "matters": 2, "since": 2018},
    {"name": "Whitmore Textiles", "practice": "IP Portfolio", "attorney": "Bennett, K.", "billed": 132000, "matters": 2, "since": 2020},
]

MATTERS = [
    {"name": "Acme vs. Zenith Trial Brief Filing", "client": "Acme Corp", "practice": "Litigation",
     "attorney": "Zane, R.", "status": "Open", "opened": "2025-03-14", "value": 420000, "branch": "Liverpool"},
    {"name": "Global Trust M&A Preliminary Hearing", "client": "Global Trust Bank", "practice": "Corporate",
     "attorney": "Specter, H.", "status": "Open", "opened": "2025-05-02", "value": 610000, "branch": "Camden"},
    {"name": "Meridian Series C Financing", "client": "Meridian Holdings Ltd.", "practice": "Corporate",
     "attorney": "Sterling, C.", "status": "Open", "opened": "2025-01-20", "value": 350000, "branch": "Richmond"},
    {"name": "Vertex Patent Portfolio Review", "client": "Vertex Industries", "practice": "IP Portfolio",
     "attorney": "Litt, L.", "status": "Open", "opened": "2025-06-11", "value": 180000, "branch": "Liverpool"},
    {"name": "Harlow Wrongful Termination Defense", "client": "Harlow & Co.", "practice": "Employment",
     "attorney": "Sterling, C.", "status": "On Hold", "opened": "2024-11-08", "value": 95000, "branch": "Camden"},
    {"name": "Nova Materials Trademark Dispute", "client": "Nova Materials", "practice": "IP Portfolio",
     "attorney": "Litt, L.", "status": "Closed", "opened": "2024-06-19", "value": 74000, "branch": "Liverpool"},
    {"name": "Zenith Labs Licensing Countersuit", "client": "Zenith Labs", "practice": "Litigation",
     "attorney": "Specter, H.", "status": "Open", "opened": "2025-02-27", "value": 260000, "branch": "Liverpool"},
    {"name": "Acme Supply Agreement Renewal", "client": "Acme Corp", "practice": "Corporate",
     "attorney": "Sterling, C.", "status": "Closed", "opened": "2024-09-03", "value": 120000, "branch": "Camden"},
    {"name": "Bright Path Governance Advisory", "client": "Bright Path Foundation", "practice": "Advisory",
     "attorney": "Sterling, C.", "status": "Open", "opened": "2025-07-01", "value": 45000, "branch": "Richmond"},
    {"name": "Vertex vs. Halcyon IP Infringement", "client": "Vertex Industries", "practice": "IP Portfolio",
     "attorney": "Litt, L.", "status": "Open", "opened": "2025-04-16", "value": 510000, "branch": "Liverpool"},
    {"name": "Halcyon Trademark Portfolio Audit", "client": "Halcyon Systems", "practice": "IP Portfolio",
     "attorney": "Pearson, J.", "status": "Open", "opened": "2025-02-10", "value": 210000, "branch": "Liverpool"},
    {"name": "Blackwood Realty Lease Restructure", "client": "Blackwood Realty", "practice": "Corporate",
     "attorney": "Ross, M.", "status": "Open", "opened": "2025-05-19", "value": 165000, "branch": "Richmond"},
    {"name": "Sunrise Logistics Award Compliance Review", "client": "Sunrise Logistics", "practice": "Employment",
     "attorney": "Bennett, K.", "status": "Open", "opened": "2025-06-02", "value": 58000, "branch": "Camden"},
    {"name": "Fentonville Council Planning Advisory", "client": "Fentonville Council", "practice": "Advisory",
     "attorney": "Paulsen, D.", "status": "Open", "opened": "2025-07-15", "value": 41000, "branch": "Richmond"},
    {"name": "Okafor Mining Environmental Claim", "client": "Okafor Mining Co.", "practice": "Litigation",
     "attorney": "Ross, M.", "status": "Open", "opened": "2025-03-28", "value": 380000, "branch": "Richmond"},
    {"name": "Delacroix Group Acquisition", "client": "Delacroix & Sons", "practice": "Corporate",
     "attorney": "Pearson, J.", "status": "Open", "opened": "2025-08-04", "value": 295000, "branch": "Liverpool"},
    {"name": "Whitmore Textiles Patent Filing", "client": "Whitmore Textiles", "practice": "IP Portfolio",
     "attorney": "Bennett, K.", "status": "Closed", "opened": "2024-10-12", "value": 68000, "branch": "Camden"},
    {"name": "Acme Corp Data Breach Response", "client": "Acme Corp", "practice": "Litigation",
     "attorney": "Zane, R.", "status": "Open", "opened": "2025-08-20", "value": 175000, "branch": "Liverpool"},
    {"name": "Meridian Holdings Employee Share Scheme", "client": "Meridian Holdings Ltd.", "practice": "Corporate",
     "attorney": "Sterling, C.", "status": "On Hold", "opened": "2025-04-11", "value": 88000, "branch": "Richmond"},
    {"name": "Vertex Industries Licensing Dispute", "client": "Vertex Industries", "practice": "IP Portfolio",
     "attorney": "Litt, L.", "status": "Closed", "opened": "2024-08-30", "value": 92000, "branch": "Liverpool"},
    {"name": "Global Trust Bank Regulatory Investigation", "client": "Global Trust Bank", "practice": "Litigation",
     "attorney": "Specter, H.", "status": "Open", "opened": "2025-09-01", "value": 520000, "branch": "Camden"},
    {"name": "Harlow & Co. Redundancy Program Advisory", "client": "Harlow & Co.", "practice": "Employment",
     "attorney": "Sterling, C.", "status": "Closed", "opened": "2024-12-05", "value": 47000, "branch": "Camden"},
    {"name": "Nova Materials Supply Contract Review", "client": "Nova Materials", "practice": "Corporate",
     "attorney": "Litt, L.", "status": "Open", "opened": "2025-07-22", "value": 63000, "branch": "Liverpool"},
    {"name": "Bright Path Foundation Charity Structuring", "client": "Bright Path Foundation", "practice": "Advisory",
     "attorney": "Sterling, C.", "status": "Open", "opened": "2025-09-10", "value": 32000, "branch": "Richmond"},
]

DEADLINES = [
    {"date": "2025-10-12", "title": "Acme vs. Zenith Trial Brief Filing", "court": "Appellate Court", "attorney": "Zane, R."},
    {"date": "2025-10-15", "title": "Global Trust M&A Preliminary Hearing", "court": "Chancery Court", "attorney": "Specter, H."},
    {"date": "2025-10-22", "title": "Vertex Patent Portfolio Filing Deadline", "court": "USPTO", "attorney": "Litt, L."},
    {"date": "2025-10-29", "title": "Halcyon Trademark Portfolio Filing", "court": "IP Australia", "attorney": "Pearson, J."},
    {"date": "2025-11-04", "title": "Meridian Series C Closing", "court": "—", "attorney": "Sterling, C."},
    {"date": "2025-11-10", "title": "Blackwood Realty Lease Signing", "court": "—", "attorney": "Ross, M."},
    {"date": "2025-11-18", "title": "Zenith Labs Licensing Countersuit Hearing", "court": "District Court", "attorney": "Specter, H."},
    {"date": "2025-11-25", "title": "Okafor Mining Environmental Tribunal", "court": "Land & Environment Court", "attorney": "Ross, M."},
    {"date": "2025-12-02", "title": "Vertex vs. Halcyon IP Infringement Trial", "court": "Federal Court", "attorney": "Litt, L."},
    {"date": "2025-12-15", "title": "Global Trust Bank Regulatory Hearing", "court": "Federal Court", "attorney": "Specter, H."},
    {"date": "2026-01-14", "title": "Delacroix Group Acquisition Completion", "court": "—", "attorney": "Pearson, J."},
    {"date": "2026-02-03", "title": "Fentonville Council Planning Panel Hearing", "court": "Land & Environment Court", "attorney": "Paulsen, D."},
]

INVOICES = [
    {"client": "Acme Corp", "invoice": "INV-1042", "amount": 86000, "status": "Paid", "issued": "2025-08-01", "due": "2025-08-31"},
    {"client": "Zenith Labs", "invoice": "INV-1043", "amount": 54000, "status": "Outstanding", "issued": "2025-08-05", "due": "2025-09-04"},
    {"client": "Meridian Holdings Ltd.", "invoice": "INV-1044", "amount": 120000, "status": "Paid", "issued": "2025-08-10", "due": "2025-09-09"},
    {"client": "Global Trust Bank", "invoice": "INV-1045", "amount": 95000, "status": "Overdue", "issued": "2025-07-12", "due": "2025-08-11"},
    {"client": "Vertex Industries", "invoice": "INV-1046", "amount": 38000, "status": "Paid", "issued": "2025-08-15", "due": "2025-09-14"},
    {"client": "Harlow & Co.", "invoice": "INV-1047", "amount": 21000, "status": "Outstanding", "issued": "2025-08-18", "due": "2025-09-17"},
    {"client": "Nova Materials", "invoice": "INV-1048", "amount": 29500, "status": "Paid", "issued": "2025-08-20", "due": "2025-09-19"},
    {"client": "Bright Path Foundation", "invoice": "INV-1049", "amount": 12000, "status": "Outstanding", "issued": "2025-08-22", "due": "2025-09-21"},
    {"client": "Halcyon Systems", "invoice": "INV-1050", "amount": 72000, "status": "Paid", "issued": "2025-08-25", "due": "2025-09-24"},
    {"client": "Blackwood Realty", "invoice": "INV-1051", "amount": 41000, "status": "Outstanding", "issued": "2025-08-28", "due": "2025-09-27"},
    {"client": "Sunrise Logistics", "invoice": "INV-1052", "amount": 18500, "status": "Paid", "issued": "2025-09-01", "due": "2025-10-01"},
    {"client": "Okafor Mining Co.", "invoice": "INV-1053", "amount": 96000, "status": "Overdue", "issued": "2025-07-20", "due": "2025-08-19"},
    {"client": "Delacroix & Sons", "invoice": "INV-1054", "amount": 58000, "status": "Paid", "issued": "2025-09-03", "due": "2025-10-03"},
    {"client": "Whitmore Textiles", "invoice": "INV-1055", "amount": 22000, "status": "Outstanding", "issued": "2025-09-05", "due": "2025-10-05"},
    {"client": "Fentonville Council", "invoice": "INV-1056", "amount": 14000, "status": "Paid", "issued": "2025-09-08", "due": "2025-10-08"},
    {"client": "Global Trust Bank", "invoice": "INV-1057", "amount": 135000, "status": "Outstanding", "issued": "2025-09-12", "due": "2025-10-12"},
]

TRUST_LEDGER = [
    {"client": "Acme Corp", "deposited": 180000, "disbursed": 60000},
    {"client": "Meridian Holdings Ltd.", "deposited": 150000, "disbursed": 40000},
    {"client": "Global Trust Bank", "deposited": 120000, "disbursed": 90000},
    {"client": "Vertex Industries", "deposited": 90000, "disbursed": 30000},
    {"client": "Halcyon Systems", "deposited": 95000, "disbursed": 20000},
    {"client": "Okafor Mining Co.", "deposited": 140000, "disbursed": 55000},
    {"client": "Delacroix & Sons", "deposited": 80000, "disbursed": 25000},
]
for t in TRUST_LEDGER:
    t["balance"] = t["deposited"] - t["disbursed"]

TRUST_TXNS = [
    {"date": "2025-09-16", "client": "Acme Corp", "type": "Deposit", "amount": 25000},
    {"date": "2025-09-14", "client": "Meridian Holdings Ltd.", "type": "Disbursement", "amount": -12000},
    {"date": "2025-09-11", "client": "Global Trust Bank", "type": "Deposit", "amount": 40000},
    {"date": "2025-09-09", "client": "Vertex Industries", "type": "Disbursement", "amount": -8000},
    {"date": "2025-09-03", "client": "Acme Corp", "type": "Disbursement", "amount": -15000},
    {"date": "2025-09-01", "client": "Halcyon Systems", "type": "Deposit", "amount": 30000},
    {"date": "2025-08-28", "client": "Okafor Mining Co.", "type": "Disbursement", "amount": -22000},
    {"date": "2025-08-20", "client": "Delacroix & Sons", "type": "Deposit", "amount": 50000},
    {"date": "2025-08-15", "client": "Global Trust Bank", "type": "Deposit", "amount": 60000},
    {"date": "2025-08-10", "client": "Acme Corp", "type": "Deposit", "amount": 18000},
]

OFFICE_ACCOUNT_BALANCE = 268400
OFFICE_INCOME_6M = [410000, 425000, 398000, 440000, 455000, 470000]
OFFICE_EXPENSE_6M = [312000, 318000, 305000, 330000, 338000, 345000]
OFFICE_TXNS = [
    {"date": "2025-09-15", "desc": "Client Fee Receipt — Meridian Holdings", "category": "Income", "amount": 42000},
    {"date": "2025-09-14", "desc": "Payroll Run — Fortnightly", "category": "Payroll", "amount": -96500},
    {"date": "2025-09-12", "desc": "Office Lease — Liverpool Branch", "category": "Rent", "amount": -8200},
    {"date": "2025-09-10", "desc": "MYOB Subscription", "category": "Software", "amount": -450},
    {"date": "2025-09-08", "desc": "Client Fee Receipt — Vertex Industries", "category": "Income", "amount": 28500},
    {"date": "2025-09-05", "desc": "InfoTrack Search Fees", "category": "Disbursements", "amount": -612},
    {"date": "2025-09-03", "desc": "Client Fee Receipt — Halcyon Systems", "category": "Income", "amount": 72000},
    {"date": "2025-08-30", "desc": "Council & Search Fees", "category": "Disbursements", "amount": -940},
    {"date": "2025-08-28", "desc": "Professional Indemnity Insurance", "category": "Insurance", "amount": -4200},
    {"date": "2025-08-25", "desc": "Client Fee Receipt — Okafor Mining", "category": "Income", "amount": 96000},
]

COMMBIZ_STATUS = [
    {"account": "Office Account", "matched": 142, "unmatched": 3, "last_sync": "2025-09-17 07:12 AM"},
    {"account": "Trust Account", "matched": 58, "unmatched": 0, "last_sync": "2025-09-17 07:12 AM"},
]

MYOB_PL = {"Revenue": 493000, "Wages": 210000, "Overheads": 86000}
MYOB_PL["Net Profit"] = MYOB_PL["Revenue"] - MYOB_PL["Wages"] - MYOB_PL["Overheads"]
MYOB_LAST_SYNC = "2025-09-17 06:02 AM"

COMMISSIONS = [
    {"matter": "Acme vs. Zenith Trial Brief Filing", "referrer": "External — Dalton & Whitmore", "rate_pct": 8, "amount": 33600, "status": "Payable"},
    {"matter": "Global Trust M&A Preliminary Hearing", "referrer": "Internal — Sterling, C.", "rate_pct": 5, "amount": 30500, "status": "Paid"},
    {"matter": "Vertex Patent Portfolio Review", "referrer": "External — IP Connect Referrals", "rate_pct": 10, "amount": 18000, "status": "Payable"},
    {"matter": "Zenith Labs Licensing Countersuit", "referrer": "Internal — Specter, H.", "rate_pct": 5, "amount": 13000, "status": "Paid"},
    {"matter": "Halcyon Trademark Portfolio Audit", "referrer": "External — IP Connect Referrals", "rate_pct": 10, "amount": 21000, "status": "Payable"},
    {"matter": "Okafor Mining Environmental Claim", "referrer": "Internal — Ross, M.", "rate_pct": 5, "amount": 19000, "status": "Paid"},
    {"matter": "Global Trust Bank Regulatory Investigation", "referrer": "External — Dalton & Whitmore", "rate_pct": 8, "amount": 41600, "status": "Payable"},
    {"matter": "Delacroix Group Acquisition", "referrer": "Internal — Pearson, J.", "rate_pct": 5, "amount": 14750, "status": "Paid"},
]

RAPIDPAY_SUMMARY = {"volume": 186400, "fee_rate": 1.75, "fees_paid": 3262}
RAPIDPAY_TXNS = [
    {"date": "2025-09-15", "client": "Acme Corp", "amount": 8600, "fee": 150.5},
    {"date": "2025-09-12", "client": "Harlow & Co.", "amount": 4200, "fee": 73.5},
    {"date": "2025-09-10", "client": "Nova Materials", "amount": 6100, "fee": 106.75},
    {"date": "2025-09-05", "client": "Bright Path Foundation", "amount": 2900, "fee": 50.75},
    {"date": "2025-09-14", "client": "Halcyon Systems", "amount": 7200, "fee": 126.0},
    {"date": "2025-09-13", "client": "Okafor Mining Co.", "amount": 9600, "fee": 168.0},
    {"date": "2025-09-09", "client": "Whitmore Textiles", "amount": 3100, "fee": 54.25},
    {"date": "2025-09-02", "client": "Delacroix & Sons", "amount": 5400, "fee": 94.5},
]

INFOTRACK_ORDERS = [
    {"matter": "Vertex Patent Portfolio Review", "search_type": "Patent Register Search", "cost": 85, "date": "2025-09-10", "status": "Complete"},
    {"matter": "Meridian Series C Financing", "search_type": "PPSR Search", "cost": 42, "date": "2025-09-08", "status": "Complete"},
    {"matter": "Global Trust M&A Preliminary Hearing", "search_type": "Company Title Search", "cost": 65, "date": "2025-09-12", "status": "Pending"},
    {"matter": "Acme vs. Zenith Trial Brief Filing", "search_type": "Land Title Search", "cost": 38, "date": "2025-09-14", "status": "Complete"},
    {"matter": "Halcyon Trademark Portfolio Audit", "search_type": "Trademark Register Search", "cost": 65, "date": "2025-09-11", "status": "Complete"},
    {"matter": "Blackwood Realty Lease Restructure", "search_type": "Land Title Search", "cost": 38, "date": "2025-09-13", "status": "Complete"},
    {"matter": "Okafor Mining Environmental Claim", "search_type": "EPA Register Search", "cost": 110, "date": "2025-09-15", "status": "Pending"},
    {"matter": "Delacroix Group Acquisition", "search_type": "Company Title Search", "cost": 65, "date": "2025-09-16", "status": "Complete"},
]

COUNCIL_SEARCHES = [
    {"matter": "Bright Path Governance Advisory", "branch": "Richmond", "search_type": "Rates Certificate", "cost": 95, "date": "2025-09-09", "status": "Complete"},
    {"matter": "Harlow Wrongful Termination Defense", "branch": "Camden", "search_type": "Section 10.7 Planning Certificate", "cost": 120, "date": "2025-09-11", "status": "Pending"},
    {"matter": "Acme vs. Zenith Trial Brief Filing", "branch": "Liverpool", "search_type": "Rates Certificate", "cost": 95, "date": "2025-09-13", "status": "Complete"},
    {"matter": "Blackwood Realty Lease Restructure", "branch": "Richmond", "search_type": "Section 10.7 Planning Certificate", "cost": 120, "date": "2025-09-14", "status": "Complete"},
    {"matter": "Fentonville Council Planning Advisory", "branch": "Richmond", "search_type": "Rates Certificate", "cost": 95, "date": "2025-09-15", "status": "Pending"},
    {"matter": "Nova Materials Supply Contract Review", "branch": "Liverpool", "search_type": "Rates Certificate", "cost": 95, "date": "2025-09-16", "status": "Complete"},
]
for c in COUNCIL_SEARCHES:
    c["council"] = BRANCH_COUNCIL[c["branch"]]

CARD_EXPENSES = [
    {"card": "Amex", "date": "2025-09-15", "merchant": "Qantas Club", "category": "Travel", "amount": 429, "branch": "Richmond"},
    {"card": "Visa", "date": "2025-09-14", "merchant": "Officeworks", "category": "Supplies", "amount": 186, "branch": "Camden"},
    {"card": "Amex", "date": "2025-09-12", "merchant": "Uber", "category": "Travel", "amount": 54, "branch": "Liverpool"},
    {"card": "Visa", "date": "2025-09-10", "merchant": "LEAP Legal Software", "category": "Software", "amount": 720, "branch": "Liverpool"},
    {"card": "Amex", "date": "2025-09-08", "merchant": "The Grounds Cafe", "category": "Client Entertainment", "amount": 142, "branch": "Camden"},
    {"card": "Visa", "date": "2025-09-05", "merchant": "Bunnings", "category": "Office Maintenance", "amount": 98, "branch": "Richmond"},
    {"card": "Amex", "date": "2025-09-16", "merchant": "Marriott Hotels", "category": "Travel", "amount": 612, "branch": "Camden"},
    {"card": "Visa", "date": "2025-09-13", "merchant": "Woolworths Metro", "category": "Supplies", "amount": 64, "branch": "Liverpool"},
    {"card": "Amex", "date": "2025-09-11", "merchant": "Ampol", "category": "Fuel", "amount": 88, "branch": "Richmond"},
    {"card": "Visa", "date": "2025-09-09", "merchant": "Zoom Subscription", "category": "Software", "amount": 45, "branch": "Camden"},
    {"card": "Amex", "date": "2025-09-07", "merchant": "Ritz Carlton Dining", "category": "Client Entertainment", "amount": 320, "branch": "Liverpool"},
    {"card": "Visa", "date": "2025-09-04", "merchant": "JB Hi-Fi", "category": "Equipment", "amount": 540, "branch": "Richmond"},
]

KPIS = [
    {"label": "Active Matters", "value": "142 Case Files", "pct": 8.3, "up": True,
     "spark": [100, 106, 103, 112, 118, 115, 124, 130, 127, 136, 133, 142]},
    {"label": "Billable Hours (MTD)", "value": "1,840.5 hrs", "pct": 5.1, "up": True,
     "spark": [1550, 1610, 1580, 1660, 1700, 1650, 1720, 1690, 1760, 1730, 1800, 1840]},
    {"label": "Collected Revenue", "value": "$1.48 M", "pct": 12.4, "up": True,
     "spark": [0.95, 1.02, 0.98, 1.10, 1.15, 1.08, 1.20, 1.18, 1.28, 1.32, 1.40, 1.48]},
    {"label": "Utilization Rate", "value": "84.2 %", "pct": -2.1, "up": False,
     "spark": [88, 87, 89, 86, 87, 85, 86, 84, 85, 83, 84, 84.2]},
    {"label": "Upcoming Deadlines", "value": "18 Matters", "pct": 15.3, "up": True,
     "spark": [10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 17, 18]},
]

TREND = pd.DataFrame({
    "month": MONTHS,
    "Litigation": [58, 62, 60, 68, 72, 70, 76, 74, 66, 72, 78, 82],
    "Corporate": [48, 52, 55, 58, 62, 66, 64, 70, 68, 74, 78, 80],
})

WORKLOAD = {"Corporate": 33, "Litigation": 25, "IP Portfolio": 25, "Employment": 17}
TOTAL_ACTIVE = 142

INSIGHTS = [
    ("TOP BILLING ASSOCIATE", "Harvey Specter, JD", "184 billable hours logged MTD (104% of target)"),
    ("LARGEST RECENT WIN", "Acme Corp vs. Zenith Labs", "Full defense verdict + $2.1M counter-claim won"),
]

BILLING_BAR_COLORS = {"Retainer Deposited (Trust)": TEAL, "Work-in-Progress (Unbilled)": "rgba(10,132,150,0.6)",
                       "Outstanding Invoices": AMBER}

STATUS_COLORS = {
    "Open": (GREEN, GREEN_TINT), "Closed": (MUTED, BG), "On Hold": (AMBER, AMBER_TINT),
    "Paid": (GREEN, GREEN_TINT), "Outstanding": (AMBER, AMBER_TINT), "Overdue": (RED, RED_TINT),
    "Complete": (GREEN, GREEN_TINT), "Pending": (AMBER, AMBER_TINT), "Payable": (AMBER, AMBER_TINT),
}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def fmt_money(v):
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1_000_000:
        return f"{sign}${v/1_000_000:.2f} M"
    if v >= 1_000:
        return f"{sign}${v/1_000:.0f} K"
    return f"{sign}${v:,.0f}"


def sparkline_svg(values, color, width=60, height=30):
    values = np.asarray(values, dtype=float)
    lo, hi = values.min(), values.max()
    span = (hi - lo) or 1.0
    n = len(values)
    step = width / (n - 1) if n > 1 else width
    pts = []
    for i, v in enumerate(values):
        x = i * step
        y = height - ((v - lo) / span) * height
        pts.append(f"{x:.1f},{y:.1f}")
    points = " ".join(pts)
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def trend_arrow(up):
    color = GREEN if up else RED
    d = "M6 2v8M2.5 6.5 6 10l3.5-3.5" if up else "M6 10V2M2.5 5.5 6 2l3.5 3.5"
    return (f'<svg width="12" height="12" viewBox="0 0 12 12" fill="none">'
            f'<path d="{d}" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def kpi_html(k):
    color = GREEN if k["up"] else RED
    return f"""
    <div class="kpi-card">
      <div class="kpi-label">{k['label']}</div>
      <div class="kpi-bottom">
        <div>
          <div class="kpi-value">{k['value']}</div>
          <div class="kpi-trend">
            {trend_arrow(k['up'])}
            <span class="pct" style="color:{color}">{'+' if k['up'] else ''}{k['pct']}%</span>
            <span class="vs">vs LY</span>
          </div>
        </div>
        {sparkline_svg(k['spark'], TEAL)}
      </div>
    </div>
    """


def plain_kpi_html(label, value, color=INK):
    return f"""
    <div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value" style="color:{color};">{value}</div>
    </div>
    """


def status_pill(status):
    fg, bg = STATUS_COLORS.get(status, (MUTED, BG))
    return f'<span class="status-pill" style="background:{bg}; color:{fg};">{status}</span>'


def plotly_base(height):
    return dict(
        margin=dict(l=8, r=8, t=4, b=4), height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False, font=dict(family="Inter, sans-serif", color=MUTED, size=10),
    )


def spacer(h=10):
    st.markdown(f'<div style="height:{h}px"></div>', unsafe_allow_html=True)


def render_html_table(df, money_cols=None, status_col=None):
    show = df.copy()
    money_cols = money_cols or []
    for col in money_cols:
        show[col] = show[col].map(fmt_money)
    if status_col and status_col in show.columns:
        show[status_col] = show[status_col].map(status_pill)
    st.write(show.to_html(escape=False, index=False, classes="simple"), unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Top bar — real, clickable navigation
# ----------------------------------------------------------------------
if "active_section" not in st.session_state:
    st.session_state.active_section = "Overview"

with st.container(border=True):
    brand_col, nav_cols_wrap, user_col = st.columns([1.1, 5.0, 1.5], vertical_alignment="center")
    with brand_col:
        st.markdown(
            '<div class="brand"><div class="brand-badge">&Lambda;</div>'
            '<div class="brand-name">D&#39;Agostino Legal</div></div>',
            unsafe_allow_html=True,
        )
    with nav_cols_wrap:
        nav_cols = st.columns(len(NAV_ITEMS))
        for col, item in zip(nav_cols, NAV_ITEMS):
            with col:
                is_active = st.session_state.active_section == item
                if st.button(item, key=f"nav_{item}",
                             type="primary" if is_active else "secondary",
                             width="stretch"):
                    st.session_state.active_section = item
                    st.rerun()
    with user_col:
        initials = "".join(part[0] for part in USER_NAME.split()[:2]).upper()
        st.markdown(
            f"""
            <div class="user-row">
              <div>
                <div class="user-name" style="text-align:right;">Welcome, {USER_NAME}</div>
                <div class="user-role" style="text-align:right;">{USER_ROLE}</div>
              </div>
              <div class="avatar-initials">{initials}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

spacer()
section = st.session_state.active_section


# ----------------------------------------------------------------------
# Overview
# ----------------------------------------------------------------------
def render_overview():
    kpi_cols = st.columns(5)
    for col, k in zip(kpi_cols, KPIS):
        with col:
            st.markdown(kpi_html(k), unsafe_allow_html=True)

    spacer()
    col_trend, col_donut, col_insights = st.columns([1.6, 1, 1])

    with col_trend:
        with st.container(border=True):
            top1, top2 = st.columns([1.6, 1], vertical_alignment="center")
            with top1:
                st.markdown('<div class="card-title">Matter Activity Trend By Practice Group</div>',
                            unsafe_allow_html=True)
            with top2:
                st.markdown(
                    f"""
                    <div class="legend-row" style="justify-content:flex-end;">
                      <span class="legend-item"><span class="legend-dot" style="background:{TEAL}"></span>Litigation</span>
                      <span class="legend-item"><span class="legend-dot" style="background:#67c1cb"></span>Corporate</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=TREND["month"], y=TREND["Litigation"], mode="lines",
                                      name="Litigation", line=dict(color=TEAL, width=2.4, shape="spline"),
                                      hovertemplate="%{x}: %{y} hrs<extra>Litigation</extra>"))
            fig.add_trace(go.Scatter(x=TREND["month"], y=TREND["Corporate"], mode="lines",
                                      name="Corporate", line=dict(color="#67c1cb", width=2.4, shape="spline"),
                                      hovertemplate="%{x}: %{y} hrs<extra>Corporate</extra>"))
            fig.update_layout(**plotly_base(200), hovermode="x unified")
            fig.update_xaxes(showgrid=False, tickfont=dict(size=9))
            fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9", tickfont=dict(size=9))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with col_donut:
        with st.container(border=True):
            st.markdown('<div class="card-title">Workload By Practice Area</div>', unsafe_allow_html=True)
            labels = list(WORKLOAD.keys())
            values = list(WORKLOAD.values())
            colors = [TEAL, "#3ba7b3", "#7bc4cd", "#b7dee2"]
            donut_col, legend_col = st.columns([1, 1], vertical_alignment="center")
            with donut_col:
                fig2 = go.Figure(data=[go.Pie(
                    labels=labels, values=values, hole=0.68,
                    marker=dict(colors=colors, line=dict(color="#ffffff", width=2)),
                    textinfo="none", sort=False,
                    hovertemplate="%{label}: %{value}%<extra></extra>",
                )])
                donut_layout = plotly_base(170)
                donut_layout["margin"] = dict(l=10, r=10, t=10, b=10)
                fig2.update_layout(**donut_layout)
                fig2.add_annotation(
                    text=f"<b style='font-size:22px;'>{TOTAL_ACTIVE}</b><br><span style='font-size:10px; color:{FAINT};'>Total Active</span>",
                    x=0.5, y=0.5, showarrow=False, align="center",
                    font=dict(family="Inter, sans-serif", color=INK),
                )
                st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})
            with legend_col:
                for label, color in zip(labels, colors):
                    st.markdown(
                        f'<div class="donut-legend-item"><span class="legend-dot" '
                        f'style="background:{color}"></span>{label} ({WORKLOAD[label]}%)</div>',
                        unsafe_allow_html=True,
                    )

    with col_insights:
        with st.container(border=True):
            st.markdown('<div class="card-title">Critical Partner Metrics</div>', unsafe_allow_html=True)
            for kicker, headline, desc in INSIGHTS:
                st.markdown(
                    f"""
                    <div style="margin-top:12px;">
                      <div class="insight-kicker">{kicker}</div>
                      <div class="insight-headline">{headline}</div>
                      <div class="insight-desc">{desc}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    spacer()
    col_matrix, col_right = st.columns([1.6, 1])

    with col_matrix:
        with st.container(border=True):
            header_row, filter_row = st.columns([2, 1.2], vertical_alignment="center")
            with header_row:
                st.markdown('<div class="card-title">Attorney Utilization Matrix (Hours MTD)</div>',
                            unsafe_allow_html=True)
            with filter_row:
                highlight = st.selectbox("Highlight practice area", ["None"] + PRACTICE_AREAS[:4],
                                          key="overview_matrix_highlight", label_visibility="collapsed")
            spacer()
            header_cells = "".join(
                f'<th style="{"color:%s;" % TEAL if c == highlight else ""}">{c}</th>'
                for c in ["Corporate", "Litigation", "IP Portfolio", "Advisory"]
            )
            rows_html = []
            for a in ATTORNEYS:
                cells = ""
                for c in ["Corporate", "Litigation", "IP Portfolio", "Advisory"]:
                    alpha = MATRIX_ALPHA[a["short"]][c]
                    border = f"outline: 2px solid {TEAL}; outline-offset:-2px;" if c == highlight else ""
                    cells += (f'<td style="background:rgba(10,132,150,{alpha}); {border}">'
                              f'{a["hours"][c]} hrs</td>')
                rows_html.append(f'<tr><td>{a["short"]}</td>{cells}<td>{a["total"]} hrs</td></tr>')
            table_html = f"""
            <table class="matrix">
              <thead><tr><th>Attorney</th>{header_cells}<th>Total Hrs</th></tr></thead>
              <tbody>{''.join(rows_html)}</tbody>
            </table>
            """
            st.markdown(table_html, unsafe_allow_html=True)

    with col_right:
        with st.container(border=True):
            st.markdown('<div class="card-title">Billing &amp; Trust Account Status (K$)</div>',
                         unsafe_allow_html=True)
            spacer()
            bars = [("Retainer Deposited (Trust)", 420, 76), ("Work-in-Progress (Unbilled)", 280, 50),
                    ("Outstanding Invoices", 110, 20)]
            for label, k_amount, pct in bars:
                st.markdown(
                    f"""
                    <div class="bar-row">
                      <div class="bar-head">
                        <span class="lbl">{label}</span>
                        <span class="val">${k_amount}K</span>
                      </div>
                      <div class="bar-track">
                        <div class="bar-fill" style="width:{pct}%; background:{BILLING_BAR_COLORS[label]};"></div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        spacer()

        with st.container(border=True):
            st.markdown('<div class="card-title">Upcoming Court Appearances &amp; Filings</div>',
                         unsafe_allow_html=True)
            spacer()
            for d in DEADLINES[:2]:
                dt = pd.to_datetime(d["date"])
                fg, bg = (TEAL, TEAL_TINT) if dt.month == 10 else (GREEN, GREEN_TINT)
                st.markdown(
                    f"""
                    <div class="deadline-item">
                      <div class="date-badge" style="background:{bg}; color:{fg};">{dt.strftime('%b %d')}</div>
                      <div>
                        <div class="deadline-title">{d['title']}</div>
                        <div class="deadline-sub">{d['court']} · Assigned: {d['attorney']}</div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.caption("Full calendar → the Calendar tab above.")

    spacer()
    col_branch_rev, col_inv_status = st.columns(2)

    with col_branch_rev:
        with st.container(border=True):
            st.markdown('<div class="card-title">Monthly Revenue by Branch</div>', unsafe_allow_html=True)
            bdf = pd.DataFrame(BRANCHES)
            fig_b = go.Figure()
            fig_b.add_trace(go.Bar(x=bdf["name"], y=bdf["monthly_revenue"], name="Revenue",
                                    marker_color=TEAL, hovertemplate="%{x}: $%{y:,.0f}<extra>Revenue</extra>"))
            fig_b.add_trace(go.Bar(x=bdf["name"], y=bdf["monthly_cost"], name="Cost",
                                    marker_color="#c7d6dc", hovertemplate="%{x}: $%{y:,.0f}<extra>Cost</extra>"))
            layout_b = plotly_base(150)
            layout_b["showlegend"] = True
            layout_b["legend"] = dict(orientation="h", y=1.2, font=dict(size=9))
            fig_b.update_layout(**layout_b, barmode="group")
            fig_b.update_yaxes(showgrid=True, gridcolor="#f1f5f9")
            st.plotly_chart(fig_b, width="stretch", config={"displayModeBar": False})

    with col_inv_status:
        with st.container(border=True):
            st.markdown('<div class="card-title">Invoice Status Breakdown</div>', unsafe_allow_html=True)
            inv_df = pd.DataFrame(INVOICES)
            by_status = inv_df.groupby("status")["amount"].sum()
            order = ["Paid", "Outstanding", "Overdue"]
            vals = [by_status.get(s, 0) for s in order]
            fig_i = go.Figure(go.Bar(
                x=order, y=vals,
                marker_color=[STATUS_COLORS[s][0] for s in order],
                hovertemplate="%{x}: $%{y:,.0f}<extra></extra>",
            ))
            fig_i.update_layout(**plotly_base(150))
            fig_i.update_yaxes(showgrid=True, gridcolor="#f1f5f9")
            st.plotly_chart(fig_i, width="stretch", config={"displayModeBar": False})


# ----------------------------------------------------------------------
# Matters (List / Types / Locations)
# ----------------------------------------------------------------------
def _matters_list_tab():
    df = pd.DataFrame(MATTERS)
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
        with c1:
            search = st.text_input("Search matters or clients", placeholder="e.g. Acme, Vertex")
        with c2:
            practice_filter = st.multiselect("Practice area", sorted(df["practice"].unique()))
        with c3:
            status_filter = st.multiselect("Status", sorted(df["status"].unique()))
        with c4:
            branch_filter = st.multiselect("Branch", BRANCH_NAMES)

        filtered = df.copy()
        if search:
            mask = (filtered["name"].str.contains(search, case=False)
                    | filtered["client"].str.contains(search, case=False)
                    | filtered["practice"].str.contains(search, case=False))
            filtered = filtered[mask]
        if practice_filter:
            filtered = filtered[filtered["practice"].isin(practice_filter)]
        if status_filter:
            filtered = filtered[filtered["status"].isin(status_filter)]
        if branch_filter:
            filtered = filtered[filtered["branch"].isin(branch_filter)]

    spacer()
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(plain_kpi_html("Matters shown", str(len(filtered))), unsafe_allow_html=True)
    with m2:
        st.markdown(plain_kpi_html("Open matters", str((filtered["status"] == "Open").sum())),
                     unsafe_allow_html=True)
    with m3:
        st.markdown(plain_kpi_html("Total est. value", fmt_money(filtered["value"].sum())),
                     unsafe_allow_html=True)

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">Matter list</div>', unsafe_allow_html=True)
        spacer()
        if filtered.empty:
            st.info("No matters match those filters.")
        else:
            show = filtered.copy()
            show["Est. Value"] = show["value"].map(fmt_money)
            show = show.rename(columns={
                "name": "Matter", "client": "Client", "practice": "Practice Area",
                "attorney": "Attorney", "status": "Status", "opened": "Opened", "branch": "Branch",
            })[["Matter", "Client", "Practice Area", "Attorney", "Branch", "Status", "Opened", "Est. Value"]]
            st.dataframe(show, width="stretch", hide_index=True)


def _matter_types_tab():
    df = pd.DataFrame(MATTERS)
    by_type = df.groupby("practice").agg(count=("name", "count"), value=("value", "sum")).reset_index()
    by_type = by_type.sort_values("value", ascending=True)

    col_chart, col_table = st.columns([1, 1])
    with col_chart:
        with st.container(border=True):
            st.markdown('<div class="card-title">Est. value by matter type</div>', unsafe_allow_html=True)
            fig = go.Figure(go.Bar(
                x=by_type["value"], y=by_type["practice"], orientation="h",
                marker=dict(color=TEAL),
                hovertemplate="%{y}: $%{x:,.0f}<extra></extra>",
            ))
            layout = plotly_base(260)
            layout["margin"] = dict(l=8, r=16, t=4, b=4)
            fig.update_layout(**layout)
            fig.update_xaxes(visible=False)
            fig.update_yaxes(tickfont=dict(size=11, color=MUTED))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with col_table:
        with st.container(border=True):
            st.markdown('<div class="card-title">Matter type summary</div>', unsafe_allow_html=True)
            spacer()
            show = by_type.sort_values("value", ascending=False).copy()
            show["value"] = show["value"].map(fmt_money)
            show = show.rename(columns={"practice": "Practice Area", "count": "Matters", "value": "Est. Value"})
            st.dataframe(show, width="stretch", hide_index=True)


def _locations_tab():
    st.markdown('<div class="section-sub">3 branches — hover a marker or the cards below for details.</div>',
                unsafe_allow_html=True)
    with st.container(border=True):
        map_df = pd.DataFrame(BRANCHES)[["lat", "lon"]]
        st.map(map_df, size=200, color="#0a8496")

    spacer()
    cols = st.columns(3)
    for col, b in zip(cols, BRANCHES):
        with col:
            margin = b["monthly_revenue"] - b["monthly_cost"]
            st.markdown(
                f"""
                <div class="branch-card">
                  <div class="branch-name">{b['name']}</div>
                  <div class="branch-council">{b['council']}</div>
                  <div class="bar-row">
                    <div class="bar-head"><span class="lbl">Headcount</span><span class="val">{b['headcount']}</span></div>
                    <div class="bar-head"><span class="lbl">Active Matters</span><span class="val">{b['active_matters']}</span></div>
                    <div class="bar-head"><span class="lbl">Monthly Revenue</span><span class="val">{fmt_money(b['monthly_revenue'])}</span></div>
                    <div class="bar-head"><span class="lbl">Monthly Cost</span><span class="val">{fmt_money(b['monthly_cost'])}</span></div>
                    <div class="bar-head"><span class="lbl">Net Margin</span>
                      <span class="val" style="color:{GREEN if margin >= 0 else RED};">{fmt_money(margin)}</span></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">Active matters by branch</div>', unsafe_allow_html=True)
        bdf = pd.DataFrame(BRANCHES)
        fig = go.Figure(go.Bar(x=bdf["name"], y=bdf["active_matters"], marker=dict(color=TEAL),
                                hovertemplate="%{x}: %{y} matters<extra></extra>"))
        fig.update_layout(**plotly_base(220))
        fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_matters():
    st.markdown('<div class="section-title">Matters</div>', unsafe_allow_html=True)
    tabs = st.tabs(["Matter List", "Matter Types", "Locations"])
    with tabs[0]:
        _matters_list_tab()
    with tabs[1]:
        _matter_types_tab()
    with tabs[2]:
        _locations_tab()


# ----------------------------------------------------------------------
# Clients
# ----------------------------------------------------------------------
def render_clients():
    st.markdown('<div class="section-title">Clients</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Firm-wide client roster, sortable by billing and tenure.</div>',
                unsafe_allow_html=True)

    df = pd.DataFrame(CLIENTS)
    with st.container(border=True):
        c1, c2 = st.columns([1.6, 1.2])
        with c1:
            search = st.text_input("Search clients", placeholder="e.g. Acme, Nova")
        with c2:
            sort_by = st.selectbox("Sort by", ["Total Billed (high→low)", "Active Matters (high→low)",
                                                "Client Since (newest)", "Client Since (oldest)"])
        filtered = df.copy()
        if search:
            filtered = filtered[filtered["name"].str.contains(search, case=False)]
        if sort_by == "Total Billed (high→low)":
            filtered = filtered.sort_values("billed", ascending=False)
        elif sort_by == "Active Matters (high→low)":
            filtered = filtered.sort_values("matters", ascending=False)
        elif sort_by == "Client Since (newest)":
            filtered = filtered.sort_values("since", ascending=False)
        else:
            filtered = filtered.sort_values("since", ascending=True)

    spacer()
    col_table, col_chart = st.columns([1.5, 1])
    with col_table:
        with st.container(border=True):
            st.markdown('<div class="card-title">Client roster</div>', unsafe_allow_html=True)
            spacer()
            if filtered.empty:
                st.info("No clients match that search.")
            else:
                show = filtered.copy()
                show["Total Billed"] = show["billed"].map(fmt_money)
                show = show.rename(columns={
                    "name": "Client", "practice": "Practice Area", "attorney": "Relationship Attorney",
                    "matters": "Active Matters", "since": "Client Since",
                })[["Client", "Practice Area", "Relationship Attorney", "Active Matters", "Client Since", "Total Billed"]]
                st.dataframe(show, width="stretch", hide_index=True)

    with col_chart:
        with st.container(border=True):
            st.markdown('<div class="card-title">Top clients by revenue</div>', unsafe_allow_html=True)
            top = df.sort_values("billed", ascending=True).tail(8)
            fig = go.Figure(go.Bar(
                x=top["billed"], y=top["name"], orientation="h",
                marker=dict(color=TEAL),
                hovertemplate="%{y}: $%{x:,.0f}<extra></extra>",
            ))
            layout = plotly_base(280)
            layout["margin"] = dict(l=8, r=16, t=4, b=4)
            fig.update_layout(**layout)
            fig.update_xaxes(visible=False)
            fig.update_yaxes(tickfont=dict(size=10, color=MUTED))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ----------------------------------------------------------------------
# Calendar
# ----------------------------------------------------------------------
def render_calendar():
    st.markdown('<div class="section-title">Calendar</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Upcoming court appearances, filings, and closings.</div>',
                unsafe_allow_html=True)

    df = pd.DataFrame(DEADLINES)
    df["dt"] = pd.to_datetime(df["date"])
    min_d, max_d = df["dt"].min().date(), df["dt"].max().date()

    with st.container(border=True):
        c1, c2 = st.columns([1.4, 1.4])
        with c1:
            date_range = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        with c2:
            attorney_filter = st.multiselect("Attorney", sorted(df["attorney"].unique()))

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
    else:
        start, end = min_d, max_d
    mask = (df["dt"].dt.date >= start) & (df["dt"].dt.date <= end)
    filtered = df[mask]
    if attorney_filter:
        filtered = filtered[filtered["attorney"].isin(attorney_filter)]
    filtered = filtered.sort_values("dt")

    spacer()
    if filtered.empty:
        st.info("No deadlines in that range.")
        return

    for month, group in filtered.groupby(filtered["dt"].dt.strftime("%B %Y")):
        with st.container(border=True):
            st.markdown(f'<div class="card-title">{month}</div>', unsafe_allow_html=True)
            spacer()
            for _, d in group.iterrows():
                fg, bg = (TEAL, TEAL_TINT) if d["dt"].month % 2 else (GREEN, GREEN_TINT)
                st.markdown(
                    f"""
                    <div class="deadline-item">
                      <div class="date-badge" style="background:{bg}; color:{fg};">{d['dt'].strftime('%b %d')}</div>
                      <div>
                        <div class="deadline-title">{d['title']}</div>
                        <div class="deadline-sub">{d['court']} · Assigned: {d['attorney']}</div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        spacer()


# ----------------------------------------------------------------------
# Finance (Office Account / Trust Account / CommBiz / MYOB /
#           Billing & Invoices / Commission / RapidPay / InfoTrack /
#           Council / Card Expenses)
# ----------------------------------------------------------------------
def _office_account_tab():
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(plain_kpi_html("Current Balance", fmt_money(OFFICE_ACCOUNT_BALANCE), TEAL), unsafe_allow_html=True)
    with m2:
        st.markdown(plain_kpi_html("This Month's Income", fmt_money(OFFICE_INCOME_6M[-1]), GREEN), unsafe_allow_html=True)
    with m3:
        st.markdown(plain_kpi_html("This Month's Expense", fmt_money(-OFFICE_EXPENSE_6M[-1]), RED), unsafe_allow_html=True)

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">Income vs Expense — last 6 months</div>', unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=MONTHS_6, y=OFFICE_INCOME_6M, name="Income", marker_color=TEAL,
                              hovertemplate="%{x}: $%{y:,.0f}<extra>Income</extra>"))
        fig.add_trace(go.Bar(x=MONTHS_6, y=OFFICE_EXPENSE_6M, name="Expense", marker_color=AMBER,
                              hovertemplate="%{x}: $%{y:,.0f}<extra>Expense</extra>"))
        layout = plotly_base(220)
        layout["showlegend"] = True
        layout["legend"] = dict(orientation="h", y=1.15)
        fig.update_layout(**layout, barmode="group")
        fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">Recent transactions</div>', unsafe_allow_html=True)
        spacer()
        df = pd.DataFrame(OFFICE_TXNS)
        show = df.copy()
        show["amount"] = show["amount"].map(fmt_money)
        show = show.rename(columns={"date": "Date", "desc": "Description", "category": "Category", "amount": "Amount"})
        st.dataframe(show, width="stretch", hide_index=True)


def _trust_account_tab():
    total_held = sum(t["balance"] for t in TRUST_LEDGER)
    m1, m2 = st.columns(2)
    with m1:
        st.markdown(plain_kpi_html("Total Trust Held", fmt_money(total_held), TEAL), unsafe_allow_html=True)
    with m2:
        st.markdown(plain_kpi_html("Clients with trust balances", str(len(TRUST_LEDGER))), unsafe_allow_html=True)

    spacer()
    col_chart, col_table = st.columns([1, 1.2])
    with col_chart:
        with st.container(border=True):
            st.markdown('<div class="card-title">Trust balance by client</div>', unsafe_allow_html=True)
            df = pd.DataFrame(TRUST_LEDGER).sort_values("balance", ascending=True)
            fig = go.Figure(go.Bar(x=df["balance"], y=df["client"], orientation="h", marker_color=TEAL,
                                    hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
            layout = plotly_base(240)
            layout["margin"] = dict(l=8, r=16, t=4, b=4)
            fig.update_layout(**layout)
            fig.update_xaxes(visible=False)
            fig.update_yaxes(tickfont=dict(size=10, color=MUTED))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with col_table:
        with st.container(border=True):
            st.markdown('<div class="card-title">Recent trust transactions</div>', unsafe_allow_html=True)
            spacer()
            df = pd.DataFrame(TRUST_TXNS)
            show = df.copy()
            show["amount"] = show["amount"].map(fmt_money)
            show = show.rename(columns={"date": "Date", "client": "Client", "type": "Type", "amount": "Amount"})
            st.dataframe(show, width="stretch", hide_index=True)


def _commbiz_tab():
    st.markdown('<div class="section-sub">Commonwealth Bank business banking feed — reconciliation status.</div>',
                unsafe_allow_html=True)
    cols = st.columns(len(COMMBIZ_STATUS))
    for col, acc in zip(cols, COMMBIZ_STATUS):
        with col:
            ok = acc["unmatched"] == 0
            fg = GREEN if ok else AMBER
            st.markdown(
                f"""
                <div class="branch-card">
                  <div class="branch-name">{acc['account']}</div>
                  <div class="branch-council">Last sync: {acc['last_sync']}</div>
                  <div class="bar-row">
                    <div class="bar-head"><span class="lbl">Matched</span><span class="val" style="color:{GREEN};">{acc['matched']}</span></div>
                    <div class="bar-head"><span class="lbl">Unmatched</span><span class="val" style="color:{fg};">{acc['unmatched']}</span></div>
                  </div>
                  {status_pill('Fully Reconciled' if ok else 'Needs Review')}
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.caption("Sample bank-feed status — wire this to a real CommBiz export or API when ready.")


def _myob_tab():
    st.markdown(f'<div class="section-sub">Last synced {MYOB_LAST_SYNC}. Current-month P&amp;L snapshot.</div>',
                unsafe_allow_html=True)
    cols = st.columns(4)
    for col, (label, val) in zip(cols, MYOB_PL.items()):
        with col:
            st.markdown(plain_kpi_html(label, fmt_money(val), TEAL if label == "Revenue" else INK),
                        unsafe_allow_html=True)

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">P&amp;L breakdown</div>', unsafe_allow_html=True)
        fig = go.Figure(go.Bar(
            x=list(MYOB_PL.keys()), y=list(MYOB_PL.values()),
            marker_color=[TEAL, AMBER, AMBER, GREEN if MYOB_PL["Net Profit"] >= 0 else RED],
            hovertemplate="%{x}: $%{y:,.0f}<extra></extra>",
        ))
        fig.update_layout(**plotly_base(220))
        fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _billing_invoices_tab():
    inv = pd.DataFrame(INVOICES)
    status_filter = st.multiselect("Invoice status", sorted(inv["status"].unique()),
                                    default=sorted(inv["status"].unique()), key="billing_status_filter")
    filtered = inv[inv["status"].isin(status_filter)] if status_filter else inv.iloc[0:0]

    spacer()
    totals = filtered.groupby("status")["amount"].sum().to_dict()
    m_cols = st.columns(3)
    for col, s in zip(m_cols, ["Paid", "Outstanding", "Overdue"]):
        with col:
            amt = totals.get(s, 0)
            fg, _ = STATUS_COLORS[s]
            st.markdown(plain_kpi_html(s, fmt_money(amt), fg), unsafe_allow_html=True)

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">Invoices</div>', unsafe_allow_html=True)
        spacer()
        if filtered.empty:
            st.info("No invoices match that filter.")
        else:
            render_html_table(
                filtered.rename(columns={"client": "Client", "invoice": "Invoice", "amount": "Amount",
                                          "status": "Status", "issued": "Issued", "due": "Due"})
                [["Invoice", "Client", "Amount", "Status", "Issued", "Due"]],
                money_cols=["Amount"], status_col="Status",
            )


def _commission_tab():
    df = pd.DataFrame(COMMISSIONS)
    status_filter = st.selectbox("Status", ["All"] + sorted(df["status"].unique()), key="commission_status_filter")
    filtered = df if status_filter == "All" else df[df["status"] == status_filter]

    m1, m2 = st.columns(2)
    with m1:
        st.markdown(plain_kpi_html("Total commission (filtered)", fmt_money(filtered["amount"].sum()), TEAL),
                     unsafe_allow_html=True)
    with m2:
        payable = df[df["status"] == "Payable"]["amount"].sum()
        st.markdown(plain_kpi_html("Payable (all matters)", fmt_money(payable), AMBER), unsafe_allow_html=True)

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">Commission by matter</div>', unsafe_allow_html=True)
        spacer()
        show = filtered.rename(columns={"matter": "Matter", "referrer": "Referrer", "rate_pct": "Rate %",
                                         "amount": "Amount", "status": "Status"})
        render_html_table(show[["Matter", "Referrer", "Rate %", "Amount", "Status"]],
                           money_cols=["Amount"], status_col="Status")


def _rapidpay_tab():
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(plain_kpi_html("Monthly Volume", fmt_money(RAPIDPAY_SUMMARY["volume"]), TEAL), unsafe_allow_html=True)
    with m2:
        st.markdown(plain_kpi_html("Merchant Fee Rate", f"{RAPIDPAY_SUMMARY['fee_rate']}%"), unsafe_allow_html=True)
    with m3:
        st.markdown(plain_kpi_html("Fees Paid", fmt_money(RAPIDPAY_SUMMARY["fees_paid"]), AMBER), unsafe_allow_html=True)

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">Recent RapidPay transactions</div>', unsafe_allow_html=True)
        spacer()
        df = pd.DataFrame(RAPIDPAY_TXNS)
        show = df.copy()
        show["amount"] = show["amount"].map(fmt_money)
        show["fee"] = show["fee"].map(lambda v: f"${v:,.2f}")
        show = show.rename(columns={"date": "Date", "client": "Client", "amount": "Amount", "fee": "Fee"})
        st.dataframe(show, width="stretch", hide_index=True)


def _infotrack_tab():
    df = pd.DataFrame(INFOTRACK_ORDERS)
    status_filter = st.multiselect("Status", sorted(df["status"].unique()), key="infotrack_status_filter")
    filtered = df[df["status"].isin(status_filter)] if status_filter else df

    m1, m2 = st.columns(2)
    with m1:
        st.markdown(plain_kpi_html("Total spend (shown)", fmt_money(filtered["cost"].sum()), TEAL),
                     unsafe_allow_html=True)
    with m2:
        st.markdown(plain_kpi_html("Searches ordered", str(len(filtered))), unsafe_allow_html=True)

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">InfoTrack search orders</div>', unsafe_allow_html=True)
        spacer()
        show = filtered.rename(columns={"matter": "Matter", "search_type": "Search Type", "cost": "Cost",
                                         "date": "Date", "status": "Status"})
        render_html_table(show[["Matter", "Search Type", "Cost", "Date", "Status"]],
                           money_cols=["Cost"], status_col="Status")


def _council_tab():
    df = pd.DataFrame(COUNCIL_SEARCHES)
    branch_filter = st.multiselect("Branch", BRANCH_NAMES, key="council_branch_filter")
    filtered = df[df["branch"].isin(branch_filter)] if branch_filter else df

    m1, m2 = st.columns(2)
    with m1:
        st.markdown(plain_kpi_html("Total council search spend", fmt_money(filtered["cost"].sum()), TEAL),
                     unsafe_allow_html=True)
    with m2:
        st.markdown(plain_kpi_html("Searches ordered", str(len(filtered))), unsafe_allow_html=True)

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">Council rate &amp; planning searches</div>', unsafe_allow_html=True)
        st.caption("Council mapped per branch: Richmond → Hawkesbury City Council · Camden → Camden Council · Liverpool → Liverpool City Council.")
        spacer()
        show = filtered.rename(columns={"matter": "Matter", "branch": "Branch", "council": "Council",
                                         "search_type": "Search Type", "cost": "Cost", "date": "Date",
                                         "status": "Status"})
        render_html_table(show[["Matter", "Branch", "Council", "Search Type", "Cost", "Date", "Status"]],
                           money_cols=["Cost"], status_col="Status")


def _card_expenses_tab():
    df = pd.DataFrame(CARD_EXPENSES)
    c1, c2 = st.columns(2)
    with c1:
        card_filter = st.multiselect("Card", sorted(df["card"].unique()), key="card_filter")
    with c2:
        branch_filter = st.multiselect("Branch", BRANCH_NAMES, key="card_branch_filter")

    filtered = df.copy()
    if card_filter:
        filtered = filtered[filtered["card"].isin(card_filter)]
    if branch_filter:
        filtered = filtered[filtered["branch"].isin(branch_filter)]

    spacer()
    amex_total = df[df["card"] == "Amex"]["amount"].sum()
    visa_total = df[df["card"] == "Visa"]["amount"].sum()
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(plain_kpi_html("Amex spend (all)", fmt_money(amex_total), TEAL), unsafe_allow_html=True)
    with m2:
        st.markdown(plain_kpi_html("Visa spend (all)", fmt_money(visa_total), "#1a56db"), unsafe_allow_html=True)
    with m3:
        st.markdown(plain_kpi_html("Shown total", fmt_money(filtered["amount"].sum())), unsafe_allow_html=True)

    spacer()
    col_chart, col_table = st.columns([1, 1.3])
    with col_chart:
        with st.container(border=True):
            st.markdown('<div class="card-title">Spend by category</div>', unsafe_allow_html=True)
            by_cat = filtered.groupby("category")["amount"].sum().sort_values(ascending=True)
            fig = go.Figure(go.Bar(x=by_cat.values, y=by_cat.index, orientation="h", marker_color=TEAL,
                                    hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
            layout = plotly_base(240)
            layout["margin"] = dict(l=8, r=16, t=4, b=4)
            fig.update_layout(**layout)
            fig.update_xaxes(visible=False)
            fig.update_yaxes(tickfont=dict(size=10, color=MUTED))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with col_table:
        with st.container(border=True):
            st.markdown('<div class="card-title">Transactions</div>', unsafe_allow_html=True)
            spacer()
            if filtered.empty:
                st.info("No transactions match that filter.")
            else:
                show = filtered.copy()
                show["amount"] = show["amount"].map(fmt_money)
                show = show.rename(columns={"card": "Card", "date": "Date", "merchant": "Merchant",
                                             "category": "Category", "amount": "Amount", "branch": "Branch"})
                st.dataframe(show[["Card", "Date", "Merchant", "Category", "Amount", "Branch"]],
                             width="stretch", hide_index=True)


def render_finance():
    st.markdown('<div class="section-title">Finance</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Office account, trust account, bank feeds, accounting sync, billing, and expenses.</div>',
                unsafe_allow_html=True)
    tabs = st.tabs(["Office Account", "Trust Account", "CommBiz", "MYOB", "Billing & Invoices",
                     "Commission", "RapidPay", "InfoTrack", "Council", "Card Expenses"])
    with tabs[0]:
        _office_account_tab()
    with tabs[1]:
        _trust_account_tab()
    with tabs[2]:
        _commbiz_tab()
    with tabs[3]:
        _myob_tab()
    with tabs[4]:
        _billing_invoices_tab()
    with tabs[5]:
        _commission_tab()
    with tabs[6]:
        _rapidpay_tab()
    with tabs[7]:
        _infotrack_tab()
    with tabs[8]:
        _council_tab()
    with tabs[9]:
        _card_expenses_tab()


# ----------------------------------------------------------------------
# Team (Roster / Payroll & Pay Rates)
# ----------------------------------------------------------------------
def _team_roster_tab():
    card_cols = st.columns(len(ATTORNEYS))
    for col, a in zip(card_cols, ATTORNEYS):
        with col:
            initials = "".join(p[0] for p in a["name"].split()[:2]).upper()
            st.markdown(
                f"""
                <div class="attorney-card">
                  <div class="attorney-avatar">{initials}</div>
                  <div style="font-weight:700; font-size:13px; color:{INK};">{a['name']}</div>
                  <div style="font-size:11px; color:{MUTED}; margin-bottom:4px;">{a['role']} · {a['branch']}</div>
                  <div style="font-size:18px; font-weight:800; color:{TEAL};">{a['utilization']}%</div>
                  <div style="font-size:10px; color:{FAINT};">utilization</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    spacer()
    with st.container(border=True):
        selected_name = st.selectbox("View detail for", [a["name"] for a in ATTORNEYS], key="team_detail_select")
    attorney = next(a for a in ATTORNEYS if a["name"] == selected_name)

    spacer()
    col_hours, col_activity = st.columns([1, 1.2])

    with col_hours:
        with st.container(border=True):
            st.markdown(f'<div class="card-title">{attorney["name"]} — Hours by Practice Area</div>',
                        unsafe_allow_html=True)
            hrs = attorney["hours"]
            fig = go.Figure(go.Bar(
                x=list(hrs.values()), y=list(hrs.keys()), orientation="h",
                marker=dict(color=TEAL),
                hovertemplate="%{y}: %{x} hrs<extra></extra>",
            ))
            layout = plotly_base(220)
            layout["margin"] = dict(l=8, r=16, t=8, b=8)
            fig.update_layout(**layout)
            fig.update_xaxes(visible=False)
            fig.update_yaxes(tickfont=dict(size=11, color=MUTED))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.markdown(
                f"""
                <div class="bar-row">
                  <div class="bar-head">
                    <span class="lbl">Utilization vs {attorney['target']}h target</span>
                    <span class="val">{attorney['utilization']}%</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill" style="width:{min(attorney['utilization'], 100)}%; background:{TEAL};"></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_activity:
        with st.container(border=True):
            st.markdown('<div class="card-title">Assigned matters</div>', unsafe_allow_html=True)
            spacer()
            m_df = pd.DataFrame(MATTERS)
            mine = m_df[m_df["attorney"] == attorney["short"]]
            if mine.empty:
                st.caption("No matters currently assigned.")
            else:
                for _, m in mine.iterrows():
                    st.markdown(
                        f"""
                        <div style="margin-bottom:10px;">
                          <span style="font-weight:700; font-size:12px; color:{INK};">{m['name']}</span>
                          {status_pill(m['status'])}
                          <div class="deadline-sub">{m['client']} · {m['practice']} · {fmt_money(m['value'])}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            spacer()
            st.markdown('<div class="card-title">Upcoming deadlines</div>', unsafe_allow_html=True)
            spacer()
            d_df = pd.DataFrame(DEADLINES)
            theirs = d_df[d_df["attorney"] == attorney["short"]]
            if theirs.empty:
                st.caption("No upcoming deadlines.")
            else:
                for _, d in theirs.iterrows():
                    dt = pd.to_datetime(d["date"])
                    st.markdown(
                        f"""
                        <div class="deadline-item">
                          <div class="date-badge" style="background:{TEAL_TINT}; color:{TEAL};">{dt.strftime('%b %d')}</div>
                          <div>
                            <div class="deadline-title">{d['title']}</div>
                            <div class="deadline-sub">{d['court']}</div>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )


def _payroll_tab():
    st.markdown('<div class="section-sub">Adjust each attorney\'s pay rate — the monthly cost below recomputes live.</div>',
                unsafe_allow_html=True)

    if "pay_rates" not in st.session_state:
        st.session_state.pay_rates = {a["short"]: a["pay_rate"] for a in ATTORNEYS}

    with st.container(border=True):
        st.markdown('<div class="card-title">Pay rates ($/hr)</div>', unsafe_allow_html=True)
        spacer()
        cols = st.columns(len(ATTORNEYS))
        for col, a in zip(cols, ATTORNEYS):
            with col:
                st.session_state.pay_rates[a["short"]] = st.number_input(
                    f"{a['name']} ({a['role']})", min_value=50, max_value=500,
                    value=int(st.session_state.pay_rates[a["short"]]), step=5,
                    key=f"pay_rate_{a['short']}",
                )

    spacer()
    rows = []
    total_cost = 0
    for a in ATTORNEYS:
        rate = st.session_state.pay_rates[a["short"]]
        monthly_cost = rate * a["target"]
        total_cost += monthly_cost
        rows.append({"Attorney": a["name"], "Role": a["role"], "Branch": a["branch"],
                      "Pay Rate": rate, "Target Hrs": a["target"], "Monthly Cost": monthly_cost})

    m1, m2 = st.columns(2)
    with m1:
        st.markdown(plain_kpi_html("Total monthly payroll (this roster)", fmt_money(total_cost), TEAL),
                     unsafe_allow_html=True)
    with m2:
        st.markdown(plain_kpi_html("Average pay rate", f"${total_cost / sum(a['target'] for a in ATTORNEYS):.0f}/hr"),
                     unsafe_allow_html=True)

    spacer()
    col_chart, col_table = st.columns([1, 1.2])
    with col_chart:
        with st.container(border=True):
            st.markdown('<div class="card-title">Monthly cost by attorney</div>', unsafe_allow_html=True)
            names = [r["Attorney"] for r in rows]
            costs = [r["Monthly Cost"] for r in rows]
            fig = go.Figure(go.Bar(x=costs, y=names, orientation="h", marker_color=TEAL,
                                    hovertemplate="%{y}: $%{x:,.0f}<extra></extra>"))
            layout = plotly_base(200)
            layout["margin"] = dict(l=8, r=16, t=4, b=4)
            fig.update_layout(**layout)
            fig.update_xaxes(visible=False)
            fig.update_yaxes(tickfont=dict(size=10, color=MUTED))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with col_table:
        with st.container(border=True):
            st.markdown('<div class="card-title">Payroll detail</div>', unsafe_allow_html=True)
            spacer()
            show = pd.DataFrame(rows)
            show["Pay Rate"] = show["Pay Rate"].map(lambda v: f"${v}/hr")
            show["Monthly Cost"] = show["Monthly Cost"].map(fmt_money)
            st.dataframe(show, width="stretch", hide_index=True)


def render_team():
    st.markdown('<div class="section-title">Team</div>', unsafe_allow_html=True)
    tabs = st.tabs(["Roster", "Payroll & Pay Rates"])
    with tabs[0]:
        _team_roster_tab()
    with tabs[1]:
        _payroll_tab()


# ----------------------------------------------------------------------
# Simulator — pay-rate uplift, hiring, and branch-takeover what-if
# ----------------------------------------------------------------------
def render_simulator():
    st.markdown('<div class="section-title">Simulator</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Model the effect of a firm-wide pay rate change, hiring more people, or taking over another branch.</div>',
                unsafe_allow_html=True)

    baseline_revenue = sum(b["monthly_revenue"] for b in BRANCHES)
    baseline_cost = sum(b["monthly_cost"] for b in BRANCHES)
    baseline_net = baseline_revenue - baseline_cost

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">Current firm snapshot (3 branches)</div>', unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(plain_kpi_html("Monthly Revenue", fmt_money(baseline_revenue), TEAL), unsafe_allow_html=True)
        with m2:
            st.markdown(plain_kpi_html("Monthly Cost", fmt_money(baseline_cost), AMBER), unsafe_allow_html=True)
        with m3:
            st.markdown(plain_kpi_html("Net Margin", fmt_money(baseline_net),
                                        GREEN if baseline_net >= 0 else RED), unsafe_allow_html=True)

    spacer()
    col_rate, col_hire = st.columns(2)

    with col_rate:
        with st.container(border=True):
            st.markdown('<div class="card-title">1. Adjust pay rates</div>', unsafe_allow_html=True)
            uplift_pct = st.slider("Pay rate uplift for all attorneys", -10, 25, 0, step=1,
                                    format="%d%%", key="sim_pay_uplift")
            base_payroll = sum(a["pay_rate"] * a["target"] for a in ATTORNEYS)
            adjusted_payroll = base_payroll * (1 + uplift_pct / 100)
            payroll_delta = adjusted_payroll - base_payroll
            st.markdown(
                f"""
                <div class="bar-row">
                  <div class="bar-head"><span class="lbl">Current payroll</span><span class="val">{fmt_money(base_payroll)}</span></div>
                  <div class="bar-head"><span class="lbl">Adjusted payroll</span><span class="val">{fmt_money(adjusted_payroll)}</span></div>
                  <div class="bar-head"><span class="lbl">Change</span>
                    <span class="val" style="color:{RED if payroll_delta > 0 else GREEN};">{fmt_money(payroll_delta)}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_hire:
        with st.container(border=True):
            st.markdown('<div class="card-title">2. Simulate hiring</div>', unsafe_allow_html=True)
            hire_count = st.number_input("Additional hires", min_value=0, max_value=20, value=0, step=1, key="sim_hire_count")
            hire_role = st.selectbox("Role", list(ROLE_PRESETS.keys()), key="sim_hire_role")
            hire_branch = st.selectbox("Branch", BRANCH_NAMES, key="sim_hire_branch")
            utilization_assumption = st.slider("Assumed utilization", 40, 100, 75, step=5,
                                                format="%d%%", key="sim_hire_util")
            preset = ROLE_PRESETS[hire_role]
            hire_cost = hire_count * preset["pay_rate"] * preset["target_hours"]
            hire_revenue = (hire_count * preset["bill_rate"] * preset["target_hours"]
                             * utilization_assumption / 100)
            st.markdown(
                f"""
                <div class="bar-row">
                  <div class="bar-head"><span class="lbl">Added monthly cost</span><span class="val" style="color:{RED};">{fmt_money(hire_cost)}</span></div>
                  <div class="bar-head"><span class="lbl">Est. added monthly revenue</span><span class="val" style="color:{GREEN};">{fmt_money(hire_revenue)}</span></div>
                  <div class="bar-head"><span class="lbl">Net effect</span>
                    <span class="val" style="color:{GREEN if hire_revenue - hire_cost >= 0 else RED};">{fmt_money(hire_revenue - hire_cost)}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(f"{hire_count} × {hire_role} at {hire_branch}, {preset['bill_rate']}$/hr bill rate, "
                       f"{preset['pay_rate']}$/hr pay rate.")

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">3. Simulate taking over another branch</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            new_branch_name = st.text_input("Branch / firm name", value="Parramatta (acquisition)", key="sim_branch_name")
        with c2:
            new_branch_revenue = st.number_input("Est. monthly revenue", min_value=0, value=90000, step=5000,
                                                  key="sim_branch_revenue")
        with c3:
            new_branch_cost = st.number_input("Est. monthly cost", min_value=0, value=65000, step=5000,
                                               key="sim_branch_cost")
        with c4:
            new_branch_attorneys = st.number_input("Attorneys transferring", min_value=0, value=3, step=1,
                                                     key="sim_branch_attorneys")
        branch_net = new_branch_revenue - new_branch_cost
        include_branch = st.checkbox("Include this branch in the projection below", value=True, key="sim_branch_include")
        st.caption(f"Est. net margin from this branch: {fmt_money(branch_net)} · "
                   f"{new_branch_attorneys} attorneys joining {new_branch_name}.")

    spacer()
    with st.container(border=True):
        st.markdown('<div class="card-title">Projected P&amp;L — baseline vs scenario</div>', unsafe_allow_html=True)

        projected_revenue = baseline_revenue + hire_revenue + (new_branch_revenue if include_branch else 0)
        projected_cost = (baseline_cost - base_payroll + adjusted_payroll + hire_cost
                           + (new_branch_cost if include_branch else 0))
        projected_net = projected_revenue - projected_cost

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Baseline", x=["Revenue", "Cost", "Net Margin"],
                              y=[baseline_revenue, baseline_cost, baseline_net],
                              marker_color="#94a3b8",
                              hovertemplate="%{x}: $%{y:,.0f}<extra>Baseline</extra>"))
        fig.add_trace(go.Bar(name="Projected", x=["Revenue", "Cost", "Net Margin"],
                              y=[projected_revenue, projected_cost, projected_net],
                              marker_color=TEAL,
                              hovertemplate="%{x}: $%{y:,.0f}<extra>Projected</extra>"))
        layout = plotly_base(260)
        layout["showlegend"] = True
        layout["legend"] = dict(orientation="h", y=1.15)
        fig.update_layout(**layout, barmode="group")
        fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        delta = projected_net - baseline_net
        st.markdown(
            f"""
            <div class="bar-row">
              <div class="bar-head"><span class="lbl">Net margin change vs baseline</span>
                <span class="val" style="color:{GREEN if delta >= 0 else RED};">{'+' if delta >= 0 else ''}{fmt_money(delta)}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ----------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------
RENDERERS = {
    "Overview": render_overview,
    "Matters": render_matters,
    "Clients": render_clients,
    "Calendar": render_calendar,
    "Finance": render_finance,
    "Team": render_team,
    "Simulator": render_simulator,
}
RENDERERS[section]()

spacer()
st.caption("Sample data, internally consistent across sections — swap the DATA section near the top for a real source.")
