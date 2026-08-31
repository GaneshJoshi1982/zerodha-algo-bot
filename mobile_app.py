import requests
import streamlit as st

BACKEND_URL = "http://92.4.85.1:10000"
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

# Process incoming token if redirected from Zerodha
if "request_token" in st.query_params:
    token = st.query_params["request_token"]
    st.info("🔄 Processing Zerodha Authentication...")

    try:
        res = requests.get(
            f"{BACKEND_URL}/callback",
            params={"request_token": token},
            timeout=10,
        )
        st.query_params.clear()
        if res.status_code == 200:
            st.success("✅ Connected successfully!")
            st.rerun()
        else:
            st.error(f"❌ Authentication Error: {res.text}")
    except Exception as e:
        st.query_params.clear()
        st.error(f"❌ Connection to Oracle failed: {e}")

# Fetch System Health from Oracle Backend
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

    if not health_data.get("login_authenticated", False):
        st.link_button(
            label="🔑 Click Here to Login to Zerodha",
            url=KITE_LOGIN_URL,
            use_container_width=True,
            type="primary",
        )

    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Kite Session",
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
    st.error("🔴 **SERVER UNREACHABLE:** Oracle Cloud backend is offline.")

st.divider()

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
                sq = requests.post(f"{BACKEND_URL}/square_off", timeout=5).json()
                st.warning(f"Square Off Signal: {sq.get('message')}")
            except Exception as e:
                st.error(f"Execution Error: {e}")

    with col_btn2:
        if st.button("🔄 Sync Account & Margins"):
            try:
                sy = requests.get(f"{BACKEND_URL}/sync", timeout=5).json()
                st.success(f"Available Equity Margin: ₹{sy.get('margin')}")
            except Exception as e:
                st.error(f"Sync Failed: {e}")

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
                "Quantity", min_value=1, value=15, step=1
            )
            order_type = st.selectbox("Order Type", ["MARKET", "LIMIT"])

        price = 0.0
        if order_type == "LIMIT":
            price = st.number_input("Limit Price", min_value=0.0, value=100.0)

        if st.form_submit_button("⚡ Push Trade Order", type="primary"):
            payload = {
                "symbol": symbol,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "order_type": order_type,
                "price": price,
            }
            try:
                tr = requests.post(
                    f"{BACKEND_URL}/push_trade", json=payload, timeout=5
                ).json()
                st.success(f"Order Placed! Order ID: {tr.get('order_id')}")
            except Exception as e:
                st.error(f"Trade Failed: {e}")

with tab3:
    st.subheader("System Event Logs")
    if st.button("Refresh Logs"):
        try:
            lg = requests.get(f"{BACKEND_URL}/logs", timeout=3).json()
            st.code(lg.get("logs"), language="text")
        except Exception as e:
            st.error(f"Error loading logs: {e}")
