-- Realisation = fees billed / standard value of time recorded. Monthly trend vs budget, write-off rate, 3-month average
-- and financial-year-to-date realisation. (Pro-rated current month: ratios are unaffected by pro-rating.)
-- Techniques: CTEs, conditional pivot of scenarios, LAG, ROWS-frame moving average, running SUM by FY (ratio of sums).
WITH pnl AS (
    SELECT d.full_date AS month_start, d.fy_label, d.fy_start_year,
           SUM(CASE WHEN s.scenario_name = 'Actual' THEN p.fees END)           AS actual_fees,
           SUM(CASE WHEN s.scenario_name = 'Actual' THEN p.standard_value END) AS actual_value,
           SUM(CASE WHEN s.scenario_name = 'Actual' THEN p.writeoff END)       AS actual_writeoff,
           SUM(CASE WHEN s.scenario_name = 'Budget' THEN p.fees END)           AS budget_fees,
           SUM(CASE WHEN s.scenario_name = 'Budget' THEN p.standard_value END) AS budget_value
    FROM fact_monthly_pnl p
    JOIN dim_scenario s ON s.scenario_key = p.scenario_key
    JOIN dim_date d     ON d.date_key = p.month_start_date_key
    GROUP BY d.full_date, d.fy_label, d.fy_start_year
    HAVING actual_fees IS NOT NULL
)
SELECT month_start, fy_label, ROUND(actual_value, 0) AS standard_value, ROUND(actual_fees, 0) AS fees_billed,
       ROUND(100.0 * actual_fees / actual_value, 1)        AS realisation_pct,
       ROUND(100.0 * budget_fees / budget_value, 1)        AS budget_realisation_pct,
       ROUND(100.0 * (actual_fees / actual_value - budget_fees / budget_value), 1) AS vs_budget_pct_pts,
       ROUND(100.0 * actual_writeoff / actual_value, 1)    AS writeoff_pct_of_value,
       ROUND(100.0 * (actual_fees / actual_value - LAG(actual_fees / actual_value) OVER (ORDER BY month_start)), 1) AS mom_change_pct_pts,
       ROUND(100.0 * SUM(actual_fees) OVER (ORDER BY month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
                   / SUM(actual_value) OVER (ORDER BY month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS rolling_3m_realisation_pct,
       ROUND(100.0 * SUM(actual_fees) OVER (PARTITION BY fy_label ORDER BY month_start)
                   / SUM(actual_value) OVER (PARTITION BY fy_label ORDER BY month_start), 1) AS fy_ytd_realisation_pct
FROM pnl
ORDER BY month_start;
