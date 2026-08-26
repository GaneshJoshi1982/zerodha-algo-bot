import requests
import streamlit as st

BACKEND_URL = "https://zerodha-algo-bot-vb36.onrender.com"

st.set_page_config(
    page_title="Mobile Bot Control Center", page_icon="📱", layout="centered"
)

st.title("📱 Mobile Algo Bot Control Center")
st.caption(
    "Connected to Cloud Backend Engine | LinReg 3M + VWAP Auto-Trailing Active"
)

# ==========================================
# 1. 2FA AUTO-LOGIN & PANIC CONTROLS
# ==========================================
st.markdown("---")
col_login, col_panic = st.columns(2)

with col_login:
    if st.button(
        "🔑 AUTO-LOGIN ZERODHA", type="secondary", use_container_width=True
    ):
        try:
            res = requests.get(f"{BACKEND_URL}/api/auto-login").json()
            if res.get("status") == "SUCCESS":
                st.success("✅ Today's Token Generated!")
            else:
                st.error(f"❌ Login Error: {res.get('error')}")
        except Exception as e:
            st.error(f"Backend Server Offline: {e}")

with col_panic:
    if st.button(
        "🚨 PANIC EXIT ALL", type="primary", use_container_width=True
    ):
        try:
            res = requests.post(
                f"{BACKEND_URL}/api/order/panic-exit-all"
            ).json()
            st.success(
                f"Panic Exit Fired! Closed {res.get('closed_positions', 0)} positions."
            )
        except Exception as e:
            st.error(f"Panic Error: {e}")

# ==========================================
# 2. ACTIVE POSITIONS & LIVE P&L
# ==========================================
st.markdown("---")
st.subheader("📊 Active Automated Positions")

try:
    positions = requests.get(f"{BACKEND_URL}/api/positions").json()
    open_positions = {
        k: v for k, v in positions.items() if v.get("status") == "OPEN"
    }

    if open_positions:
        total_pnl = sum(
            [v.get("unrealized_pnl", 0.0) for v in open_positions.values()]
        )
        st.metric(
            "Total Unrealized P&L",
            f"₹{total_pnl:,.2f}",
            delta=f"{total_pnl:,.2f}",
        )

        for pos_id, pos in open_positions.items():
            with st.container():
                st.markdown(
                    f"**{pos.get('tradingsymbol')}** ({pos.get('side')})"
                )
                col1, col2 = st.columns(2)
                col1.write(f"Qty: **{pos.get('quantity')}**")
                col1.write(f"Entry: **₹{pos.get('entry_price')}**")
                col1.write(f"LTP: **₹{pos.get('current_ltp')}**")
                col2.write(f"Trailing SL: **₹{pos.get('current_sl')}**")
                col2.write(f"Target: **₹{pos.get('target_price')}**")
                col2.write(f"P&L: **₹{pos.get('unrealized_pnl')}**")
                st.divider()
    else:
        st.info("No active open positions monitored by backend.")
except Exception:
    st.warning(
        "⚠️ Waiting for backend server connection or valid Zerodha API session... Click Auto-Login above!"
    )

# ==========================================
# 3. FULLY AUTOMATED TRADE ENTRY OVERRIDE
# ==========================================
st.markdown("---")
st.subheader("⚡ Fire Manual Scalp Order")

LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
    "SENSEX": 20,
}

symbol = st.selectbox("Index Symbol", list(LOT_SIZES.keys()))
default_qty = LOT_SIZES[symbol]
exchange = "BFO" if symbol in ["SENSEX", "BANKEX"] else "NFO"

col_opt, col_strike = st.columns(2)
opt_type = col_opt.selectbox("Option Type", ["CE", "PE"])
default_strike = (
    24200 if symbol == "NIFTY" else (52000 if symbol == "BANKNIFTY" else 80000)
)
strike_price = col_strike.number_input(
    "Strike Price", value=default_strike, step=100
)

# Auto-Fetch Symbol & Token from Backend API
auto_symbol = ""
auto_token = 0
expiry_info = ""

try:
    url = f"{BACKEND_URL}/api/get-symbol?index={symbol}&strike={int(strike_price)}&type={opt_type}"
    res = requests.get(url).json()
    if res.get("status") == "SUCCESS":
        auto_symbol = res.get("tradingsymbol")
        auto_token = res.get("instrument_token")
        expiry_info = res.get("expiry")
except Exception:
    pass

tradingsymbol = st.text_input(
    "Trading Symbol (Auto-Selected)",
    value=auto_symbol
    if auto_symbol
    else f"{symbol}26AUG{int(strike_price)}{opt_type}",
)
token_id = st.number_input(
    "Instrument Token (Auto-Fetched)",
    value=auto_token if auto_token else 256265,
)

if expiry_info:
    st.caption(f"🗓️ Nearest Active Contract Expiry: **{expiry_info}**")

side = st.radio("Side", ["BUY", "SELL"], horizontal=True)
qty = st.number_input("Quantity", value=default_qty, step=default_qty)
entry_price = st.number_input("Limit Entry Rate (₹)", value=100.0, step=1.0)

if st.button("🚀 SUBMIT ORDER TO BOT", type="primary", use_container_width=True):
    payload = {
        "symbol": symbol,
        "exchange": exchange,
        "tradingsymbol": tradingsymbol,
        "instrument_token": token_id,
        "transaction_type": side,
        "quantity": qty,
        "price": entry_price,
        "max_risk_inr": 2000.0,
    }
    try:
        res = requests.post(f"{BACKEND_URL}/api/order/submit", json=payload)
        if res.status_code == 200:
            st.success("✅ Order Transmitted to Cloud Engine!")
        else:
            st.error(f"❌ Rejected: {res.json().get('detail')}")
    except Exception as e:
        st.error(f"Execution Error: {e}")

# ==========================================
# 4. SYSTEM AUDIT LOGS
# ==========================================
st.markdown("---")
st.subheader("📋 System Audit Logs")
try:
    logs = requests.get(f"{BACKEND_URL}/api/logs").json()
    if logs:
        st.text_area(
            "Live Log Output", value="\n".join(reversed(logs)), height=150
        )
except Exception:
    pass
