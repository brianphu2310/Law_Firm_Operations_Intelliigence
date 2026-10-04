-- Client concentration: share of the last 12 months' invoiced fees (ex-GST), cumulative share, and the
-- Herfindahl-Hirschman index (HHI, 0-10,000; above 2,500 is conventionally "highly concentrated").
-- Techniques: CTEs, scalar as-of lookup, RANK, running SUM over an ordered window, window SUM for totals, CASE tiers.
WITH asof AS (SELECT meta_value AS as_of FROM etl_meta WHERE meta_key = 'as_of_date'),
rev AS (
    SELECT c.client_name, pa.practice_area AS primary_practice_area, c.country, SUM(i.amount_ex_gst) AS fees_12m, COUNT(*) AS invoices
    FROM fact_invoice i
    JOIN dim_client c         ON c.client_key = i.client_key
    JOIN dim_practice_area pa ON pa.practice_area_key = c.primary_practice_area_key
    JOIN dim_date d           ON d.date_key = i.issue_date_key
    CROSS JOIN asof a
    WHERE d.full_date > date(a.as_of, '-12 months') AND d.full_date <= a.as_of
    GROUP BY c.client_name, pa.practice_area, c.country
),
ranked AS (
    SELECT r.*, 1.0 * fees_12m / SUM(fees_12m) OVER () AS share,
           RANK() OVER (ORDER BY fees_12m DESC) AS client_rank,
           SUM(fees_12m) OVER (ORDER BY fees_12m DESC, client_name ROWS UNBOUNDED PRECEDING) AS running_fees
    FROM rev r
)
SELECT client_rank, client_name, primary_practice_area, country, invoices, ROUND(fees_12m, 0) AS fees_12m,
       ROUND(100 * share, 1) AS pct_of_fees,
       ROUND(100.0 * running_fees / SUM(fees_12m) OVER (), 1) AS cumulative_pct,
       ROUND(10000 * SUM(share * share) OVER (), 0) AS firm_hhi,
       CASE WHEN share >= 0.15 THEN 'Key client (15%+)' WHEN share >= 0.07 THEN 'Major (7-15%)' ELSE 'Standard' END AS tier
FROM ranked
ORDER BY client_rank, client_name;
