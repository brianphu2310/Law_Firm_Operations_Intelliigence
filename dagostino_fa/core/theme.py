"""Design tokens + global CSS (kept in one place so every page looks the same)."""
import streamlit as st

BG = "#f0eefb"; CARD = "#ffffff"; BORDER = "#e2e8f0"; TEAL = "#0a8496"; TEAL_TINT = "#ecfeff"
INK = "#0f172a"; MUTED = "#475569"; FAINT = "#94a3b8"; GREEN = "#10b981"; RED = "#ef4444"; AMBER = "#f59e0b"
GREEN_TINT = "#f0fdf4"; RED_TINT = "#fef2f2"; AMBER_TINT = "#fffbeb"; BLUE = "#2f7fd8"; INDIGO = "#6366f1"; VIOLET = "#9061d6"
SHADOW = "0 10px 28px rgba(15,23,42,0.20), 0 3px 8px rgba(15,23,42,0.12)"
SERIES = [TEAL, "#4fb6c4", BLUE, INDIGO, VIOLET, AMBER, "#94a3b8"]           # default chart palette
AREA_COLORS = {"Corporate": TEAL, "Litigation": BLUE, "IP Portfolio": INDIGO, "Employment": AMBER, "Advisory": "#8fcbe0"}

# one accent per practice/search platform (same order as PLATFORM_OPTIONS)
PLATFORM_COLOR_LIST = ["#22d3ee", "#34d399", "#fbbf24", "#fb7185", "#a78bfa", "#60a5fa", "#f472b6"]


def base_css():
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class^="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {BG}; }}
.block-container {{ padding-top: 0.5rem; padding-bottom: 0.6rem; padding-left: 1rem; padding-right: 1rem; max-width: 1440px; }}

