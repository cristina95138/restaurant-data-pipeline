"""POS sales connector: REST API with OAuth2 client-credentials auth and pagination."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date

import httpx

from ..logging_utils import log
from ..retry import RetryableHTTPError, raise_for_retryable, with_retries


@dataclass
class POSClient:
    base_url: str
    client_id: str
    client_secret: str
    transport: httpx.BaseTransport | None = None  # injectable for tests / local mock
    page_size: int = 500
    _token: str | None = field(default=None, init=False, repr=False)
    _token_expiry: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._http = httpx.Client(base_url=self.base_url, transport=self.transport, timeout=30.0)

    # --- auth -----------------------------------------------------------------
    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        def request() -> httpx.Response:
            return raise_for_retryable(
                self._http.post(
                    "/oauth/token",
                    data={"grant_type": "client_credentials"},
                    auth=(self.client_id, self.client_secret),
                )
            )

        body = with_retries(request).json()
        self._token = body["access_token"]
        self._token_expiry = time.time() + int(body.get("expires_in", 3600))
        return self._token

    # --- data -----------------------------------------------------------------
    def fetch_sales(self, business_date: date) -> list[dict]:
        """Return every closed check for one business date, following pagination."""
        rows: list[dict] = []
        page: int | None = 1
        while page is not None:
            def request(current: int = page) -> httpx.Response:
                response = self._http.get(
                    "/v1/sales",
                    params={
                        "business_date": business_date.isoformat(),
                        "page": current,
                        "page_size": self.page_size,
                    },
                    headers={"Authorization": f"Bearer {self._access_token()}"},
                )
                if response.status_code == 401:  # token revoked early: refresh and retry
                    self._token = None
                    raise RetryableHTTPError(response)
                return raise_for_retryable(response)

            body = with_retries(request).json()
            rows.extend(body["data"])
            page = body.get("next_page")

        log("pos_fetched", business_date=business_date, rows=len(rows))
        return rows
