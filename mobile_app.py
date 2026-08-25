import requests
import streamlit as st

# Replace with your deployed Render URL or local backend
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
# 3. MANUAL TRADE ENTRY OVERRIDE (AUTO-SELECT)
# ==========================================
st.markdown("---")
st.subheader("⚡ Fire Manual Scalp Order")

# Dynamic Index Lot Sizes Mapping (Updated Standard Sizes)
LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
    "SENSEX": 20
}

# Index Selection
symbol = st.selectbox("Index Symbol", list(LOT_SIZES.keys()))
default_qty = LOT_SIZES[symbol]
exchange = "BFO" if symbol in ["SENSEX", "BANKEX"] else "NFO"

# Symbol Constructor Inputs
col_opt, col_strike = st.columns(2)
opt_type = col_opt.selectbox("Option Type", ["CE", "PE"])
strike_price = col_strike.number_input("Strike Price", value=24200 if symbol == "NIFTY" else 52000, step=100)
expiry_code = st.text_input("Expiry Tag (e.g. 26AUG)", value="26AUG")

# Auto-Generated Trading Symbol
auto_tradingsymbol = f"{symbol}{expiry_code}{int(strike_price)}{opt_type}"
tradingsymbol = st.text_input("Trading Symbol (Auto-Generated)", value=auto_tradingsymbol)

# Auto-Fetch Instrument Token from Backend API
auto_token = 0
try:
    token_res = requests.get(f"{BACKEND_URL}/api/get-token?symbol={tradingsymbol}").json()
    auto_token = token_res.get("instrument_token", 0)
except Exception:
    pass

token_id = st.number_input("Instrument Token", value=auto_token if auto_token else 256265)

# Order Controls
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
