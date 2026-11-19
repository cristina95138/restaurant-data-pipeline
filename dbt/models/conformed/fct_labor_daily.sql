-- Daily labor per store on the shared store_key.
select
    s.store_key,
    l.work_date                       as business_date,
    count(*)                          as shift_count,
    count(distinct l.employee_id)     as employee_count,
    sum(l.hours_worked)               as labor_hours
from {{ ref('stg_labor_shifts') }} l
left join {{ ref('dim_store') }} s
    on cast(l.store_number as {{ dbt.type_string() }}) = s.labor_store_number
group by 1, 2
