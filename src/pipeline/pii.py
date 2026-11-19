"""Keep personal data out of the warehouse at ingestion.

Two layers, both enforced before anything is written:

1. **Allowlist per source.** Only columns explicitly listed in ``SOURCE_SCHEMAS``
   pass through. A new column appearing in a source export is dropped (and
   logged) instead of silently landing in the warehouse.
2. **Value scan.** Every string value that survives is scanned for patterns that
   look like personal data (SSNs, full card numbers). A hit fails the whole
   batch, because a match means the allowlist or the source is wrong.

Employee identifiers are pseudonymised with a keyed hash so joins still work
across sources without storing the raw ID.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from typing import Iterable

from .logging_utils import log

# Columns allowed into the raw layer, per source. Anything else is dropped.
SOURCE_SCHEMAS: dict[str, set[str]] = {
    "pos_sales": {
        "check_id",
        "location_code",
        "business_date",
        "closed_at",
        "net_sales",
        "tax",
        "guest_count",
        "order_channel",
    },
    "labor_shifts": {
        "shift_id",
        "store_number",
        "work_date",
        "employee_id",  # pseudonymised below
        "job_code",
        "clock_in",
        "clock_out",
    },
}

# Columns that must be pseudonymised rather than stored raw.
PSEUDONYMISE: dict[str, set[str]] = {"labor_shifts": {"employee_id"}}

SSN_RE = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


class PIIViolation(Exception):
    """Raised when a value that looks like personal data survives the allowlist."""


def _pseudonym_key() -> bytes:
    # In prod this comes from Secret Manager. The default only exists for local runs/tests,
    # and production refuses to start without a real key.
    key = os.environ.get("PSEUDONYM_KEY")
    if not key:
        if os.environ.get("WAREHOUSE") == "bigquery":
            raise RuntimeError("PSEUDONYM_KEY must be set in production (mount it from Secret Manager)")
        key = "local-dev-only-key"
    return key.encode()


def pseudonymise(value: str) -> str:
    return hmac.new(_pseudonym_key(), value.encode(), hashlib.sha256).hexdigest()[:16]


def scrub(source: str, rows: Iterable[dict]) -> list[dict]:
    """Apply the allowlist, pseudonymise IDs and scan values. Returns clean rows."""
    if source not in SOURCE_SCHEMAS:
        raise KeyError(f"No PII schema registered for source '{source}'")
    allowed = SOURCE_SCHEMAS[source]
    to_hash = PSEUDONYMISE.get(source, set())

    clean: list[dict] = []
    dropped: set[str] = set()
    for row in rows:
        dropped.update(set(row) - allowed)
        out = {k: v for k, v in row.items() if k in allowed}
        _scan(source, out, skip=to_hash)
        for col in to_hash & out.keys():
            if out[col] is not None:
                out[col] = pseudonymise(str(out[col]))
        clean.append(out)

    if dropped:
        log("pii_columns_dropped", "WARNING", source=source, columns=sorted(dropped))
    return clean


TIMESTAMP_COLUMNS = {"closed_at", "clock_in", "clock_out", "business_date", "work_date"}


def _scan(source: str, row: dict, skip: set[str] = frozenset()) -> None:
    """Scan raw values before pseudonymisation. Columns in ``skip`` get hashed anyway."""
    for col, value in row.items():
        if col in skip or not isinstance(value, str):
            continue
        # Timestamps and ISO dates contain digit runs; skip them explicitly.
        if col in TIMESTAMP_COLUMNS:
            continue
        if SSN_RE.search(value) or CARD_RE.search(value):
            raise PIIViolation(f"{source}.{col} contains a value that looks like personal data")
