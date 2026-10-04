-- Active matter billing position (the simulated data has no per-matter cost, so matter profitability is expressed as billing
-- performance against estimated value; practice-area profitability is in query 04).
-- Active matter billing position: is each matter billed in line with its progress?
-- expected_billing = estimated value x progress. Under-billed matters (expected well above billed + WIP) are a cash-flow
-- risk; WIP-heavy matters are a billing backlog. Ranked within practice area; top 40 by WIP shown.
-- Techniques: CTE, CASE flags, RANK and PERCENT_RANK PARTITION BY area, NTILE across the firm, window SUM share.
WITH live AS (
    SELECT m.matter_id, m.matter_name, c.client_name, pa.practice_area, a.attorney_short, m.status,
           p.estimated_value, p.billed_to_date, p.wip_balance, p.progress_ratio, p.days_open,
           p.estimated_value * p.progress_ratio AS expected_billing
    FROM dim_matter m
    JOIN fact_matter_position p ON p.matter_key = m.matter_key
    JOIN dim_client c           ON c.client_key = m.client_key
    JOIN dim_practice_area pa   ON pa.practice_area_key = m.practice_area_key
    JOIN dim_attorney a         ON a.attorney_key = m.attorney_key
    WHERE m.status IN ('Open', 'On Hold')
)
SELECT matter_id, matter_name, client_name, practice_area, attorney_short, status,
       ROUND(estimated_value, 0) AS estimated_value, ROUND(100 * progress_ratio, 0) AS progress_pct,
       ROUND(billed_to_date, 0) AS billed, ROUND(wip_balance, 0) AS wip,
       ROUND(expected_billing - billed_to_date, 0) AS billing_gap,
       ROUND(100.0 * billed_to_date / NULLIF(expected_billing, 0), 0) AS billed_vs_expected_pct,
       CASE WHEN expected_billing = 0 THEN 'Not started'
            WHEN billed_to_date < 0.75 * expected_billing THEN 'Under-billed'
            WHEN billed_to_date > 1.05 * expected_billing THEN 'Billed ahead of progress' ELSE 'In line' END AS billing_flag,
       RANK() OVER (PARTITION BY practice_area ORDER BY wip_balance DESC) AS wip_rank_in_area,
       ROUND(PERCENT_RANK() OVER (PARTITION BY practice_area ORDER BY days_open), 2) AS age_percent_rank_in_area,
       NTILE(4) OVER (ORDER BY wip_balance DESC) AS wip_quartile_firm,
       ROUND(100.0 * wip_balance / SUM(wip_balance) OVER (), 2) AS pct_of_firm_wip
FROM live
ORDER BY wip_balance DESC, matter_id
LIMIT 40;
