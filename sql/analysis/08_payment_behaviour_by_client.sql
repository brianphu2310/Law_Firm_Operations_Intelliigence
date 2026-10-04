-- Payment behaviour: average days from invoice to payment per client per financial year, change vs the previous
-- year, share paid after the 30-day terms, and a client-level slow-payer quartile.
-- Only paid invoices are measured (unpaid ones are covered by the receivables-ageing query).
-- Techniques: CTEs, LAG PARTITION BY client, NTILE, PERCENT_RANK, population standard deviation from AVG(x*x) - AVG(x)^2.
WITH paid AS (
    SELECT c.client_name, d.fy_label, d.fy_start_year, i.days_to_pay, i.amount_total,
           CASE WHEN i.days_to_pay > 30 THEN 1 ELSE 0 END AS paid_late
    FROM fact_invoice i
    JOIN dim_client c ON c.client_key = i.client_key
    JOIN dim_date d   ON d.date_key = i.issue_date_key
    WHERE i.is_paid = 1 AND d.full_date >= '2023-07-01'
),
by_year AS (
    SELECT client_name, fy_label, fy_start_year, COUNT(*) AS paid_invoices, SUM(amount_total) AS paid_value,
           AVG(days_to_pay) AS avg_days, SQRT(MAX(AVG(1.0 * days_to_pay * days_to_pay) - AVG(days_to_pay) * AVG(days_to_pay), 0)) AS sd_days,
           100.0 * SUM(paid_late) / COUNT(*) AS pct_paid_late
    FROM paid GROUP BY client_name, fy_label, fy_start_year
)
SELECT client_name, fy_label, paid_invoices, ROUND(paid_value, 0) AS paid_value, ROUND(avg_days, 1) AS avg_days_to_pay,
       ROUND(sd_days, 1) AS sd_days, ROUND(pct_paid_late, 1) AS pct_paid_late,
       ROUND(avg_days - LAG(avg_days) OVER (PARTITION BY client_name ORDER BY fy_start_year), 1) AS change_vs_prior_fy_days,
       NTILE(4) OVER (PARTITION BY fy_label ORDER BY avg_days DESC) AS slow_payer_quartile,
       ROUND(PERCENT_RANK() OVER (PARTITION BY fy_label ORDER BY avg_days), 2) AS speed_percent_rank,
       RANK() OVER (PARTITION BY fy_label ORDER BY avg_days DESC) AS slowest_rank_in_fy
FROM by_year
ORDER BY fy_start_year, slowest_rank_in_fy, client_name;
