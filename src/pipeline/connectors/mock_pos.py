"""In-process mock of the POS API, backed by sample_data/pos/*.json.

Used by ``--mock`` runs and by tests so the real connector code (auth, paging,
retries) runs end to end without network access.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx


def mock_pos_transport(data_dir: str | Path, fail_first: int = 0) -> httpx.MockTransport:
    data_dir = Path(data_dir)
    state = {"failures_left": fail_first}

    def handler(request: httpx.Request) -> httpx.Response:
        if state["failures_left"] > 0:
            state["failures_left"] -= 1
            return httpx.Response(503, headers={"Retry-After": "0"})

        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "mock-token", "expires_in": 3600})

        if request.url.path == "/v1/sales":
            if request.headers.get("Authorization") != "Bearer mock-token":
                return httpx.Response(401)
            business_date = request.url.params["business_date"]
            page = int(request.url.params.get("page", 1))
            size = int(request.url.params.get("page_size", 500))
            path = data_dir / f"sales_{business_date}.json"
            rows = json.loads(path.read_text()) if path.exists() else []
            chunk = rows[(page - 1) * size : page * size]
            next_page = page + 1 if page * size < len(rows) else None
            return httpx.Response(200, json={"data": chunk, "next_page": next_page})

        return httpx.Response(404)

    return httpx.MockTransport(handler)
