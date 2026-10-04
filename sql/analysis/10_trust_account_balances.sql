-- Client trust-account balances over the last 12 months: month-on-month movement, share of total trust money,
-- trailing 12-month range and a rank. Trust money is held for clients (not firm revenue); monitoring it is a core
-- legal-practice control.
-- Techniques: CTE, LAG, AVG/MIN/MAX over ROWS frames, share-of-total window, RANK PARTITION BY month, filter after windowing.
WITH bal AS (
    SELECT c.client_name, d.full_date AS month_start, b.closing_balance
    FROM fact_trust_balance b
    JOIN dim_client c ON c.client_key = b.client_key
    JOIN dim_date d   ON d.date_key = b.month_start_date_key
),
windowed AS (
    SELECT client_name, month_start, closing_balance,
           closing_balance - LAG(closing_balance) OVER (PARTITION BY client_name ORDER BY month_start) AS mom_change,
           AVG(closing_balance) OVER (PARTITION BY client_name ORDER BY month_start ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS avg_3m,
           MIN(closing_balance) OVER (PARTITION BY client_name ORDER BY month_start ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS min_12m,
           MAX(closing_balance) OVER (PARTITION BY client_name ORDER BY month_start ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS max_12m,
           100.0 * closing_balance / SUM(closing_balance) OVER (PARTITION BY month_start) AS pct_of_trust,
           RANK() OVER (PARTITION BY month_start ORDER BY closing_balance DESC) AS balance_rank,
           SUM(closing_balance) OVER (PARTITION BY month_start) AS total_trust
    FROM bal
)
SELECT month_start, client_name, ROUND(closing_balance, 0) AS closing_balance, ROUND(mom_change, 0) AS mom_change,
       ROUND(100.0 * mom_change / (closing_balance - mom_change), 1) AS mom_change_pct,
       ROUND(avg_3m, 0) AS avg_3m, ROUND(min_12m, 0) AS min_12m, ROUND(max_12m, 0) AS max_12m,
       ROUND(pct_of_trust, 1) AS pct_of_trust, balance_rank, ROUND(total_trust, 0) AS total_trust,
       CASE WHEN closing_balance < 0.7 * max_12m THEN 'Well below 12m peak' WHEN closing_balance > 1.2 * avg_3m THEN 'Rising' ELSE 'Stable' END AS trend_flag
FROM windowed
WHERE month_start >= (SELECT date(MAX(month_start), '-11 months') FROM bal)
ORDER BY month_start, balance_rank;
