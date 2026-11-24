"""Static reference data (people, clients, branches, named matters, deadlines).
Everything time-varying is generated in core/model.py from this reference set so that
every number in the dashboard reconciles to one source of truth."""
import pandas as pd

AS_OF = pd.Timestamp("2025-09-17")           # "today" for the sample data (system sync date)
START = pd.Timestamp("2023-07-01")           # first month of history
PLAN_END = pd.Timestamp("2026-06-01")        # last budget month (FY26 ends 30 Jun 2026)
FY_START_MONTH = 7                           # Australian financial year: 1 Jul – 30 Jun

AREAS = ["Corporate", "Litigation", "IP Portfolio", "Employment", "Advisory"]
NAV_ITEMS = ["Overview", "Finance", "People", "Matters", "Clients", "Calendar", "Simulator"]
USER_NAME, USER_ROLE = "Brian Phu", "Financial Analyst"

BRANCHES = [
    {"name": "Richmond", "lat": -33.6003, "lon": 150.7514, "council": "Hawkesbury City Council", "support": 4, "rent": 7600},
    {"name": "Camden", "lat": -34.0489, "lon": 150.6993, "council": "Camden Council", "support": 6, "rent": 8400},
    {"name": "Liverpool", "lat": -33.9209, "lon": 150.8809, "council": "Liverpool City Council", "support": 7, "rent": 8200},
]
BRANCH_NAMES = [b["name"] for b in BRANCHES]

# Where matters come from (sample data): suburbs of Western, South-Western and North-Western Sydney with approximate
# coordinates and a rounded, indicative population. Each Australian matter is given a client suburb, drawn by population and
# by distance from the office that handles it (people use a nearby office). Used for the catchment map and branch-site analysis.
SUBURBS = [
    # name, lat, lon, population (approx., rounded)
    ("Richmond", -33.600, 150.752, 6000), ("North Richmond", -33.587, 150.718, 5000), ("Windsor", -33.612, 150.818, 2000),
    ("Riverstone", -33.676, 150.862, 8000), ("Schofields", -33.700, 150.870, 27000), ("Marsden Park", -33.695, 150.836, 15000),
    ("Rouse Hill", -33.682, 150.915, 7000), ("Kellyville", -33.712, 150.957, 28000), ("Castle Hill", -33.730, 151.004, 39000),
    ("Quakers Hill", -33.735, 150.885, 26000), ("Blacktown", -33.771, 150.906, 47000), ("Rooty Hill", -33.772, 150.844, 13000),
    ("Mount Druitt", -33.769, 150.819, 17000), ("St Marys", -33.763, 150.774, 12000), ("Kingswood", -33.759, 150.720, 9000),
    ("Penrith", -33.751, 150.694, 14000), ("Glenmore Park", -33.790, 150.670, 23000), ("Parramatta", -33.815, 151.001, 30000),
    ("Merrylands", -33.836, 150.992, 28000), ("Smithfield", -33.851, 150.942, 11000), ("Bossley Park", -33.862, 150.884, 15000),
    ("Fairfield", -33.872, 150.956, 18000), ("Cabramatta", -33.894, 150.937, 21000), ("Green Valley", -33.903, 150.867, 21000),
    ("Liverpool", -33.920, 150.923, 31000), ("Bankstown", -33.918, 151.035, 34000), ("Prestons", -33.942, 150.871, 17000),
    ("Casula", -33.950, 150.900, 17000), ("Edmondson Park", -33.966, 150.861, 15000), ("Leppington", -33.954, 150.810, 10000),
    ("Ingleburn", -33.998, 150.866, 14000), ("Macquarie Fields", -33.993, 150.887, 13000), ("Oran Park", -33.994, 150.739, 15000),
    ("Minto", -34.028, 150.846, 12000), ("Harrington Park", -34.025, 150.725, 11000), ("Narellan", -34.042, 150.735, 12000),
    ("Mount Annan", -34.053, 150.759, 11000), ("Camden", -34.054, 150.696, 3000), ("Campbelltown", -34.065, 150.814, 13000),
    ("Picton", -34.170, 150.612, 5000),
]
CATCHMENT_KM = 10.0       # how fast demand falls with distance from the office that handles the matter (exp(-d / 10 km))
BRANCH_COUNCIL = {b["name"]: b["council"] for b in BRANCHES}

