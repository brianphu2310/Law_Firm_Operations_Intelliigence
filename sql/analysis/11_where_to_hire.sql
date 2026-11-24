-- Where to hire: demand, pressure and margin by practice area over the last 12 months (the Principal's hiring question).
-- pressure  = utilisation of the lawyers already doing the area's work, weighted by their hours in it;
-- demand    = growth in matters opened vs the 12 months before; margin = fees less allocated fee-earner salary.
-- priority  = 40% pressure + 35% demand growth + 25% margin, each min-max scaled 0-100 across areas (same rule as the app).
-- Techniques: CTEs, date arithmetic for a rolling window with a partial first month, weighted averages, MIN/MAX windows, RANK, CASE.
WITH asof AS (
    SELECT date(meta_value) AS as_of, date(meta_value, '-1 year', '+1 day') AS ltm_start, date(meta_value, '-2 years', '+1 day') AS prior_start
    FROM etl_meta WHERE meta_key = 'as_of_date'
),
w AS (      -- weight of each month inside the window: the first month counts only from the window start
    SELECT d.date_key,
           CASE WHEN d.full_date < date(a.ltm_start, 'start of month') THEN 0.0
                WHEN d.full_date = date(a.ltm_start, 'start of month')
                     THEN (julianday(date(d.full_date, '+1 month')) - julianday(a.ltm_start)) / (julianday(date(d.full_date, '+1 month')) - julianday(d.full_date))
                ELSE 1.0 END AS w
    FROM dim_date d CROSS JOIN asof a
    WHERE d.day_of_month = 1 AND d.full_date <= a.as_of
),
att AS (
    SELECT am.attorney_key, SUM(am.billable_hours * w.w) AS hours, SUM(am.capacity_hours * w.w) AS capacity
    FROM fact_attorney_month am JOIN w ON w.date_key = am.month_start_date_key
    GROUP BY am.attorney_key
),
area_att AS (
    SELECT t.practice_area_key, t.attorney_key, SUM(t.billable_hours * w.w) AS hours, SUM(t.fees_realised * w.w) AS fees,
           SUM(t.allocated_salary_cost * w.w) AS salary
    FROM fact_time_by_area t JOIN w ON w.date_key = t.month_start_date_key
    GROUP BY t.practice_area_key, t.attorney_key
),
area AS (
    SELECT aa.practice_area_key, SUM(aa.hours) AS hours, SUM(aa.fees) AS fees, SUM(aa.salary) AS salary,
           SUM(aa.hours * att.hours / att.capacity) / SUM(aa.hours) AS lawyer_util,
           SUM(CASE WHEN aa.hours > 0.1 * att.hours THEN 1 ELSE 0 END) AS lawyers
    FROM area_att aa JOIN att ON att.attorney_key = aa.attorney_key
    GROUP BY aa.practice_area_key
),
demand AS (
    SELECT m.practice_area_key,
           SUM(CASE WHEN od.full_date BETWEEN a.ltm_start AND a.as_of THEN 1 ELSE 0 END) AS opened,
           SUM(CASE WHEN od.full_date BETWEEN a.prior_start AND date(a.ltm_start, '-1 day') THEN 1 ELSE 0 END) AS opened_prior
    FROM dim_matter m JOIN dim_date od ON od.date_key = m.opened_date_key CROSS JOIN asof a
    GROUP BY m.practice_area_key
),
calc AS (
    SELECT pa.practice_area, ar.hours, ar.fees, ar.lawyer_util, ar.lawyers, ar.fees / ar.hours AS eff_rate,
           (ar.fees - ar.salary) / ar.fees AS margin, d.opened, (1.0 * d.opened - d.opened_prior) / d.opened_prior AS growth
    FROM area ar
    JOIN dim_practice_area pa ON pa.practice_area_key = ar.practice_area_key
    JOIN demand d             ON d.practice_area_key = ar.practice_area_key
),
scored AS (
    SELECT *,
           0.40 * 100.0 * (lawyer_util - MIN(lawyer_util) OVER ()) / (MAX(lawyer_util) OVER () - MIN(lawyer_util) OVER ())
         + 0.35 * 100.0 * (growth - MIN(growth) OVER ()) / (MAX(growth) OVER () - MIN(growth) OVER ())
         + 0.25 * 100.0 * (margin - MIN(margin) OVER ()) / (MAX(margin) OVER () - MIN(margin) OVER ()) AS priority
    FROM calc
)
SELECT practice_area, opened AS matters_opened_12m, ROUND(100 * growth, 1) AS matters_growth_pct, ROUND(hours, 0) AS billable_hours_12m,
       lawyers, ROUND(100 * lawyer_util, 1) AS lawyer_utilisation_pct, ROUND(eff_rate, 0) AS effective_rate, ROUND(fees, 0) AS fees_12m,
       ROUND(100 * margin, 1) AS margin_pct, ROUND(priority, 1) AS priority_score,
       RANK() OVER (ORDER BY priority DESC) AS priority_rank,
       CASE RANK() OVER (ORDER BY priority DESC) WHEN 1 THEN 'Hire here first' WHEN 2 THEN 'Next in line' ELSE 'Hold' END AS verdict
FROM scored
ORDER BY priority_rank;
