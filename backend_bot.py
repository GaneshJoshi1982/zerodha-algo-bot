import asyncio
from datetime import datetime
import os
import threading
import time
from urllib.parse import parse_qs, urlparse

from fastapi import BackgroundTasks, FastAPI, HTTPException
from kiteconnect import KiteConnect
import numpy as np
import pandas as pd
from pydantic import BaseModel
import pyotp
import requests

# ==========================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================
# Read from Render Environment Variables (Fallback to local strings if testing)
API_KEY = os.getenv("API_KEY", "magym2s4yk13gsze")
API_SECRET = os.getenv("API_SECRET", "83cuxyx91lv9ae371ogcs6ckvu5kto8q")
USER_ID = os.getenv("ZERODHA_USER_ID", "YOUR_USER_ID")
PASSWORD = os.getenv("ZERODHA_PASSWORD", "YOUR_PASSWORD")
TOTP_SECRET = os.getenv("ZERODHA_TOTP_SECRET", "YOUR_TOTP_SECRET_KEY")

TOKEN_FILE = "access_token.txt"

# Standard Regulatory Lot Sizes
LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
    "SENSEX": 20,
    "BANKEX": 30,
}

app = FastAPI(title="Zerodha Automated Execution Bot Backend")

# Memory State
ACTIVE_POSITIONS = {}
TRADE_LOGS = []


def get_kite_client():
    kite = KiteConnect(api_key=API_KEY)
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                access_token = f.read().strip()
            kite.set_access_token(access_token)
            return kite
        return None
    except Exception as e:
        print(f"Error restoring Kite Client: {e}")
        return None


# ==========================================
# 2. AUTOMATED DAILY LOGIN SYSTEM (PyOTP)
# ==========================================
@app.post("/api/auto-login")
def auto_login_zerodha():
    """Automates Zerodha's 2FA login using PyOTP to fetch and save a fresh access_token."""
    global TRADE_LOGS
    try:
        session = requests.Session()

        # Step 1: Submit Username & Password
        login_payload = {"user_id": USER_ID, "password": PASSWORD}
        res1 = session.post(
            "https://kite.zerodha.com/api/login", data=login_payload
        ).json()
        if res1.get("status") != "success":
            raise Exception(f"Phase 1 Login Failed: {res1}")

        request_id = res1["data"]["request_id"]

        # Step 2: Auto-Generate 2FA TOTP Code using PyOTP
        totp = pyotp.TOTP(TOTP_SECRET)
        twofa_code = totp.now()

        twofa_payload = {
            "user_id": USER_ID,
            "request_id": request_id,
            "twofa_value": twofa_code,
        }
        res2 = session.post(
            "https://kite.zerodha.com/api/twofa", data=twofa_payload
        ).json()
        if res2.get("status") != "success":
            raise Exception(f"Phase 2 2FA Failed: {res2}")

        # Step 3: Authorize OAuth to get request_token
        auth_url = (
            f"https://kite.zerodha.com/connect/login?v=3&api_key={API_KEY}"
        )
        auth_res = session.get(auth_url, allow_redirects=True)

        parsed_url = urlparse(auth_res.url)
        query_params = parse_qs(parsed_url.query)

        if "request_token" not in query_params:
            raise Exception("Request Token missing in OAuth redirect response.")

        request_token = query_params["request_token"][0]

        # Step 4: Exchange request_token for final access_token
        kite = KiteConnect(api_key=API_KEY)
        session_data = kite.generate_session(
            request_token, api_secret=API_SECRET
        )
        access_token = session_data["access_token"]

        # Save token to file
        with open(TOKEN_FILE, "w") as f:
            f.write(access_token)

        msg = f"🔑 [{datetime.now().strftime('%H:%M:%S')}] ZERODHA AUTO-LOGIN SUCCESSFUL!"
        TRADE_LOGS.append(msg)
        print(msg)

        return {
            "status": "SUCCESS",
            "message": "Zerodha Auto-Login Complete!",
            "access_token": access_token,
        }

    except Exception as e:
        err_msg = f"❌ Auto-Login Failed: {str(e)}"
        TRADE_LOGS.append(err_msg)
        return {"status": "FAILED", "error": str(e)}


