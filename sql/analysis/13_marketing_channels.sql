-- Marketing: where new clients come from and what each new matter costs by channel, last 12 months (the Principal's marketing question).
-- The channel mix (dim_marketing_channel, an assumption) splits the firm's real totals: marketing cost (referrals are paid by
-- commission instead), inquiries and matters opened. Fees = new matters x average fees billed per matter worked in the year x channel value.
-- Techniques: CTEs, rolling window with partial first month, scalar totals, weighted allocation with SUM() OVER (), RANK, CASE.
WITH asof AS (
    SELECT date(meta_value) AS as_of, date(meta_value, '-1 year', '+1 day') AS ltm_start FROM etl_meta WHERE meta_key = 'as_of_date'
),
w AS (
    SELECT d.date_key,
           CASE WHEN d.full_date < date(a.ltm_start, 'start of month') THEN 0.0
                WHEN d.full_date = date(a.ltm_start, 'start of month')
                     THEN (julianday(date(d.full_date, '+1 month')) - julianday(a.ltm_start)) / (julianday(date(d.full_date, '+1 month')) - julianday(d.full_date))
                ELSE 1.0 END AS w
    FROM dim_date d CROSS JOIN asof a
    WHERE d.day_of_month = 1 AND d.full_date <= a.as_of
),
pnl AS (
    SELECT SUM(p.marketing * w.w) AS marketing, SUM(p.commission * w.w) AS commission, SUM(p.fees * w.w) AS fees
    FROM fact_monthly_pnl p JOIN w ON w.date_key = p.month_start_date_key JOIN dim_scenario s ON s.scenario_key = p.scenario_key
    WHERE s.scenario_name = 'Actual'
),
funnel AS (SELECT SUM(f.inquiries * w.w) AS inquiries FROM fact_monthly_funnel f JOIN w ON w.date_key = f.month_start_date_key),
matters AS (
    SELECT SUM(CASE WHEN od.full_date BETWEEN a.ltm_start AND a.as_of THEN 1 ELSE 0 END) AS new_matters,
           SUM(CASE WHEN od.full_date <= a.as_of AND (cd.full_date IS NULL OR cd.full_date >= a.ltm_start) THEN 1 ELSE 0 END) AS worked
    FROM dim_matter m JOIN dim_date od ON od.date_key = m.opened_date_key LEFT JOIN dim_date cd ON cd.date_key = m.closed_date_key CROSS JOIN asof a
),
mix AS (
    SELECT c.*, c.inquiry_share * c.conversion_factor AS w_matters, c.inquiry_share * c.conversion_factor * c.value_factor AS w_fees
    FROM dim_marketing_channel c
),
alloc AS (
    SELECT x.channel,
           CASE WHEN x.spend_share = 0 THEN p.commission ELSE p.marketing * x.spend_share END AS spend,
           f.inquiries * x.inquiry_share AS inquiries,
           m.new_matters * x.w_matters / SUM(x.w_matters) OVER () AS new_matters,
           m.new_matters * (p.fees / m.worked) * x.w_fees / SUM(x.w_fees) OVER () AS fees
    FROM mix x CROSS JOIN pnl p CROSS JOIN funnel f CROSS JOIN matters m
)
SELECT channel, ROUND(spend, 0) AS spend_12m, ROUND(inquiries, 0) AS inquiries_12m, ROUND(new_matters, 1) AS new_matters_12m,
       ROUND(100.0 * new_matters / inquiries, 1) AS conversion_pct, ROUND(spend / inquiries, 0) AS cost_per_inquiry,
       ROUND(spend / new_matters, 0) AS cost_per_new_matter, ROUND(fees, 0) AS fees_from_new_matters,
       RANK() OVER (ORDER BY spend / new_matters) AS cost_rank,
       CASE WHEN spend / new_matters <= 800 THEN 'Grow' WHEN spend / new_matters <= 1500 THEN 'Keep' ELSE 'Cut or fix' END AS action
FROM alloc
ORDER BY cost_rank;
