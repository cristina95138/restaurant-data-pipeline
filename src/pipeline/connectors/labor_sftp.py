"""Labor / timekeeping connector: daily CSV export dropped on an SFTP server.

The vendor writes one file per business day: ``shifts_YYYY-MM-DD.csv``.
Locally (and in tests) the same files are read from a directory, so the parsing
and validation code path is identical to production.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path
from typing import Protocol

from ..logging_utils import log

EXPECTED_HEADER = {"shift_id", "store_number", "work_date", "employee_id", "job_code", "clock_in", "clock_out"}


class FileSource(Protocol):
    def read_text(self, filename: str) -> str: ...


class LocalDirSource:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def read_text(self, filename: str) -> str:
        return (self.directory / filename).read_text()


class SFTPSource:
    """Reads files from the vendor SFTP server using key auth (key mounted from Secret Manager)."""

    def __init__(self, host: str, user: str, key_path: str, remote_dir: str):
        self.host, self.user, self.key_path, self.remote_dir = host, user, key_path, remote_dir

    def read_text(self, filename: str) -> str:
        import paramiko  # optional dependency, only needed in prod

        client = paramiko.SSHClient()
        client.load_system_host_keys()  # host key must be pinned; never AutoAddPolicy in prod
        client.connect(self.host, username=self.user, key_filename=self.key_path, timeout=30)
        try:
            with client.open_sftp() as sftp, sftp.open(f"{self.remote_dir}/{filename}") as fh:
                return fh.read().decode("utf-8")
        finally:
            client.close()


class SchemaDrift(Exception):
    pass


def fetch_shifts(source: FileSource, work_date: date) -> list[dict]:
    filename = f"shifts_{work_date.isoformat()}.csv"
    text = source.read_text(filename)
    reader = csv.DictReader(io.StringIO(text))

    missing = EXPECTED_HEADER - set(reader.fieldnames or [])
    if missing:
        # Required columns gone: fail loudly instead of loading half a file.
        raise SchemaDrift(f"{filename} is missing columns: {sorted(missing)}")

    rows = list(reader)
    log("labor_fetched", work_date=work_date, rows=len(rows), file=filename)
    return rows
