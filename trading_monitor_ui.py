"""Streamlit UI for the always-on Oracle PAPER trading engine.

Display only: this module cannot place, modify, or cancel broker orders.
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


def render_auto_trading_monitor(client) -> None:
    st.subheader("🤖 Auto Trading Monitor")
    st.caption(
        "Read-only view of the always-on Oracle trading engine. "
        "Closing or refreshing this dashboard does not stop the server engine."
    )

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
        st.info("Safety: LIVE broker execution is locked. Monitor is read-only.")

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