# ==========================================
# 3. INDICATOR LOGIC (VWAP & EMA-9)
# ==========================================
def calculate_vwap_and_ema9(df_5m):
    if df_5m is None or df_5m.empty or len(df_5m) < 5:
        return 0.0, 0.0

    df = df_5m.copy()
    df["tp"] = (df["high"] + df["low"] + df["close"]) / 3.0
    df["vwap"] = (df["tp"] * df["volume"]).cumsum() / df[
        "volume"
    ].cumsum().replace(0, np.nan)
    df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()

    latest_vwap = round(df["vwap"].iloc[-1], 2)
    latest_ema9 = round(df["ema_9"].iloc[-1], 2)
    return latest_vwap, latest_ema9


# ==========================================
# 4. BACKGROUND AUTOMATED TRAILING ENGINE
# ==========================================
def background_trailing_loop():
    print(
        "⚡ Background Execution Engine & Dynamic Trailing Engine Running 24/7."
    )
    while True:
        try:
            kite = get_kite_client()
            if kite and ACTIVE_POSITIONS:
                for pos_id, pos in list(ACTIVE_POSITIONS.items()):
                    if pos["status"] != "OPEN":
                        continue

                    tradingsymbol = pos["tradingsymbol"]
                    exchange = pos["exchange"]
                    token = pos["instrument_token"]

                    # Fetch live tick quote
                    quote_key = f"{exchange}:{tradingsymbol}"
                    quotes = kite.quote([quote_key])
                    ltp = quotes.get(quote_key, {}).get("last_price", 0.0)

                    if ltp <= 0:
                        continue

                    pos["current_ltp"] = ltp
                    pos["unrealized_pnl"] = round(
                        (ltp - pos["entry_price"]) * pos["quantity"], 2
                    )

                    # 1. Target Hit Check (+40%)
                    if ltp >= pos["target_price"]:
                        execute_market_exit(
                            pos_id, reason="TARGET HIT (40%+ PROFIT)"
                        )
                        continue

                    # 2. Hard Stop Loss Check (-15%)
                    if ltp <= pos["current_sl"]:
                        execute_market_exit(
                            pos_id, reason="HARD STOP LOSS BREACHED"
                        )
                        continue

                    # 3. Dynamic EMA-9 Trailing Calculation
                    to_date = datetime.now()
                    from_date = to_date.replace(
                        hour=9, minute=15, second=0, microsecond=0
                    )
                    candles = kite.historical_data(
                        instrument_token=token,
                        from_date=from_date,
                        to_date=to_date,
                        interval="5minute",
                    )
                    df_5m = pd.DataFrame(candles)

                    if not df_5m.empty:
                        _, ema9_val = calculate_vwap_and_ema9(df_5m)

                        # Trail SL higher if EMA-9 moves above initial SL
                        if (
                            ema9_val > pos["current_sl"]
                            and ltp > pos["entry_price"]
                        ):
                            pos["current_sl"] = ema9_val
                            TRADE_LOGS.append(
                                f"📈 [{datetime.now().strftime('%H:%M:%S')}] TRAILING SL RAISED to ₹{ema9_val} for {tradingsymbol}"
                            )

                        # Auto-Exit on 5M Candle Close below EMA-9
                        latest_close = df_5m["close"].iloc[-1]
                        if (
                            latest_close < ema9_val
                            and ema9_val > pos["entry_price"]
                        ):
                            execute_market_exit(
                                pos_id, reason="5M EMA-9 BREACH (PROFIT LOCKED)"
                            )

        except Exception as e:
            print(f"Error in background engine: {e}")

        time.sleep(3)


# Start Background Thread on Launch
trailing_thread = threading.Thread(
    target=background_trailing_loop, daemon=True
)
trailing_thread.start()


# ==========================================
# 5. FASTAPI API ENDPOINTS
# ==========================================
class OrderRequest(BaseModel):
    symbol: str
    exchange: str
    tradingsymbol: str
    instrument_token: int
    transaction_type: str
    quantity: int
    price: float
    max_risk_inr: float = 2000.0


def execute_market_exit(pos_id: str, reason: str):
    pos = ACTIVE_POSITIONS.get(pos_id)
    if not pos or pos["status"] != "OPEN":
        return False

    kite = get_kite_client()
    if not kite:
        return False

    exit_side = (
        kite.TRANSACTION_TYPE_SELL
        if pos["side"] == "BUY"
        else kite.TRANSACTION_TYPE_BUY
    )

    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=pos["exchange"],
            tradingsymbol=pos["tradingsymbol"],
            transaction_type=exit_side,
            quantity=pos["quantity"],
            product=kite.PRODUCT_MIS,
            order_type=kite.ORDER_TYPE_MARKET,
        )
        pos["status"] = f"CLOSED ({reason})"
        pos["exit_price"] = pos.get("current_ltp", 0.0)
        TRADE_LOGS.append(
            f"🔴 [{datetime.now().strftime('%H:%M:%S')}] AUTO EXIT: {pos['tradingsymbol']} | Reason: {reason}"
        )
        return True
    except Exception as e:
        TRADE_LOGS.append(
            f"❌ [{datetime.now().strftime('%H:%M:%S')}] EXIT FAILED: {str(e)}"
        )
        return False


