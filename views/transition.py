"""Transition: the cut-over from LEAP to triConvey (Smokeball) and from InfoTrack to TriSearch, and what it left behind.

Reads the committed snapshot in integration/snapshot/ (written by `python -m integration.quality`). All data is simulated; the dates
and the rules behind the checks are in core/transition.py and docs/TRANSITION.md, which also say what is sourced and what is assumed.
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import transition as T
from core import ui
from core.ref import AS_OF
from core.theme import AMBER, GREEN, MUTED, RED, TEAL

SNAP = Path(__file__).resolve().parent.parent / "integration" / "snapshot"
NEEDED = {"migration_recon", "matter_type_mapping_recon", "ar_migration_recon", "trust_migration_recon", "trust_r48_status",
          "supplier_disbursement_recon", "supplier_switch_summary", "migration_exceptions"}
SUPPLIER_COLOR = {"InfoTrack": "#94a3b8", "TriSearch": TEAL}


@st.cache_data(show_spinner=False)
def _load():
    return {p.stem: pd.read_csv(p) for p in SNAP.glob("*.csv")}


def _money(v):
    try:
        x = round(float(v), 2) + 0.0
        return f"${x:,.2f}".replace("$-", "-$")
    except (TypeError, ValueError):
        return "" if pd.isna(v) else str(v)


def _timeline_html(left: int):
    steps = [("Final collection", "Fri 29 Aug", "LEAP frozen, staff stop entering data", "#94a3b8"),
             ("Buffer day", "Mon 1 Sep", "weekend and Monday: entries live in neither system", AMBER),
             ("Go-live", "Tue 2 Sep", "triConvey opens, TriSearch becomes the supplier", TEAL),
             ("Today (sample data)", AS_OF.strftime("%a %-d %b"), f"{left} working day(s) left on the August trust reconciliation", RED if left <= 2 else AMBER),
             ("r48 due", T.recon_due().strftime("%a %-d %b"), "15 working days after month end", MUTED)]
    chips = []
    for i, (name, when, sub, color) in enumerate(steps):
        chips.append(f'<div style="flex:1;min-width:140px;background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid {color};border-radius:10px;padding:9px 10px">'
                     f'<div style="font-weight:800;color:#0f172a;font-size:12.5px">{name} · {when}</div>'
                     f'<div style="color:{MUTED};font-size:10.5px;margin-top:2px">{sub}</div></div>')
    return f'<div style="display:flex;gap:6px;flex-wrap:wrap">{"".join(chips)}</div>'


def render(M, cur, cmp):
    ui.page_header("Transition", "LEAP → triConvey and InfoTrack → TriSearch: what the cut-over left behind, and who has to fix it by when",
                   "Simulated cut-over")
    d = _load()
    if not NEEDED <= set(d):
        ui.note("No pipeline snapshot found. Run <code>python -m integration.extract_load</code> then <code>python -m integration.quality</code>.", "warn")
        return
    mig, types, ar, trust, r48 = d["migration_recon"], d["matter_type_mapping_recon"], d["ar_migration_recon"], d["trust_migration_recon"], d["trust_r48_status"]
    sup, summ, exc = d["supplier_disbursement_recon"], d["supplier_switch_summary"], d["migration_exceptions"]
    left = T.RECON_WORKING_DAYS - T.working_days_elapsed(AS_OF)
    r = r48.iloc[0]
    out = mig["outcome"].value_counts()
    sup_bad = sup[sup["result"] != "Matched"]
    unrecovered = float(sup.loc[sup["result"] == "On supplier feed, not in ledger", "fee_ex_gst"].sum())

    with ui.card("timeline"):
        ui.card_title("The cut-over", right="hard cut-over, no dual running")
        st.markdown(_timeline_html(left), unsafe_allow_html=True)

    ui.spacer(6)
    ui.kpi_row([
        dict(label="August trust reconciliation", value=("Does not balance" if r["statement_2_ledgers"] != "Balances" else "Balances"), label_cmp=None,
             accent=RED if r["statement_2_ledgers"] != "Balances" else GREEN, color=RED if r["statement_2_ledgers"] != "Balances" else GREEN,
             sub=f"ledgers {_money(r['ledgers_vs_cash_book'])} vs cash book · {left} working days left"),
        dict(label="Matters migrated cleanly", value=f"{int(out.get('Migrated', 0))}/{len(mig)}", label_cmp=None, accent=AMBER, color=AMBER,
             sub=f"{int(out.get('Not migrated', 0))} missing, {int(out.get('Duplicated', 0))} duplicated, "
                 f"{int(types['fell_to_general'].sum())} fell to 'General'"),
        dict(label="Open invoices migrated", value=f"{int((ar['result'] == 'Matched').sum())}/{len(ar)}", label_cmp=None, accent=AMBER, color=AMBER,
             sub=f"{_money(ar.loc[ar['result'] != 'Matched', 'difference'].sum())} net difference"),
        dict(label="Supplier orders not in the ledger", value=f"{int((sup['result'] == 'On supplier feed, not in ledger').sum())}", label_cmp=None,
             accent=RED, color=RED, sub=f"{_money(unrecovered)} ex GST at risk of never being billed"),
    ], spacer_after=6)

    tabs = st.tabs(["Trust (r48)", "Matters and invoices", "Search suppliers", "Exceptions log"])

    with tabs[0]:
        ui.note("Two statements are due 15 working days after month end (Legal Profession Uniform General Rules 2015, r48). The August one straddles "
                "both systems: LEAP to the Friday, triConvey after. The opening balances were keyed by hand in the Trust Transition session, "
                "so no vendor test migration checked them.", "")
        stmt = pd.DataFrame([
            ("Statement 1: bank → cash book", _money(r["bank_balance"]), _money(r["cash_book_balance"]),
             f"less unpresented cheques {_money(r['unpresented_cheques'])}, plus deposits not banked {_money(r['deposits_not_banked'])}",
             _money(r["bank_vs_cash_book"]), r["statement_1_bank"]),
            ("Statement 2: ledgers → cash book", _money(r["ledger_total"]), _money(r["cash_book_balance"]),
             f"{int(r['ledgers_listed'])} client ledgers listed", _money(r["ledgers_vs_cash_book"]), r["statement_2_ledgers"])],
            columns=["Statement", "Starts from", "Compared with", "Reconciling items", "Difference", "Result"])
        st.dataframe(stmt, hide_index=True, width="stretch")
        t2 = trust.copy()
        for c in ("leap_balance", "triconvey_balance", "difference"):
            t2[c] = t2[c].map(_money)
        st.dataframe(t2.rename(columns={"client_name": "Client", "leap_balance": "LEAP at the Friday freeze", "triconvey_balance": "Opening balance keyed in triConvey",
                                        "difference": "Difference", "result": "Result"}), hide_index=True, width="stretch")
        st.caption("Planted cause: a receipt posted in LEAP after the Friday extract ran never reached the hand-keyed opening balance. "
                   "A ledger that ends up below zero is a breach whatever the amount, so this has to be fixed before the reconciliation is signed.")

    with tabs[1]:
        c1, c2 = st.columns(2)
        with c1:
            with ui.card("types"):
                ui.card_title("Matter types: an unmapped type becomes 'General'", right="active matters at the freeze")
                st.dataframe(types.rename(columns={"practice_area": "LEAP practice area", "matters": "Matters", "same_type": "Same type",
                                                   "fell_to_general": "Fell to General", "result": "Result"}), hide_index=True, width="stretch")
                st.caption("The vendor's trial check samples about five matters, so a whole unmapped area can pass it. Counting every matter does not.")
        with c2:
            with ui.card("outcome"):
                ui.card_title("Matters", right=f"{len(mig)} active in LEAP")
                o = mig["outcome"].value_counts()
                fig = go.Figure(go.Bar(x=o.index, y=o.values, marker_color=[GREEN if k == "Migrated" else AMBER for k in o.index],
                                       text=o.values, textposition="outside"))
                fig.update_layout(**ui.base_layout(210))
                ui.show(ui.style_axes(fig), key="tr_matter_outcome")
        a2 = ar.copy()
        for c in ("leap_total", "triconvey_total", "difference"):
            a2[c] = a2[c].map(_money)
        with ui.card("ar"):
            ui.card_title("Open invoices at the freeze", right="migrate as one total each; paid history stays in LEAP")
            st.dataframe(a2.rename(columns={"invoice_number": "Invoice", "matter_number": "Matter", "client_name": "Client", "leap_total": "LEAP total",
                                            "triconvey_total": "triConvey total", "difference": "Difference", "result": "Result"}),
                         hide_index=True, width="stretch")

    with tabs[2]:
        ui.note("InfoTrack posts to the matter when an order completes. TriSearch charges the matter when the order is placed, and only creates "
                "the disbursement if the integration setting is on. Orders placed while LEAP was frozen and triConvey not yet open have to be re-keyed by hand.", "")
        s = summ.copy()
        s["month"] = pd.to_datetime(s["month"])
        fig = go.Figure()
        for sp in ("InfoTrack", "TriSearch"):
            g = s[s["supplier"] == sp].sort_values("month")
            fig.add_bar(x=g["month"].dt.strftime("%b %y"), y=g["orders"], name=sp, marker_color=SUPPLIER_COLOR[sp])
        fig.update_layout(barmode="stack", **ui.base_layout(230, legend=True))
        with ui.card("switch"):
            ui.card_title("Search orders by supplier", right="September is a part month (to 17 Sep)")
            ui.show(ui.style_axes(fig), key="tr_supplier_orders")
            lt = s.dropna(subset=["avg_land_title_fee"]).sort_values(["supplier", "month"]).groupby("supplier").tail(1)
            st.caption("Latest average land title search, ex GST: " + " · ".join(
                f"{x.supplier} {_money(x.avg_land_title_fee)} (service fee {_money(x.avg_land_title_service_fee)})" for x in lt.itertuples())
                + f". The NSW registry fee inside both is {_money(T.NSW_LRS_SEARCH_EX_GST)} ex GST. Supplier mark-ups are assumptions, not published prices.")
        by = sup.assign(likely_cause=sup["likely_cause"].fillna("")).groupby(["result", "likely_cause", "supplier"]).size().reset_index(name="Orders")
        by = by[by["result"] != "Matched"]
        st.dataframe(by.rename(columns={"result": "Result", "likely_cause": "Likely cause", "supplier": "Supplier"}), hide_index=True, width="stretch")
        bad = sup_bad.copy()
        bad["fee_ex_gst"] = bad["fee_ex_gst"].map(_money)
        st.dataframe(bad[["supplier", "order_id", "ordered_date", "matter_number", "service", "fee_ex_gst", "result", "likely_cause"]]
                     .rename(columns={"supplier": "Supplier", "order_id": "Order", "ordered_date": "Ordered", "matter_number": "Matter", "service": "Service",
                                      "fee_ex_gst": "Fee ex GST", "result": "Result", "likely_cause": "Likely cause"}), hide_index=True, width="stretch")
        st.caption(f"{len(sup) - len(sup_bad)} of {len(sup)} orders in the cut-over window match a ledger line one-to-one. "
                   "Two TriSearch orders carry a re-typed reference and still match after normalising it.")

    with tabs[3]:
        e = exc.copy()
        e["amount"] = e["amount"].map(lambda v: "" if pd.isna(v) else _money(v))
        kinds = e["kind"].value_counts()
        ui.kpi_row([dict(label=k, value=str(n), label_cmp=None, accent=AMBER) for k, n in kinds.items()][:6], spacer_after=6)
        st.dataframe(e.rename(columns={"kind": "Kind", "reference": "Reference", "client_name": "Client", "finding": "Finding", "amount": "Amount"}),
                     hide_index=True, width="stretch")
        ui.csv_button(exc, "cutover_exceptions", "tr_exc")
