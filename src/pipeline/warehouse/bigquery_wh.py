"""BigQuery adapter for production.

Auth uses the Cloud Run job's service account (Application Default
Credentials), so there are no keys to manage. Each load goes to a temporary
table, then a single transaction swaps the day's partition, which keeps
retries and backfills idempotent.

Note: exercised against BigQuery in the deployed environment; CI covers the
same logic through the DuckDB adapter.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


class BigQueryWarehouse:
    def __init__(self, project: str | None, raw_dataset: str):
        from google.cloud import bigquery  # imported lazily so local runs don't need it

        self.bq = bigquery
        self.client = bigquery.Client(project=project)
        self.dataset = f"{self.client.project}.{raw_dataset}"

    def replace_partition(self, table: str, partition_col: str, partition_value: str, rows: list[dict], batch_id: str) -> int:
        if not rows:
            return 0
        bq = self.bq
        ingested_at = datetime.now(timezone.utc).isoformat()
        payload = [
            {**{k: None if v is None else str(v) for k, v in row.items()}, "_batch_id": batch_id, "_ingested_at": ingested_at}
            for row in rows
        ]
        target = f"{self.dataset}.{table}"
        tmp = f"{self.dataset}._tmp_{table}_{uuid.uuid4().hex[:8]}"

        schema = [bq.SchemaField(c, "STRING") for c in sorted({c for r in payload for c in r})]
        self.client.load_table_from_json(
            payload, tmp, job_config=bq.LoadJobConfig(schema=schema, write_disposition="WRITE_TRUNCATE")
        ).result()

        cols = ", ".join(f"`{f.name}`" for f in schema)
        add_missing = "\n".join(
            f"ALTER TABLE `{target}` ADD COLUMN IF NOT EXISTS `{f.name}` STRING;" for f in schema
        )
        try:
            self.client.query(
                f"""
                CREATE TABLE IF NOT EXISTS `{target}` LIKE `{tmp}`;
                {add_missing}
                BEGIN TRANSACTION;
                DELETE FROM `{target}` WHERE `{partition_col}` = @partition_value;
                INSERT INTO `{target}` ({cols}) SELECT {cols} FROM `{tmp}`;
                COMMIT TRANSACTION;
                """,
                job_config=bq.QueryJobConfig(
                    query_parameters=[bq.ScalarQueryParameter("partition_value", "STRING", partition_value)]
                ),
            ).result()
        finally:
            self.client.delete_table(tmp, not_found_ok=True)
        return len(rows)

    def query(self, sql: str) -> list[tuple]:
        return [tuple(r.values()) for r in self.client.query(sql).result()]
