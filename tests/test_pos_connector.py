from datetime import date

import httpx
import pytest

from pipeline import retry as retry_mod
from pipeline.config import REPO_ROOT
from pipeline.connectors.mock_pos import mock_pos_transport
from pipeline.connectors.pos_api import POSClient


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)


def client(transport, page_size=500):
    return POSClient("https://mock-pos.local", "id", "secret", transport=transport, page_size=page_size)


def test_paginates_through_all_checks():
    data_dir = REPO_ROOT / "sample_data" / "pos"
    all_rows = client(mock_pos_transport(data_dir)).fetch_sales(date(2026, 11, 13))
    paged_rows = client(mock_pos_transport(data_dir), page_size=25).fetch_sales(date(2026, 11, 13))
    assert len(all_rows) > 25
    assert [r["check_id"] for r in paged_rows] == [r["check_id"] for r in all_rows]


def test_retries_transient_503s():
    transport = mock_pos_transport(REPO_ROOT / "sample_data" / "pos", fail_first=2)
    rows = client(transport).fetch_sales(date(2026, 11, 13))
    assert rows


def test_gives_up_after_max_attempts():
    transport = httpx.MockTransport(lambda req: httpx.Response(503))
    with pytest.raises(retry_mod.RetryableHTTPError):
        client(transport).fetch_sales(date(2026, 11, 13))


def test_auth_failure_is_not_retried_forever():
    transport = httpx.MockTransport(lambda req: httpx.Response(400, json={"error": "invalid_client"}))
    with pytest.raises(httpx.HTTPStatusError):
        client(transport).fetch_sales(date(2026, 11, 13))


def test_refreshes_token_after_401():
    calls = {"token": 0, "sales": 0}

    def handler(request):
        if request.url.path == "/oauth/token":
            calls["token"] += 1
            return httpx.Response(200, json={"access_token": f"t{calls['token']}", "expires_in": 3600})
        calls["sales"] += 1
        if request.headers["Authorization"] == "Bearer t1":
            return httpx.Response(401)
        return httpx.Response(200, json={"data": [{"check_id": "1"}], "next_page": None})

    rows = client(httpx.MockTransport(handler)).fetch_sales(date(2026, 11, 13))
    assert rows == [{"check_id": "1"}]
    assert calls["token"] == 2
