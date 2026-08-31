import requests
import streamlit as st

BACKEND_URL = "http://92.4.85.1:10000"  # Oracle Static IP

st.set_page_config(page_title="Zerodha Trading Bot", layout="wide")
st.title("⚡ Zerodha Algorithmic Trading Terminal")

# ------------------------------------------------------------------------------
# 1. Capture and Process Token When Zerodha Redirects Back to Streamlit
# ------------------------------------------------------------------------------
query_params = st.query_params
if "request_token" in query_params:
    req_token = query_params["request_token"]
    st.info("🔄 Validating Zerodha Token with Oracle Backend...")

    try:
        # Pass the request_token to Oracle server to generate access_token
        callback_res = requests.get(
            f"{BACKEND_URL}/callback",
            params={"request_token": req_token},
            timeout=10,
        )

        if callback_res.status_code == 200:
            st.success("✅ Connected to Zerodha successfully!")
            st.query_params.clear()
            st.rerun()
        else:
            err_msg = callback_res.json().get(
                "detail", "Token validation failed"
            )
            st.error(f"❌ Login Failed: {err_msg}")
    except Exception as e:
        st.error(f"❌ Could not connect to Oracle backend: {e}")

# ------------------------------------------------------------------------------
# 2. Fetch Backend Health Status
# ------------------------------------------------------------------------------
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

    # Display Login Button if Zerodha session is inactive
    if not checks.get("login_authenticated", False):
        st.link_button(
            label="🔑 Click Here to Login to Zerodha",
            url=f"{BACKEND_URL}/login",
            use_container_width=True,
            type="primary",
        )

    # Detailed Connection Matrix
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Kite Login",
        "Connected" if checks.get("login_authenticated") else "Disconnected",
    )
    col2.metric(
        "IP Whitelist (92.4.85.1)",
        "Active" if checks.get("ip_whitelisted") else "Pending",
    )
    col3.metric(
        "Cloud Engine",
        "Running" if checks.get("service_active") else "Stopped",
    )

except Exception:
    st.error(
        "🔴 **SERVER UNREACHABLE:** Oracle Cloud service is not responding or port 10000 is closed."
    )

st.divider()
st.subheader("Strategy Controls")
st.text("Indices Enabled: NIFTY 50 | BANKNIFTY | FINNIFTY")
st.text("Execution Rules: Max 2 trades/session | Hard Exit @ 3:05 PM")
