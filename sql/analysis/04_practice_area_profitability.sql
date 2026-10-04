-- Practice-area profitability by financial year: fees less fee-earner salary cost allocated by hours share.
-- Allocation rule: an attorney's monthly salary cost (capacity hours x pay rate x wage index) is split across practice
-- areas in proportion to the hours they recorded there that month (see docs/DATA_DICTIONARY.md). Overheads are not allocated.
-- Techniques: CTEs, RANK within FY, LAG across FYs, share-of-total windows, CASE.
WITH area_fy AS (
    SELECT d.fy_label, d.fy_start_year, pa.practice_area,
           SUM(t.billable_hours) AS hours, SUM(t.standard_value) AS standard_value, SUM(t.fees_realised) AS fees,
           SUM(t.allocated_salary_cost) AS salary_cost
    FROM fact_time_by_area t
    JOIN dim_practice_area pa ON pa.practice_area_key = t.practice_area_key
    JOIN dim_date d           ON d.date_key = t.month_start_date_key
    GROUP BY d.fy_label, d.fy_start_year, pa.practice_area
),
calc AS (
    SELECT *, fees - salary_cost AS contribution,
           (fees - salary_cost) / fees AS margin,
           fees / hours AS effective_rate,
           fees / standard_value AS realisation
    FROM area_fy
)
SELECT fy_label, practice_area, ROUND(hours, 0) AS hours, ROUND(fees, 0) AS fees, ROUND(salary_cost, 0) AS allocated_salary,
       ROUND(contribution, 0) AS contribution, ROUND(100 * margin, 1) AS contribution_margin_pct,
       ROUND(effective_rate, 0) AS effective_rate_per_hour, ROUND(100 * realisation, 1) AS realisation_pct,
       ROUND(100.0 * fees / SUM(fees) OVER (PARTITION BY fy_label), 1) AS pct_of_fy_fees,
       RANK() OVER (PARTITION BY fy_label ORDER BY margin DESC) AS margin_rank_in_fy,
       ROUND(100 * (margin - LAG(margin) OVER (PARTITION BY practice_area ORDER BY fy_start_year)), 1) AS margin_change_vs_prior_fy_pts,
       CASE WHEN margin >= 0.45 THEN 'Strong' WHEN margin >= 0.30 THEN 'Moderate' ELSE 'Thin' END AS margin_band
FROM calc
ORDER BY fy_start_year, margin_rank_in_fy;
