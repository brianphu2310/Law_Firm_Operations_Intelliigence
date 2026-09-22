"""Reporting periods: presets, comparison windows, and day-weighted aggregation of the monthly model."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
import streamlit as st

from .ref import AS_OF, START


@dataclass(frozen=True)
class Period:
    start: pd.Timestamp
    end: pd.Timestamp
    label: str

    @property
    def days(self):
        return int((self.end - self.start).days + 1)

    def short(self):
        return f"{self.start:%d %b %y} – {self.end:%d %b %y}"


def _fy_label(ts):
    y = ts.year if ts.month >= 7 else ts.year - 1
    return f"FY{(y + 1) % 100:02d}"


def _quarter_start(ts):
    fy_start = pd.Timestamp(year=ts.year if ts.month >= 7 else ts.year - 1, month=7, day=1)
    k = ((ts.year - fy_start.year) * 12 + ts.month - fy_start.month) // 3
    return fy_start + pd.DateOffset(months=3 * k)


def _shift(p: Period, months: int, label: str) -> Period:
    def sh(d, is_end):
        if is_end and d == d + pd.offsets.MonthEnd(0):
            return (d + pd.DateOffset(months=months)) + pd.offsets.MonthEnd(0)
        return d + pd.DateOffset(months=months)
    return Period(sh(p.start, False), sh(p.end, True), label)


def presets():
    m0 = AS_OF.replace(day=1)
    q0 = _quarter_start(AS_OF)
    fy0 = pd.Timestamp(year=AS_OF.year if AS_OF.month >= 7 else AS_OF.year - 1, month=7, day=1)
    lm0 = m0 - pd.DateOffset(months=1)
    lq0 = q0 - pd.DateOffset(months=3)
    qn = ((q0.year - fy0.year) * 12 + q0.month - fy0.month) // 3 + 1
    out = {
        "This month (MTD)": (Period(m0, AS_OF, f"{AS_OF:%b %Y} MTD"), 1),
        "Last month": (Period(lm0, m0 - pd.Timedelta(days=1), f"{lm0:%b %Y}"), 1),
        f"This quarter (QTD)": (Period(q0, AS_OF, f"{_fy_label(AS_OF)} Q{qn} QTD"), 3),
        "Last quarter": (Period(lq0, q0 - pd.Timedelta(days=1), f"{_fy_label(lq0)} Q{((lq0.year - (lq0.year if lq0.month >= 7 else lq0.year - 1)) * 12 + lq0.month - 7) // 3 % 4 + 1}"), 3),
        "Last 6 months": (Period(m0 - pd.DateOffset(months=5), AS_OF, "Last 6 months"), 6),
        "Last 12 months": (Period(m0 - pd.DateOffset(months=11), AS_OF, "Last 12 months"), 12),
        f"{_fy_label(fy0 - pd.DateOffset(months=12))} (last financial year)": (Period(fy0 - pd.DateOffset(months=12), fy0 - pd.Timedelta(days=1), _fy_label(fy0 - pd.DateOffset(months=12))), 12),
        f"{_fy_label(fy0 - pd.DateOffset(months=24))} (two years ago)": (Period(fy0 - pd.DateOffset(months=24), fy0 - pd.DateOffset(months=12) - pd.Timedelta(days=1), _fy_label(fy0 - pd.DateOffset(months=24))), 12),
    }
    return out


DEFAULT_PRESET = "This quarter (QTD)"
CUSTOM = "Custom range"
COMPARE_MODES = ["Prior period", "Same period last year", "No comparison"]


def current_periods():
    """(current, comparison|None) from the sidebar/topbar controls."""
    pre = presets()
    key = st.session_state.get("period_preset", DEFAULT_PRESET)
    mode = st.session_state.get("compare_mode", COMPARE_MODES[0])
    if key == CUSTOM:
        s = pd.Timestamp(st.session_state.get("custom_start", pd.Timestamp("2025-07-01")))
        e = pd.Timestamp(st.session_state.get("custom_end", AS_OF))
        s, e = min(s, e), min(max(s, e), AS_OF)
        cur, shift = Period(s, e, f"{s:%d %b} – {e:%d %b %y}"), None
    else:
        cur, shift = pre.get(key, pre[DEFAULT_PRESET])
    if mode == "No comparison":
        return cur, None
    if mode == "Same period last year":
        return cur, _shift(cur, -12, "same period last year")
    if shift is None:                                    # custom: equal-length window immediately before
        n = cur.days
        return cur, Period(cur.start - pd.Timedelta(days=n), cur.start - pd.Timedelta(days=1), "prior period")
    return cur, _shift(cur, -shift, "prior period")


def month_weights(p: Period, index):
    out = {}
    for m in pd.date_range(p.start.replace(day=1), p.end, freq="MS"):
        me = m + pd.offsets.MonthEnd(0)
        d = (min(p.end, me) - max(p.start, m)).days + 1
        if d > 0:
            out[m] = d / m.days_in_month
    w = pd.Series(out, dtype=float)
    return w[w.index.isin(index)]


def has_data(p: Period):
    return p is not None and p.start >= START


def flow(df, p: Period, cols):
    """Day-weighted sum of full-month-equivalent columns over the period."""
    if p is None or not has_data(p):
        return pd.Series(np.nan, index=[cols] if isinstance(cols, str) else cols) if not isinstance(cols, str) else np.nan
    w = month_weights(p, df.index)
    if isinstance(cols, str):
        return float((df.loc[w.index, cols] * w).sum())
    return (df.loc[w.index, cols].mul(w, axis=0)).sum()


def stock_at(stock, col, date):
    x = stock["date"].map(pd.Timestamp.toordinal).values.astype(float)
    y = stock[col].values.astype(float)
    ok = ~np.isnan(y)
    return float(np.interp(pd.Timestamp(date).toordinal(), x[ok], y[ok]))


def months_in(p: Period):
    return pd.date_range(p.start.replace(day=1), p.end, freq="MS")


def delta(cur, prev):
    """Relative change, or None when either side is missing or the comparison base is zero (works for int, float and numpy values)."""
    if cur is None or prev is None:
        return None
    try:
        if np.isnan(cur) or np.isnan(prev) or prev == 0:
            return None
    except TypeError:
        return None
    return (cur - prev) / abs(prev)


def init_state():
    ss = st.session_state
    ss.setdefault("period_preset", DEFAULT_PRESET)
    ss.setdefault("compare_mode", COMPARE_MODES[0])
    ss.setdefault("custom_start", pd.Timestamp("2025-07-01").date())
    ss.setdefault("custom_end", AS_OF.date())


def render_period_control():
    """Popover with presets, comparison mode and custom dates. Called inside the top bar."""
    pre = presets()
    cur, cmp_ = current_periods()
    with st.popover(f"📅  {cur.label}", use_container_width=True):
        st.markdown("**Reporting period**")
        st.radio("Period", list(pre) + [CUSTOM], key="period_preset", label_visibility="collapsed")
        if st.session_state.get("period_preset") == CUSTOM:
            c1, c2 = st.columns(2)
            c1.date_input("From", key="custom_start", min_value=START.date(), max_value=AS_OF.date())
            c2.date_input("To", key="custom_end", min_value=START.date(), max_value=AS_OF.date())
        st.markdown("**Compare with**")
        st.radio("Compare", COMPARE_MODES, key="compare_mode", label_visibility="collapsed")
        st.caption(f"Data as of {AS_OF:%d %b %Y} · financial year 1 Jul – 30 Jun. "
                   f"{cur.short()} ({cur.days} days)" + (f" vs {cmp_.short()}" if cmp_ else ""))
