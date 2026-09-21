"""One dedicated evaluation dashboard per platform (LEAP, triConvey, Smokeball, Actionstep, PracticeEvolve, Clio, MyCase)."""
from dataclasses import replace
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import platforms as P
from core import ui
from core.theme import TEAL, INK, MUTED, FAINT, GREEN, RED, AMBER, BLUE, INDIGO


def _badges(name):
    return "".join(f'<span style="display:inline-block;background:{c};color:#fff;font-weight:800;font-size:11px;border-radius:7px;padding:4px 7px;margin-right:4px">{t}</span>'
                   for t, c in P.PLATFORMS[name]["badges"])


def render(M, name, cur, cmp):
    p = P.PLATFORMS[name]
    is_base = name == P.BASELINE
    base = P.base_inputs(M)

    # ---- scenario + assumptions (per platform, kept in session state) ----
    with st.expander("Scenario & assumptions", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        scen = c1.radio("Scenario", list(P.SCENARIOS), horizontal=True, key=f"scen_{name}")
        disc = c2.slider("Discount rate", 0.05, 0.20, 0.10, 0.01, format="%.2f", key=f"disc_{name}")
        ben = c3.slider("Benefit realisation", 0.0, 1.0, P.SCENARIOS[scen]["benefit_realisation"], 0.05, key=f"ben_{name}_{scen}",
                        help="Share of the assumed productivity uplift that is actually captured")
        ramp = c4.slider("Ramp-up (months)", 1, 12, 6, key=f"ramp_{name}")
        c5, c6, c7, c8 = st.columns(4)
        mig = c5.slider("Migration cost multiplier", 0.5, 2.0, P.SCENARIOS[scen]["migration_mult"], 0.05, key=f"mig_{name}_{scen}")
        vol = c6.slider("Search volume growth / yr", 0.0, 0.20, P.SCENARIOS[scen]["vol_growth"], 0.01, key=f"vol_{name}_{scen}")
        dip = c7.slider("Cut-over productivity dip", 0.0, 0.30, 0.10, 0.01, key=f"dip_{name}")
        esc = c8.slider("Extra price escalation", -0.02, 0.08, P.SCENARIOS[scen]["esc_delta"], 0.005, format="%.3f", key=f"esc_{name}_{scen}")
        ui.note("Prices, scores, migration costs and productivity uplift are illustrative sample inputs, not vendor facts. Replace them with real quotes before relying on the result.", "warn")
    inp = replace(base, discount=disc, benefit_realisation=ben, ramp_months=ramp, migration_mult=mig, vol_growth=vol, dip_pct=dip, esc_delta=esc)

    ev, cf = P.evaluate(name, inp)
    weights = st.session_state.get("crit_weights", P.DEFAULT_WEIGHTS)
    score = P.weighted_score(name, weights); base_score = P.weighted_score(P.BASELINE, weights)
    verdict, vkind = P.verdict(name, ev, score, base_score)
    rk = P.ranking(inp, weights)
    row = rk[rk["name"] == name].iloc[0]

    st.markdown(f'<div class="page-head"><div><div class="page-title">{_badges(name)}&nbsp; {name}</div><div class="page-sub">{p["tagline"]}</div></div>'
                f'<span>{ui.pill(verdict, vkind)} <span class="page-tag">Rank {int(row["rank"])} of 7 · {scen} case</span></span></div>', unsafe_allow_html=True)

    # ---- KPI row ----
    pay = "n/a" if is_base else (f"{ev['payback']} mo" if ev["payback"] else "> 36 mo")
    irr = "n/a" if is_base or ev["irr"] is None else ui.fmt_pct(min(ev["irr"], 9.99), 0)
    ui.kpi_row([
        dict(label="Annual run-cost", value=ui.fmt_money(ev["run_rate"]), label_cmp=None, accent=p["color"], sub=f"{ui.fmt_money(ev['cost_per_fee_earner'])} per fee earner"),
        dict(label="Change vs current / yr", value="—" if is_base else ui.fmt_money(ev["run_rate_delta"], sign=True), label_cmp=None, accent=p["color"],
             color=INK if is_base else (GREEN if ev["run_rate_delta"] < 0 else RED), sub="at today's prices and volumes"),
        dict(label="One-off cost", value=ui.fmt_money(ev["one_off"]), label_cmp=None, accent=p["color"], sub=f"go-live in ~{ev['go_live']} mo" if not is_base else "no migration"),
        dict(label="3-year NPV", value="—" if is_base else ui.fmt_money(ev["npv"], sign=True), label_cmp=None, accent=p["color"],
             color=INK if is_base else (GREEN if ev["npv"] > 0 else RED), sub=f"at {disc:.0%} discount rate"),
        dict(label="Payback / IRR", value=pay, label_cmp=None, accent=p["color"], sub=f"IRR {irr}"),
        dict(label="Weighted score", value=f"{score:.1f}", label_cmp=None, accent=p["color"], sub=f"current system {base_score:.1f}"),
    ], spacer_after=6)

    tabs = st.tabs(["Summary", "Cost & TCO", "Cash flow & NPV", "Scorecard", "Implementation & risk", "Sensitivity"])

    # ------------------------------------------------------------------ Summary
    with tabs[0]:
        c1, c2 = st.columns([1.15, 1])
        with c1:
            with ui.card("ps1"):
                ui.card_title("Why this verdict", "auto-generated from the model")
                bullets = []
                if is_base:
                    bullets.append(f"This is the incumbent: {ui.fmt_money(ev['run_rate'])} a year at today's volumes ({inp.searches_pm:.0f} searches a month, {inp.seats} seats).")
                    bullets.append(f"Highest reliability ({p['scores']['Reliability']}) and integration ({p['scores']['Integration']}) scores of the seven, but the weakest cost score ({p['scores']['Cost']}).")
                    bullets.append("Every other platform is measured against this cash flow, so change nothing here unless the real contract price has changed.")
                else:
                    bullets.append(f"Run-cost is {ui.fmt_money(abs(ev['run_rate_delta']))} a year {'lower' if ev['run_rate_delta'] < 0 else 'higher'} than LEAP + InfoTrack before any productivity benefit.")
                    bullets.append(f"Switching costs {ui.fmt_money(ev['one_off'])} up front (migration, cut-over dip) and about {ev['go_live']} months of running both systems.")
                    bullets.append(f"Assumed benefit is {ui.fmt_money(ev['benefit_3y'])} over three years at {ben:.0%} realisation; NPV is {ui.fmt_money(ev['npv'], sign=True)}.")
                    bullets.append(f"Weighted score {score:.1f} vs {base_score:.1f} for the current system ({score - base_score:+.1f}).")
                    if ev["npv"] > 0 and (ev["benefit_3y"] > 1.5 * abs(ev["tco_delta"]) and ev["tco_delta"] > 0):
                        bullets.append("Most of the value comes from the assumed productivity benefit, not lower fees – validate it in a trial before committing.")
                st.markdown("".join(f'<div style="display:flex;gap:8px;margin:7px 0;font-size:12.5px;color:{INK}"><span style="color:{p["color"]}">●</span><span>{b}</span></div>' for b in bullets), unsafe_allow_html=True)
        with c2:
            with ui.card("ps2"):
                ui.card_title("Profile vs current system")
                fig = go.Figure()
                cats = P.CRITERIA + [P.CRITERIA[0]]
                fig.add_trace(go.Scatterpolar(r=[P.PLATFORMS[P.BASELINE]["scores"][c] for c in cats], theta=cats, name="Current", line=dict(color="#94a3b8", dash="dot"), fill="none"))
                fig.add_trace(go.Scatterpolar(r=[p["scores"][c] for c in cats], theta=cats, name=P.SHORT[name], line=dict(color=p["color"], width=2.5), fill="toself", fillcolor=ui_rgba(p["color"], 0.18)))
                fig.update_layout(**ui.base_layout(265, legend=True, margin=dict(l=40, r=40, t=36, b=26)), polar=dict(radialaxis=dict(range=[50, 100], showticklabels=False, gridcolor="#e2e8f0"), angularaxis=dict(tickfont=dict(size=10))))
                ui.show(fig, key=f"radar_{name}")
        with ui.card("ps3"):
            ui.card_title("Head-to-head: all seven platforms", "rank uses 50% weighted score + 50% NPV")
            tbl = rk.copy()
            tbl["Verdict"] = [P.verdict(n, P.evaluate(n, inp)[0], s, base_score)[0] for n, s in zip(tbl["name"], tbl["score"])]
            out = pd.DataFrame({"Platform": tbl["name"], "Run-cost / yr": tbl["run_rate"].round(0), "Δ vs current": (tbl["run_rate"] - P.run_rate(P.BASELINE, inp)).round(0),
                                "3-yr NPV": tbl["npv"].round(0), "Payback (mo)": [("—" if n == P.BASELINE else (str(int(x)) if pd.notna(x) else "> 36")) for n, x in zip(tbl["name"], tbl["payback"])], "Score": tbl["score"], "Rank": tbl["rank"], "Verdict": tbl["Verdict"]}).sort_values("Rank")
            st.dataframe(out, hide_index=True, width="stretch", column_config={
                "Run-cost / yr": ui.money_col("Run-cost / yr"), "Δ vs current": ui.money_col("Δ vs current"), "3-yr NPV": ui.money_col("3-yr NPV"),
                "Score": st.column_config.NumberColumn("Score", format="%.1f")})

    # ---------------------------------------------------------------- Cost & TCO
    with tabs[1]:
        c1, c2 = st.columns([1.3, 1])
        yrs = [f"Year {i + 1}" for i in range(3)]
        with c1:
            with ui.card("pc1"):
                ui.card_title("Three-year cost by component", "$ nominal, incl. escalation and volume growth")
                cur_y = [cf["cur"].iloc[i * 12:(i + 1) * 12].sum() for i in range(3)]
                sub_y = [cf["sub"].iloc[i * 12:(i + 1) * 12].sum() for i in range(3)]
                sea_y = [cf["search"].iloc[i * 12:(i + 1) * 12].sum() for i in range(3)]
                ovl_y = [cf["overlap"].iloc[i * 12:(i + 1) * 12].sum() for i in range(3)]
                one_y = [cf["one_off"].iloc[i * 12:(i + 1) * 12].sum() for i in range(3)]
                fig = go.Figure()
                for lab, ys, col in [("Subscriptions", sub_y, p["color"]), ("Searches", sea_y, ui_rgba(p["color"], 0.55)), ("Parallel running", ovl_y, AMBER), ("One-off", one_y, RED)]:
                    if sum(ys) > 0:
                        fig.add_trace(go.Bar(x=yrs, y=ys, name=lab, marker_color=col, hovertemplate="%{x}: $%{y:,.0f}<extra>" + lab + "</extra>"))
                if not is_base:
                    fig.add_trace(go.Scatter(x=yrs, y=cur_y, name="Current system", mode="lines+markers", line=dict(color=INK, dash="dot"), hovertemplate="%{x}: $%{y:,.0f}<extra>Current system</extra>"))
                fig.update_layout(**ui.base_layout(270, legend=True), barmode="stack", bargap=0.35)
                ui.show(ui.style_axes(fig, "$,.0f"), key=f"tco_{name}")
        with c2:
            with ui.card("pc2"):
                ui.card_title("Unit economics")
                rows = [("Cost per fee earner / yr", ev["cost_per_fee_earner"], P.run_rate(P.BASELINE, inp) / inp.fee_earners),
                        ("Cost per search (all-in)", ev["cost_per_search"], P.PLATFORMS[P.BASELINE]["sub"] * inp.seats / inp.searches_pm + P.PLATFORMS[P.BASELINE]["fee"]),
                        ("Seat price / month", p["sub"], P.PLATFORMS[P.BASELINE]["sub"]), ("Per-search fee", p["fee"], P.PLATFORMS[P.BASELINE]["fee"]),
                        ("Price escalator / yr", p["esc"] + esc, P.PLATFORMS[P.BASELINE]["esc"] + esc)]
                html = '<table class="simple"><thead><tr><th>Metric</th><th class="num">This platform</th><th class="num">Current</th></tr></thead><tbody>'
                for lab, a, b in rows:
                    f = (lambda v: f"{v:.1%}") if "escalator" in lab else (lambda v: f"${v:,.0f}")
                    html += f'<tr><td>{lab}</td><td class="num">{f(a)}</td><td class="num">{f(b)}</td></tr>'
                st.markdown(html + "</tbody></table>", unsafe_allow_html=True)
                ui.spacer(6)
                ui.note(f"Three-year TCO: {ui.fmt_money(ev['tco_alt'])} vs {ui.fmt_money(ev['tco_cur'])} for the current system ({ui.fmt_money(ev['tco_delta'], sign=True)}).")

    # --------------------------------------------------------- Cash flow & NPV
    with tabs[2]:
        c1, c2 = st.columns(2)
        with c1:
            with ui.card("pf1"):
                ui.card_title("Cumulative net cash flow vs current system", "month 0 = contract signed")
                fig = go.Figure(go.Scatter(x=cf["t"], y=cf["cum"], mode="lines", fill="tozeroy", line=dict(color=p["color"], width=2.5), fillcolor=ui_rgba(p["color"], 0.15),
                                           hovertemplate="Month %{x}: $%{y:,.0f}<extra></extra>"))
                fig.add_hline(y=0, line_color="#94a3b8", line_width=1)
                if not is_base and ev["payback"]:
                    fig.add_vline(x=ev["payback"] - 1, line_dash="dot", line_color=GREEN, annotation_text=f"payback ~{ev['payback']} mo", annotation_font_size=10)
                fig.update_layout(**ui.base_layout(260))
                ui.show(ui.style_axes(fig, "$,.0f"), key=f"cum_{name}")
        with c2:
            with ui.card("pf2"):
                ui.card_title("NPV bridge", "three-year, discounted")
                rm = (1 + inp.discount) ** (1 / 12) - 1
                disc_ = 1 / (1 + rm) ** cf["t"]
                items = [("Productivity benefit", float((cf["benefit"] * disc_).sum())), ("Fee changes", -float(((cf["alt"] - cf["cur"]) * disc_).sum())),
                         ("Parallel running", -float((cf["overlap"] * disc_).sum())), ("One-off costs", -float((cf["one_off"] * disc_).sum()))]
                fig = go.Figure(go.Waterfall(x=[i[0] for i in items] + ["NPV"], y=[i[1] for i in items] + [0], measure=["relative"] * 4 + ["total"],
                                             increasing=dict(marker=dict(color=GREEN)), decreasing=dict(marker=dict(color=RED)), totals=dict(marker=dict(color=p["color"])),
                                             hovertemplate="%{x}: $%{y:,.0f}<extra></extra>"))
                fig.update_layout(**ui.base_layout(260))
                ui.show(ui.style_axes(fig, "$,.0f"), key=f"wf_{name}")
        with ui.card("pf3"):
            ui.card_title("Annual cash-flow table", "incremental vs current system")
            yr = pd.DataFrame({"": yrs})
            yr["Productivity benefit"] = [cf["benefit"].iloc[i * 12:(i + 1) * 12].sum() for i in range(3)]
            yr["Fee difference"] = [-(cf["alt"].iloc[i * 12:(i + 1) * 12].sum() - cf["cur"].iloc[i * 12:(i + 1) * 12].sum()) for i in range(3)]
            yr["Parallel running"] = [-cf["overlap"].iloc[i * 12:(i + 1) * 12].sum() for i in range(3)]
            yr["One-off"] = [-cf["one_off"].iloc[i * 12:(i + 1) * 12].sum() for i in range(3)]
            yr["Net"] = yr[["Productivity benefit", "Fee difference", "Parallel running", "One-off"]].sum(axis=1)
            tot = {"": "3-year total", **{c: yr[c].sum() for c in yr.columns[1:]}}
            yr = pd.concat([yr, pd.DataFrame([tot])], ignore_index=True)
            ui.render_html_table(yr, num_cols=yr.columns[1:], total_row=True, fmt={c: (lambda v: ui.fmt_money(v, sign=True)) for c in yr.columns[1:]})

    # ---------------------------------------------------------------- Scorecard
    with tabs[3]:
        c1, c2 = st.columns([1, 1.2])
        with c1:
            with ui.card("pw1"):
                ui.card_title("Criteria weights", "applies to every platform")
                w = {}
                for cn in P.CRITERIA:
                    w[cn] = st.slider(cn, 0, 50, P.DEFAULT_WEIGHTS[cn], 5, key=f"w_{cn}_{name}")
                st.session_state["crit_weights"] = w
                ui.note(f"Total weight {sum(w.values())} (normalised automatically).")
        with c2:
            with ui.card("pw2"):
                ui.card_title("Score by criterion vs current")
                fig = go.Figure()
                fig.add_trace(go.Bar(y=P.CRITERIA, x=[P.PLATFORMS[P.BASELINE]["scores"][c] for c in P.CRITERIA], orientation="h", name="Current", marker_color="#cbd5e1"))
                fig.add_trace(go.Bar(y=P.CRITERIA, x=[p["scores"][c] for c in P.CRITERIA], orientation="h", name=P.SHORT[name], marker_color=p["color"]))
                fig.update_layout(**ui.base_layout(260, legend=True), barmode="group")
                fig.update_xaxes(range=[50, 100])
                ui.show(ui.style_axes(fig), key=f"sc_{name}")
        ui.note("Scores are analyst judgements (0–100) and should be replaced by findings from demos, reference calls and a trial.")

    # ----------------------------------------------- Implementation & risk
    with tabs[4]:
        with ui.card("pi1"):
            ui.card_title("Implementation plan", f"{p['impl_weeks']} weeks" if not is_base else "no change")
            if is_base:
                st.markdown("No migration is required for the current system.")
            else:
                g = P.gantt(name)
                fig = go.Figure()
                for ph, s, e in g:
                    fig.add_trace(go.Bar(y=[ph], x=[e - s], base=[s], orientation="h", marker_color=p["color"], showlegend=False, hovertemplate=f"{ph}: week %{{base:.1f}} → %{{x:.1f}} long<extra></extra>"))
                fig.update_layout(**ui.base_layout(220)); fig.update_yaxes(autorange="reversed")
                fig.update_xaxes(title=dict(text="weeks from contract signature", font=dict(size=10)))
                ui.show(ui.style_axes(fig), key=f"gantt_{name}")
        with ui.card("pi2"):
            ui.card_title("Risk register", "probability × impact (1–5)")
            rr = P.risk_register(name)
            rr["Rating"] = np.where(rr["score"] >= 15, "High", np.where(rr["score"] >= 8, "Medium", "Low"))
            st.dataframe(rr.rename(columns={"risk": "Risk", "probability": "P", "impact": "I", "score": "Score", "mitigation": "Mitigation"})[["Risk", "P", "I", "Score", "Rating", "Mitigation"]],
                         hide_index=True, width="stretch", height=250,
                         column_config={"P": st.column_config.NumberColumn("P", width="small"), "I": st.column_config.NumberColumn("I", width="small"), "Score": st.column_config.NumberColumn("Score", width="small"),
                                        "Rating": st.column_config.TextColumn("Rating", width="small"), "Risk": st.column_config.TextColumn("Risk", width="medium"), "Mitigation": st.column_config.TextColumn("Mitigation", width="large")})

    # -------------------------------------------------------------- Sensitivity
    with tabs[5]:
        with ui.card("pz1"):
            ui.card_title("NPV sensitivity", "benefit realisation × search volume")
            if is_base:
                st.markdown("Sensitivity is measured against the current system, so it does not apply to the baseline.")
            else:
                bv = [0.0, 0.25, 0.5, 0.75, 1.0]; vm = [0.7, 0.85, 1.0, 1.15, 1.3]
                z = P.npv_grid(name, inp, bv, vm)
                fig = go.Figure(go.Heatmap(z=z, x=[f"{b:.0%}" for b in bv], y=[f"{v:.0%}" for v in vm], colorscale=[[0, "#fecaca"], [0.5, "#f8fafc"], [1, "#a7f3d0"]], zmid=0,
                                           text=[[ui.fmt_money(v) for v in r] for r in z], texttemplate="%{text}", hovertemplate="benefit %{x}, volume %{y}: %{text}<extra></extra>"))
                fig.update_layout(**ui.base_layout(300, margin=dict(l=50, r=8, t=6, b=34)))
                fig.update_xaxes(type="category", title=dict(text="benefit realisation", font=dict(size=10))); fig.update_yaxes(type="category", title=dict(text="search volume vs today", font=dict(size=10)))
                ui.show(fig, key=f"heat_{name}")
                be = next((b for b in np.linspace(0, 1, 101) if P.evaluate(name, replace(inp, benefit_realisation=b))[0]["npv"] >= 0), None)
                ui.note(f"Break-even: NPV turns positive at about {be:.0%} benefit realisation." if be is not None else "NPV stays negative even at 100% benefit realisation.", "good" if be is not None and be < 0.5 else "warn")


def ui_rgba(h, a):
    h = h.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"
