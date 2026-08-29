import streamlit as st
import requests

BACKEND_URL = "http://92.4.85.1:10000"  # Your Oracle Static IP

st.set_page_config(page_title="Zerodha Trading Bot", layout="wide")
st.title("⚡ Zerodha Algorithmic Trading Terminal")

# Fetch Real-time Backend Health Status
try:
    res = requests.get(f"{BACKEND_URL}/health", timeout=3).json()
    status_color = res.get("status", "RED")
    status_msg = res.get("message", "Offline")
    checks = res.get("checks", {})
    
    if status_color == "GREEN":
        st.success(f"🟢 **SYSTEM ACTIVE:** {status_msg}")
    elif status_color == "YELLOW":
        st.warning(f"🟡 **ACTION REQUIRED:** {status_msg}")
    else:
        st.error(f"🔴 **SYSTEM DISCONNECTED:** {status_msg}")

    # Detailed Connection Matrix
    col1, col2, col3 = st.columns(3)
    col1.metric("Kite Login", "Connected" if checks.get("login_authenticated") else "Disconnected")
    col2.metric("IP Whitelist (92.4.85.1)", "Active" if checks.get("ip_whitelisted") else "Pending")
    col3.metric("Cloud Engine", "Running" if checks.get("service_active") else "Stopped")

except Exception:
    st.error("🔴 **SERVER UNREACHABLE:** Oracle Cloud service is not responding or port 10000 is closed.")

st.divider()
st.subheader("Strategy Controls")
st.text("Indices Enabled: NIFTY 50 | BANKNIFTY | FINNIFTY")
st.text("Execution Rules: Max 2 trades/session | Hard Exit @ 3:05 PM")
