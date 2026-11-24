# Power BI report

The project's front end: the whole dashboard and the Decision Simulator as a Power BI project, 22 pages (15 report pages plus one per platform), about 295 DAX measures,
one semantic model over the warehouse. It lives in `powerbi/` as a **Power BI Project (.pbip)**: plain text files
(TMDL for the model, PBIR JSON for the report) that Git can diff and CI can test.

## Preview without Power BI

`powerbi/demo/index.html` is a browser preview of the same 22 pages: positions, titles and fields come from the report's own
PBIR files, and every number is computed in Python the way the DAX measures compute it (`python -m powerbi.demo`). Page
navigation, the Period slicer and the Platform slicer work, and so does the whole Simulator: presets, every lever and the
goal-seek target. The browser runs the Simulator from the same formula spec that generates the DAX (`powerbi/sim_spec.py`,
translated to JavaScript), and gives the same results as the Python engine for every preset. Other filters (status, area,
office) work only in Power BI.

## Open it

1. Install **Power BI Desktop** (Windows, free, latest version).
2. Open `powerbi/LawFirmDecisionSupport.pbip`.
3. On first open choose **Refresh**; if asked how to connect to `raw.githubusercontent.com`, pick **Anonymous** and privacy
   level **Public**.

Data loads from the CSVs in this GitHub repository (`data/warehouse` and `data/powerbi`) through the `BaseUrl` parameter.
To load from a fork or another branch: *Transform data → Edit parameters → BaseUrl*.

## Pages

| Section | Pages | What it answers |
|---|---|---|
| Overview | 1 | KPIs vs prior period, intake funnel, hours and revenue by area, trust/WIP/receivables, decisions to make |
| Finance | P&L & outlook · Cash & billing · Trust & costs | P&L vs budget, FY26 outlook, 13-week cash, receivables ageing, DSO, lock-up, trust, supplier and card spend |
| People | Performance · Hiring & departments · Branches & pay | Fee-earner utilisation and contribution, where to hire, support staff vs workload, office profit, cost of a pay review |
| Matters | 1 | Matter ledger with filters, opened vs closed, WIP by age |
| Clients | Clients · Marketing | Client league, concentration, payment behaviour, cost per new matter by channel |
| Calendar | 1 | Agenda and workload by lawyer |
| Platforms | 7 (one per platform, in the sidebar) | Verdict, NPV, payback and cost of the platform; ranking, NPV, cumulative cash flow, scorecard, risks, implementation plan, NPV sensitivity |
| Simulator | Decide · Test the plan | 12 presets + 30 levers; profit bridge, effects and cash, what moves profit most, what it would take, delivery range, presets side by side |
| Check | 1 | Assumptions, and every Simulator result in DAX compared with the Python engine |

A dark **sidebar** on every page lists the pages and the seven platform + search combinations (one page each). On the Overview each question has the chart that fits its answer: a ranking (software), a gauge against the minimum cash balance (branch), columns (hiring), a diverging bar (support staff), a line (pay) and a treemap of new matters per $1,000 (growth). The **Period** slicer (top right, synced across pages) picks the reporting period, with the same periods and day weights as the Python model.

## How it is built

```
python -m powerbi.build        # data/powerbi/*.csv, then the .pbip project
```

* `powerbi/exports.py` writes the analysis tables Power BI reads next to the warehouse: reporting periods and their
  month weights, period-end balances, decision tables, cash forecast, FY outlook, platform evaluation, and the Simulator's
  expected results.
* `powerbi/model.py` writes the semantic model: 45 tables loaded from CSV with Power Query, 37 relationships, the
  descriptive DAX measures (period sums use the same day weights as the Python app), and the Simulator tables.
* `powerbi/sim_spec.py` holds the Simulator as one formula spec. The same spec is **translated to DAX** (one measure per
  output, a chain of VARs) and **evaluated in Python**. `tests/test_powerbi.py` checks the Python evaluation against
  `core/simulate.py` for every preset and 300 random lever mixes; the report's **Check** page runs the DAX against the same
  expected numbers when you open it.
* `powerbi/report.py` writes the pages and visuals. Every JSON file is validated against Microsoft's published PBIR schemas,
  and every field and DAX reference is checked against the model.

## How the Simulator works in DAX

* Each lever is a disconnected table shown as a dropdown slicer. A slicer left empty takes the preset's value; picking a
  value overrides it. The preset bar sets every lever at once.
* Goal seek ("what would it take") evaluates profit over the lever's grid with `CALCULATE` + `TREATAS` and keeps the
  first value that hits the target. The pay-review funding rate is found to 0.01%.
* "How sure are we" re-runs the scenario with 75% and 50% of the improvements delivered; "every preset side by side"
  evaluates each preset row in its own filter context.

## Known limits

* Lever slicers are dropdowns, not sliders, and show empty until you change them (the card "Levers in this scenario"
  lists what is switched on).
* Saved scenarios are not available (report viewers cannot save state); use the presets side by side instead.
* Not yet opened in Power BI Desktop by the author of this build: the files are validated against the schemas, not
  against a running Power BI. Report any error with the page and visual name.

## Matters map

`Matters · Map` (a sub-tab of Matters) answers the "where" half of the branch question:

- **Where clients come from**: Australian matters opened in the last 12 months by client suburb, coloured by the distance to the
  nearest office (under 5 km, 5–10 km, over 10 km). The Overview shows the same demand in Power BI's default map look (road
  map, one bubble colour, size = matters), next to the profit trend.
- **Where a new branch would help most**: for every suburb, the matters from clients more than 10 km from every office that a new office
  there would bring within 10 km (`core/catchment.py`, the same rules as `sql/analysis/14_branch_site.sql`; a test checks they agree).
- Matters by client country, and the distance bands as a column chart.

Client suburbs are **sample data**: each Australian matter's suburb is drawn by an indicative population and by distance from the office
that handles it, so the result shows how the analysis works, not a real market study.

The catchment maps are **scatter charts over a static basemap image** (longitude on X, latitude on Y, axes pinned to the image's
extent), not Power BI map visuals. The Bing Map visual is being retired and shows a banner saying so, its Azure Maps replacement
came up blank, and both depend on map services an organisation can switch off. The scatter version needs no map service, so it
works on any tenant, in PDF exports and in Publish to web. `python -m powerbi.mapimage` redraws the images
(`powerbi/assets/maps/`: Natural Earth coastline, today's offices and the best site) when the suburbs or offices change; the
build only copies them. The client-country map is still a Power BI map visual. The browser preview draws the same maps itself.