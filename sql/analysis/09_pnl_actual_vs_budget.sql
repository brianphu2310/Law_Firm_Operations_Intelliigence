-- Monthly profit and loss: actual vs budget, variance, margin, and financial-year-to-date running totals.
-- The as-of month is pro-rated in both scenarios, so the comparison is like for like.
-- Techniques: CTEs, conditional pivot of scenario rows, window SUM running totals by FY, LAG, CASE variance flag.
WITH pivoted AS (
    SELECT d.full_date AS month_start, d.fy_label, d.fy_start_year,
           SUM(CASE WHEN s.scenario_name = 'Actual' THEN p.revenue END)          AS act_revenue,
           SUM(CASE WHEN s.scenario_name = 'Budget' THEN p.revenue END)          AS bud_revenue,
           SUM(CASE WHEN s.scenario_name = 'Actual' THEN p.total_costs END)      AS act_costs,
           SUM(CASE WHEN s.scenario_name = 'Budget' THEN p.total_costs END)      AS bud_costs,
           SUM(CASE WHEN s.scenario_name = 'Actual' THEN p.operating_profit END) AS act_profit,
           SUM(CASE WHEN s.scenario_name = 'Budget' THEN p.operating_profit END) AS bud_profit
    FROM fact_monthly_pnl p
    JOIN dim_scenario s ON s.scenario_key = p.scenario_key
    JOIN dim_date d     ON d.date_key = p.month_start_date_key
    GROUP BY d.full_date, d.fy_label, d.fy_start_year
    HAVING act_revenue IS NOT NULL
)
SELECT month_start, fy_label,
       ROUND(act_revenue, 0) AS actual_revenue, ROUND(bud_revenue, 0) AS budget_revenue,
       ROUND(act_profit, 0)  AS actual_profit,  ROUND(bud_profit, 0)  AS budget_profit,
       ROUND(100.0 * (act_revenue - bud_revenue) / bud_revenue, 1) AS revenue_var_pct,
       ROUND(100.0 * (act_profit - bud_profit) / bud_profit, 1)    AS profit_var_pct,
       ROUND(100.0 * act_profit / act_revenue, 1)                  AS actual_margin_pct,
       ROUND(100.0 * (act_revenue - LAG(act_revenue) OVER (ORDER BY month_start)) / LAG(act_revenue) OVER (ORDER BY month_start), 1) AS revenue_mom_pct,
       ROUND(SUM(act_profit) OVER (PARTITION BY fy_label ORDER BY month_start), 0) AS actual_profit_fy_ytd,
       ROUND(SUM(bud_profit) OVER (PARTITION BY fy_label ORDER BY month_start), 0) AS budget_profit_fy_ytd,
       ROUND(SUM(act_profit) OVER (PARTITION BY fy_label ORDER BY month_start) - SUM(bud_profit) OVER (PARTITION BY fy_label ORDER BY month_start), 0) AS profit_ytd_variance,
       CASE WHEN act_profit >= bud_profit THEN 'Favourable' WHEN act_profit >= 0.9 * bud_profit THEN 'Within 10%' ELSE 'Adverse' END AS profit_flag
FROM pivoted
ORDER BY month_start;
