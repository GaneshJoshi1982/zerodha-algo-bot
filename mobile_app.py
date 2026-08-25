import requests
import streamlit as st

# Replace with your deployed Render URL or keep local for testing
BACKEND_URL = "https://zerodha-algo-bot-vb36.onrender.com"

st.set_page_config(page_title="Mobile Bot Control Center", page_icon="📱", layout="centered")

st.title("📱 Mobile Algo Bot Control Center")
st.caption("Connected to Cloud Backend Engine | VWAP + 5M EMA-9 Auto-Trailing Active")

# ==========================================
# 1. EMERGENCY PANIC CONTROL
# ==========================================
st.markdown("---")
if st.button("🚨 EMERGENCY PANIC EXIT ALL", type="primary", use_container_width=True):
    try:
        res = requests.post(f"{BACKEND_URL}/api/order/panic-exit-all").json()
        st.success(f"Emergency Triggered! Closed {res.get('closed_positions', 0)} positions.")
    except Exception as e:
        st.error(f"Error firing panic exit: {e}")

# ==========================================
# 2. ACTIVE POSITIONS & LIVE P&L
# ==========================================
st.markdown("---")
st.subheader("📊 Active Automated Positions")

try:
    positions = requests.get(f"{BACKEND_URL}/api/positions").json()
    open_positions = {k: v for k, v in positions.items() if v.get("status") == "OPEN"}

    if open_positions:
        total_pnl = sum([v.get("unrealized_pnl", 0.0) for v in open_positions.values()])
        st.metric("Total Unrealized P&L", f"₹{total_pnl:,.2f}", delta=f"{total_pnl:,.2f}")

        for pos_id, pos in open_positions.items():
            with st.container():
                st.markdown(f"**{pos.get('tradingsymbol')}** ({pos.get('side')})")
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
    st.warning("⚠️ Waiting for backend server connection or valid Zerodha API session...")

# ==========================================
# 3. MANUAL TRADE ENTRY OVERRIDE (DYNAMIC)
# ==========================================
st.markdown("---")
st.subheader("⚡ Fire Manual Scalp Order")

# Standard Index Lot Sizes
LOT_SIZES = {
    "NIFTY": 75,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "SENSEX": 10,
    "BANKEX": 15
}

symbol = st.selectbox("Index Symbol", list(LOT_SIZES.keys()))

# Dynamically set quantity based on selected index
default_qty = LOT_SIZES[symbol]

tradingsymbol = st.text_input("Trading Symbol", value=f"{symbol}26AUG24200CE")
exchange = "BFO" if symbol in ["SENSEX", "BANKEX"] else "NFO"

# Dynamic instrument token fetch attempt
auto_token = 0
try:
    token_res = requests.get(f"{BACKEND_URL}/api/get-token?symbol={tradingsymbol}").json()
    auto_token = token_res.get("instrument_token", 0)
except Exception:
    pass

token_id = st.number_input("Instrument Token", value=auto_token if auto_token else 256265)
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
        "max_risk_inr": 2000.0
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
# 4. SYSTEM LOGS
# ==========================================
st.markdown("---")
st.subheader("📋 System Audit Logs")
try:
    logs = requests.get(f"{BACKEND_URL}/api/logs").json()
    if logs:
        st.text_area("Live Log Output", value="\n".join(reversed(logs)), height=150)
except Exception:
    pass
