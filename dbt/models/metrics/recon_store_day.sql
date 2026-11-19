-- Every store-day seen in either system, flagged by which systems have it.
-- The reconciliation target (>= 99% present in both) is enforced by tests/assert_store_day_match_rate.sql.
select
    coalesce(s.store_key, l.store_key)           as store_key,
    coalesce(s.business_date, l.business_date)   as business_date,
    s.store_key is not null                      as in_pos,
    l.store_key is not null                      as in_labor
from {{ ref('fct_sales_daily') }} s
full outer join {{ ref('fct_labor_daily') }} l
    on s.store_key = l.store_key
   and s.business_date = l.business_date
