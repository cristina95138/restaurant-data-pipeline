"""Warehouse adapters.

The raw layer keeps every source column as a string plus load metadata, so a
type change at the source can never break ingestion. Typing and cleaning happen
in the dbt staging layer.

Loads are idempotent: re-running a day replaces that day's partition instead
of appending duplicates, so backfills and retries are safe.
"""

from __future__ import annotations

from typing import Protocol

from ..config import Settings


class Warehouse(Protocol):
    def replace_partition(self, table: str, partition_col: str, partition_value: str, rows: list[dict], batch_id: str) -> int: ...

    def query(self, sql: str) -> list[tuple]: ...


def get_warehouse(settings: Settings) -> Warehouse:
    if settings.warehouse == "duckdb":
        from .duckdb_wh import DuckDBWarehouse

        return DuckDBWarehouse(settings.duckdb_path)
    if settings.warehouse == "bigquery":
        from .bigquery_wh import BigQueryWarehouse

        return BigQueryWarehouse(settings.bq_project, settings.bq_raw_dataset)
    raise ValueError(f"Unknown WAREHOUSE '{settings.warehouse}'")
