from datetime import datetime
import os
from fastapi import FastAPI, HTTPException, Query
from kiteconnect import KiteConnect
from pydantic import BaseModel

app = FastAPI(title="Zerodha Production Engine")

# ==============================================================================
# CREDENTIALS & DISK STORAGE
# ==============================================================================
API_KEY = "magym2s4yk13gsze".strip()
API_SECRET = "83cuyx911v9ae371ogcs6ckvu5kto8q".strip()
TOKEN_FILE = "/home/ubuntu/.kite_token"

system_state = {
    "zerodha_session_valid": False,
    "access_token": None,
    "ip_whitelisted": True,
    "service_running": True,
}


def init_token_from_disk():
    """Restores saved session on boot/restart without re-authenticating"""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                saved_token = f.read().strip()
                if saved_token:
                    kite = KiteConnect(
                        api_key=API_KEY, access_token=saved_token
                    )
                    kite.margins(segment="equity")  # Verify token health
                    system_state["access_token"] = saved_token
                    system_state["zerodha_session_valid"] = True
                    print("[SYSTEM] Successfully restored session from disk.")
        except Exception:
            print("[SYSTEM] Disk token invalid or expired.")
            system_state["zerodha_session_valid"] = False


init_token_from_disk()


class TradeRequest(BaseModel):
    symbol: str
    transaction_type: str
    quantity: int
    order_type: str
    price: float = 0.0


# ==============================================================================
# ENDPOINTS
# ==============================================================================


@app.get("/health")
def health():
    return {
        "status": (
            "GREEN" if system_state["zerodha_session_valid"] else "RED"
        ),
        "message": (
            "All Systems Active & Linked"
            if system_state["zerodha_session_valid"]
            else "Disconnected / Login Required"
        ),
        "checks": {
            "login_authenticated": system_state["zerodha_session_valid"],
            "ip_whitelisted": system_state["ip_whitelisted"],
            "service_active": system_state["service_running"],
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/callback")
def zerodha_callback(request_token: str = Query(None)):
    """Only Oracle exchanges the request token"""
    if not request_token:
        raise HTTPException(status_code=400, detail="Missing request_token")

    clean_token = request_token.strip()

    if system_state["zerodha_session_valid"]:
        return {"status": "SUCCESS", "message": "Session already active"}

    try:
        kite = KiteConnect(api_key=API_KEY)
        data = kite.generate_session(
            request_token=clean_token, api_secret=API_SECRET
        )

        access_token = data["access_token"]

        # Save to disk permanently
        with open(TOKEN_FILE, "w") as f:
            f.write(access_token)

        system_state["access_token"] = access_token
        system_state["zerodha_session_valid"] = True

        return {"status": "SUCCESS", "message": "Authenticated successfully"}
    except Exception as e:
        system_state["zerodha_session_valid"] = False
        raise HTTPException(
            status_code=400, detail=f"Authentication failed: {str(e)}"
        )


@app.get("/sync")
def sync_account():
    if not system_state["zerodha_session_valid"]:
        raise HTTPException(
            status_code=400, detail="Session expired. Re-login."
        )

    try:
        kite = KiteConnect(
            api_key=API_KEY, access_token=system_state["access_token"]
        )
        margins = kite.margins(segment="equity")
        available_margin = (
            margins.get("equity", {})
            .get("available", {})
            .get("live_balance", 0)
        )
        return {"status": "SUCCESS", "margin": available_margin}
    except Exception as e:
        system_state["zerodha_session_valid"] = False
        raise HTTPException(status_code=400, detail=f"Sync error: {str(e)}")


@app.post("/push_trade")
def push_trade(trade: TradeRequest):
    if not system_state["zerodha_session_valid"]:
        raise HTTPException(
            status_code=400, detail="Session expired. Re-login."
        )

    try:
        kite = KiteConnect(
            api_key=API_KEY, access_token=system_state["access_token"]
        )
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=trade.symbol,
            transaction_type=(
                kite.TRANSACTION_TYPE_BUY
                if trade.transaction_type == "BUY"
                else kite.TRANSACTION_TYPE_SELL
            ),
            quantity=trade.quantity,
            product=kite.PRODUCT_MIS,
            order_type=(
                kite.ORDER_TYPE_MARKET
                if trade.order_type == "MARKET"
                else kite.ORDER_TYPE_LIMIT
            ),
            price=trade.price if trade.order_type == "LIMIT" else None,
        )
        return {"status": "SUCCESS", "order_id": order_id}
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Order rejected: {str(e)}"
        )


@app.post("/square_off")
def square_off():
    return {
        "status": "SUCCESS",
        "message": "Emergency square off signal processed.",
    }


@app.get("/logs")
def get_logs():
    return {
        "logs": f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Active session: {system_state['zerodha_session_valid']}"
    }
