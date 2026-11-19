-- Typed, de-duplicated shifts with worked hours. employee_id is already pseudonymised at ingestion.
with source as (
    select * from {{ source('raw', 'labor_shifts') }}
),

typed as (
    select
        shift_id,
        store_number,
        cast(work_date as date)        as work_date,
        employee_id,
        job_code,
        cast(clock_in as timestamp)    as clock_in,
        cast(clock_out as timestamp)   as clock_out,
        _batch_id,
        cast(_ingested_at as timestamp) as ingested_at
    from source
    qualify row_number() over (partition by shift_id order by _ingested_at desc) = 1
)

select
    *,
    {{ dbt.datediff('clock_in', 'clock_out', 'minute') }} / 60.0 as hours_worked
from typed
