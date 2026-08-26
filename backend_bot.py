import asyncio
from datetime import datetime
import math
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
# 1. CONFIGURATION & ENVIRONMENT SETUP
# ==========================================
API_KEY = os.getenv("API_KEY", "magym2s4yk13gsze")
API_SECRET = os.getenv("API_SECRET", "83cuxyx91lv9ae371ogcs6ckvu5kto8q")
USER_ID = os.getenv("ZERODHA_USER_ID", "YOUR_USER_ID")
PASSWORD = os.getenv("ZERODHA_PASSWORD", "YOUR_PASSWORD")
TOTP_SECRET = os.getenv("ZERODHA_TOTP_SECRET", "YOUR_TOTP_SECRET_KEY")

TOKEN_FILE = "access_token.txt"

# Regulatory Lot Sizes
LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
    "SENSEX": 20,
    "BANKEX": 30,
}

# Overtrading & Risk Protection Caps
MAX_DAILY_TRADES = 3
MAX_DAILY_LOSS = -1000.0  # Circuit breaker at ₹1,000 loss
DAILY_TRADE_COUNT = 0
DAILY_CUMULATIVE_PNL = 0.0

# 15-Minute Cooling-Off Period Settings
LAST_EXIT_TIMESTAMP = None
COOLING_PERIOD_SECONDS = 15 * 60

app = FastAPI(
    title="Zerodha Institutional LinReg Execution Bot Engine", version="3.2"
)

ACTIVE_POSITIONS = {}
TRADE_LOGS = []


def get_kite_client():
    """Restores the KiteConnect client using stored access_token."""
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
# 2. AUTOMATED DAILY 2FA LOGIN SYSTEM
# ==========================================
@app.get("/api/auto-login")
def auto_login_zerodha():
    """Automates Zerodha's 2FA login using PyOTP via GET for 1-click browser/app activation.

    Scans entire redirect history to extract request_token reliably even with
    127.0.0.1 redirect URLs.
    """
    global TRADE_LOGS
    try:
        session = requests.Session()

        # Step 1: Submit Credentials
        res1 = session.post(
            "https://kite.zerodha.com/api/login",
            data={"user_id": USER_ID, "password": PASSWORD},
        ).json()
        if res1.get("status") != "success":
            raise Exception(f"Phase 1 Login Failed: {res1}")

        request_id = res1["data"]["request_id"]

        # Step 2: Auto-Generate 2FA TOTP Code via PyOTP
        totp = pyotp.TOTP(TOTP_SECRET)
        twofa_code = totp.now()

        res2 = session.post(
            "https://kite.zerodha.com/api/twofa",
            data={
                "user_id": USER_ID,
                "request_id": request_id,
                "twofa_value": twofa_code,
            },
        ).json()
        if res2.get("status") != "success":
            raise Exception(f"Phase 2 2FA Failed: {res2}")

        # Step 3: Capture OAuth Redirect Token across all response histories
        auth_url = (
            f"https://kite.zerodha.com/connect/login?v=3&api_key={API_KEY}"
        )
        auth_res = session.get(auth_url, allow_redirects=True)

        request_token = None
        # Loop through redirect history and final response to catch request_token
        for resp in auth_res.history + [auth_res]:
            # Check Location header or response URL
            target_url = resp.headers.get("Location", resp.url)
            parsed = urlparse(target_url)
            params = parse_qs(parsed.query)
            if "request_token" in params:
                request_token = params["request_token"][0]
                break

        if not request_token:
            raise Exception(
                f"Request Token missing. Check Redirect URL setting in Developer Console. Final URL: {auth_res.url}"
            )

        # Step 4: Exchange request_token for final Session Access Token
        kite = KiteConnect(api_key=API_KEY)
        session_data = kite.generate_session(
            request_token, api_secret=API_SECRET
        )
        access_token = session_data["access_token"]

        with open(TOKEN_FILE, "w") as f:
            f.write(access_token)

        msg = f"🔑 [{datetime.now().strftime('%H:%M:%S')}] ZERODHA AUTO-LOGIN SUCCESSFUL!"
        TRADE_LOGS.append(msg)
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
# 3. LINREG CANDLES & INDICATOR MATH
# ==========================================
def calculate_linreg_and_indicators(df_3m, period=11):
    """Computes Linear Regression Candles & 3M EMA-9 to eliminate false wicks."""
    if df_3m is None or df_3m.empty or len(df_3m) < period:
        return 0.0, 0.0, 0.0

    df = df_3m.copy()
    x = np.arange(period)

    def linreg_val(series):
        if len(series) < period:
            return series.iloc[-1]
        slope, intercept = np.polyfit(x, series, 1)
        return slope * (period - 1) + intercept

    df["lr_close"] = (
        df["close"].rolling(window=period).apply(linreg_val, raw=False)
    )
    df["lr_open"] = (
        df["open"].rolling(window=period).apply(linreg_val, raw=False)
    )
    df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()

    latest_lr_close = round(df["lr_close"].iloc[-2], 2)
    latest_lr_open = round(df["lr_open"].iloc[-2], 2)
    latest_ema9 = round(df["ema_9"].iloc[-2], 2)

    return latest_lr_close, latest_lr_open, latest_ema9


