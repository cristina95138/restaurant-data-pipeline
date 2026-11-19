#!/usr/bin/env bash
# Daily job executed by Cloud Run Jobs (triggered by Cloud Scheduler).
# Each step logs structured JSON; a non-zero exit fails the job execution,
# which Cloud Monitoring alerts on.
set -euo pipefail

RUN_DATE="${RUN_DATE:-$(date -u -d 'yesterday' +%F)}"
DBT_TARGET="${DBT_TARGET:-prod}"

echo "{\"severity\":\"INFO\",\"event\":\"job_start\",\"run_date\":\"${RUN_DATE}\"}"

# 1. Extract + scrub + load raw (a failing source is logged but doesn't block the others)
ingest_status=0
python -m pipeline ingest --source all --date "${RUN_DATE}" || ingest_status=$?

# 2. Transform and test: staging -> conformed -> metrics
(cd dbt && dbt build --target "${DBT_TARGET}" --profiles-dir .)

# 3. Post-load checks
python -m pipeline freshness
python -m pipeline reconcile --threshold 0.99

exit "${ingest_status}"
