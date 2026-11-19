import pytest

from pipeline.pii import PIIViolation, pseudonymise, scrub


def test_columns_outside_allowlist_are_dropped():
    rows = [
        {
            "shift_id": "S1",
            "store_number": "1014",
            "work_date": "2026-11-13",
            "employee_id": "E1014001",
            "job_code": "COOK",
            "clock_in": "2026-11-13T07:00:00",
            "clock_out": "2026-11-13T15:00:00",
            "employee_name": "Jane Doe",
            "ssn": "999-12-3456",
            "hourly_rate": "21.50",
        }
    ]
    (out,) = scrub("labor_shifts", rows)
    assert "ssn" not in out and "employee_name" not in out and "hourly_rate" not in out
    assert out["job_code"] == "COOK"


def test_employee_id_is_pseudonymised_consistently():
    row = {"shift_id": "S1", "employee_id": "E1014001"}
    (a,) = scrub("labor_shifts", [row])
    (b,) = scrub("labor_shifts", [dict(row)])
    assert a["employee_id"] != "E1014001"
    assert a["employee_id"] == b["employee_id"] == pseudonymise("E1014001")


def test_ssn_hidden_in_allowed_column_fails_the_batch():
    # A vendor puts an SSN in a free-text field we do allow: the load must stop.
    rows = [{"shift_id": "S1", "job_code": "COOK 123-45-6789"}]
    with pytest.raises(PIIViolation):
        scrub("labor_shifts", rows)


def test_card_number_in_pos_field_fails_the_batch():
    rows = [{"check_id": "1", "order_channel": "4111 1111 1111 1111"}]
    with pytest.raises(PIIViolation):
        scrub("pos_sales", rows)


def test_timestamps_are_not_false_positives():
    rows = [{"check_id": "100001", "closed_at": "2026-11-13T19:45:00", "business_date": "2026-11-13"}]
    assert scrub("pos_sales", rows)[0]["check_id"] == "100001"


def test_unknown_source_is_rejected():
    with pytest.raises(KeyError):
        scrub("payroll", [{"anything": 1}])
