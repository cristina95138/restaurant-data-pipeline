"""Orchestrates one source for one business date: extract -> scrub PII -> load raw."""

from __future__ import annotations

import uuid
from datetime import date

from .config import REPO_ROOT, Settings
from .connectors.labor_sftp import LocalDirSource, SFTPSource, fetch_shifts
from .connectors.mock_pos import mock_pos_transport
from .connectors.pos_api import POSClient
from .logging_utils import log
from .pii import scrub
from .warehouse import Warehouse


def run_pos(settings: Settings, wh: Warehouse, business_date: date, mock: bool = False) -> int:
    if mock:
        client = POSClient(
            base_url="https://mock-pos.local",
            client_id="mock",
            client_secret="mock",
            transport=mock_pos_transport(REPO_ROOT / "sample_data" / "pos"),
        )
    else:
        if not (settings.pos_client_id and settings.pos_client_secret):
            raise RuntimeError("POS_CLIENT_ID / POS_CLIENT_SECRET not set (mount them from Secret Manager)")
        client = POSClient(settings.pos_base_url, settings.pos_client_id, settings.pos_client_secret)

    rows = scrub("pos_sales", client.fetch_sales(business_date))
    return _load(wh, "pos_sales", "business_date", business_date, rows)


def run_labor(settings: Settings, wh: Warehouse, work_date: date, mock: bool = False) -> int:
    if mock or not settings.sftp_host:
        source = LocalDirSource(settings.labor_local_dir)
    else:
        source = SFTPSource(settings.sftp_host, settings.sftp_user, settings.sftp_key_path, settings.labor_remote_dir)

    rows = scrub("labor_shifts", fetch_shifts(source, work_date))
    return _load(wh, "labor_shifts", "work_date", work_date, rows)


def _load(wh: Warehouse, table: str, partition_col: str, day: date, rows: list[dict]) -> int:
    batch_id = uuid.uuid4().hex
    loaded = wh.replace_partition(table, partition_col, day.isoformat(), rows, batch_id)
    log("raw_loaded", table=table, business_date=day, rows=loaded, batch_id=batch_id)
    return loaded


RUNNERS = {"pos": run_pos, "labor": run_labor}
