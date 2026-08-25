import requests
import streamlit as st

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Mobile Bot Control Center", page_icon="📱", layout="narrow")

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
    open_positions = {k: v for k, v in positions.items() if v["status"] == "OPEN"}

    if open_positions:
        total_pnl = sum([v["unrealized_pnl"] for v in open_positions.values()])
        st.metric("Total Unrealized P&L", f"₹{total_pnl:,.2f}", delta=f"{total_pnl:,.2f}")

        for pos_id, pos in open_positions.items():
            with st.container():
                st.markdown(f"**{pos['tradingsymbol']}** ({pos['side']})")
                col1, col2 = st.columns(2)
                col1.write(f"Qty: **{pos['quantity']}**")
                col1.write(f"Entry: **₹{pos['entry_price']}**")
                col1.write(f"LTP: **₹{pos['current_ltp']}**")
                col2.write(f"Trailing SL: **₹{pos['current_sl']}**")
                col2.write(f"Target: **₹{pos['target_price']}**")
                col2.write(f"P&L: **₹{pos['unrealized_pnl']}**")
                st.divider()
    else:
        st.info("No active open positions monitored by backend.")
except Exception:
    st.warning("⚠️ Waiting for backend server connection...")

# ==========================================
# 3. MANUAL TRADE ENTRY OVERRIDE
# ==========================================
st.markdown("---")
st.subheader("⚡ Fire Manual Scalp Order")

symbol = st.selectbox("Index Symbol", ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX"])
tradingsymbol = st.text_input("Trading Symbol", value="NIFTY26AUG24200CE")
exchange = "BFO" if symbol in ["SENSEX", "BANKEX"] else "NFO"
token_id = st.number_input("Instrument Token", value=256265)
side = st.radio("Side", ["BUY", "SELL"], horizontal=True)
qty = st.number_input("Quantity", value=65, step=5)
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