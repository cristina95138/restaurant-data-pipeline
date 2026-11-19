"""Runtime configuration.

Everything comes from environment variables. In Cloud Run, secrets (API client
secrets, SFTP keys) are mounted from Secret Manager as env vars, so nothing
sensitive ever lives in the repo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    return value if value not in ("", None) else default


@dataclass(frozen=True)
class Settings:
    warehouse: str  # "duckdb" (local/CI) or "bigquery" (prod)
    duckdb_path: str
    bq_project: str | None
    bq_raw_dataset: str

    pos_base_url: str
    pos_client_id: str | None
    pos_client_secret: str | None

    sftp_host: str | None
    sftp_user: str | None
    sftp_key_path: str | None
    labor_remote_dir: str
    labor_local_dir: str

    freshness_max_lag_days: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            warehouse=_env("WAREHOUSE", "duckdb"),
            duckdb_path=_env("DUCKDB_PATH", str(REPO_ROOT / "warehouse.duckdb")),
            bq_project=_env("BQ_PROJECT"),
            bq_raw_dataset=_env("BQ_RAW_DATASET", "raw"),
            pos_base_url=_env("POS_BASE_URL", "https://pos.example.com"),
            pos_client_id=_env("POS_CLIENT_ID"),
            pos_client_secret=_env("POS_CLIENT_SECRET"),
            sftp_host=_env("SFTP_HOST"),
            sftp_user=_env("SFTP_USER"),
            sftp_key_path=_env("SFTP_KEY_PATH"),
            labor_remote_dir=_env("LABOR_REMOTE_DIR", "/exports/timekeeping"),
            labor_local_dir=_env("LABOR_LOCAL_DIR", str(REPO_ROOT / "sample_data" / "labor")),
            freshness_max_lag_days=int(_env("FRESHNESS_MAX_LAG_DAYS", "1")),
        )
