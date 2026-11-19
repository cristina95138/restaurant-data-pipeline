import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def settings(tmp_path, monkeypatch):
    from pipeline.config import Settings

    monkeypatch.setenv("WAREHOUSE", "duckdb")
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.setenv("LABOR_LOCAL_DIR", str(ROOT / "sample_data" / "labor"))
    monkeypatch.delenv("SFTP_HOST", raising=False)
    return Settings.from_env()
