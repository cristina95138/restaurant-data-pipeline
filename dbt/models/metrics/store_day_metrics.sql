-- Agent-facing table: one row per store per day with the numbers a labor-scheduling
-- or prep-forecasting agent needs. Only reconciled store-days are included.
select
    d.store_key,
    d.store_name,
    d.market,
    s.business_date,
    s.net_sales,
    s.check_count,
    s.guest_count,
    l.labor_hours,
    l.shift_count,
    round(s.net_sales / nullif(l.labor_hours, 0), 2)   as sales_per_labor_hour,
    round(s.net_sales / nullif(s.guest_count, 0), 2)   as avg_spend_per_guest
from {{ ref('fct_sales_daily') }} s
join {{ ref('fct_labor_daily') }} l
    on s.store_key = l.store_key
   and s.business_date = l.business_date
join {{ ref('dim_store') }} d
    on s.store_key = d.store_key
