"""Secure Streamlit entrypoint for the Oracle-backed dashboard cutover.

This module is intentionally separate from the large legacy analysis file while the
cutover is validated. It never receives the Zerodha API secret or access token and
contains no broker order-placement capability.
"""
from __future__ import annotations

import streamlit as st

from oracle_client import OracleAPIError, OracleAuthRequired, OracleDashboardClient
from trading_monitor_ui import render_auto_trading_monitor


def _secret(name: str) -> str:
    try:
        value = st.secrets[name]
    except Exception:
        value = ""
    return str(value).strip()


def build_oracle_client() -> OracleDashboardClient | None:
    base_url = _secret("ORACLE_BRIDGE_URL")
    api_token = _secret("BACKEND_API_TOKEN")
    if not base_url or not api_token:
        st.error(
            "Streamlit Secrets are incomplete. ORACLE_BRIDGE_URL and "
            "BACKEND_API_TOKEN are required."
        )
        return None
    return OracleDashboardClient(base_url=base_url, api_token=api_token)


def process_zerodha_callback(client: OracleDashboardClient) -> None:
    request_token = st.query_params.get("request_token")
    if isinstance(request_token, list):
        request_token = request_token[0] if request_token else None
    if not request_token:
        return

    try:
        client.exchange_request_token(str(request_token).strip())
    except Exception as exc:
        st.error(f"Zerodha authentication could not be completed: {exc}")
        return

    st.query_params.clear()
    st.success("Zerodha authentication completed securely on Oracle.")
    st.rerun()


def render_login(client: OracleDashboardClient) -> bool:
    try:
        status = client.auth_status()
    except OracleAPIError as exc:
        st.error(f"Oracle authentication service unavailable: {exc}")
        return False

    authenticated = bool(status.get("authenticated")) or status.get("state") == "AUTHENTICATED"
    if authenticated:
        return True

    st.warning(
        "Zerodha authentication is required. Automatic PAPER execution remains "
        "blocked until Oracle validates a fresh Zerodha session."
    )
    try:
        login = client.auth_login()
        login_url = login.get("login_url") or login.get("url")
    except Exception as exc:
        st.error(f"Unable to create Zerodha login link: {exc}")
        return False

    if login_url:
        st.link_button("Login with Zerodha", login_url, type="primary")
    else:
        st.error("Oracle did not return a Zerodha login URL.")
    return False


def run_secure_shell() -> OracleDashboardClient | None:
    st.set_page_config(
        page_title="Institutional F&O & Cash Intelligence Terminal",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    client = build_oracle_client()
    if client is None:
        return None

    process_zerodha_callback(client)
    st.title("⚡ Zerodha Trading Bot — Oracle Monitor")
    render_auto_trading_monitor(client)
    return client


if __name__ == "__main__":
    run_secure_shell()
