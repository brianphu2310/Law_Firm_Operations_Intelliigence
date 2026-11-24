-- Support staffing: is each department over- or under-staffed for the work it carries? (the Principal's staffing question)
-- Workload drivers (last 12 months): reception = inquiries, shared by each office's share of new matters; paralegals = active
-- matters per office; accounts = invoices + trust transactions + supplier orders (firm-wide); marketing = marketing + referral spend.
-- needed = base roles per office + workload / workload a role carries (dim_department). Benchmarks are assumptions.
-- Techniques: CTEs, scalar subqueries, UNION ALL of office-level and firm-wide rows, CASE status bands, window share.
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
