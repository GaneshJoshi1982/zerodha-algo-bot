"""Streamlit UI for the always-on Oracle PAPER trading engine.

The dashboard may change only the persistent server-side auto-trading ON/OFF control.
It cannot place, modify, or cancel broker orders. OFF blocks new entries only; Oracle
continues market-data collection and lifecycle management for any open position.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from oracle_client import OracleAPIError, OracleAuthRequired


def _money(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _text(value: Any, default: str = "—") -> str:
    return default if value in (None, "") else str(value)


def _position_rows(indices: dict) -> list[dict]:
    rows = []
    for index_name, state in indices.items():
        pos = state.get("open_position") or {}
        signal = state.get("latest_signal") or {}
        rows.append(
            {
                "Index": index_name,
                "Signal": signal.get("action", "HOLD"),
                "Signal candle": signal.get("candle_time"),
                "Open contract": pos.get("tradingsymbol", "—"),
                "Qty": pos.get("quantity", "—"),
                "Entry": pos.get("entry_price"),
                "Last": pos.get("last_price"),
                "Highest": pos.get("highest_price"),
                "Stop": pos.get("stop_price"),
                "Breakeven": bool(pos.get("breakeven_active", False)),
                "Trailing": bool(pos.get("trailing_active", False)),
                "Gross P&L": pos.get("gross_pnl"),
                "Completed today": state.get("completed_trades_today", 0),
                "Slots left": state.get("remaining_trade_slots", 0),
            }
        )
    return rows


def _render_engine_control(client) -> None:
    st.markdown("#### Trading Engine Control")
    try:
        control = client.trading_engine_control()
    except OracleAPIError as exc:
        st.error(f"Trading Engine control unavailable: {exc}")
        return
    except Exception as exc:
        st.error(f"Trading Engine control connection error: {exc}")
        return

    enabled = bool(control.get("enabled", False))
    left, right = st.columns([2, 1])
    with left:
        if enabled:
            st.success("Trading Engine: ON — Oracle may open new PAPER trades only when all existing safety gates permit.")
        else:
            st.warning("Trading Engine: OFF — new automated entries are blocked.")
        st.caption(
            "This setting is stored on Oracle. Data collection and management of existing "
            "positions continue when the Trading Engine is OFF."
        )
    with right:
        label = "Turn Trading Engine OFF" if enabled else "Turn Trading Engine ON"
        if st.button(label, type="primary" if not enabled else "secondary", use_container_width=True):
            try:
                updated = client.set_trading_engine(not enabled)
            except OracleAPIError as exc:
                st.error(f"Unable to change Trading Engine state: {exc}")
                return
            except Exception as exc:
                st.error(f"Trading Engine control connection error: {exc}")
                return
            new_state = bool(updated.get("enabled", False))
            st.session_state["engine_control_flash"] = (
                "success" if new_state else "info",
                f"Trading Engine is now {'ON' if new_state else 'OFF'} on Oracle.",
            )
            st.rerun()

    flash = st.session_state.pop("engine_control_flash", None)
    if flash:
        level, message = flash
        if level == "success":
            st.success(message)
        else:
            st.info(message)


def render_auto_trading_monitor(client) -> None:
    st.subheader("🤖 Auto Trading Monitor")
    st.caption(
        "Oracle is the always-on trading brain. Closing or refreshing this dashboard "
        "does not change the server-side Trading Engine state."
    )

    _render_engine_control(client)
    st.divider()

    try:
        monitor = client.trading_monitor()
    except OracleAuthRequired:
        st.warning("Zerodha authentication is required. The Oracle engine remains fail-safe and execution-ineligible until authentication succeeds.")
        return
    except OracleAPIError as exc:
        st.error(f"Oracle Trading Monitor unavailable: {exc}")
        return
    except Exception as exc:
        st.error(f"Trading Monitor connection error: {exc}")
        return

    auth = monitor.get("authentication") or {}
    scheduler = monitor.get("scheduler") or {}
    health = monitor.get("data_health") or {}
    calendar = monitor.get("market_calendar") or {}

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Mode", _text(monitor.get("mode")))
    c2.metric("Zerodha", "Connected" if auth.get("authenticated") else _text(auth.get("state"), "AUTH_REQUIRED"))
    c3.metric("Scheduler", "Running" if scheduler.get("running") else "Stopped")
    c4.metric("Market", _text(calendar.get("session_state")))
    c5.metric("Execution eligible", "YES" if health.get("execution_eligible") else "NO")

    if monitor.get("live_execution_implemented"):
        st.error("Safety warning: server reports LIVE execution implemented.")
    else:
        st.info("Safety: LIVE broker execution is locked. Trading Engine control applies to PAPER new entries only.")

    if not health.get("healthy"):
        st.warning(f"Market data health: {_text(health.get('reason'), 'NOT HEALTHY')}. Automatic entry remains blocked when required data is unhealthy.")

    rows = _position_rows(monitor.get("indices") or {})
    if rows:
        df = pd.DataFrame(rows)
        for col in ("Entry", "Last", "Highest", "Stop", "Gross P&L"):
            if col in df.columns:
                df[col] = df[col].map(_money)
        st.markdown("#### Index / Position Status")
        st.dataframe(df, use_container_width=True, hide_index=True)

    closed = monitor.get("closed_trades_today") or []
    st.markdown("#### Completed Trades Today")
    if closed:
        closed_df = pd.DataFrame(closed)
        preferred = [
            "underlying", "tradingsymbol", "option_type", "quantity",
            "entry_price", "exit_price", "gross_pnl", "gross_pnl_pct",
            "entry_time", "exit_time", "trade_duration_seconds", "exit_reason",
        ]
        columns = [c for c in preferred if c in closed_df.columns]
        st.dataframe(closed_df[columns] if columns else closed_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No completed PAPER trades recorded for the current trading day.")

    with st.expander("Engine diagnostics"):
        st.write("As of:", _text(monitor.get("as_of")))
        st.write("Scheduler heartbeat:", _text(scheduler.get("heartbeat")))
        st.write("Last lifecycle monitor:", _text(scheduler.get("last_paper_lifecycle_at")))
        st.write("Data health checked:", _text(health.get("checked_at")))
        st.write("Chain analytics eligible:", bool(health.get("chain_analytics_eligible", False)))