# base = monthly billable hours at the Sep-2025 run-rate; real_factor = relative realisation vs firm average
ATTORNEYS = [
    {"name": "Clara Sterling", "short": "Sterling, C.", "role": "Senior Managing Partner", "branch": "Richmond", "start": "2016-01-01",
     "target": 190, "bill_rate": 650, "pay_rate": 210, "real_factor": 1.03,
     "base": {"Corporate": 45, "Litigation": 20, "IP Portfolio": 72, "Employment": 8, "Advisory": 15}},
    {"name": "Harvey Specter", "short": "Specter, H.", "role": "Senior Associate", "branch": "Camden", "start": "2018-01-01",
     "target": 190, "bill_rate": 520, "pay_rate": 170, "real_factor": 1.02,
     "base": {"Corporate": 10, "Litigation": 140, "IP Portfolio": 5, "Employment": 0, "Advisory": 25}},
    {"name": "Rachel Zane", "short": "Zane, R.", "role": "Associate", "branch": "Liverpool", "start": "2020-01-01",
     "target": 190, "bill_rate": 380, "pay_rate": 120, "real_factor": 0.97,
     "base": {"Corporate": 85, "Litigation": 40, "IP Portfolio": 15, "Employment": 12, "Advisory": 10}},
    {"name": "Louis Litt", "short": "Litt, L.", "role": "Senior Partner", "branch": "Liverpool", "start": "2015-01-01",
     "target": 190, "bill_rate": 560, "pay_rate": 175, "real_factor": 0.99,
     "base": {"Corporate": 30, "Litigation": 15, "IP Portfolio": 95, "Employment": 8, "Advisory": 5}},
    {"name": "Katrina Bennett", "short": "Bennett, K.", "role": "Associate", "branch": "Camden", "start": "2024-02-01",
     "target": 190, "bill_rate": 400, "pay_rate": 130, "real_factor": 0.96,
     "base": {"Corporate": 60, "Litigation": 25, "IP Portfolio": 30, "Employment": 15, "Advisory": 40}},
    {"name": "Mike Ross", "short": "Ross, M.", "role": "Senior Associate", "branch": "Richmond", "start": "2019-01-01",
     "target": 190, "bill_rate": 500, "pay_rate": 160, "real_factor": 1.0,
     "base": {"Corporate": 70, "Litigation": 60, "IP Portfolio": 20, "Employment": 5, "Advisory": 15}},
    {"name": "Jessica Pearson", "short": "Pearson, J.", "role": "Senior Partner", "branch": "Liverpool", "start": "2012-01-01",
     "target": 190, "bill_rate": 700, "pay_rate": 230, "real_factor": 1.04,
     "base": {"Corporate": 100, "Litigation": 30, "IP Portfolio": 20, "Employment": 5, "Advisory": 10}},
    {"name": "Donna Paulsen", "short": "Paulsen, D.", "role": "Associate", "branch": "Richmond", "start": "2024-08-01",
     "target": 190, "bill_rate": 360, "pay_rate": 115, "real_factor": 0.95,
     "base": {"Corporate": 40, "Litigation": 35, "IP Portfolio": 45, "Employment": 0, "Advisory": 55}},
]
ATT_BY_SHORT = {a["short"]: a for a in ATTORNEYS}

