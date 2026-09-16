"""Read-only client used by the Streamlit dashboard.

Trading and broker credentials remain on the Oracle server.  This module deliberately
contains no order-placement method.
"""
from __future__ import annotations

from typing import Any, Iterable
import requests


class OracleAPIError(RuntimeError):
    pass


class OracleAuthRequired(OracleAPIError):
    pass


class OracleDashboardClient:
    def __init__(self, base_url: str, api_token: str, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"X-API-Token": api_token})

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(
            method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs
        )
        if response.status_code == 401:
            try:
                detail = response.json().get("detail")
            except Exception:
                detail = None
            if isinstance(detail, dict) and detail.get("state") == "AUTH_REQUIRED":
                raise OracleAuthRequired(detail.get("message", "Zerodha authentication is required."))
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            body = response.text[:500]
            raise OracleAPIError(f"Oracle API {response.status_code}: {body}") from exc
        return response.json()

    def auth_status(self) -> dict:
        return self._request("GET", "/auth/status")

    def auth_login(self) -> dict:
        return self._request("GET", "/auth/login")

    def exchange_request_token(self, request_token: str) -> dict:
        return self._request(
            "POST", "/auth/bridge/exchange", json={"request_token": request_token}
        )

    def trading_monitor(self) -> dict:
        return self._request("GET", "/dashboard/trading-monitor")

    def profile(self) -> dict:
        return self._request("GET", "/dashboard/profile")

    def instruments(self, exchange: str | None = None) -> list[dict]:
        params = {"exchange": exchange} if exchange else None
        data = self._request("GET", "/dashboard/instruments", params=params)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("instruments", "data", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    def quote(self, instruments: Iterable[str] | str) -> dict:
        values = [instruments] if isinstance(instruments, str) else list(instruments)
        return self._request("POST", "/dashboard/quote", json={"instruments": values})

    def ltp(self, instruments: Iterable[str] | str) -> dict:
        # Kite-compatible subset derived from the protected quote response.
        quotes = self.quote(instruments)
        result = {}
        for key, value in quotes.items():
            if isinstance(value, dict):
                result[key] = {
                    "instrument_token": value.get("instrument_token"),
                    "last_price": value.get("last_price"),
                }
        return result

    def historical_data(
        self,
        instrument_token: int,
        from_date: Any,
        to_date: Any,
        interval: str,
        continuous: bool = False,
        oi: bool = False,
    ) -> list[dict]:
        def encode(value: Any) -> str:
            return value.isoformat() if hasattr(value, "isoformat") else str(value)

        payload = {
            "instrument_token": int(instrument_token),
            "from_date": encode(from_date),
            "to_date": encode(to_date),
            "interval": interval,
            "continuous": bool(continuous),
            "oi": bool(oi),
        }
        data = self._request("POST", "/dashboard/historical", json=payload)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("candles", "data", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []
