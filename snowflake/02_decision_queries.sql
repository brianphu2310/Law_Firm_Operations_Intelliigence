-- The Principal's decision queries in Snowflake SQL (generated from sql/analysis/, do not edit by hand).
-- Run after 01_setup_and_load.sql. Each query returns the same rows as the local SQLite version in docs/query_results/.
USE SCHEMA LAW_FIRM.ANALYTICS;

-- ============================================================ 09_pnl_actual_vs_budget
-- Monthly profit and loss: actual vs budget, variance, margin, and financial-year-to-date running totals.
-- The as-of month is pro-rated in both scenarios, so the comparison is like for like.
-- Snowflake dialect (translated from sql/analysis/). Techniques: CTEs, conditional pivot of scenario rows, window SUM running totals by FY, LAG, CASE variance flag.
WITH pivoted AS (
    SELECT d.full_date AS month_start, d.fy_label, d.fy_start_year,
           SUM(CASE WHEN s.scenario_name = 'Actual' THEN p.revenue END)          AS act_revenue,
           SUM(CASE WHEN s.scenario_name = 'Budget' THEN p.revenue END)          AS bud_revenue,
           SUM(CASE WHEN s.scenario_name = 'Actual' THEN p.total_costs END)      AS act_costs,
           SUM(CASE WHEN s.scenario_name = 'Budget' THEN p.total_costs END)      AS bud_costs,
           SUM(CASE WHEN s.scenario_name = 'Actual' THEN p.operating_profit END) AS act_profit,
           SUM(CASE WHEN s.scenario_name = 'Budget' THEN p.operating_profit END) AS bud_profit
    FROM fact_monthly_pnl p
    JOIN dim_scenario s ON s.scenario_key = p.scenario_key
    JOIN dim_date d     ON d.date_key = p.month_start_date_key
    GROUP BY d.full_date, d.fy_label, d.fy_start_year
    HAVING act_revenue IS NOT NULL
)
SELECT month_start, fy_label,
       ROUND(act_revenue, 0) AS actual_revenue, ROUND(bud_revenue, 0) AS budget_revenue,
       ROUND(act_profit, 0)  AS actual_profit,  ROUND(bud_profit, 0)  AS budget_profit,
       ROUND(100.0 * (act_revenue - bud_revenue) / bud_revenue, 1) AS revenue_var_pct,
       ROUND(100.0 * (act_profit - bud_profit) / bud_profit, 1)    AS profit_var_pct,
       ROUND(100.0 * act_profit / act_revenue, 1)                  AS actual_margin_pct,
       ROUND(100.0 * (act_revenue - LAG(act_revenue) OVER (ORDER BY month_start)) / LAG(act_revenue) OVER (ORDER BY month_start), 1) AS revenue_mom_pct,
       ROUND(SUM(act_profit) OVER (PARTITION BY fy_label ORDER BY month_start), 0) AS actual_profit_fy_ytd,
       ROUND(SUM(bud_profit) OVER (PARTITION BY fy_label ORDER BY month_start), 0) AS budget_profit_fy_ytd,
       ROUND(SUM(act_profit) OVER (PARTITION BY fy_label ORDER BY month_start) - SUM(bud_profit) OVER (PARTITION BY fy_label ORDER BY month_start), 0) AS profit_ytd_variance,
       CASE WHEN act_profit >= bud_profit THEN 'Favourable' WHEN act_profit >= 0.9 * bud_profit THEN 'Within 10%' ELSE 'Adverse' END AS profit_flag
FROM pivoted
ORDER BY month_start;

-- ============================================================ 11_where_to_hire
-- Where to hire: demand, pressure and margin by practice area over the last 12 months (the Principal's hiring question).
-- pressure  = utilisation of the lawyers already doing the area's work, weighted by their hours in it;
-- demand    = growth in matters opened vs the 12 months before; margin = fees less allocated fee-earner salary.
-- priority  = 40% pressure + 35% demand growth + 25% margin, each min-max scaled 0-100 across areas (same rule as the app).
-- Snowflake dialect (translated from sql/analysis/). Techniques: CTEs, date arithmetic for a rolling window with a partial first month, weighted averages, MIN/MAX windows, RANK, CASE.
WITH asof AS (
    SELECT TO_DATE(meta_value) AS as_of, DATEADD(day, 1, DATEADD(year, -1, TO_DATE(meta_value))) AS ltm_start, DATEADD(day, 1, DATEADD(year, -2, TO_DATE(meta_value))) AS prior_start
    FROM etl_meta WHERE meta_key = 'as_of_date'
),
w AS (      -- weight of each month inside the window: the first month counts only from the window start
    SELECT d.date_key,
           CASE WHEN d.full_date < DATE_TRUNC('month', a.ltm_start) THEN 0.0
                WHEN d.full_date = DATE_TRUNC('month', a.ltm_start)
                     THEN DATEDIFF(day, a.ltm_start, DATEADD(month, 1, d.full_date)) / DATEDIFF(day, d.full_date, DATEADD(month, 1, d.full_date))
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
           SUM(CASE WHEN od.full_date BETWEEN a.prior_start AND DATEADD(day, -1, a.ltm_start) THEN 1 ELSE 0 END) AS opened_prior
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

-- ============================================================ 12_support_staffing
-- Support staffing: is each department over- or under-staffed for the work it carries? (the Principal's staffing question)
-- Workload drivers (last 12 months): reception = inquiries, shared by each office's share of new matters; paralegals = active
-- matters per office; accounts = invoices + trust transactions + supplier orders (firm-wide); marketing = marketing + referral spend.
-- needed = base roles per office + workload / workload a role carries (dim_department). Benchmarks are assumptions.
-- Snowflake dialect (translated from sql/analysis/). Techniques: CTEs, scalar subqueries, UNION ALL of office-level and firm-wide rows, CASE status bands, window share.
WITH asof AS (
    SELECT TO_DATE(meta_value) AS as_of, DATEADD(day, 1, DATEADD(year, -1, TO_DATE(meta_value))) AS ltm_start FROM etl_meta WHERE meta_key = 'as_of_date'
),
w AS (
    SELECT d.date_key,
           CASE WHEN d.full_date < DATE_TRUNC('month', a.ltm_start) THEN 0.0
                WHEN d.full_date = DATE_TRUNC('month', a.ltm_start)
                     THEN DATEDIFF(day, a.ltm_start, DATEADD(month, 1, d.full_date)) / DATEDIFF(day, d.full_date, DATEADD(month, 1, d.full_date))
                ELSE 1.0 END AS w
    FROM dim_date d CROSS JOIN asof a
    WHERE d.day_of_month = 1 AND d.full_date <= a.as_of
),
inquiries AS (SELECT SUM(f.inquiries * w.w) AS n FROM fact_monthly_funnel f JOIN w ON w.date_key = f.month_start_date_key),
opened_by AS (
    SELECT m.branch_key, COUNT(*) AS n FROM dim_matter m JOIN dim_date d ON d.date_key = m.opened_date_key CROSS JOIN asof a
    WHERE d.full_date BETWEEN a.ltm_start AND a.as_of GROUP BY m.branch_key
),
active_by AS (
    SELECT m.branch_key, COUNT(*) AS n
    FROM dim_matter m JOIN dim_date od ON od.date_key = m.opened_date_key LEFT JOIN dim_date cd ON cd.date_key = m.closed_date_key CROSS JOIN asof a
    WHERE od.full_date <= a.as_of AND (cd.full_date IS NULL OR cd.full_date > a.as_of) GROUP BY m.branch_key
),
firm AS (
    SELECT (SELECT COUNT(*) FROM fact_invoice i JOIN dim_date d ON d.date_key = i.issue_date_key CROSS JOIN asof a WHERE d.full_date BETWEEN a.ltm_start AND a.as_of)
         + (SELECT COUNT(*) FROM fact_trust_txn t JOIN dim_date d ON d.date_key = t.txn_date_key CROSS JOIN asof a WHERE d.full_date BETWEEN a.ltm_start AND a.as_of)
         + (SELECT COUNT(*) FROM fact_supplier_order o JOIN dim_date d ON d.date_key = o.order_date_key CROSS JOIN asof a WHERE d.full_date BETWEEN a.ltm_start AND a.as_of)
           AS transactions,
           (SELECT SUM((p.marketing + p.commission) * w.w) FROM fact_monthly_pnl p JOIN w ON w.date_key = p.month_start_date_key
            JOIN dim_scenario s ON s.scenario_key = p.scenario_key WHERE s.scenario_name = 'Actual') AS spend
),
office_rows AS (
    SELECT b.branch_name AS office, dp.department, fs.headcount, dp.monthly_pay, dp.base_per_office, dp.workload_per_fte,
           CASE dp.department WHEN 'Reception & admin' THEN (SELECT n FROM inquiries) * ob.n / (SELECT SUM(n) FROM opened_by)
                              ELSE COALESCE(ab.n, 0) END AS workload
    FROM fact_staffing fs
    JOIN dim_branch b      ON b.branch_key = fs.branch_key
    JOIN dim_department dp ON dp.department_key = fs.department_key
    LEFT JOIN opened_by ob ON ob.branch_key = fs.branch_key
    LEFT JOIN active_by ab ON ab.branch_key = fs.branch_key
    WHERE dp.is_firm_wide = 0
),
firm_rows AS (
    SELECT 'All offices' AS office, dp.department, SUM(fs.headcount) AS headcount, dp.monthly_pay, dp.base_per_office, dp.workload_per_fte,
           CASE dp.department WHEN 'Accounts & trust' THEN (SELECT transactions FROM firm) ELSE (SELECT spend FROM firm) END AS workload
    FROM fact_staffing fs JOIN dim_department dp ON dp.department_key = fs.department_key
    WHERE dp.is_firm_wide = 1
    GROUP BY dp.department, dp.monthly_pay, dp.base_per_office, dp.workload_per_fte
),
rows_ AS (
    SELECT *, base_per_office + workload / workload_per_fte AS needed FROM (SELECT * FROM office_rows UNION ALL SELECT * FROM firm_rows)
)
SELECT office, department, headcount, ROUND(workload, 0) AS workload_12m, ROUND(needed, 1) AS roles_needed, ROUND(headcount - needed, 1) AS gap,
       CASE WHEN headcount - needed >= 0.75 THEN 'Over-staffed' WHEN headcount - needed <= -0.75 THEN 'Under-staffed'
            WHEN headcount - needed <= -0.25 THEN 'Stretched' ELSE 'About right' END AS status,
       ROUND((headcount - needed) * monthly_pay * 12, 0) AS gap_cost_a_year,
       ROUND(100.0 * headcount / SUM(headcount) OVER (), 1) AS pct_of_support_staff
FROM rows_
ORDER BY CASE department WHEN 'Reception & admin' THEN 1 WHEN 'Paralegals & clerks' THEN 2 WHEN 'Accounts & trust' THEN 3 ELSE 4 END, office;

-- ============================================================ 13_marketing_channels
-- Marketing: where new clients come from and what each new matter costs by channel, last 12 months (the Principal's marketing question).
-- The channel mix (dim_marketing_channel, an assumption) splits the firm's real totals: marketing cost (referrals are paid by
-- commission instead), inquiries and matters opened. Fees = new matters x average fees billed per matter worked in the year x channel value.
-- Snowflake dialect (translated from sql/analysis/). Techniques: CTEs, rolling window with partial first month, scalar totals, weighted allocation with SUM() OVER (), RANK, CASE.
WITH asof AS (
    SELECT TO_DATE(meta_value) AS as_of, DATEADD(day, 1, DATEADD(year, -1, TO_DATE(meta_value))) AS ltm_start FROM etl_meta WHERE meta_key = 'as_of_date'
),
w AS (
    SELECT d.date_key,
           CASE WHEN d.full_date < DATE_TRUNC('month', a.ltm_start) THEN 0.0
                WHEN d.full_date = DATE_TRUNC('month', a.ltm_start)
                     THEN DATEDIFF(day, a.ltm_start, DATEADD(month, 1, d.full_date)) / DATEDIFF(day, d.full_date, DATEADD(month, 1, d.full_date))
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