# ==========================================
# 4. BACKGROUND TRAILING & EXECUTION ENGINE
# ==========================================
def background_trailing_loop():
    global DAILY_CUMULATIVE_PNL
    print("⚡ LinReg Multi-Timeframe Background Engine Active 24/7.")
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
                            pos_id, reason="TARGET HIT (+40% PROFIT)"
                        )
                        continue

                    # 2. Hard Stop Loss Check (-15%)
                    if ltp <= pos["current_sl"]:
                        execute_market_exit(
                            pos_id, reason="HARD STOP LOSS BREACHED"
                        )
                        continue

                    # 3. LinReg Smoothed Trailing SL Check (3-Minute Chart)
                    to_date = datetime.now()
                    from_date = to_date.replace(
                        hour=9, minute=15, second=0, microsecond=0
                    )
                    candles = kite.historical_data(
                        instrument_token=token,
                        from_date=from_date,
                        to_date=to_date,
                        interval="3minute",
                    )
                    df_3m = pd.DataFrame(candles)

                    if not df_3m.empty:
                        lr_close, lr_open, ema9_val = (
                            calculate_linreg_and_indicators(df_3m)
                        )

                        if (
                            ema9_val > pos["current_sl"]
                            and ltp > pos["entry_price"]
                        ):
                            pos["current_sl"] = ema9_val
                            TRADE_LOGS.append(
                                f"📈 [{datetime.now().strftime('%H:%M:%S')}] TRAILING SL RAISED to ₹{ema9_val} for {tradingsymbol}"
                            )

                        if (
                            lr_close < ema9_val
                            and ema9_val > pos["entry_price"]
                        ):
                            execute_market_exit(
                                pos_id,
                                reason="3M LINREG CANDLE BREACHED EMA-9 (PROFIT LOCKED)",
                            )

        except Exception as e:
            print(f"Error in background engine: {e}")

        time.sleep(3)


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
    global LAST_EXIT_TIMESTAMP, DAILY_CUMULATIVE_PNL
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

        realized = pos["unrealized_pnl"]
        DAILY_CUMULATIVE_PNL += realized
        LAST_EXIT_TIMESTAMP = datetime.now()

        TRADE_LOGS.append(
            f"🔴 [{datetime.now().strftime('%H:%M:%S')}] AUTO EXIT: {pos['tradingsymbol']} | PnL: ₹{realized} | Reason: {reason}"
        )
        TRADE_LOGS.append(
            f"⏳ [{datetime.now().strftime('%H:%M:%S')}] COOLING-OFF TIMER STARTED for {COOLING_PERIOD_SECONDS // 60} minutes."
        )
        return True
    except Exception as e:
        TRADE_LOGS.append(
            f"❌ [{datetime.now().strftime('%H:%M:%S')}] EXIT FAILED: {str(e)}"
        )
        return False


@app.get("/api/get-symbol")
def get_auto_symbol(index: str, strike: int, type: str):
    """Dynamically resolves the active contract symbol and instrument token."""
    kite = get_kite_client()
    if not kite:
        return {"status": "ERROR", "message": "Zerodha API Unavailable."}

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
                "message": f"No contract found for {index} {strike} {type}",
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
    kite = get_kite_client()
    if not kite:
        return {"status": "ERROR", "instrument_token": 0}
    try:
        quotes = kite.quote([f"NFO:{symbol}", f"BFO:{symbol}"])
        token = list(quotes.values())[0]["instrument_token"]
        return {"status": "SUCCESS", "instrument_token": token}
    except Exception:
        return {"status": "ERROR", "instrument_token": 0}


@app.post("/api/order/submit")
def submit_automated_order(req: OrderRequest):
    global DAILY_TRADE_COUNT, DAILY_CUMULATIVE_PNL, LAST_EXIT_TIMESTAMP

    if DAILY_TRADE_COUNT >= MAX_DAILY_TRADES:
        raise HTTPException(
            status_code=400,
            detail=f"Daily trade limit ({MAX_DAILY_TRADES}) reached! Order blocked.",
        )

    if DAILY_CUMULATIVE_PNL <= MAX_DAILY_LOSS:
        raise HTTPException(
            status_code=400,
            detail=f"Daily Loss Limit (₹{MAX_DAILY_LOSS}) reached! Bot locked for safety.",
        )

    if LAST_EXIT_TIMESTAMP:
        seconds_elapsed = (
            datetime.now() - LAST_EXIT_TIMESTAMP
        ).total_seconds()
        if seconds_elapsed < COOLING_PERIOD_SECONDS:
            remaining_mins = int(
                math.ceil((COOLING_PERIOD_SECONDS - seconds_elapsed) / 60.0)
            )
            raise HTTPException(
                status_code=400,
                detail=f"Cooling period active! Wait {remaining_mins} more minute(s).",
            )

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

        DAILY_TRADE_COUNT += 1
        TRADE_LOGS.append(
            f"🟢 [{datetime.now().strftime('%H:%M:%S')}] ORDER FIRED ({DAILY_TRADE_COUNT}/{MAX_DAILY_TRADES}): {req.transaction_type} {req.quantity}x {req.tradingsymbol} @ ₹{req.price}"
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