# w = billing weight inside its practice area; delay = mean days from invoice to payment; freq = chance of being invoiced in a month
CLIENTS = [
    {"name": "Acme Corp", "practice": "Litigation", "attorney": "Zane, R.", "since": 2019, "w": 612, "delay": 30, "freq": 0.9, "country": "Australia"},
    {"name": "Zenith Labs", "practice": "Litigation", "attorney": "Specter, H.", "since": 2021, "w": 390, "delay": 58, "freq": 0.7, "country": "Australia"},
    {"name": "Okafor Mining Co.", "practice": "Litigation", "attorney": "Ross, M.", "since": 2019, "w": 445, "delay": 66, "freq": 0.8, "country": "Australia"},
    {"name": "Pacific Rim Traders", "practice": "Litigation", "attorney": "Ross, M.", "since": 2024, "w": 275, "delay": 41, "freq": 0.5, "country": "United States"},
    {"name": "Ganges Textile Exports", "practice": "Litigation", "attorney": "Zane, R.", "since": 2023, "w": 210, "delay": 47, "freq": 0.5, "country": "India"},
    {"name": "Meridian Holdings Ltd.", "practice": "Corporate", "attorney": "Sterling, C.", "since": 2017, "w": 540, "delay": 22, "freq": 0.95, "country": "Australia"},
    {"name": "Global Trust Bank", "practice": "Corporate", "attorney": "Specter, H.", "since": 2020, "w": 475, "delay": 62, "freq": 0.85, "country": "Australia"},
    {"name": "Blackwood Realty", "practice": "Corporate", "attorney": "Ross, M.", "since": 2021, "w": 220, "delay": 34, "freq": 0.7, "country": "Australia"},
    {"name": "Delacroix & Sons", "practice": "Corporate", "attorney": "Pearson, J.", "since": 2018, "w": 288, "delay": 27, "freq": 0.7, "country": "Australia"},
    {"name": "Singapore Trading Group", "practice": "Corporate", "attorney": "Pearson, J.", "since": 2022, "w": 240, "delay": 44, "freq": 0.5, "country": "Singapore"},
    {"name": "London Capital Partners", "practice": "Corporate", "attorney": "Specter, H.", "since": 2023, "w": 310, "delay": 39, "freq": 0.5, "country": "United Kingdom"},
    {"name": "Meridian Pacific Trust", "practice": "Corporate", "attorney": "Pearson, J.", "since": 2023, "w": 195, "delay": 36, "freq": 0.5, "country": "Hong Kong"},
    {"name": "Vertex Industries", "practice": "IP Portfolio", "attorney": "Litt, L.", "since": 2018, "w": 268, "delay": 26, "freq": 0.9, "country": "Australia"},
    {"name": "Nova Materials", "practice": "IP Portfolio", "attorney": "Litt, L.", "since": 2020, "w": 198, "delay": 31, "freq": 0.7, "country": "Australia"},
    {"name": "Halcyon Systems", "practice": "IP Portfolio", "attorney": "Pearson, J.", "since": 2016, "w": 315, "delay": 24, "freq": 0.8, "country": "Australia"},
    {"name": "Whitmore Textiles", "practice": "IP Portfolio", "attorney": "Bennett, K.", "since": 2020, "w": 132, "delay": 40, "freq": 0.6, "country": "Australia"},
    {"name": "Nippon Precision Ltd", "practice": "IP Portfolio", "attorney": "Litt, L.", "since": 2022, "w": 145, "delay": 33, "freq": 0.5, "country": "Japan"},
    {"name": "Hanwoo Precision Ltd", "practice": "IP Portfolio", "attorney": "Litt, L.", "since": 2024, "w": 88, "delay": 37, "freq": 0.4, "country": "South Korea"},
    {"name": "Harlow & Co.", "practice": "Employment", "attorney": "Sterling, C.", "since": 2022, "w": 142, "delay": 35, "freq": 0.8, "country": "Australia"},
    {"name": "Sunrise Logistics", "practice": "Employment", "attorney": "Bennett, K.", "since": 2022, "w": 98, "delay": 29, "freq": 0.7, "country": "Australia"},
    {"name": "Bright Path Foundation", "practice": "Advisory", "attorney": "Sterling, C.", "since": 2023, "w": 86, "delay": 33, "freq": 0.7, "country": "Australia"},
    {"name": "Fentonville Council", "practice": "Advisory", "attorney": "Paulsen, D.", "since": 2023, "w": 64, "delay": 45, "freq": 0.6, "country": "Australia"},
    {"name": "Auckland Ventures Ltd", "practice": "Advisory", "attorney": "Sterling, C.", "since": 2021, "w": 100, "delay": 38, "freq": 0.5, "country": "New Zealand"},
]
COUNTRY_ISO3 = {"Australia": "AUS", "Singapore": "SGP", "New Zealand": "NZL", "United Kingdom": "GBR", "United States": "USA",
                "Japan": "JPN", "Hong Kong": "HKG", "South Korea": "KOR", "India": "IND"}