# --- Dynamic Instrument & Symbol Lookup Endpoints ---
@app.get("/api/get-symbol")
def get_auto_symbol(index: str, strike: int, type: str):
    """Fetches the active nearest expiry contract trading symbol automatically."""
    kite = get_kite_client()
    if not kite:
        return {
            "status": "ERROR",
            "message": "Zerodha API Unavailable. Please Auto-Login.",
        }

    try:
        exchange = "BFO" if index in ["SENSEX", "BANKEX"] else "NFO"
        instruments = kite.instruments(exchange)

        matching = [
            inst
            for inst in instruments
            if inst["name"] == index
            and inst["strike"] == float(strike)
            and inst["instrument_type"] == type
        ]

        if not matching:
            return {
                "status": "ERROR",
                "message": f"No matching contract found for {index} {strike} {type}",
            }

        matching.sort(key=lambda x: x["expiry"])
        nearest = matching[0]

        return {
            "status": "SUCCESS",
            "tradingsymbol": nearest["tradingsymbol"],
            "instrument_token": nearest["instrument_token"],
            "expiry": str(nearest["expiry"]),
        }
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


@app.get("/api/get-token")
def get_token(symbol: str):
    """Fetches instrument token for a given symbol string."""
    kite = get_kite_client()
    if not kite:
        return {"status": "ERROR", "instrument_token": 0}
    try:
        quotes = kite.quote([f"NFO:{symbol}", f"BFO:{symbol}"])
        token = list(quotes.values())[0]["instrument_token"]
        return {"status": "SUCCESS", "instrument_token": token}
    except Exception:
        return {"status": "ERROR", "instrument_token": 0}


# --- Order Execution Endpoints ---
@app.post("/api/order/submit")
def submit_automated_order(req: OrderRequest):
    kite = get_kite_client()
    if not kite:
        raise HTTPException(
            status_code=500, detail="Zerodha API Client Unavailable"
        )

    initial_sl = round(req.price * 0.85, 2)
    target_price = round(req.price * 1.40, 2)
    projected_risk = (req.price - initial_sl) * req.quantity

    if projected_risk > req.max_risk_inr:
        raise HTTPException(
            status_code=400,
            detail=f"Projected Risk (₹{projected_risk:,.2f}) exceeds Limit (₹{req.max_risk_inr:,.2f})",
        )

    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=req.exchange,
            tradingsymbol=req.tradingsymbol,
            transaction_type=req.transaction_type,
            quantity=req.quantity,
            product=kite.PRODUCT_MIS,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=req.price,
        )

        pos_id = f"{req.tradingsymbol}_{datetime.now().strftime('%H%M%S')}"
        ACTIVE_POSITIONS[pos_id] = {
            "order_id": order_id,
            "tradingsymbol": req.tradingsymbol,
            "exchange": req.exchange,
            "instrument_token": req.instrument_token,
            "side": req.transaction_type,
            "quantity": req.quantity,
            "entry_price": req.price,
            "current_ltp": req.price,
            "initial_sl": initial_sl,
            "current_sl": initial_sl,
            "target_price": target_price,
            "status": "OPEN",
            "entry_time": datetime.now().strftime("%H:%M:%S"),
            "unrealized_pnl": 0.0,
        }

        TRADE_LOGS.append(
            f"🟢 [{datetime.now().strftime('%H:%M:%S')}] ORDER FIRED: {req.transaction_type} {req.quantity}x {req.tradingsymbol} @ ₹{req.price}"
        )
        return {
            "status": "SUCCESS",
            "order_id": order_id,
            "position_id": pos_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/positions")
def get_active_positions():
    return ACTIVE_POSITIONS


@app.get("/api/logs")
def get_logs():
    return TRADE_LOGS


@app.post("/api/order/panic-exit-all")
def panic_exit_all():
    closed_count = 0
    for pos_id, pos in list(ACTIVE_POSITIONS.items()):
        if pos["status"] == "OPEN":
            if execute_market_exit(pos_id, reason="MOBILE PANIC EXIT BUTTON"):
                closed_count += 1
    return {"status": "SUCCESS", "closed_positions": closed_count}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=10000)
