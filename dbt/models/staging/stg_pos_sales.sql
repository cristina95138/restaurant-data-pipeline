-- Typed, de-duplicated POS checks. If a check was loaded twice, keep the latest load.
with source as (
    select * from {{ source('raw', 'pos_sales') }}
)

select
    check_id,
    location_code,
    cast(business_date as date)              as business_date,
    cast(closed_at as timestamp)             as closed_at,
    cast(net_sales as {{ dbt.type_numeric() }})   as net_sales,
    cast(tax as {{ dbt.type_numeric() }})         as tax,
    cast(guest_count as {{ dbt.type_int() }})     as guest_count,
    order_channel,
    _batch_id,
    cast(_ingested_at as timestamp)          as ingested_at
from source
qualify row_number() over (partition by check_id order by _ingested_at desc) = 1
