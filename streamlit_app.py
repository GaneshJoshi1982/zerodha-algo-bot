"""Phase 2M.3 Streamlit entrypoint.

Preserves the complete legacy analysis application while replacing its runtime Zerodha
session object with the protected Oracle read-only client. The always-on trading engine
remains on Oracle; this process is display/analysis only.
"""
from __future__ import annotations

import streamlit as st

import app as legacy_app
from oracle_client import OracleAPIError, OracleDashboardClient
from trading_monitor_ui import render_auto_trading_monitor


def _secret(name: str) -> str:
    try:
        return str(st.secrets[name]).strip()
    except Exception:
        return ""


def _client() -> OracleDashboardClient | None:
    base_url = _secret("ORACLE_BRIDGE_URL")
    token = _secret("BACKEND_API_TOKEN")
    if not base_url or not token:
        st.error("Streamlit Secrets must contain ORACLE_BRIDGE_URL and BACKEND_API_TOKEN.")
        return None
    return OracleDashboardClient(base_url, token)


def _handle_callback(client: OracleDashboardClient) -> None:
    request_token = st.query_params.get("request_token")
    if isinstance(request_token, list):
        request_token = request_token[0] if request_token else None
    if not request_token:
        return
    try:
        client.exchange_request_token(str(request_token).strip())
    except Exception as exc:
        st.error(f"Zerodha login exchange failed: {exc}")
        return
    st.query_params.clear()
    st.success("Zerodha authentication completed securely on Oracle.")
    st.rerun()


def _show_login(client: OracleDashboardClient) -> None:
    st.warning("Zerodha authentication is required. Oracle will keep PAPER execution blocked until authentication succeeds.")
    try:
        payload = client.auth_login()
        url = payload.get("login_url") or payload.get("url")
        if url:
            st.link_button("Login with Zerodha", url, type="primary")
        else:
            st.error("Oracle did not return a Zerodha login URL.")
    except Exception as exc:
        st.error(f"Unable to obtain Zerodha login link: {exc}")


def oracle_authenticated_kite(client: OracleDashboardClient):
    """Drop-in replacement for legacy get_authenticated_kite()."""
    try:
        status = client.auth_status()
    except OracleAPIError as exc:
        st.error(f"Oracle authentication service unavailable: {exc}")
        return None

    if bool(status.get("authenticated")) or status.get("state") == "AUTHENTICATED":
        return client
    _show_login(client)
    return None


def main() -> None:
    client = _client()
    if client is None:
        return

    _handle_callback(client)

    # Preserve every existing scanner/analysis path. Only the function that supplies
    # the Kite-like transport is replaced; calls are proxied to protected Oracle APIs.
    legacy_app.get_authenticated_kite = lambda: oracle_authenticated_kite(client)

    # The monitor is rendered by the legacy app integration in the next cutover step.
    # Until then, the full legacy UI remains byte-for-byte preserved by calling main().
    legacy_app.main()


if __name__ == "__main__":
    main()
