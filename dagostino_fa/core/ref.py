"""Static reference data (people, clients, branches, named matters, deadlines).
Everything time-varying is generated in core/model.py from this reference set so that
every number in the dashboard reconciles to one source of truth."""
import pandas as pd

AS_OF = pd.Timestamp("2025-09-17")           # "today" for the sample data (system sync date)
START = pd.Timestamp("2023-07-01")           # first month of history
PLAN_END = pd.Timestamp("2026-06-01")        # last budget month (FY26 ends 30 Jun 2026)
FY_START_MONTH = 7                           # Australian financial year: 1 Jul – 30 Jun

AREAS = ["Corporate", "Litigation", "IP Portfolio", "Employment", "Advisory"]
NAV_ITEMS = ["Overview", "Matters", "Clients", "Calendar", "Finance", "Team", "Simulator"]
USER_NAME, USER_ROLE = "Brian Phu", "Financial Analyst"

BRANCHES = [
    {"name": "Richmond", "lat": -33.6003, "lon": 150.7514, "council": "Hawkesbury City Council", "support": 4, "rent": 7600},
    {"name": "Camden", "lat": -34.0489, "lon": 150.6993, "council": "Camden Council", "support": 6, "rent": 8400},
    {"name": "Liverpool", "lat": -33.9209, "lon": 150.8809, "council": "Liverpool City Council", "support": 7, "rent": 8200},
]
BRANCH_NAMES = [b["name"] for b in BRANCHES]
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
