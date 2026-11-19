"""DuckDB adapter for local development and CI. Mirrors the BigQuery raw layout."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb

META_COLUMNS = ["_batch_id", "_ingested_at"]


class DuckDBWarehouse:
    def __init__(self, path: str):
        self.path = path

    def _connect(self) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect(self.path)
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        return con

    def replace_partition(self, table: str, partition_col: str, partition_value: str, rows: list[dict], batch_id: str) -> int:
        if not rows:
            return 0
        columns = sorted({c for row in rows for c in row})
        all_cols = columns + META_COLUMNS
        ingested_at = datetime.now(timezone.utc).isoformat()

        con = self._connect()
        try:
            col_defs = ", ".join(f'"{c}" VARCHAR' for c in all_cols)
            con.execute(f"CREATE TABLE IF NOT EXISTS raw.{table} ({col_defs})")
            # Add any new (allowlisted) columns without breaking existing loads.
            existing = {r[0] for r in con.execute(f"DESCRIBE raw.{table}").fetchall()}
            for col in all_cols:
                if col not in existing:
                    con.execute(f'ALTER TABLE raw.{table} ADD COLUMN "{col}" VARCHAR')

            values = [
                [None if row.get(c) is None else str(row.get(c)) for c in columns] + [batch_id, ingested_at]
                for row in rows
            ]
            placeholders = ", ".join("?" for _ in all_cols)
            col_list = ", ".join(f'"{c}"' for c in all_cols)

            con.execute("BEGIN TRANSACTION")
            con.execute(f'DELETE FROM raw.{table} WHERE "{partition_col}" = ?', [partition_value])
            con.executemany(f"INSERT INTO raw.{table} ({col_list}) VALUES ({placeholders})", values)
            con.execute("COMMIT")
            return len(rows)
        finally:
            con.close()

    def query(self, sql: str) -> list[tuple]:
        con = duckdb.connect(self.path, read_only=True)
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()
