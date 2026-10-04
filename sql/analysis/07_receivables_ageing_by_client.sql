-- Receivables ageing by client at the as-of date (invoices issued and not yet paid), bucketed by days past due.
-- Techniques: CTE with as-of lookup, JULIANDAY, conditional aggregation (pivot), RANK by overdue, share windows, CASE.
WITH asof AS (SELECT meta_value AS as_of, CAST(REPLACE(meta_value, '-', '') AS INTEGER) AS as_of_key FROM etl_meta WHERE meta_key = 'as_of_date'),
open_inv AS (
    SELECT c.client_name, i.invoice_number, i.amount_total,
           CAST(julianday(a.as_of) - julianday(dd.full_date) AS INTEGER) AS days_past_due
    FROM fact_invoice i
    JOIN dim_client c ON c.client_key = i.client_key
    JOIN dim_date dd  ON dd.date_key = i.due_date_key
    CROSS JOIN asof a
    WHERE i.issue_date_key <= a.as_of_key AND (i.paid_date_key IS NULL OR i.paid_date_key > a.as_of_key)
),
by_client AS (
    SELECT client_name, COUNT(*) AS open_invoices, SUM(amount_total) AS ar_total,
           SUM(CASE WHEN days_past_due <= 0  THEN amount_total ELSE 0 END) AS not_yet_due,
           SUM(CASE WHEN days_past_due BETWEEN 1 AND 30  THEN amount_total ELSE 0 END) AS due_1_30,
           SUM(CASE WHEN days_past_due BETWEEN 31 AND 60 THEN amount_total ELSE 0 END) AS due_31_60,
           SUM(CASE WHEN days_past_due BETWEEN 61 AND 90 THEN amount_total ELSE 0 END) AS due_61_90,
           SUM(CASE WHEN days_past_due > 90 THEN amount_total ELSE 0 END)              AS due_90_plus,
           MAX(days_past_due) AS max_days_past_due
    FROM open_inv GROUP BY client_name
)
SELECT client_name, open_invoices, ROUND(ar_total, 0) AS ar_incl_gst, ROUND(not_yet_due, 0) AS not_yet_due,
       ROUND(due_1_30, 0) AS days_1_30, ROUND(due_31_60, 0) AS days_31_60, ROUND(due_61_90, 0) AS days_61_90, ROUND(due_90_plus, 0) AS days_90_plus,
       max_days_past_due,
       ROUND(100.0 * (ar_total - not_yet_due) / ar_total, 1) AS pct_overdue,
       ROUND(100.0 * ar_total / SUM(ar_total) OVER (), 1) AS pct_of_firm_ar,
       RANK() OVER (ORDER BY (ar_total - not_yet_due) DESC) AS overdue_rank,
       CASE WHEN due_61_90 + due_90_plus > 0 THEN 'Escalate' WHEN due_1_30 + due_31_60 > 0 THEN 'Chase' ELSE 'Monitor' END AS collections_action
FROM by_client
ORDER BY overdue_rank, client_name;
