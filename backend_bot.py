import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from kiteconnect import KiteConnect

app = FastAPI(title="Zerodha Algo Trading Engine")

# Global System State
system_state = {
    "zerodha_session_valid": False,
    "ip_whitelisted": False,
    "service_running": True,
    "access_token": None,
    "trade_counters": {
        "NIFTY": {"morning": 0, "afternoon": 0},
        "BANKNIFTY": {"morning": 0, "afternoon": 0},
        "FINNIFTY": {"morning": 0, "afternoon": 0}
    }
}

# Configuration
CONFIG = {
    "MAX_TRADES_PER_SESSION": 2,
    "MAX_TRADES_PER_DAY": 4,
    "MORNING_START": "09:20",
    "MORNING_END": "10:45",
    "AFTERNOON_START": "13:30",
    "AFTERNOON_END": "14:45",
    "ENTRY_CUTOFF": "15:00",
    "HARD_SQUARE_OFF": "15:05"
}

class LoginRequest(BaseModel):
    api_key: str
    api_secret: str
    request_token: str

@app.get("/health")
def get_system_status():
    """
    Returns GREEN only when login and IP whitelist are BOTH fully validated.
    """
    is_session_valid = system_state["zerodha_session_valid"]
    is_ip_valid = system_state["ip_whitelisted"]
    is_running = system_state["service_running"]

    if is_session_valid and is_ip_valid and is_running:
        status_color = "GREEN"
        status_message = "All Systems Active (Authenticated & Whitelisted)"
    elif is_session_valid and not is_ip_valid:
        status_color = "YELLOW"
        status_message = "Pending IP Whitelist Approval (Locked until Monday)"
    else:
        status_color = "RED"
        status_message = "Disconnected / Session Expired"

    return {
        "status": status_color,
        "message": status_message,
        "checks": {
            "login_authenticated": is_session_valid,
            "ip_whitelisted": is_ip_valid,
            "service_active": is_running
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@app.post("/login")
def authenticate_zerodha(payload: LoginRequest):
    try:
        kite = KiteConnect(api_key=payload.api_key)
        data = kite.generate_session(payload.request_token, api_secret=payload.api_secret)
        system_state["access_token"] = data["access_token"]
        system_state["zerodha_session_valid"] = True
        
        # Test IP Whitelist connectivity
        try:
            kite.profile()
            system_state["ip_whitelisted"] = True
        except Exception:
            system_state["ip_whitelisted"] = False

        return {"status": "success", "message": "Authenticated with Zerodha"}
    except Exception as e:
        system_state["zerodha_session_valid"] = False
        raise HTTPException(status_code=400, detail=str(e))

def is_within_trading_window():
    now = datetime.now().strftime("%H:%M")
    if CONFIG["MORNING_START"] <= now <= CONFIG["MORNING_END"]:
        return "MORNING"
    elif CONFIG["AFTERNOON_START"] <= now <= CONFIG["AFTERNOON_END"]:
        return "AFTERNOON"
    elif now >= CONFIG["HARD_SQUARE_OFF"]:
        return "SQUARE_OFF"
    return "CLOSED"
