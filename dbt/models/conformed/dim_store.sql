-- One row per restaurant, with the identifiers each source system uses for it.
select
    store_key,
    store_name,
    market,
    timezone,
    pos_location_code,
    cast(labor_store_number as {{ dbt.type_string() }}) as labor_store_number
from {{ ref('store_crosswalk') }}