# Named "key matters" (hand-written); the model generates the remaining ones so the ledger reconciles to 142 active.
NAMED_MATTERS = [
    ("Acme vs. Zenith Trial Brief Filing", "Acme Corp", "Litigation", "Zane, R.", "Open", "2025-03-14", 420000, "Liverpool", "Australia"),
    ("Global Trust M&A Preliminary Hearing", "Global Trust Bank", "Corporate", "Specter, H.", "Open", "2025-05-02", 610000, "Camden", "Australia"),
    ("Meridian Series C Financing", "Meridian Holdings Ltd.", "Corporate", "Sterling, C.", "Open", "2025-01-20", 350000, "Richmond", "Australia"),
    ("Vertex Patent Portfolio Review", "Vertex Industries", "IP Portfolio", "Litt, L.", "Open", "2025-06-11", 180000, "Liverpool", "Australia"),
    ("Harlow Wrongful Termination Defense", "Harlow & Co.", "Employment", "Sterling, C.", "On Hold", "2024-11-08", 95000, "Camden", "Australia"),
    ("Nova Materials Trademark Dispute", "Nova Materials", "IP Portfolio", "Litt, L.", "Closed", "2024-06-19", 74000, "Liverpool", "Australia"),
    ("Zenith Labs Licensing Countersuit", "Zenith Labs", "Litigation", "Specter, H.", "Open", "2025-02-27", 260000, "Liverpool", "Australia"),
    ("Acme Supply Agreement Renewal", "Acme Corp", "Corporate", "Sterling, C.", "Closed", "2024-09-03", 120000, "Camden", "Australia"),
    ("Bright Path Governance Advisory", "Bright Path Foundation", "Advisory", "Sterling, C.", "Open", "2025-07-01", 45000, "Richmond", "Australia"),
    ("Vertex vs. Halcyon IP Infringement", "Vertex Industries", "IP Portfolio", "Litt, L.", "Open", "2025-04-16", 510000, "Liverpool", "Australia"),
    ("Halcyon Trademark Portfolio Audit", "Halcyon Systems", "IP Portfolio", "Pearson, J.", "Open", "2025-02-10", 210000, "Liverpool", "Australia"),
    ("Blackwood Realty Lease Restructure", "Blackwood Realty", "Corporate", "Ross, M.", "Open", "2025-05-19", 165000, "Richmond", "Australia"),
    ("Sunrise Logistics Award Compliance Review", "Sunrise Logistics", "Employment", "Bennett, K.", "Open", "2025-06-02", 58000, "Camden", "Australia"),
    ("Fentonville Council Planning Advisory", "Fentonville Council", "Advisory", "Paulsen, D.", "Open", "2025-07-15", 41000, "Richmond", "Australia"),
    ("Okafor Mining Environmental Claim", "Okafor Mining Co.", "Litigation", "Ross, M.", "Open", "2025-03-28", 380000, "Richmond", "Australia"),
    ("Delacroix Group Acquisition", "Delacroix & Sons", "Corporate", "Pearson, J.", "Open", "2025-08-04", 295000, "Liverpool", "Australia"),
    ("Whitmore Textiles Patent Filing", "Whitmore Textiles", "IP Portfolio", "Bennett, K.", "Closed", "2024-10-12", 68000, "Camden", "Australia"),
    ("Acme Corp Data Breach Response", "Acme Corp", "Litigation", "Zane, R.", "Open", "2025-08-20", 175000, "Liverpool", "Australia"),
    ("Meridian Holdings Employee Share Scheme", "Meridian Holdings Ltd.", "Corporate", "Sterling, C.", "On Hold", "2025-04-11", 88000, "Richmond", "Australia"),
    ("Vertex Industries Licensing Dispute", "Vertex Industries", "IP Portfolio", "Litt, L.", "Closed", "2024-08-30", 92000, "Liverpool", "Australia"),
    ("Global Trust Bank Regulatory Investigation", "Global Trust Bank", "Litigation", "Specter, H.", "Open", "2025-09-01", 520000, "Camden", "Australia"),
    ("Harlow & Co. Redundancy Program Advisory", "Harlow & Co.", "Employment", "Sterling, C.", "Closed", "2024-12-05", 47000, "Camden", "Australia"),
    ("Nova Materials Supply Contract Review", "Nova Materials", "Corporate", "Litt, L.", "Open", "2025-07-22", 63000, "Liverpool", "Australia"),
    ("Bright Path Foundation Charity Structuring", "Bright Path Foundation", "Advisory", "Sterling, C.", "Open", "2025-09-10", 32000, "Richmond", "Australia"),
    ("Singapore Trading Group Cross-Border Supply Agreement", "Singapore Trading Group", "Corporate", "Pearson, J.", "Open", "2025-06-15", 240000, "Liverpool", "Singapore"),
    ("Auckland Ventures NZ Market Entry Advisory", "Auckland Ventures Ltd", "Advisory", "Sterling, C.", "Open", "2025-07-08", 68000, "Richmond", "New Zealand"),
    ("Auckland Ventures NZ Trademark Filing", "Auckland Ventures Ltd", "IP Portfolio", "Bennett, K.", "Closed", "2025-01-18", 32000, "Camden", "New Zealand"),
    ("London Capital Partners Fund Structuring", "London Capital Partners", "Corporate", "Specter, H.", "Open", "2025-08-12", 310000, "Camden", "United Kingdom"),
    ("Pacific Rim Traders US Distribution Dispute", "Pacific Rim Traders", "Litigation", "Ross, M.", "Open", "2025-05-30", 275000, "Richmond", "United States"),
    ("Nippon Precision IP Licensing", "Nippon Precision Ltd", "IP Portfolio", "Litt, L.", "Open", "2025-09-02", 145000, "Liverpool", "Japan"),
    ("Meridian Pacific Trust Structuring", "Meridian Pacific Trust", "Corporate", "Pearson, J.", "Open", "2025-08-25", 195000, "Liverpool", "Hong Kong"),
    ("Hanwoo Precision Trademark Registration", "Hanwoo Precision Ltd", "IP Portfolio", "Litt, L.", "On Hold", "2025-07-30", 88000, "Camden", "South Korea"),
    ("Ganges Textile Exports Contract Dispute", "Ganges Textile Exports", "Litigation", "Zane, R.", "Open", "2025-06-20", 210000, "Liverpool", "India"),
]
NAMED_DEADLINES = [
    ("2025-10-12", "Acme vs. Zenith Trial Brief Filing", "Appellate Court", "Zane, R."),
    ("2025-10-15", "Global Trust M&A Preliminary Hearing", "Chancery Court", "Specter, H."),
    ("2025-10-22", "Vertex Patent Portfolio Filing Deadline", "USPTO", "Litt, L."),
    ("2025-10-29", "Halcyon Trademark Portfolio Filing", "IP Australia", "Pearson, J."),
    ("2025-11-04", "Meridian Series C Closing", "—", "Sterling, C."),
    ("2025-11-10", "Blackwood Realty Lease Signing", "—", "Ross, M."),
    ("2025-11-18", "Zenith Labs Licensing Countersuit Hearing", "District Court", "Specter, H."),
    ("2025-11-25", "Okafor Mining Environmental Tribunal", "Land & Environment Court", "Ross, M."),
    ("2025-12-02", "Vertex vs. Halcyon IP Infringement Trial", "Federal Court", "Litt, L."),
    ("2025-12-15", "Global Trust Bank Regulatory Hearing", "Federal Court", "Specter, H."),
    ("2026-01-14", "Delacroix Group Acquisition Completion", "—", "Pearson, J."),
    ("2026-02-03", "Fentonville Council Planning Panel Hearing", "Land & Environment Court", "Paulsen, D."),
]
# trust ledger balances at AS_OF (the model generates monthly history that lands exactly on these)
TRUST_TARGET = {"Acme Corp": 120000, "Meridian Holdings Ltd.": 110000, "Global Trust Bank": 30000, "Vertex Industries": 60000,
                "Halcyon Systems": 75000, "Okafor Mining Co.": 85000, "Delacroix & Sons": 55000}
