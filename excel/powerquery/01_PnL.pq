// Query name: PnL  ->  load to the "PnL" sheet as table tblPnL
// Monthly actual vs budget profit (sql/analysis/09_pnl_actual_vs_budget.sql).
let
    Source = fnQueryResult("docs/query_results", "09_pnl_actual_vs_budget"),
    Typed  = Table.TransformColumnTypes(Source, {
                 {"month_start", type date}, {"fy_label", type text},
                 {"actual_revenue", Currency.Type}, {"budget_revenue", Currency.Type}, {"actual_profit", Currency.Type}, {"budget_profit", Currency.Type},
                 {"revenue_var_pct", type number}, {"profit_var_pct", type number}, {"actual_margin_pct", type number}, {"revenue_mom_pct", type number},
                 {"actual_profit_fy_ytd", Currency.Type}, {"budget_profit_fy_ytd", Currency.Type}, {"profit_ytd_variance", Currency.Type}, {"profit_flag", type text}},
                 "en-AU")
in
    Typed
