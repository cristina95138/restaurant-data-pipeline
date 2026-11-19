"""End-to-end: mock sources -> raw layer, plus idempotency, schema drift and checks."""

from datetime import date

import pytest

from pipeline.checks import check_freshness, check_reconciliation
from pipeline.connectors.labor_sftp import SchemaDrift, fetch_shifts
from pipeline.runner import run_labor, run_pos
from pipeline.warehouse import get_warehouse

DAY = date(2026, 11, 13)


def test_ingest_lands_rows_without_personal_data(settings):
    wh = get_warehouse(settings)
    assert run_pos(settings, wh, DAY, mock=True) > 0
    assert run_labor(settings, wh, DAY, mock=True) > 0

    labor_cols = {r[0] for r in wh.query("DESCRIBE raw.labor_shifts")}
    pos_cols = {r[0] for r in wh.query("DESCRIBE raw.pos_sales")}
    assert not labor_cols & {"ssn", "employee_name", "hourly_rate"}
    assert not pos_cols & {"card_last4", "customer_email"}


def test_rerunning_a_day_is_idempotent(settings):
    wh = get_warehouse(settings)
    first = run_pos(settings, wh, DAY, mock=True)
    run_pos(settings, wh, DAY, mock=True)
    (count,) = wh.query("SELECT COUNT(*) FROM raw.pos_sales")[0]
    assert count == first


def test_missing_required_column_fails_loudly(tmp_path):
    (tmp_path / "shifts_2026-11-13.csv").write_text("shift_id,store_number\nS1,1014\n")

    class Dir:
        def read_text(self, name):
            return (tmp_path / name).read_text()

    with pytest.raises(SchemaDrift):
        fetch_shifts(Dir(), DAY)


def test_freshness_flags_stale_sources(settings):
    wh = get_warehouse(settings)
    run_pos(settings, wh, DAY, mock=True)
    run_labor(settings, wh, DAY, mock=True)
    assert all(check_freshness(wh, date(2026, 11, 14)).values())
    assert not any(check_freshness(wh, date(2026, 11, 20)).values())


def test_reconciliation_rate(settings):
    import duckdb

    con = duckdb.connect(settings.duckdb_path)
    con.execute("CREATE SCHEMA metrics")
    con.execute("CREATE TABLE metrics.recon_store_day (store_key VARCHAR, business_date DATE, in_pos BOOLEAN, in_labor BOOLEAN)")
    from datetime import timedelta

    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(100)]
    rows = [("S1", d, True, True) for d in days[:99]] + [("S1", days[99], True, False)]  # 99 of 100 matched
    con.executemany("INSERT INTO metrics.recon_store_day VALUES (?, ?, ?, ?)", rows)
    con.close()

    wh = get_warehouse(settings)
    assert check_reconciliation(wh) == pytest.approx(0.99)
