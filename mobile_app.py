import requests
import streamlit as st

BACKEND_URL = "http://92.4.85.1:10000"  # Oracle Cloud Static IP
KITE_API_KEY = "magym2s4yk13gsze"
KITE_LOGIN_URL = (
    f"https://kite.zerodha.com/connect/login?v=3&api_key={KITE_API_KEY}"
)

st.set_page_config(
    page_title="Zerodha Trading Bot",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.title("⚡ Zerodha Algorithmic Trading Terminal")

# ------------------------------------------------------------------------------
# 1. Process Request Token automatically and clean URL parameters
# ------------------------------------------------------------------------------
if "request_token" in st.query_params:
    req_token = st.query_params["request_token"]

    with st.spinner("🔄 Authenticating session with Oracle Backend..."):
        try:
            callback_res = requests.get(
                f"{BACKEND_URL}/callback",
                params={"request_token": req_token},
                timeout=10,
            )

            # Instantly clear query params before rerunning
            st.query_params.clear()

            if callback_res.status_code == 200:
                st.success("✅ Connected to Zerodha successfully!")
                st.rerun()
            else:
                err_msg = callback_res.json().get(
                    "detail", "Token exchange failed"
                )
                st.error(f"❌ Login Failed: {err_msg}")
        except Exception as e:
            st.query_params.clear()
            st.error(f"❌ Could not contact backend: {e}")

# ------------------------------------------------------------------------------
# 2. Fetch Backend Health Status & Banner
# ------------------------------------------------------------------------------
health_data = {}
try:
    res = requests.get(f"{BACKEND_URL}/health", timeout=3).json()
    status_color = res.get("status", "RED")
    status_msg = res.get("message", "Offline")
    health_data = res.get("checks", {})

    if status_color == "GREEN":
        st.success(f"🟢 **SYSTEM ACTIVE:** {status_msg}")
    else:
        st.error(f"🔴 **SYSTEM DISCONNECTED:** {status_msg}")

    # Direct Kite Connect Login Button
    if not health_data.get("login_authenticated", False):
        st.link_button(
            label="🔑 Click Here to Login to Zerodha",
            url=KITE_LOGIN_URL,
            use_container_width=True,
            type="primary",
        )

    # Connection Matrix
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Kite Login",
        (
            "Connected"
            if health_data.get("login_authenticated")
            else "Disconnected"
        ),
    )
    col2.metric(
        "IP Whitelist (92.4.85.1)",
        "Active" if health_data.get("ip_whitelisted") else "Pending",
    )
    col3.metric(
        "Cloud Engine",
        "Running" if health_data.get("service_active") else "Stopped",
    )

except Exception:
    st.error(
        "🔴 **SERVER UNREACHABLE:** Oracle Cloud service is not responding or port 10000 is closed."
    )

st.divider()

# ------------------------------------------------------------------------------
# 3. Multi-Tab Navigation Interface
# ------------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(
    ["⚙️ Strategy Controls", "🚀 Push Manual Trade", "📋 System Audit Logs"]
)

with tab1:
    st.subheader("Strategy Parameters & Session Controls")
    st.text("Indices Enabled: NIFTY 50 | BANKNIFTY | FINNIFTY")
    st.text("Execution Rules: Max 2 trades/session | Hard Exit @ 3:05 PM")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🚨 Emergency Square Off All", type="primary"):
            try:
                sq_res = requests.post(
                    f"{BACKEND_URL}/square_off", timeout=5
                ).json()
                st.warning(
                    f"Square off status: {sq_res.get('message', 'Signal Sent')}"
                )
            except Exception as e:
                st.error(f"Failed to execute square off: {e}")

    with col_btn2:
        if st.button("🔄 Sync Account & Margins"):
            with st.spinner("Syncing with Zerodha..."):
                try:
                    sync_res = requests.get(
                        f"{BACKEND_URL}/sync", timeout=5
                    ).json()
                    if sync_res.get("status") == "SUCCESS":
                        st.success(
                            f"Synced! Margin Info: {sync_res.get('margin', 'N/A')}"
                        )
                    else:
                        st.error("Sync failed: Check backend connection.")
                except Exception as e:
                    st.error(f"Sync failed: {e}")

with tab2:
    st.subheader("🚀 Push Manual Signal / Instant Trade")
    with st.form("push_trade_form"):
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            symbol = st.text_input("Trading Symbol", value="NIFTY26AUG24000CE")
            transaction_type = st.radio(
                "Transaction Type", ["BUY", "SELL"], horizontal=True
            )
        with col_t2:
            quantity = st.number_input(
                "Quantity (Lots/Units)", min_value=1, value=15, step=1
            )
            order_type = st.selectbox("Order Type", ["MARKET", "LIMIT"])

        price = 0.0
        if order_type == "LIMIT":
            price = st.number_input("Limit Price", min_value=0.0, value=100.0)

        submit_trade = st.form_submit_button(
            "⚡ Push Trade Order to Market", type="primary"
        )

        if submit_trade:
            payload = {
                "symbol": symbol,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "order_type": order_type,
                "price": price,
            }
            try:
                trade_res = requests.post(
                    f"{BACKEND_URL}/push_trade", json=payload, timeout=5
                ).json()
                if trade_res.get("status") == "SUCCESS":
                    st.success(
                        f"✅ Order Placed Successfully! Order ID: {trade_res.get('order_id', 'N/A')}"
                    )
                else:
                    st.error(
                        f"❌ Trade Rejected: {trade_res.get('detail', 'Unknown error')}"
                    )
            except Exception as e:
                st.error(f"❌ Failed to push trade: {e}")

with tab3:
    st.subheader("System Event Logs")
    if st.button("Refresh Logs"):
        try:
            logs_res = requests.get(f"{BACKEND_URL}/logs", timeout=3).json()
            st.code(logs_res.get("logs", "No logs found"), language="text")
        except Exception as e:
            st.error(f"Failed to load logs: {e}")
