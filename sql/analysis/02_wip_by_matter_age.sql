-- Work-in-progress by matter age and practice area, for matters still open or on hold at the as-of date.
-- The simulation holds WIP per matter (not per time entry), so ageing is by matter age (days open), a proxy for WIP age.
-- Techniques: CTE, CASE ageing buckets, window SUM() OVER (PARTITION BY) for share within area, running total, RANK.
WITH live AS (
    SELECT pa.practice_area, p.wip_balance, p.days_open, p.estimated_value,
           CASE WHEN p.days_open <= 90 THEN '1. 0-90 days' WHEN p.days_open <= 180 THEN '2. 91-180 days'
                WHEN p.days_open <= 365 THEN '3. 181-365 days' ELSE '4. Over 1 year' END AS age_bucket
    FROM dim_matter m
    JOIN fact_matter_position p ON p.matter_key = m.matter_key
    JOIN dim_practice_area pa   ON pa.practice_area_key = m.practice_area_key
    WHERE m.status IN ('Open', 'On Hold')
),
grid AS (
    SELECT practice_area, age_bucket, COUNT(*) AS matters, SUM(wip_balance) AS wip, SUM(estimated_value) AS estimated_value
    FROM live GROUP BY practice_area, age_bucket
)
SELECT practice_area, age_bucket, matters, ROUND(wip, 0) AS wip,
       ROUND(100.0 * wip / SUM(wip) OVER (PARTITION BY practice_area), 1) AS pct_of_area_wip,
       ROUND(100.0 * wip / SUM(wip) OVER (), 1)                          AS pct_of_firm_wip,
       ROUND(SUM(wip) OVER (PARTITION BY practice_area ORDER BY age_bucket), 0) AS running_wip_in_area,
       ROUND(wip / matters, 0)                                           AS avg_wip_per_matter,
       RANK() OVER (ORDER BY wip DESC)                                   AS wip_rank
FROM grid
ORDER BY practice_area, age_bucket;
