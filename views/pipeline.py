"""Pipeline: the MYOB -> n8n -> Snowflake integration layer, its load audit, data-quality checks and reconciliation to this app.

Reads the committed snapshot in integration/snapshot/ (written by `python -m integration.quality`), so the page works on
Streamlit Cloud without a warehouse connection. All data is simulated.
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import ui
from core.theme import AMBER, GREEN, MUTED, RED, TEAL

SNAP = Path(__file__).resolve().parent.parent / "integration" / "snapshot"
BUCKETS = ["Not yet due", "1–30 days", "31–60 days", "61–90 days", "90+ days"]
BUCKET_COLORS = ["#86c9d1", "#fbbf24", "#f59e0b", "#ef4444", "#991b1b"]
STAGES = [("5 source APIs", "MYOB · LEAP · triConvey · InfoTrack · PEXA"), ("n8n + OAuth", "daily 6am, incremental, Auth0 JWT"), ("Snowflake RAW", "VARIANT + load audit"),
          ("STAGING", "LATERAL FLATTEN, de-dup"), ("MARTS", "revenue, ageing, collections"),
          ("Consumers", "Excel + Power Query · Streamlit")]


@st.cache_data(show_spinner=False)
def _load():
    return {p.stem: pd.read_csv(p) for p in SNAP.glob("*.csv")}


def _money_or_text(v):
    """Reconciliation cells hold dollars or a date: show dollars to the cent, anything else as text."""
    try:
        x = round(float(v), 2) + 0.0                     # + 0.0 turns -0.0 into 0.0, so no "-$0.00"
        return f"${x:,.2f}".replace("$-", "-$")
    except (TypeError, ValueError):
        return str(v)


def _flow_html():
    chips = []
    for i, (name, sub) in enumerate(STAGES):
        chips.append(f'<div style="flex:1;min-width:120px;background:#ecfeff;border:1px solid #a5e3ea;border-radius:10px;padding:9px 10px">'
                     f'<div style="font-weight:800;color:{TEAL};font-size:12.5px">{name}</div>'
                     f'<div style="color:{MUTED};font-size:10.5px;margin-top:2px">{sub}</div></div>')
        if i < len(STAGES) - 1:
            chips.append(f'<div style="align-self:center;color:{TEAL};font-weight:800">→</div>')
    return f'<div style="display:flex;gap:6px;flex-wrap:wrap">{"".join(chips)}</div>'


def render(M, cur, cmp):
    ui.page_header("Data pipeline", "Accounting, practice-management, search and settlement data through n8n into Snowflake, checked and reconciled",
                   "Simulated source data")
    d = _load()
    if not {"load_audit", "quality_checks", "reconciliation", "aged_receivables", "collection_performance"} <= set(d):
        ui.note("No pipeline snapshot found. Run <code>python -m integration.extract_load</code> then <code>python -m integration.quality</code>.", "warn")
        return
    audit, checks, rec = d["load_audit"], d["quality_checks"], d["reconciliation"]
    aged, coll = d["aged_receivables"], d["collection_performance"]
    last = audit[audit["loaded_at"] == audit["loaded_at"].max()]
    ok_res = int((last["status"] == "OK").sum())
    n_checks, n_pass = len(checks), int(checks["passed"].astype(bool).sum())
    r_pass = int(rec["passed"].astype(bool).sum())
    ar = float(aged["balance_due"].sum())
    ar_row = rec[rec["check"] == "Receivables incl. GST"]
    ar_app = float(ar_row["app"].iloc[0]) if len(ar_row) else None
    ui.kpi_row([
        dict(label="Last load", value=pd.Timestamp(last["loaded_at"].iloc[0]).strftime("%d %b %y"), label_cmp=None, accent=TEAL,
             sub=f"{ok_res} of {len(last)} resources OK"),
        dict(label="Records loaded", value=f"{int(audit['loaded_count'].sum()):,}", label_cmp=None, accent=TEAL, sub="across all batches"),
        dict(label="Quality checks", value=f"{n_pass}/{n_checks}", label_cmp=None, accent=GREEN if n_pass == n_checks else RED,
             color=GREEN if n_pass == n_checks else RED, sub="accounting integrity"),
        dict(label="Reconciled to app", value=f"{r_pass}/{len(rec)}", label_cmp=None, accent=GREEN if r_pass == len(rec) else RED,
             color=GREEN if r_pass == len(rec) else RED, sub="receivables, ageing, revenue"),
        dict(label="Receivables (pipeline)", value=ui.fmt_money(ar), label_cmp=None, accent=TEAL,
             sub=f"app {ui.fmt_money(ar_app)} · as at {aged['as_at'].iloc[0]}" if ar_app is not None and len(aged) else None),
    ], spacer_after=6)

    with ui.card("flow"):
        ui.card_title("How the data flows", right="every stage is in integration/")
        st.markdown(_flow_html(), unsafe_allow_html=True)
        ui.spacer(6)
        ui.note("All five systems are <b>simulated</b> from this app's own model, each served by a mock API with its own paging style "
                "(MYOB OData, LEAP pages, Smokeball offset/limit, InfoTrack page numbers, PEXA cursors) behind OAuth 2.0. "
                "Switching a source to its live API changes configuration, not code.", "")

    tabs = st.tabs(["Reconciliation", "Cross-system", "Migration dry run", "Data quality", "Load audit", "Receivables by age",
                    "Collections by practice area"])
    with tabs[0]:
        t = rec.copy()
        for c in ("app", "pipeline", "difference"):
            t[c] = t[c].map(_money_or_text)
        t["Result"] = t["passed"].map({True: "✅ PASS", False: "❌ FAIL", "True": "✅ PASS", "False": "❌ FAIL"})
        st.dataframe(t.drop(columns="passed").rename(columns={"check": "Check", "app": "App (core.model)", "pipeline": "Pipeline (marts)",
                                                              "difference": "Difference"}), hide_index=True, width="stretch")
        st.caption("Differences are cent rounding: the MYOB export rounds each invoice to the cent, the app keeps full precision.")
    with tabs[1]:
        sync = d.get("invoice_sync_recon")
        disb = d.get("disbursements_by_matter")
        if sync is not None:
            res = sync["result"].value_counts()
            ui.kpi_row([
                dict(label="LEAP → MYOB invoices matched", value=f"{int(res.get('Matched', 0))}/{len(sync)}", label_cmp=None,
                     accent=GREEN if res.get("Matched", 0) == len(sync) else RED, sub="number and total incl. GST"),
                dict(label="InfoTrack + PEXA disbursements", value=ui.fmt_money(float(disb["total_disbursements"].sum())) if disb is not None else "—",
                     label_cmp=None, accent=TEAL, sub=f"{len(disb)} matters, every order linked to a LEAP matter" if disb is not None else None),
            ], spacer_after=6)
        if disb is not None:
            st.dataframe(disb.sort_values("total_disbursements", ascending=False).head(25), hide_index=True, width="stretch",
                         column_config={"search_fees": ui.money_col("InfoTrack fees", "$%,.2f"), "pexa_fees": ui.money_col("PEXA fees", "$%,.2f"),
                                        "total_disbursements": ui.money_col("Total", "$%,.2f")})
            st.caption("Top 25 matters by search and settlement disbursements, ex GST.")
    with tabs[2]:
        mig, exc = d.get("migration_recon"), d.get("migration_exceptions")
        if mig is not None:
            out = mig["outcome"].value_counts()
            ui.kpi_row([
                dict(label="Active LEAP matters", value=f"{int((mig['outcome'] != 'Unexpected in triConvey').sum())}", label_cmp=None, accent=TEAL),
                dict(label="Migrated once", value=f"{int(out.get('Migrated', 0))}", label_cmp=None, accent=GREEN),
                dict(label="Findings for cut-over log", value=f"{len(exc) if exc is not None else 0}", label_cmp=None, accent=AMBER, color=AMBER),
            ], spacer_after=6)
        ui.note("LEAP is the source of truth; triConvey is a migration rehearsal. These findings are what the reconciliation caught "
                "and would go on the cut-over issues log before go-live.", "warn")
        if exc is not None:
            e = exc.copy()
            e["amount"] = e["amount"].map(lambda v: "" if pd.isna(v) else _money_or_text(v))
            st.dataframe(e.rename(columns={"kind": "Kind", "reference": "Reference", "client_name": "Client", "finding": "Finding", "amount": "Amount"}),
                         hide_index=True, width="stretch")
        tm = d.get("trust_migration_recon")
        if tm is not None:
            t2 = tm.copy()
            for c in ("leap_balance", "triconvey_balance", "difference"):
                t2[c] = t2[c].map(_money_or_text)
            st.dataframe(t2.rename(columns={"client_name": "Client", "leap_balance": "LEAP balance", "triconvey_balance": "triConvey balance",
                                            "difference": "Difference", "result": "Result"}), hide_index=True, width="stretch")
    with tabs[3]:
        t = checks.copy()
        t["Result"] = t["passed"].map({True: "✅ PASS", False: "❌ FAIL", "True": "✅ PASS", "False": "❌ FAIL"})
        st.dataframe(t.drop(columns="passed").rename(columns={"check": "Check", "failures": "Failing rows"}), hide_index=True, width="stretch")
    with tabs[4]:
        st.dataframe(audit.sort_values("loaded_at", ascending=False), hide_index=True, width="stretch")
        st.caption("api_count is the MYOB response's Count; a run fails if any resource loads a different number of rows.")
    with tabs[5]:
        b = aged.groupby("ageing_bucket")["balance_due"].sum().reindex(BUCKETS).fillna(0)
        fig = go.Figure(go.Bar(x=b.index, y=b.values, marker_color=BUCKET_COLORS, text=[ui.fmt_money(v) for v in b.values], textposition="outside",
                               hovertemplate="%{x}: %{y:$,.0f}<extra></extra>"))
        fig.update_layout(**ui.base_layout(260))
        ui.show(ui.style_axes(fig, y_fmt="$,.0f"), key="pipe_ageing")
        st.dataframe(aged.sort_values("days_past_due", ascending=False), hide_index=True, width="stretch",
                     column_config={"balance_due": ui.money_col("Balance due", "$%,.2f")})
    with tabs[6]:
        st.dataframe(coll.sort_values("avg_days_to_pay", ascending=False), hide_index=True, width="stretch",
                     column_config={"outstanding": ui.money_col("Outstanding"), "pct_paid_on_time": st.column_config.NumberColumn("% paid on time", format="%.1f%%")})
        ui.csv_button(coll, "collection_performance", "pipe_coll")
