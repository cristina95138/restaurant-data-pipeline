-- Daily sales per store on the shared store_key.
-- A POS location missing from the crosswalk yields a null store_key, which the not_null test catches.
select
    s.store_key,
    p.business_date,
    count(*)                 as check_count,
    sum(p.guest_count)       as guest_count,
    sum(p.net_sales)         as net_sales,
    sum(p.tax)               as tax
from {{ ref('stg_pos_sales') }} p
left join {{ ref('dim_store') }} s
    on p.location_code = s.pos_location_code
group by 1, 2