/* Sidebar — narrow, black, floating rounded block (not edge-to-edge) */
section[data-testid="stSidebar"] {{
    width: 190px !important; min-width: 190px !important;
    background: {BG} !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{ display: none !important; }}
section[data-testid="stSidebar"] > div {{
    padding: 8px 6px 6px 8px;
    background: {BG} !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
    background: #14171c; border-radius: 16px; padding: 14px 12px 10px 12px;
    box-shadow: 0 10px 26px rgba(15,23,42,0.18), 0 3px 7px rgba(15,23,42,0.11);
    /* kéo khối đen xuống tận chân trang: đáy cách viền dưới 11px = cùng đường đáy với hàng card cuối */
    box-sizing: border-box; min-height: calc(100vh - 19px);
}}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] p,
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] label,
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] span {{ color: #ffffff !important; }}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: rgba(255,255,255,0.6) !important; }}
.sidebar-brand {{ display:flex; align-items:center; gap:8px; margin-bottom:14px; }}
.sidebar-brand-badge {{
    background:#ffffff; width:26px; height:26px; border-radius:7px;
    display:flex; align-items:center; justify-content:center;
    color:#14171c; font-weight:800; font-size:15px; flex-shrink:0;
}}
section[data-testid="stSidebar"] .sidebar-brand-badge {{ color:#14171c !important; }}
.sidebar-brand-name {{ font-weight:700; font-size:13px; color:#ffffff !important; }}
.sidebar-label {{ font-size:12.5px; font-weight:700; color:#ffffff; margin-bottom:2px; }}
.sidebar-sub {{ font-size:11px; color:rgba(255,255,255,0.55); margin-bottom:12px; line-height:1.4; }}

/* Plotly never draws narrower than ~150px — nudge it so the sidebar's polar chart isn't clipped */
section[data-testid="stSidebar"] [data-testid="stPlotlyChart"] {{ overflow: visible !important; }}
section[data-testid="stSidebar"] [data-testid="stPlotlyChart"] .js-plotly-plot {{ margin-left: -9px; }}

/* Platform picker rows — real full-width clickable buttons, not radio dots */
section[data-testid="stSidebar"] div[data-testid="stButton"] button {{
    width: 100% !important; text-align: left !important; justify-content: flex-start !important;
    border-radius: 10px !important; padding: 6px 12px !important; font-size: 12.5px !important;
    font-weight: 500 !important; color: rgba(255,255,255,0.75) !important;
    background: rgba(255,255,255,0.06) !important; border: 1px solid transparent !important;
    margin-bottom: 4px !important; white-space: normal !important; line-height: 1.25 !important;
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover {{
    background: rgba(255,255,255,0.14) !important; color: #ffffff !important;
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {{
    background: #ffffff !important; color: #14171c !important; font-weight: 700 !important;
    border: 1px solid #ffffff !important;
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] * {{
    color: #14171c !important;
}}
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; }}
div[data-testid="stVerticalBlock"] {{ gap: 0.35rem; }}

div[class*="st-key-cardblock_"] {{
    background:{CARD} !important; border-radius: 18px !important;
    box-shadow: 0 10px 28px rgba(15,23,42,0.20), 0 3px 8px rgba(15,23,42,0.12) !important;
    border: 1px solid #dbe6ee !important; padding: 0.65rem !important;
}}

.brand {{ display:flex; align-items:center; gap:8px; height:38px; white-space:nowrap; }}
.brand-badge {{
    background:#ffffff; width:26px; height:26px; border-radius:7px;
    display:flex; align-items:center; justify-content:center;
    color:{TEAL}; font-weight:800; font-size:14px; flex-shrink:0;
}}
.brand-name {{ font-weight:700; font-size:13px; color:#ffffff; white-space:nowrap; }}
.user-row {{ display:flex; align-items:center; gap:8px; justify-content:flex-end; height:38px; white-space:nowrap; }}
.avatar-initials {{
    width:30px; height:30px; border-radius:15px; background:#ffffff;
    color:{TEAL}; font-weight:700; font-size:11px;
    display:flex; align-items:center; justify-content:center; flex-shrink:0;
}}
.user-name {{ font-weight:600; font-size:12px; color:#ffffff; line-height:1.2; white-space:nowrap; }}
.user-role {{ font-size:9.5px; color:rgba(255,255,255,0.75); line-height:1.2; white-space:nowrap; }}

.st-key-topbar div[data-testid="stButton"] button {{
    border-radius: 999px !important; font-weight: 600 !important; font-size: 12px !important;
    padding: 6px 2px !important; border: 1px solid transparent !important;
    background: transparent !important; color: {TEAL_TINT} !important; box-shadow: none !important;
    white-space: nowrap !important; overflow: visible !important;
}}
.st-key-topbar div[data-testid="stButton"] button:hover {{ color:#ffffff !important; border-color:rgba(255,255,255,0.4) !important; }}
.st-key-topbar div[data-testid="stButton"] button[kind="primary"] {{
    background:#ffffff !important; color:{TEAL} !important; border:1px solid #ffffff !important;
}}

.st-key-topbar {{
    background:{TEAL} !important; border-radius:16px !important; padding:8px 16px !important;
    box-shadow: 0 10px 28px rgba(15,23,42,0.20), 0 3px 8px rgba(15,23,42,0.12) !important;
}}

.kpi-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:14px; padding:5px 10px; height:100%; box-shadow: 0 10px 26px rgba(15,23,42,0.18), 0 3px 7px rgba(15,23,42,0.11); margin-bottom:16px; }}
.kpi-label {{ font-size:11px; font-weight:500; color:{MUTED}; margin-bottom:1px; }}
.kpi-bottom {{ display:flex; align-items:flex-end; justify-content:space-between; gap:8px; }}
.kpi-value {{ font-size:17px; font-weight:700; color:{INK}; white-space:nowrap; }}
.kpi-trend {{ display:flex; align-items:center; gap:4px; margin-top:0px; white-space:nowrap; }}
.kpi-trend .pct {{ font-size:10.5px; font-weight:600; }}
.kpi-trend .vs {{ font-size:9.5px; color:{FAINT}; }}

.card-title {{ font-size:13.5px; font-weight:700; color:{INK}; margin-bottom:2px; white-space:nowrap; }}
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

table.matrix {{ width:100%; border-collapse:collapse; font-size:11.5px; }}
table.matrix th {{ background:{BG}; font-weight:600; color:{MUTED}; padding:5px 4px; text-align:center; font-size:10.5px; }}
table.matrix td {{ border:0.5px solid {BORDER}; height:27px; text-align:center; font-weight:500; color:{INK}; }}

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

.attorney-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:16px; padding:14px; text-align:center; box-shadow: 0 10px 26px rgba(15,23,42,0.18), 0 3px 7px rgba(15,23,42,0.11); }}
.attorney-avatar {{
    width:42px; height:42px; border-radius:21px; background:{TEAL}; color:#fff;
    font-weight:700; font-size:14px; display:flex; align-items:center; justify-content:center;
    margin: 0 auto 8px auto;
}}

.branch-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:16px; padding:14px; box-shadow: 0 10px 26px rgba(15,23,42,0.18), 0 3px 7px rgba(15,23,42,0.11); }}
.branch-name {{ font-size:14px; font-weight:700; color:{INK}; }}
.branch-council {{ font-size:11px; color:{MUTED}; margin-bottom:8px; }}
</style>
"""



def sidebar_css():
    per_btn = "".join(f'div[class*="st-key-platform_btn_{i}"]{{--pc:{c};}}' for i, c in enumerate(PLATFORM_COLOR_LIST))
    return """<style>
/* ===== Sidebar: soft gradient background + one colour cue per platform (no looping animation) ===== */
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    background:
        radial-gradient(120% 40% at 0% 0%, rgba(34,211,238,0.10), transparent 62%),
        linear-gradient(180deg, #14181f 0%, #101720 100%) !important;
    border: 1px solid rgba(255,255,255,0.05);
}
section[data-testid="stSidebar"] .sidebar-brand-badge {
    background: linear-gradient(135deg, #22b8cf, #3b82f6) !important; color: #ffffff !important;
}
.sidebar-divider { height: 1px; margin: 10px 0 8px; background: rgba(255,255,255,0.12); }

section[data-testid="stSidebar"] div[data-testid="stButton"] button {
    position: relative !important; padding: 6px 12px 6px 28px !important;
    background: rgba(255,255,255,0.06) !important; border: 1px solid transparent !important;
    color: rgba(255,255,255,0.80) !important; transition: background .15s ease, border-color .15s ease !important;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] button::before {
    content: ""; position: absolute; left: 12px; top: 50%; width: 7px; height: 7px; margin-top: -3.5px; border-radius: 50%;
    background: var(--pc, #22d3ee);
}
section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
    background: rgba(255,255,255,0.12) !important; color: #ffffff !important;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"] {
    background: #ffffff !important; color: #14171c !important; font-weight: 700 !important;
    border-color: #ffffff !important; box-shadow: 0 0 0 1.5px var(--pc, #22d3ee) !important;
}
/* short screens: drop the repeated legend (each button already carries its colour dot) and tighten spacing so the sidebar never scrolls */
@media (max-height: 880px) {
    .sb-legend { display: none !important; }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button { padding-top: 4px !important; padding-bottom: 4px !important; }
    .sidebar-brand { margin-bottom: 8px !important; }
    .sidebar-divider { margin: 6px 0 6px !important; }
}
@media (max-height: 800px) {
    .sidebar-sub { display: none; }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button { margin-bottom: 3px !important; }
}
""" + per_btn + "</style>"




EXTRA = """<style>
/* ---------- page furniture ---------- */
.page-head { display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin:2px 0 16px 0; }
.page-title { font-size:19px; font-weight:800; color:#0f172a; line-height:1.15; }
.page-sub { font-size:12px; color:#475569; margin-top:1px; }
.page-tag { font-size:11px; font-weight:600; color:#475569; background:#ffffff; border:1px solid #e2e8f0; border-radius:999px; padding:3px 10px; white-space:nowrap; }
.note { font-size:11.5px; color:#475569; background:#f8fafc; border-left:3px solid #94a3b8; border-radius:8px; padding:6px 10px; margin:4px 0; }
.note.warn { background:#fffbeb; border-left-color:#f59e0b; color:#78350f; }
.note.good { background:#f0fdf4; border-left-color:#10b981; color:#14532d; }
.pill { display:inline-block; padding:2px 9px; border-radius:999px; font-size:11px; font-weight:700; white-space:nowrap; }
.kpi-sub { font-size:10px; color:#94a3b8; margin-top:1px; }
.kpi-accent { border-top:3px solid var(--acc, #0a8496); }
.tbl-note { font-size:10.5px; color:#94a3b8; margin-top:2px; }

/* ---------- tabs ---------- */
.stTabs [data-baseweb="tab-list"] { gap:4px; border-bottom:1px solid #dbe6ee; }
.stTabs [data-baseweb="tab"] { padding:6px 12px; font-size:12.5px; font-weight:600; color:#475569; }
.stTabs [aria-selected="true"] { color:#0a8496 !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color:#0a8496 !important; }

/* ---------- top-bar period popover ---------- */
.st-key-topbar [data-testid="stPopover"] button { width:100%; border-radius:999px !important; background:rgba(255,255,255,.16) !important;
    color:#ffffff !important; border:1px solid rgba(255,255,255,.35) !important; font-size:12px !important; font-weight:600 !important; padding:5px 10px !important; }
.st-key-topbar [data-testid="stPopover"] button:hover { background:rgba(255,255,255,.26) !important; }
.st-key-topbar [data-testid="stPopover"] button p { color:#ffffff !important; }

/* ---------- normal buttons / download buttons on content pages ---------- */
.stDownloadButton button, div[class*="st-key-act_"] button { border-radius:999px !important; border:1px solid #0a8496 !important; color:#0a8496 !important; background:#ffffff !important; font-size:12px !important; font-weight:600 !important; padding:4px 12px !important; }
.stDownloadButton button:hover, div[class*="st-key-act_"] button:hover { background:#ecfeff !important; }
[data-testid="stDataFrame"] { border-radius:10px; overflow:hidden; }
table.simple { width:100%; border-collapse:collapse; font-size:12px; }
table.simple th { text-align:left; color:#475569; font-weight:600; padding:6px 8px; font-size:11px; border-bottom:1px solid #e2e8f0; }
table.simple td { padding:6px 8px; border-bottom:1px solid #f1f5f9; color:#0f172a; }
table.simple td.num, table.simple th.num { text-align:right; font-variant-numeric:tabular-nums; }
table.simple tr.total td { font-weight:800; border-top:2px solid #cbd5e1; background:#f8fafc; }
table.simple tr.sub td { font-weight:700; background:#f8fafc; }
</style>"""


def _compact(css):
    return "\n".join(l for l in css.splitlines() if l.strip())


def inject_css(css):
    """Inject a <style> block without going through Markdown (Markdown can end an HTML block early and print CSS as text).
    The marker span lets the global rule below collapse the empty element container that st.html leaves behind."""
    st.html('<span class="fit-css"></span>' + _compact(css))


HIDE_CSS = """<style>
div[data-testid="stElementContainer"]:has(.fit-css), .element-container:has(.fit-css) { display:none !important; }
</style>"""


def apply_theme():
    inject_css(HIDE_CSS + base_css() + sidebar_css() + EXTRA)
