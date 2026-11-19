-- Fails (returns a row) when fewer than var('recon_threshold') of store-days appear in both POS and labor.
with stats as (
    select
        count(*) as store_days,
        sum(case when in_pos and in_labor then 1 else 0 end) as matched
    from {{ ref('recon_store_day') }}
)

select store_days, matched, matched * 1.0 / store_days as match_rate
from stats
where store_days = 0
   or matched * 1.0 / store_days < {{ var('recon_threshold') }}
