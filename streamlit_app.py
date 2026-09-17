"""Oracle-backed Streamlit dashboard entrypoint.

Oracle is the always-on trading brain. Streamlit is monitor/analysis only: closing or
refreshing this screen cannot stop the PAPER engine.
"""
from __future__ import annotations

import hashlib

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
    """Consume a Zerodha callback exactly once per Streamlit browser session.

    The raw request_token is never persisted or displayed. Query parameters are cleared
    before the network exchange so Streamlit reruns cannot accidentally reuse a one-time
    Zerodha request token. A short SHA-256 fingerprint is kept only in session state to
    suppress duplicate handling of the same callback within the current browser session.
    """
    request_token = st.query_params.get("request_token")
    if isinstance(request_token, list):
        request_token = request_token[0] if request_token else None
    if not request_token:
        return

    request_token = str(request_token).strip()
    if not request_token:
        st.query_params.clear()
        return

    fingerprint = hashlib.sha256(request_token.encode("utf-8")).hexdigest()[:16]
    previous = st.session_state.get("zerodha_callback_fingerprint")

    # Remove the sensitive, one-time callback token from the browser URL immediately.
    # This also prevents Streamlit reruns from retrying a consumed/failed request token.
    st.query_params.clear()

    if previous == fingerprint:
        return
    st.session_state["zerodha_callback_fingerprint"] = fingerprint

    try:
        client.exchange_request_token(request_token)
    except Exception as exc:
        st.session_state["zerodha_auth_flash"] = (
            "error",
            f"Zerodha login exchange failed: {exc}",
        )
        st.rerun()

    st.session_state["zerodha_auth_flash"] = (
        "success",
        "Zerodha authentication completed securely on Oracle.",
    )
    st.rerun()


def _show_auth_flash() -> None:
    flash = st.session_state.pop("zerodha_auth_flash", None)
    if not flash:
        return
    level, message = flash
    if level == "success":
        st.success(message)
    else:
        st.error(message)


def _show_login(client: OracleDashboardClient) -> None:
    st.warning("Zerodha authentication is required. Oracle keeps PAPER execution blocked until authentication succeeds.")
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
    try:
        status = client.auth_status()
    except OracleAPIError as exc:
        st.error(f"Oracle authentication service unavailable: {exc}")
        return None
    if bool(status.get("authenticated")) or status.get("state") == "AUTHENTICATED":
        st.success("Zerodha Connected")
        return client
    _show_login(client)
    return None


def main() -> None:
    st.set_page_config(page_title="Institutional F&O & Cash Intelligence Terminal", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")
    client = _client()
    if client is None:
        return
    _handle_callback(client)
    _show_auth_flash()

    st.sidebar.title("⚡ Zerodha Trading System")
    workspace = st.sidebar.radio("Workspace", ["🤖 Auto Trading Monitor", "📊 Analysis Dashboard"], key="oracle_workspace")
    st.sidebar.caption("Oracle trading continues independently of this screen.")

    if workspace == "🤖 Auto Trading Monitor":
        st.title("⚡ Zerodha Trading Bot")
        try:
            auth = client.auth_status()
            if bool(auth.get("authenticated")) or auth.get("state") == "AUTHENTICATED":
                st.success("Zerodha Connected")
            else:
                _show_login(client)
        except OracleAPIError as exc:
            st.error(f"Oracle authentication service unavailable: {exc}")
        render_auto_trading_monitor(client)
        return

    # Preserve every legacy analysis/scanner path. Only authentication and market-data
    # transport are substituted with protected Oracle calls.
    legacy_app.get_authenticated_kite = lambda: oracle_authenticated_kite(client)
    legacy_app.st.set_page_config = lambda *args, **kwargs: None
    legacy_app.main()


if __name__ == "__main__":
    main()
