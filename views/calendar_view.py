"""Calendar — court dates and filing deadlines."""
import calendar as _cal
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import ui
from core.ref import AS_OF, ATTORNEYS
from core.theme import TEAL, INDIGO, AMBER, RED, INK, MUTED, inject_css, AREA_COLORS

KIND_ORDER = ["Hearing / Trial", "Mediation", "Filing / Deadline", "Key date"]
KIND_COLOR = {"Hearing / Trial": RED, "Mediation": INDIGO, "Filing / Deadline": AMBER, "Key date": TEAL}


def _kind(title, typ=""):
    """Bucket any deadline into one of four groups, by keywords in its type or title. Used everywhere on this page
    (month-view chips, the legend and the per-attorney workload chart) so the legend never grows past 4 entries,
    however many distinct `type` values (e.g. "Opposition Deadline", "Board Approval") exist in the data."""
    s = f"{typ} {title}".lower()
    if any(k in s for k in ("hearing", "trial", "tribunal", "panel")):
        return "Hearing / Trial"
    if any(k in s for k in ("mediation", "conciliation", "review meeting")):
        return "Mediation"
    if any(k in s for k in ("filing", "deadline", "response", "due", "examination", "opposition")):
        return "Filing / Deadline"
    return "Key date"


def _kind_color(title, typ=""):
    return KIND_COLOR[_kind(title, typ)]


