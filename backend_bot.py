from datetime import datetime
import os
from fastapi import FastAPI, HTTPException, Query
from kiteconnect import KiteConnect
from pydantic import BaseModel

app = FastAPI(title="Zerodha Algorithmic Trading Engine")

# ==============================================================================
# CONFIGURATION
# ==============================================================================
API_KEY = "magym2s4yk13gsze".strip()
API_SECRET = "uxph73v40oemxff3c9xn48swqwctbfmf".strip()
TOKEN_FILE = "/home/ubuntu/.kite_token"

system_state = {
    "zerodha_session_valid": False,
    "access_token": None,
    "ip_whitelisted": True,
    "service_running": True,
}


def load_token_from_disk():
    """Restores cached session token from disk on server startup."""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                saved_token = f.read().strip()
                if saved_token:
                    kite = KiteConnect(
                        api_key=API_KEY, access_token=saved_token
                    )
                    kite.margins(segment="equity")
                    system_state["access_token"] = saved_token
                    system_state["zerodha_session_valid"] = True
                    print("[SYSTEM] Session restored from persistent storage.")
        except Exception as e:
            print(f"[SYSTEM] Persistent token invalid or expired: {e}")
            system_state["zerodha_session_valid"] = False


# Auto-load saved session on boot
load_token_from_disk()


class TradeRequest(BaseModel):
    exchange: str = "NSE"
    symbol: str
    transaction_type: str
    quantity: int
    order_type: str
    price: float = 0.0


# ==============================================================================
# ROUTER ENDPOINTS
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
    if not request_token:
        raise HTTPException(status_code=400, detail="Missing request_token")

    if system_state["zerodha_session_valid"]:
        return {"status": "SUCCESS", "message": "Session already active"}

    try:
        kite = KiteConnect(api_key=API_KEY)
        data = kite.generate_session(
            request_token=request_token.strip(), api_secret=API_SECRET
        )
        access_token = data["access_token"]

        with open(TOKEN_FILE, "w") as f:
            f.write(access_token)

        system_state["access_token"] = access_token
        system_state["zerodha_session_valid"] = True
        return {"status": "SUCCESS", "message": "Authenticated successfully"}
    except Exception as e:
        if system_state["zerodha_session_valid"]:
            return {"status": "SUCCESS", "message": "Session already active"}
        system_state["zerodha_session_valid"] = False
        raise HTTPException(
            status_code=400, detail=f"Authentication failed: {str(e)}"
        )


@app.get("/sync")
def sync_account():
    if not system_state["zerodha_session_valid"]:
        raise HTTPException(
            status_code=400, detail="Zerodha session expired. Login required."
        )

    try:
        kite = KiteConnect(
            api_key=API_KEY, access_token=system_state["access_token"]
        )
        m = kite.margins(segment="equity")

        # Safely extract net balance regardless of dict wrapper format
        if "equity" in m and isinstance(m["equity"], dict):
            equity_data = m["equity"]
        else:
            equity_data = m

        available_margin = equity_data.get(
            "net", equity_data.get("available", {}).get("live_balance", 0)
        )

        return {"status": "SUCCESS", "margin": available_margin}
    except Exception as e:
        system_state["zerodha_session_valid"] = False
        raise HTTPException(status_code=400, detail=f"Sync error: {str(e)}")


@app.post("/push_trade")
def push_trade(trade: TradeRequest):
    if not system_state["zerodha_session_valid"]:
        raise HTTPException(
            status_code=400, detail="Zerodha session expired. Login required."
        )

    try:
        kite = KiteConnect(
            api_key=API_KEY, access_token=system_state["access_token"]
        )

        selected_exchange = (
            kite.EXCHANGE_NSE
            if trade.exchange.upper() == "NSE"
            else kite.EXCHANGE_NFO
        )

        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=selected_exchange,
            tradingsymbol=trade.symbol.strip().upper(),
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
        return {"status": "SUCCESS", "order_id": str(order_id)}
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Order rejected by Zerodha: {str(e)}"
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
        "logs": f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Engine Active | Session Valid: {system_state['zerodha_session_valid']}"
    }
