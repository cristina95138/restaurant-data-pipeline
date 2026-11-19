# Deploying to Google Cloud

The pipeline runs as a **Cloud Run job** triggered daily by **Cloud Scheduler**.
Secrets live in **Secret Manager** and are injected as environment variables at runtime.
The job authenticates to BigQuery with its own service account, so there are no key files anywhere.

## One-time setup

```bash
PROJECT=your-project
REGION=us-east1
SA=restaurant-pipeline@${PROJECT}.iam.gserviceaccount.com

# Service account with least privilege
gcloud iam service-accounts create restaurant-pipeline --project "$PROJECT"
gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" --role roles/bigquery.jobUser
for ds in raw staging conformed metrics; do
  bq --project_id "$PROJECT" mk --dataset --location US "$ds" || true
  # dataEditor scoped to each dataset rather than the whole project
  bq add-iam-policy-binding --member="serviceAccount:$SA" --role=roles/bigquery.dataEditor "$PROJECT:$ds"
done

# Secrets (values entered interactively, never committed)
for s in pos-client-id pos-client-secret sftp-private-key pseudonym-key; do
  gcloud secrets create "$s" --project "$PROJECT" --replication-policy automatic
  gcloud secrets versions add "$s" --data-file=- --project "$PROJECT"
  gcloud secrets add-iam-policy-binding "$s" --member "serviceAccount:$SA" --role roles/secretmanager.secretAccessor --project "$PROJECT"
done
```

## Build and deploy the job

```bash
gcloud builds submit --tag "$REGION-docker.pkg.dev/$PROJECT/pipelines/restaurant-data-pipeline:latest"

gcloud run jobs deploy restaurant-daily \
  --image "$REGION-docker.pkg.dev/$PROJECT/pipelines/restaurant-data-pipeline:latest" \
  --region "$REGION" --service-account "$SA" \
  --task-timeout 3600 --max-retries 2 \
  --set-env-vars BQ_PROJECT=$PROJECT,POS_BASE_URL=https://api.your-pos.example,SFTP_HOST=sftp.your-labor.example,SFTP_USER=export,SFTP_KEY_PATH=/secrets/sftp/key \
  --set-secrets POS_CLIENT_ID=pos-client-id:latest,POS_CLIENT_SECRET=pos-client-secret:latest,PSEUDONYM_KEY=pseudonym-key:latest,/secrets/sftp/key=sftp-private-key:latest
```

## Schedule

```bash
# 6:00 AM Eastern, after the POS closes the previous business day and the labor export lands
gcloud scheduler jobs create http restaurant-daily-trigger \
  --location "$REGION" --schedule "0 6 * * *" --time-zone "America/New_York" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs/restaurant-daily:run" \
  --http-method POST --oauth-service-account-email "$SA"
```

## Monitoring and alerts

All logs are JSON with `severity` and `event` fields, so Cloud Logging can filter them directly.

| Alert | Log filter | Why |
|---|---|---|
| Job failed | `resource.type="cloud_run_job" AND severity>=ERROR` | Any failed step (ingest, dbt test, freshness, reconciliation) |
| Source stale | `jsonPayload.event="freshness_check" AND jsonPayload.fresh=false` | A source stopped delivering |
| Reconciliation below target | `jsonPayload.event="reconciliation_check" AND severity="ERROR"` | Store/date keys drifting between POS and labor |
| PII guard tripped | `jsonPayload.event="ingest_failed" AND jsonPayload.error=~"PIIViolation"` | Personal data appeared in an allowed field |

Create a log-based metric for each filter and an alert policy that notifies the team channel when the count is greater than 0.