OFFICE_CASH_AT_AS_OF = 268_400
COMMISSIONS = [
    ("Acme vs. Zenith Trial Brief Filing", "External — Dalton & Whitmore", 8, 33600, "Payable"),
    ("Global Trust M&A Preliminary Hearing", "Internal — Sterling, C.", 5, 30500, "Paid"),
    ("Vertex Patent Portfolio Review", "External — IP Connect Referrals", 10, 18000, "Payable"),
    ("Zenith Labs Licensing Countersuit", "Internal — Specter, H.", 5, 13000, "Paid"),
    ("Halcyon Trademark Portfolio Audit", "External — IP Connect Referrals", 10, 21000, "Payable"),
    ("Okafor Mining Environmental Claim", "Internal — Ross, M.", 5, 19000, "Paid"),
    ("Global Trust Bank Regulatory Investigation", "External — Dalton & Whitmore", 8, 41600, "Payable"),
    ("Delacroix Group Acquisition", "Internal — Pearson, J.", 5, 14750, "Paid"),
]
SEARCH_TYPES = {  # (relative cost weight, share of orders); costs are rescaled so the mean equals the platform per-search fee
    "Land Title Search": (0.9, 0.34), "Company Title Search": (1.05, 0.22), "PPSR Search": (0.6, 0.20),
    "Trademark Register Search": (1.4, 0.10), "Patent Register Search": (2.6, 0.06), "EPA Register Search": (3.2, 0.03),
    "Court Record Search": (0.8, 0.05),
}
CARD_CATEGORIES = {  # (share of card spend, typical merchants)
    "Travel": (0.28, ["Qantas Club", "Uber", "Marriott Hotels", "Virgin Australia"]),
    "Software": (0.16, ["LEAP Legal Software", "Zoom Subscription", "Adobe", "Microsoft 365"]),
    "Client Entertainment": (0.14, ["The Grounds Cafe", "Ritz Carlton Dining", "Rockpool"]),
    "Supplies": (0.16, ["Officeworks", "Woolworths Metro", "Staples"]),
    "Fuel": (0.08, ["Ampol", "Shell", "BP"]),
    "Equipment": (0.10, ["JB Hi-Fi", "Harvey Norman", "Apple"]),
    "Office Maintenance": (0.08, ["Bunnings", "Coles", "Cleanaway"]),
}

