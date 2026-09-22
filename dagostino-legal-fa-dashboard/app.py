"""D'Agostino Legal — Financial Operations Dashboard (entry point).

Run:  streamlit run app.py
"""
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="D'Agostino Legal — Operations", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")

from core import platforms as P
from core import theme, ui
from core.model import build_model
from core.period import current_periods, init_state, render_period_control
from core.ref import AS_OF, NAV_ITEMS, USER_NAME, USER_ROLE
from core.theme import PLATFORM_COLOR_LIST
from views import calendar_view, clients, finance, matters, overview, platform_view, simulator, team

PAGES = {"Overview": overview.render, "Matters": matters.render, "Clients": clients.render, "Calendar": calendar_view.render,
         "Finance": finance.render, "Team": team.render, "Simulator": simulator.render}


@st.cache_resource(show_spinner="Building the financial model…")
def get_model():
    return build_model()


def _rgba(h, a):
    h = h.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


theme.apply_theme()
M = get_model()
init_state()
ss = st.session_state
ss.setdefault("view_kind", "page")
ss.setdefault("view_name", "Overview")
ss.setdefault("polar_nonce", 0)
ui.reset_card_counter()


def go_platform(name):
    ss.view_kind, ss.view_name = "platform", name
    st.rerun()


# ----------------------------------------------------------------- sidebar ----
with st.sidebar:
    st.markdown('<div class="sidebar-brand"><div class="sidebar-brand-badge">D</div><div class="sidebar-brand-name">D\'Agostino Legal</div></div>', unsafe_allow_html=True)
    inp = P.base_inputs(M)
    names = P.NAMES
    costs = [P.run_rate(n, inp) for n in names]
    selected = ss.view_name if ss.view_kind == "platform" else None
    st.markdown('<div class="sidebar-label" style="margin-bottom:0px;">Annual run-cost — all platforms</div>'
                '<div style="font-size:10px; color:rgba(255,255,255,0.5); margin-bottom:2px;">Click a wedge to open its dashboard</div>', unsafe_allow_html=True)
    fig = go.Figure(go.Barpolar(r=costs, theta=[P.SHORT[n] for n in names],
                                marker_color=[_rgba(P.COLORS[n], 0.90 if n == selected else 0.34) for n in names],
                                marker_line_color=["#ffffff" if n == selected else "rgba(255,255,255,0.22)" for n in names], marker_line_width=2,
                                hovertemplate="%{theta}: %{customdata}<extra></extra>", customdata=[ui.fmt_money(c) for c in costs]))
    fig.update_layout(margin=dict(l=8, r=8, t=6, b=6), height=140, paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                      font=dict(family="Inter, sans-serif", color="rgba(255,255,255,0.8)", size=9),
                      polar=dict(bgcolor="rgba(255,255,255,0.04)",
                                 radialaxis=dict(visible=True, showticklabels=False, ticks="", gridcolor="rgba(255,255,255,0.12)", linecolor="rgba(255,255,255,0.12)"),
                                 angularaxis=dict(gridcolor="rgba(255,255,255,0.12)", linecolor="rgba(255,255,255,0.2)", showticklabels=False, ticks="")))
    ev = st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, on_select="rerun", selection_mode="points", key=f"platform_polar_{ss.polar_nonce}")
    if ev and ev.selection and ev.selection.points:
        clicked = ev.selection.points[0].get("theta")
        if clicked in P.SHORT_TO_FULL:
            ss.polar_nonce += 1                      # new chart key → selection resets, so the same wedge can be clicked again later
            go_platform(P.SHORT_TO_FULL[clicked])
    legend = "".join(f'<div style="display:flex; align-items:center; gap:5px; font-size:10px; color:{"#ffffff" if n == selected else "rgba(255,255,255,0.62)"}; '
                     f'font-weight:{"700" if n == selected else "400"};"><span style="width:7px; height:7px; border-radius:999px; flex-shrink:0; background:{P.COLORS[n]}; '
                     f'opacity:{"1" if n == selected else "0.5"};"></span>{P.SHORT[n]}</div>' for n in names)
    st.markdown(f'<div class="sb-legend" style="display:grid; grid-template-columns:1fr 1fr; gap:5px 8px; margin-top:8px;">{legend}</div><div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-label">Practice &amp; search platforms</div><div class="sidebar-sub">Open a system to see its own evaluation dashboard.</div>', unsafe_allow_html=True)
    for i, n in enumerate(names):
        if st.button(n, key=f"platform_btn_{i}", type="primary" if n == selected else "secondary", width="stretch"):
            go_platform(n)

# ----------------------------------------------------------------- top bar ----
with st.container(key="topbar"):
    nav_wrap, period_col, user_col = st.columns([5.4, 1.9, 1.5], vertical_alignment="center")
    with nav_wrap:
        for col, item in zip(st.columns([1.0 if i != "Simulator" else 1.45 for i in NAV_ITEMS]), NAV_ITEMS):      # the highlighted tab gets extra room
            with col:
                if st.button("★ Simulator" if item == "Simulator" else item, key=f"nav_{item}", type="primary" if (ss.view_kind == "page" and ss.view_name == item) else "secondary", width="stretch"):
                    ss.view_kind, ss.view_name = "page", item
                    st.rerun()
    with period_col:
        render_period_control()
    with user_col:
        initials = "".join(part[0] for part in USER_NAME.split()[:2]).upper()
        st.markdown(f'<div class="user-row"><div><div class="user-name" style="text-align:right;">Welcome, {USER_NAME}</div>'
                    f'<div class="user-role" style="text-align:right;">{USER_ROLE}</div></div><div class="avatar-initials">{initials}</div></div>', unsafe_allow_html=True)
ui.spacer(2)

# ------------------------------------------------------------------- router ----
cur, cmp = current_periods()
if ss.view_kind == "platform":
    platform_view.render(M, ss.view_name, cur, cmp)
else:
    PAGES.get(ss.view_name, overview.render)(M, cur, cmp)
