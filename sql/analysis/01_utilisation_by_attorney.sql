-- Fee-earner utilisation (billable hours / capacity hours) by month, with rank within the month, month-on-month change
-- and a 3-month moving average. Months are pro-rated for the as-of month, so ratios are comparable.
-- Techniques: CTE, date dimension join, RANK() PARTITION BY month, LAG, AVG over ROWS frame, PERCENT_RANK.
WITH monthly AS (
    SELECT d.full_date AS month_start, d.fy_label, a.attorney_name, a.role, b.branch_name,
           m.billable_hours, m.capacity_hours,
           1.0 * m.billable_hours / m.capacity_hours AS utilisation
    FROM fact_attorney_month m
    JOIN dim_attorney a ON a.attorney_key = m.attorney_key
    JOIN dim_branch b   ON b.branch_key = a.home_branch_key
    JOIN dim_date d     ON d.date_key = m.month_start_date_key
)
SELECT month_start, fy_label, attorney_name, role, branch_name,
       ROUND(billable_hours, 1) AS billable_hours, ROUND(capacity_hours, 1) AS capacity_hours,
       ROUND(100 * utilisation, 1) AS utilisation_pct,
       RANK() OVER (PARTITION BY month_start ORDER BY utilisation DESC) AS rank_in_month,
       ROUND(100 * (utilisation - LAG(utilisation) OVER (PARTITION BY attorney_name ORDER BY month_start)), 1) AS mom_change_pct_pts,
       ROUND(100 * AVG(utilisation) OVER (PARTITION BY attorney_name ORDER BY month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS moving_avg_3m_pct,
       ROUND(PERCENT_RANK() OVER (PARTITION BY month_start ORDER BY utilisation), 2) AS percent_rank_in_month,
       CASE WHEN utilisation >= 1.0 THEN 'At / over target' WHEN utilisation >= 0.8 THEN 'Healthy (80-100%)'
            WHEN utilisation >= 0.6 THEN 'Below target' ELSE 'Under-utilised' END AS band
FROM monthly
ORDER BY month_start, rank_in_month, attorney_name;
