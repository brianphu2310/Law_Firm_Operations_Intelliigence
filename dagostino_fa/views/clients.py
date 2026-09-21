"""Clients — revenue concentration, receivables and payment behaviour."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import metrics as X
from core import ui
from core.period import delta, has_data
from core.ref import AS_OF, AREAS
from core.theme import AREA_COLORS, TEAL, INDIGO, AMBER, RED, GREEN, INK, MUTED

BUCKET_COLORS = ["#86c9d1", "#fbbf24", "#f59e0b", "#ef4444", "#991b1b"]


def render(M, cur, cmp):
    ui.page_header("Clients", "Revenue, concentration, receivables and how quickly each client pays", ui.period_tag(cur, cmp))
    ct = X.client_table(M, cur, cmp)
    end = cur.end
    has_c = cmp is not None and has_data(cmp)
    lab = ui.cmp_label(cmp)
    billed = ct[ct["revenue"] > 0].sort_values("revenue", ascending=False)
    total = ct["revenue"].sum()
    prev_total = ct["prev"].sum() if has_c else None
    top5 = billed["revenue"].head(5).sum() / total if total else np.nan
    ar = X.ar_total(M, end)
    overdue = ct["overdue"].sum()
    dso = X.dso(M, end)
    dso_p = X.dso(M, cmp.end) if has_c else None
    ui.kpi_row([
        dict(label="Billed revenue (ex GST)", value=ui.fmt_money(total), d=delta(total, prev_total) if has_c else None, label_cmp=lab, accent=TEAL, spark=X.spark(M, "revenue", end)),
        dict(label="Clients billed", value=f"{len(billed)}", d=delta(len(billed), int((ct['prev'] > 0).sum())) if has_c else None, label_cmp=lab, accent=TEAL, sub=f"of {len(ct)} clients on file"),
        dict(label="Top-5 client share", value=ui.fmt_pct(top5, 0), label_cmp=None, accent=TEAL, sub=f"largest: {billed.iloc[0]['client'] if len(billed) else '—'}"),
        dict(label="Receivables (incl. GST)", value=ui.fmt_money(ar), label_cmp=None, accent=TEAL, sub=f"as of {end:%d %b %y}"),
        dict(label="Overdue receivables", value=ui.fmt_money(overdue), label_cmp=None, accent=RED, color=RED if ar and overdue / ar > 0.25 else INK, sub=f"{overdue / ar:.0%} of receivables" if ar else None),
        dict(label="DSO (90-day)", value=f"{dso:.0f} days", d=delta(dso, dso_p) if has_c else None, up_good=False, label_cmp=lab, accent=TEAL),
    ], spacer_after=6)

    tabs = st.tabs(["Client league", "Concentration", "Receivables & payment", "Client profile"])

    # ------------------------------------------------------------- league
    with tabs[0]:
        with ui.card("c1"):
            f1, f2, f3 = st.columns([1.3, 1.3, 1.6])
            areas = f1.multiselect("Practice area", AREAS, key="c_area")
            country = f2.selectbox("Country", ["All"] + sorted(ct["country"].unique()), key="c_country")
            q = f3.text_input("Search client", key="c_q")
            d = ct.copy()
            if areas: d = d[d["practice"].isin(areas)]
            if country != "All": d = d[d["country"] == country]
            if q: d = d[d["client"].str.contains(q, case=False)]
            d = d.sort_values("revenue", ascending=False)
            d["chg"] = np.where(d["prev"] > 0, (d["revenue"] - d["prev"]) / d["prev"], np.nan) if has_c else np.nan
            c1, c2 = st.columns([6, 1])
            c1.markdown(f'<div class="tbl-note">{len(d)} clients · billed {ui.fmt_money(d["revenue"].sum())} · receivables {ui.fmt_money(d["ar"].sum())}</div>', unsafe_allow_html=True)
            with c2: ui.csv_button(d, "clients", "clients")
            show = d[["client", "practice", "attorney", "country", "since", "revenue", "chg", "share", "ar", "overdue", "days_to_pay", "active_matters"]].copy()
            show[["revenue", "ar", "overdue"]] = show[["revenue", "ar", "overdue"]].round(0)
            show["days_to_pay"] = show["days_to_pay"].round(0)
            st.dataframe(show, hide_index=True, width="stretch", height=430, column_config={
                "client": st.column_config.TextColumn("Client", width=190), "practice": st.column_config.TextColumn("Practice", width=100), "attorney": st.column_config.TextColumn("Lead", width=90),
                "country": st.column_config.TextColumn("Country", width=110), "since": st.column_config.NumberColumn("Since", format="%d", width=60),
                "revenue": ui.money_col("Billed"), "chg": st.column_config.NumberColumn("Δ vs comp.", format="percent", width=85), "share": st.column_config.ProgressColumn("Share", format="percent", min_value=0, max_value=0.25, width=90),
                "ar": ui.money_col("Receivable"), "overdue": ui.money_col("Overdue"), "days_to_pay": st.column_config.NumberColumn("Days to pay", format="%d", width=85),
                "active_matters": st.column_config.NumberColumn("Active matters", format="%d", width=100)})

    # ------------------------------------------------------ concentration
    with tabs[1]:
        c1, c2 = st.columns([1.6, 1])
        with c1:
            with ui.card("c2"):
                ui.card_title("Revenue by client (Pareto)", cur.label)
                b = billed.head(15)
                cum = b["revenue"].cumsum() / total
                fig = go.Figure()
                fig.add_trace(go.Bar(x=b["client"], y=b["revenue"], marker_color=[AREA_COLORS[a] for a in b["practice"]], name="Billed",
                                     hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
                fig.add_trace(go.Scatter(x=b["client"], y=cum, yaxis="y2", name="Cumulative share", line=dict(color=INK, width=2), mode="lines+markers"))
                fig.update_layout(**ui.base_layout(300, legend=True), yaxis2=dict(overlaying="y", side="right", tickformat=".0%", range=[0, 1.02], showgrid=False, tickfont=dict(size=9)))
                fig.update_xaxes(tickangle=-35, tickfont=dict(size=9))
                ui.show(ui.style_axes(fig, "$,.0f"), key="c_pareto")
        with c2:
            with ui.card("c3"):
                ui.card_title("Revenue mix by practice area")
                g = billed.groupby("practice")["revenue"].sum().reindex(AREAS).fillna(0)
                ui.donut(list(g.index), list(g.values), [AREA_COLORS[a] for a in g.index], h=190, center=f"<b style='font-size:17px'>{ui.fmt_money(g.sum())}</b>", key="c_donut")
                leg = "".join(f'<div class="donut-legend-item" style="margin-bottom:0;"><span class="legend-dot" style="background:{AREA_COLORS[a]}"></span>{a} ({g[a] / g.sum():.0%})</div>' for a in g.index)
                st.markdown(f'<div style="display:grid; grid-template-columns:1fr 1fr; gap:3px 10px;">{leg}</div>', unsafe_allow_html=True)
        with ui.card("c4"):
            ui.card_title("Movers vs comparison period", "largest changes in billed revenue")
            if has_c:
                mv = ct.assign(diff=ct["revenue"] - ct["prev"]).sort_values("diff")
                mv = pd.concat([mv.head(6), mv.tail(6)])
                fig = go.Figure(go.Bar(y=mv["client"], x=mv["diff"], orientation="h", marker_color=[GREEN if v > 0 else RED for v in mv["diff"]], hovertemplate="%{y}: %{x:+,.0f}<extra></extra>"))
                fig.update_layout(**ui.base_layout(300))
                ui.show(ui.style_axes(fig), key="c_movers")
            else:
                st.markdown("Select a comparison period in the top bar to see movers.")

    # ----------------------------------------------- receivables & payment
    with tabs[2]:
        o, ageing = X.ar_ageing(M, end)
        c1, c2 = st.columns([1, 1.2])
        with c1:
            with ui.card("c5"):
                ui.card_title("Receivables ageing", f"at {end:%d %b %y}")
                fig = go.Figure(go.Bar(x=ageing.index.astype(str), y=ageing.values, marker_color=BUCKET_COLORS, text=[ui.fmt_money(v) for v in ageing.values], textposition="outside",
                                       hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
                fig.update_layout(**ui.base_layout(260, margin=dict(l=8, r=8, t=24, b=4)))
                ui.show(ui.style_axes(fig, "$,.0f"), key="c_ageing")
                ui.note(f"Overdue {ui.fmt_money(ageing.iloc[1:].sum())} ({ageing.iloc[1:].sum() / ageing.sum():.0%}); 60+ days late {ui.fmt_money(ageing.iloc[3:].sum())}." if ageing.sum() else "No open receivables.",
                        "warn" if ageing.sum() and ageing.iloc[3:].sum() / ageing.sum() > 0.05 else "good")
        with c2:
            with ui.card("c6"):
                ui.card_title("Payment behaviour", "days to pay (trailing 12 months) vs billed revenue; bubble = receivable")
                b = ct[ct["revenue"] > 0]
                fig = go.Figure(go.Scatter(x=b["days_to_pay"], y=b["revenue"], mode="markers+text", text=[n.split()[0] for n in b["client"]], textposition="top center", textfont=dict(size=8),
                                           marker=dict(size=np.clip(b["ar"] / 6000, 7, 40), color=[AREA_COLORS[a] for a in b["practice"]], opacity=0.75, line=dict(color="#fff", width=1)),
                                           customdata=np.c_[b["client"], b["ar"]], hovertemplate="%{customdata[0]}<br>%{x:.0f} days · billed $%{y:,.0f} · receivable $%{customdata[1]:,.0f}<extra></extra>"))
                fig.add_vline(x=30, line_dash="dot", line_color="#94a3b8", annotation_text="30-day terms", annotation_font_size=9)
                fig.update_layout(**ui.base_layout(260))
                fig.update_xaxes(title=dict(text="average days to pay", font=dict(size=10)))
                ui.show(ui.style_axes(fig, "$,.0f"), key="c_pay")
        with ui.card("c7"):
            ui.card_title("Chase list", "overdue invoices, oldest first")
            od = o[o["past_due"] > 0].sort_values("past_due", ascending=False)
            out = od[["invoice", "client", "attorney", "issue", "due", "past_due", "total"]].copy()
            out["total"] = out["total"].round(0)
            if len(out):
                st.dataframe(out, hide_index=True, width="stretch", height=min(320, 60 + 35 * len(out)), column_config={
                    "invoice": "Invoice", "client": "Client", "attorney": "Lead", "issue": st.column_config.DateColumn("Issued", format="DD MMM YY"), "due": st.column_config.DateColumn("Due", format="DD MMM YY"),
                    "past_due": st.column_config.NumberColumn("Days overdue", format="%d"), "total": ui.money_col("Amount (incl. GST)")})
            else:
                st.markdown("No overdue invoices at this date.")

    # ---------------------------------------------------------- profile
    with tabs[3]:
        with ui.card("c8"):
            name = st.selectbox("Client", list(ct.sort_values("revenue", ascending=False)["client"]), key="c_profile")
            r = ct[ct["client"] == name].iloc[0]
            inv = M["inv"]; ci = inv[inv["client"] == name]
            k = st.columns(5)
            k[0].metric("Billed in period", ui.fmt_money(r["revenue"]))
            k[1].metric("Billed since Jul 23", ui.fmt_money(r["since_start"]))
            k[2].metric("Receivable", ui.fmt_money(r["ar"]))
            k[3].metric("Days to pay", "—" if pd.isna(r["days_to_pay"]) else f"{r['days_to_pay']:.0f}")
            k[4].metric("Active matters", f"{int(r['active_matters'])}")
            st.markdown(f'<div class="tbl-note">{r["practice"]} · lead {r["attorney"]} · client since {int(r["since"])} · {r["country"]}</div>', unsafe_allow_html=True)
            m = ci.assign(month=ci["issue"].dt.to_period("M").dt.to_timestamp()).groupby("month")["ex_gst"].sum()
            fig = go.Figure(go.Bar(x=m.index, y=m.values, marker_color=AREA_COLORS[r["practice"]], hovertemplate="%{x|%b %y}: $%{y:,.0f}<extra></extra>"))
            fig.update_layout(**ui.base_layout(200)); fig.update_xaxes(tickformat="%b %y")
            ui.show(ui.style_axes(fig, "$,.0f"), key="c_prof_chart")
            mm = M["matters"]; mm = mm[(mm["client"] == name) & (mm["status"].isin(["Open", "On Hold"]))]
            out = mm[["id", "name", "attorney", "status", "opened", "est_value", "wip"]].copy(); out[["est_value", "wip"]] = out[["est_value", "wip"]].round(0)
            st.dataframe(out, hide_index=True, width="stretch", height=min(300, 60 + 35 * max(len(out), 1)), column_config={
                "id": "ID", "name": "Active matter", "attorney": "Attorney", "status": "Status", "opened": st.column_config.DateColumn("Opened", format="DD MMM YY"), "est_value": ui.money_col("Est. value"), "wip": ui.money_col("WIP")})
