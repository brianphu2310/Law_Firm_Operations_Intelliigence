-- Saved questions for a Metabase "Partner debtors review" dashboard on Snowflake
-- (Admin > Databases > Add > Snowflake, then New > SQL query for each). {{practice_area}} is an optional Metabase filter.

-- Q1. Receivables by age (bar)
select ageing_bucket, count(*) as invoices, sum(balance_due) as balance_due
from law_firm.marts.aged_receivables
group by 1
order by case ageing_bucket when 'Not yet due' then 1 when '1–30 days' then 2 when '31–60 days' then 3 when '61–90 days' then 4 else 5 end;

-- Q2. Monthly revenue by practice area (stacked bar)
select month, practice_area, revenue_ex_gst
from law_firm.marts.revenue_monthly
where 1 = 1 [[and practice_area = {{practice_area}}]]
order by month;

-- Q3. Collection performance by practice area (table)
select * from law_firm.marts.collection_performance order by avg_days_to_pay desc;

-- Q4. Chase list: overdue invoices, largest first
select customer_name, invoice_number, attorney, due_date, days_past_due, balance_due
from law_firm.marts.aged_receivables
where days_past_due > 0
order by balance_due desc
limit 20;

-- Q5. Pipeline health (number: should be 0)
select count(*) as failed_resources_last_run
from law_firm.raw.load_audit
where loaded_at = (select max(loaded_at) from law_firm.raw.load_audit) and status <> 'OK';
