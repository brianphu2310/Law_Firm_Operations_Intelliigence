"""Reusable UI pieces: formatters, KPI cards, cards/containers, chart helpers, tables."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .theme import (TEAL, TEAL_TINT, INK, MUTED, FAINT, GREEN, RED, AMBER, BG, BORDER, GREEN_TINT, RED_TINT, AMBER_TINT)

# ------------------------------------------------------------------ format ----
def fmt_money(v, dec=None, sign=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    s = "-" if v < 0 else ("+" if sign and v > 0 else "")
    a = abs(v)
    if a >= 1_000_000:
        return f"{s}${a / 1_000_000:.{2 if dec is None else dec}f}M"
    if a >= 10_000:
        return f"{s}${a / 1_000:.{0 if dec is None else dec}f}K"
    if a >= 1_000:
        return f"{s}${a / 1_000:.{1 if dec is None else dec}f}K"
    return f"{s}${a:,.{0 if dec is None else dec}f}"


def fmt_num(v, dec=0):
    return "—" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:,.{dec}f}"


def fmt_pct(v, dec=1, sign=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{'+' if sign and v > 0 else ''}{v * 100:.{dec}f}%"


def pp(v, dec=1):
    """Percentage-point difference."""
    return "—" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{'+' if v > 0 else ''}{v * 100:.{dec}f} pp"


# ------------------------------------------------------------- html bits ----
def sparkline_svg(values, color=TEAL, width=60, height=28):
    v = np.asarray(values, dtype=float)
    if len(v) < 2 or np.all(np.isnan(v)):
        return ""
    lo, hi = np.nanmin(v), np.nanmax(v)
    span = (hi - lo) or 1.0
    step = width / (len(v) - 1)
    pts = " ".join(f"{i * step:.1f},{height - ((x - lo) / span) * (height - 4) - 2:.1f}" for i, x in enumerate(v))
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"><polyline points="{pts}" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def _arrow(up, color):
    d = "M6 10V2M2.5 5.5 6 2l3.5 3.5" if up else "M6 2v8M2.5 6.5 6 10l3.5-3.5"
    return (f'<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="{d}" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def delta_html(d, up_good=True, label="vs prior", kind="pct"):
    """d = relative change (or pp change when kind='pp'); None → n/a."""
    if d is None or (isinstance(d, float) and np.isnan(d)):
        return f'<span class="vs" style="color:{FAINT}">n/a</span>'
    if abs(d) < (5e-4 if kind == "pct" else 5e-4):          # rounds to 0.0 → neutral, no misleading red/green arrow
        return f'<span style="display:inline-flex;align-items:center;gap:4px"><span class="pct" style="color:{FAINT}">0.0{"%" if kind == "pct" else " pp"}</span><span class="vs">{label}</span></span>'
    good = (d >= 0) == up_good
    color = GREEN if good else RED
    txt = pp(d) if kind == "pp" else f"{'+' if d > 0 else ''}{d * 100:.1f}%"
    return (f'<span style="display:inline-flex;align-items:center;gap:4px">{_arrow(d >= 0, color)}'
            f'<span class="pct" style="color:{color}">{txt}</span><span class="vs">{label}</span></span>')


def kpi_html(label, value, d=None, up_good=True, label_cmp="vs prior", kind="pct", spark=None, sub=None, color=INK, accent=None, min_h=0):
    css = []
    if accent:
        css.append(f"--acc:{accent}")
    if min_h:
        css.append(f"min-height:{min_h}px")
    style = f' style="{";".join(css)}"' if css else ""
    cls = "kpi-card kpi-accent" if accent else "kpi-card"
    sp = sparkline_svg(spark, accent or TEAL) if spark is not None else ""
    trend = f'<div class="kpi-trend">{delta_html(d, up_good, label_cmp, kind)}</div>' if label_cmp is not None else ""
    subh = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (f'<div class="{cls}"{style}><div class="kpi-label">{label}</div><div class="kpi-bottom"><div>'
            f'<div class="kpi-value" style="color:{color}">{value}</div>{trend}{subh}</div>{sp}</div></div>')


def kpi_row(items, spacer_after=0, min_h=88):
    """items: list of dicts for kpi_html. Renders one equal-width row (min_h keeps cards level when only some have a sub-line)."""
    for col, it in zip(st.columns(len(items)), items):
        with col:
            st.markdown(kpi_html(**{"min_h": min_h, **it}), unsafe_allow_html=True)
    if spacer_after:
        spacer(spacer_after)


def pill(text, kind="neutral"):
    fg, bg = {"good": (GREEN, GREEN_TINT), "bad": (RED, RED_TINT), "warn": (AMBER, AMBER_TINT), "info": (TEAL, TEAL_TINT),
              "neutral": (MUTED, BG)}[kind]
    return f'<span class="pill" style="background:{bg};color:{fg}">{text}</span>'


STATUS_KIND = {"Open": "good", "Closed": "neutral", "On Hold": "warn", "Paid": "good", "Outstanding": "warn", "Overdue": "bad",
               "Complete": "good", "Pending": "warn", "Payable": "warn", "Deposit": "good", "Disbursement": "warn"}


def status_pill(s):
    return pill(s, STATUS_KIND.get(s, "neutral"))


def note(text, kind=""):
    st.markdown(f'<div class="note {kind}">{text}</div>', unsafe_allow_html=True)


def spacer(h=8):
    st.markdown(f'<div style="height:{h}px"></div>', unsafe_allow_html=True)


def page_header(title, sub=None, tag=None):
    tag_h = f'<span class="page-tag">{tag}</span>' if tag else ""
    sub_h = f'<div class="page-sub">{sub}</div>' if sub else ""
    st.markdown(f'<div class="page-head"><div><div class="page-title">{title}</div>{sub_h}</div>{tag_h}</div>', unsafe_allow_html=True)


def card_title(text, right=None):
    r = f'<span style="font-size:10.5px;color:{FAINT};font-weight:500">{right}</span>' if right else ""
    st.markdown(f'<div class="card-title" style="display:flex;justify-content:space-between;align-items:baseline;padding-bottom:12px">'
                f'<span>{text}</span>{r}</div>', unsafe_allow_html=True)


_seq = [0]


def card(key=None):
    """White rounded card. Keys are unique per render so each gets the .st-key-cardblock_* styling."""
    _seq[0] += 1
    return st.container(border=True, key=f"cardblock_{key or 'c'}_{_seq[0]}")


def reset_card_counter():
    _seq[0] = 0


# ------------------------------------------------------------------ charts ---
def base_layout(h, legend=False, **kw):
    lay = dict(margin=dict(l=8, r=8, t=6, b=4), height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
               showlegend=legend, font=dict(family="Inter, sans-serif", color=MUTED, size=10), hoverlabel=dict(font_size=11))
    if legend:
        lay["legend"] = dict(orientation="h", y=1.14, x=0, font=dict(size=10), bgcolor="rgba(0,0,0,0)")
    lay.update(kw)
    return lay


def style_axes(fig, y_fmt=None, grid=True, x_grid=False):
    fig.update_xaxes(showgrid=x_grid, gridcolor="#f1f5f9", tickfont=dict(size=9), zeroline=False)
    fig.update_yaxes(showgrid=grid, gridcolor="#f1f5f9", tickfont=dict(size=9), zeroline=False, tickformat=y_fmt)
    return fig


def show(fig, key=None, **kw):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key, **kw)


def donut(labels, values, colors, h=150, center=None, key=None):
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.68, marker=dict(colors=colors, line=dict(color="#fff", width=2)),
                           textinfo="none", sort=False, hovertemplate="%{label}: %{percent}<extra></extra>"))
    fig.update_layout(**base_layout(h, margin=dict(l=2, r=2, t=2, b=2)))
    if center:
        fig.add_annotation(text=center, x=0.5, y=0.5, showarrow=False, align="center", font=dict(family="Inter, sans-serif", color=INK))
    show(fig, key=key)


# ------------------------------------------------------------------ tables ---
def csv_button(df, name, key):
    st.download_button("⬇ CSV", df.to_csv(index=False).encode("utf-8"), file_name=f"{name}.csv", mime="text/csv", key=f"dl_{key}")


def money_col(label, fmt="$%,d"):
    """Whole-dollar column with thousands separators (sprintf-js format; values are rounded on display)."""
    return st.column_config.NumberColumn(label, format=fmt)


def render_html_table(df, num_cols=(), total_row=False, sub_rows=(), fmt=None):
    """Compact HTML table (used for P&L-style statements)."""
    fmt = fmt or {}
    head = "".join(f'<th class="{"num" if c in num_cols else ""}">{c}</th>' for c in df.columns)
    body = ""
    for i, (_, r) in enumerate(df.iterrows()):
        cls = "total" if total_row and i == len(df) - 1 else ("sub" if i in sub_rows else "")
        tds = "".join(f'<td class="{"num" if c in num_cols else ""}">{fmt[c](r[c]) if c in fmt else r[c]}</td>' for c in df.columns)
        body += f'<tr class="{cls}">{tds}</tr>'
    st.markdown(f'<table class="simple"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>', unsafe_allow_html=True)


def period_tag(cur, cmp):
    from .period import has_data
    tag = f"{cur.label} · {cur.short()}"
    if cmp is None:
        return tag
    return tag + (f"  vs  {cmp.short()}" if has_data(cmp) else "  · no comparison data before Jul 2023")


def cmp_label(cmp):
    if cmp is None:
        return None
    return "vs LY" if "last year" in cmp.label else "vs prior"