def render(M, cur, cmp):
    ui.page_header("Calendar", "Court appearances, filings and completions across all matters", f"As of {AS_OF:%d %b %Y}")
    dl = M["deadlines"].copy()
    dl["days"] = (dl["date"] - AS_OF).dt.days
    up = dl[dl["days"] >= 0]
    n30, n60, n90 = [int((up["days"] <= n).sum()) for n in (30, 60, 90)]
    this_week = int((up["days"] <= 7).sum())
    court = int(up[(up["days"] <= 30) & (up["court"] != "—")].shape[0])
    ui.kpi_row([
        dict(label="This week", value=f"{this_week}", label_cmp=None, accent=RED, sub="next 7 days"),
        dict(label="Next 30 days", value=f"{n30}", label_cmp=None, accent=AMBER, sub=f"{court} in a court or tribunal"),
        dict(label="Next 60 days", value=f"{n60}", label_cmp=None, accent=TEAL),
        dict(label="Next 90 days", value=f"{n90}", label_cmp=None, accent=TEAL),
        dict(label="Busiest attorney (30 d)", value=up[up["days"] <= 30]["attorney"].value_counts().index[0] if n30 else "—", label_cmp=None, accent=INDIGO,
             sub=f"{up[up['days'] <= 30]['attorney'].value_counts().iloc[0]} dates" if n30 else None),
    ], spacer_after=6)

    tabs = st.tabs(["Month view", "Agenda", "Workload"])

    with tabs[0]:
        months = [AS_OF.replace(day=1) + pd.DateOffset(months=i) for i in range(0, 6)]
        with ui.card("cal1"):
            sel = st.selectbox("Month", months, format_func=lambda d: d.strftime("%B %Y"), key="cal_month")
            inject_css("""<style>
.cal-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:4px; }
.cal-h { font-size:10.5px; font-weight:700; color:#475569; text-align:center; padding:2px 0; }
.cal-c { min-height:74px; background:#f8fafc; border:1px solid #eef2f6; border-radius:8px; padding:3px 5px; overflow:hidden; }
.cal-c.off { background:transparent; border-color:transparent; }
.cal-c.today { border:2px solid #0a8496; background:#ecfeff; }
.cal-d { font-size:10.5px; font-weight:700; color:#64748b; }
.cal-e { font-size:9.5px; line-height:1.25; margin-top:2px; padding:1px 4px; border-radius:4px; color:#fff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.cal-more { font-size:9px; color:#64748b; margin-top:1px; }
</style>""")
            y, m = sel.year, sel.month
            evs = dl[(dl["date"].dt.year == y) & (dl["date"].dt.month == m)]
            by_day = {d: g for d, g in evs.groupby(evs["date"].dt.day)}
            html = '<div class="cal-grid">' + "".join(f'<div class="cal-h">{d}</div>' for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
            for week in _cal.Calendar(firstweekday=0).monthdayscalendar(y, m):
                for day in week:
                    if day == 0:
                        html += '<div class="cal-c off"></div>'
                        continue
                    is_today = (y, m, day) == (AS_OF.year, AS_OF.month, AS_OF.day)
                    cell = f'<div class="cal-d">{day}</div>'
                    g = by_day.get(day)
                    if g is not None:
                        for _, e in g.head(2).iterrows():
                            cell += f'<div class="cal-e" style="background:{_kind_color(e["title"], e["type"])}" title="{e["title"]} · {e["attorney"]}">{e["title"]}</div>'
                        if len(g) > 2:
                            cell += f'<div class="cal-more">+{len(g) - 2} more</div>'
                    html += f'<div class="cal-c{" today" if is_today else ""}">{cell}</div>'
            st.markdown(html + "</div>", unsafe_allow_html=True)
            ui.spacer(14)
            legend_line = " · ".join(f'<span style="color:{KIND_COLOR[k]}">■</span> {k}' for k in KIND_ORDER)
            st.markdown(f'<div class="tbl-note">{len(evs)} dates in {sel:%B %Y}. {legend_line}. Today is outlined.</div>', unsafe_allow_html=True)

    with tabs[1]:
        with ui.card("cal2"):
            f1, f2, f3 = st.columns(3)
            atts = f1.multiselect("Attorney", [a["short"] for a in ATTORNEYS], key="cal_att")
            horizon = f2.selectbox("Horizon", ["Next 30 days", "Next 60 days", "Next 90 days", "All upcoming"], index=1, key="cal_h")
            kinds = f3.multiselect("Type", sorted(up["type"].unique()), key="cal_kind")
            d = up.copy()
            if atts: d = d[d["attorney"].isin(atts)]
            if kinds: d = d[d["type"].isin(kinds)]
            lim = {"Next 30 days": 30, "Next 60 days": 60, "Next 90 days": 90}.get(horizon)
            if lim: d = d[d["days"] <= lim]
            c1, c2 = st.columns([6, 1])
            c1.markdown(f'<div class="tbl-note">{len(d)} upcoming dates</div>', unsafe_allow_html=True)
            with c2: ui.csv_button(d.drop(columns=["matter_id"]), "deadlines", "deadlines")
            st.dataframe(d[["date", "days", "title", "type", "court", "attorney"]], hide_index=True, width="stretch", height=380, column_config={
                "date": st.column_config.DateColumn("Date", format="ddd DD MMM YY", width=120), "days": st.column_config.NumberColumn("In (days)", format="%d", width=80), "title": st.column_config.TextColumn("Matter / event", width=380),
                "type": st.column_config.TextColumn("Type", width=140), "court": st.column_config.TextColumn("Court / body", width=170), "attorney": st.column_config.TextColumn("Attorney", width=100)})

    with tabs[2]:
        c1, c2 = st.columns(2)
        with c1:
            with ui.card("cal3"):
                ui.card_title("Dates per week", "next 13 weeks")
                wk = ((up["days"] // 7)).clip(upper=12)
                g = wk.value_counts().reindex(range(13)).fillna(0)
                labels = [(AS_OF + pd.Timedelta(days=7 * i)).strftime("%d %b") for i in range(13)]
                fig = go.Figure(go.Bar(x=labels, y=g.values, marker_color=[RED if i == 0 else TEAL for i in range(13)], hovertemplate="week of %{x}: %{y} dates<extra></extra>"))
                fig.update_layout(**ui.base_layout(260))
                ui.show(ui.style_axes(fig), key="cal_weeks")
        with c2:
            with ui.card("cal4"):
                ui.card_title("Dates per attorney", "next 60 days, by type")
                d60 = up[up["days"] <= 60].copy()
                d60["kind"] = [_kind(t, ty) for t, ty in zip(d60["title"], d60["type"])]
                g = d60.groupby(["attorney", "kind"]).size().unstack(fill_value=0).reindex(columns=KIND_ORDER, fill_value=0)
                g = g.loc[:, (g.sum(axis=0) > 0)]                                  # drop a bucket only if nothing in the window uses it
                g = g.loc[g.sum(axis=1).sort_values().index]
                CH = max(220, 34 * len(g.index) + 70)                              # enough row height regardless of how many attorneys have dates
                fig = go.Figure([go.Bar(y=g.index, x=g[c], orientation="h", name=c, marker_color=KIND_COLOR[c], hovertemplate="%{y} — " + c + ": %{x}<extra></extra>") for c in g.columns])
                fig.update_layout(**ui.base_layout(CH, legend=True))
                fig.update_layout(barmode="stack", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=10)), margin=dict(l=8, r=8, t=34, b=4))
                ui.show(ui.style_axes(fig), key="cal_att_chart")
        ui.note("Clusters of court dates in the same week on the same attorney are a capacity risk: check billable-hour plans and cover before those weeks.")
