# Runbook

What to do when the daily job alerts. Every log line is JSON with an `event` field; start there.

## Daily schedule

| Time (ET) | What happens |
|---|---|
| 6:00 | Cloud Scheduler starts the `restaurant-daily` Cloud Run job for yesterday's business date |
| ~6:05 | Ingest POS and labor into `raw` (each source independently) |
| ~6:10 | `dbt build`: staging, conformed and metrics models, plus all data tests |
| ~6:12 | Freshness and reconciliation checks |

## Common alerts

### `ingest_failed` for one source
1. Read the `error` field in the log line.
2. **HTTP 401/403 from POS:** the API credentials were rotated or revoked. Update `pos-client-secret` in Secret Manager, then re-run.
3. **`retry_exhausted` / 5xx:** the vendor API is down. Re-run later; loads are idempotent.
4. **`SchemaDrift`:** the labor export changed its columns. Compare the file header to `EXPECTED_HEADER` in `connectors/labor_sftp.py`. Don't loosen the check until you know what changed.
5. **`PIIViolation`:** personal data showed up in an allowed field. **Do not bypass.** The batch was not loaded. Find the field in the log, contact the vendor, and if the field is needed, add a cleaning rule before re-running.

### `freshness_check` with `fresh=false`
The latest business date in `raw` is older than allowed. Check whether ingest failed (above), or whether the vendor export is late. Confirm the file or API data exists for the date, then re-run.

### `reconciliation_check` below 0.99
Store-days exist in one system but not the other.
```sql
select * from metrics.recon_store_day where not (in_pos and in_labor) order by business_date desc;
```
- **Store only in POS or only in labor for every day:** a new or renamed location. Add it to `dbt/seeds/store_crosswalk.csv`, then run `dbt seed && dbt build`.
- **A single missing day:** usually a late or failed load for one source. Re-run that date.

### dbt test failure
Run `dbt build --select <failing_model>+` locally against a copy of the data, read the failing rows with `dbt show`, and fix the model or the source data. Never delete the test to get green.

## Re-running and backfilling

Loads replace the whole business date, so re-running is always safe.

```bash
# Re-run one day
gcloud run jobs execute restaurant-daily --region us-east1 --update-env-vars RUN_DATE=2026-11-15

# Backfill a range locally against prod
WAREHOUSE=bigquery python -m pipeline ingest --source pos --date 2026-11-15 --days 7
(cd dbt && dbt build --target prod --profiles-dir .)
```

## Adding a new source
1. Write a connector in `src/pipeline/connectors/` that returns a list of dicts for one business date.
2. Register its allowed columns (and any to pseudonymise) in `pii.py`. Columns not listed never reach the warehouse.
3. Add a runner in `runner.py`, a freshness target in `checks.py`, and a source in `dbt/models/staging/_sources.yml`.
4. Add a staging model with typing and dedupe, then join it on `store_key` / `business_date` in `conformed`.
5. Add tests, open a PR, and let CI run the end-to-end build.
