"""Post-load checks: data freshness and cross-source reconciliation."""

from __future__ import annotations

from datetime import date, timedelta

from .logging_utils import log
from .warehouse import Warehouse

# source name -> (raw table, business date column)
FRESHNESS_TARGETS = {
    "pos_sales": ("raw.pos_sales", "business_date"),
    "labor_shifts": ("raw.labor_shifts", "work_date"),
}


def check_freshness(wh: Warehouse, today: date, max_lag_days: int = 1) -> dict[str, bool]:
    """A source is fresh if its latest business date is within ``max_lag_days`` of today."""
    results: dict[str, bool] = {}
    for source, (table, col) in FRESHNESS_TARGETS.items():
        (latest,) = wh.query(f"SELECT MAX({col}) FROM {table}")[0]
        fresh = latest is not None and date.fromisoformat(str(latest)) >= today - timedelta(days=max_lag_days)
        results[source] = fresh
        log(
            "freshness_check",
            "INFO" if fresh else "ERROR",
            source=source,
            latest_business_date=latest,
            max_lag_days=max_lag_days,
            fresh=fresh,
        )
    return results


def check_reconciliation(wh: Warehouse, threshold: float = 0.99) -> float:
    """Share of store-days present in both POS and labor (built by dbt: metrics.recon_store_day)."""
    total, matched = wh.query(
        "SELECT COUNT(*), SUM(CASE WHEN in_pos AND in_labor THEN 1 ELSE 0 END) FROM metrics.recon_store_day"
    )[0]
    rate = (matched or 0) / total if total else 0.0
    log(
        "reconciliation_check",
        "INFO" if rate >= threshold else "ERROR",
        store_days=total,
        matched=matched,
        match_rate=round(rate, 4),
        threshold=threshold,
    )
    return rate