# ------------------------------------------------------------------ decision inputs (assumptions, shown in the app) ----
# Support staff by department and branch (sums to each branch's "support" count above). Monthly all-in cost per role is
# illustrative and averages close to the $5,400 the P&L model uses for support payroll.
DEPT_PAY = {"Reception & admin": 4650, "Paralegals & clerks": 5600, "Accounts & trust": 5900, "Marketing": 5900}
DEPARTMENTS = {
    "Richmond": {"Reception & admin": 1, "Paralegals & clerks": 2, "Accounts & trust": 1},
    "Camden": {"Reception & admin": 3, "Paralegals & clerks": 2, "Accounts & trust": 1},
    "Liverpool": {"Reception & admin": 1, "Paralegals & clerks": 3, "Accounts & trust": 2, "Marketing": 1},
}
# Workload each role can carry in a year (benchmarks are assumptions for the method, not industry standards)
DEPT_DRIVERS = {
    "Reception & admin": dict(driver="Inquiries a year", per_fte=600, base_per_branch=1.0,
                              note="one front desk per office, plus one more for every 600 inquiries a year"),
    "Paralegals & clerks": dict(driver="Active matters", per_fte=22, base_per_branch=0.0, note="one for every 22 active matters"),
    "Accounts & trust": dict(driver="Invoices, receipts and supplier orders a year", per_fte=1000, base_per_branch=0.0, firm_wide=True,
                             note="one for every 1,000 invoices, trust receipts and supplier orders a year, plus payroll, BAS and reconciliations (firm-wide team)"),
    "Marketing": dict(driver="Marketing and referral spend a year", per_fte=150000, base_per_branch=0.0, firm_wide=True,
                      note="one for every $150K of marketing and referral spend a year"),
}
PARALEGAL_LEVERAGE_HOURS = 200     # billable hours a year a new paralegal frees up for fee earners (assumption)
# Australian private-sector wages rose 3.4% in the year to the September quarter 2026 (ABS Wage Price Index, released 18 Nov 2026)
MARKET_WAGE_GROWTH = 0.034

# Where new clients come from. spend = share of the marketing budget (referrals are paid by commission instead);
# inquiries = share of inquiries; conv = inquiry-to-matter conversion relative to the firm average; value = fee per matter relative to average.
MARKETING_CHANNELS = {
    "Google Ads": dict(spend=0.40, inquiries=0.30, conv=0.70, value=0.80),
    "Website & SEO": dict(spend=0.20, inquiries=0.20, conv=1.00, value=1.00),
    "Referrals": dict(spend=0.00, inquiries=0.30, conv=1.50, value=1.40),
    "LinkedIn & social": dict(spend=0.25, inquiries=0.12, conv=0.60, value=0.90),
    "Events & community": dict(spend=0.15, inquiries=0.08, conv=1.10, value=1.00),
}
MARKETING_EFFICIENCY = 0.4         # extra spend buys inquiries at 40% of the channel's current rate (diminishing returns)
FIRST_YEAR_BILLING = 0.35          # share of a new matter's typical fees billed in the year it arrives (matters arrive through the year)

# New matter types the firm could open. fee = average fee per matter; mature = matters a month at full speed;
# ramp = months to reach it; staff = who it needs; launch = one-off launch campaign; monthly = ongoing marketing a month.
NEW_AREAS = {
    "Wills & Estates": dict(fee=2800, mature=18, ramp=12, role="Associate", support=0, launch=25000, monthly=3000),
    "Family Law": dict(fee=14000, mature=4, ramp=9, role="Senior Associate", support=0, launch=30000, monthly=4000),
    "Property & Conveyancing": dict(fee=1900, mature=20, ramp=6, role="Associate", support=1, launch=20000, monthly=3000),
    "Commercial Leasing": dict(fee=6500, mature=6, ramp=9, role="Associate", support=0, launch=10000, monthly=1500),
}
