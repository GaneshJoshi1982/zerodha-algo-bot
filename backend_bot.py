import os
import time
import math
import numpy as np
import pandas as pd
import threading
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from kiteconnect import KiteConnect

# ==========================================
# 1. ENVIRONMENT CONFIGURATION & CONSTANTS
# ==========================================
API_KEY = os.getenv("API_KEY", "your_api_key")
API_SECRET = os.getenv("API_SECRET", "your_api_secret")
TOKEN_FILE = "access_token.txt"

LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
    "SENSEX": 20,
    "BANKEX": 30
}

# Risk Management Parameters
MAX_DAILY_TRADES = 3
MAX_DAILY_LOSS = -1000.0
COOLING_PERIOD_SECONDS = 15 * 60  # 15 minutes cooling-off timer

# Runtime State Tracking
DAILY_TRADE_COUNT = 0
DAILY_CUMULATIVE_PNL = 0.0
LAST_EXIT_TIMESTAMP = None
ACTIVE_POSITIONS = {}
TRADE_LOGS = []

app = FastAPI(title="Institutional LinReg & HM Execution Engine", version="5.0")


def get_kite_client():
    """Restores active Kite Connect session from token file."""
    kite = KiteConnect(api_key=API_KEY)
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                token = f.read().strip()
            kite.set_access_token(token)
            return kite
        return None
    except Exception as e:
        print(f"Error initializing Kite Client: {e}")
        return None


# ==========================================
# 2. AUTHENTICATION & LOGIN ENDPOINTS
# ==========================================
@app.get("/api/get-access-token")
def get_access_token():
    """Returns the active access token stored in access_token.txt."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
        if token:
            return {"status": "SUCCESS", "access_token": token}
    return {"status": "ERROR", "message": "No active access token stored yet."}


@app.get("/api/set-request-token")
def set_request_token(request_token: str):
    """Exchanges request_token for a 24-hour access_token."""
    global TRADE_LOGS
    try:
        kite = KiteConnect(api_key=API_KEY)
        session_data = kite.generate_session(request_token, api_secret=API_SECRET)
        access_token = session_data["access_token"]
        
        with open(TOKEN_FILE, "w") as f:
            f.write(access_token)
            
        msg = f"🔑 [{datetime.now().strftime('%H:%M:%S')}] SESSION TOKEN SET SUCCESSFULLY!"
        TRADE_LOGS.append(msg)
        return {"status": "SUCCESS", "message": "Token active for 24 hours!", "access_token": access_token}
    except Exception as e:
        return {"status": "FAILED", "error": str(e)}


@app.get("/api/auto-login")
def auto_login_zerodha(request: Request):
    """Catches all query parameters sent back by Zerodha redirect callback."""
    params = dict(request.query_params)
    req_token = params.get("request_token")
    if req_token:
        return set_request_token(req_token)
    return {"status": "FAILED", "error": f"No request_token found in parameters: {params}"}


# ==========================================
# 3. STREAMLIT FRONTEND API ENDPOINTS
# ==========================================
@app.get("/api/positions")
def get_active_positions():
    """Returns currently active open positions for Streamlit UI."""
    return ACTIVE_POSITIONS


@app.get("/api/logs")
def get_system_logs():
    """Returns runtime logs for Streamlit text area."""
    return TRADE_LOGS


@app.post("/api/order/panic-exit-all")
def panic_exit_all_positions():
    """Instantly closes all active open positions via Market Order."""
    closed_count = 0
    for pos_id, pos in list(ACTIVE_POSITIONS.items()):
        if pos.get("status") == "OPEN":
            success = execute_market_exit(pos_id, reason="🚨 PANIC EXIT BUTTON TRIGGERED BY USER")
            if success:
                closed_count += 1
    return {"status": "SUCCESS", "closed_positions": closed_count}


@app.get("/api/get-symbol")
def get_symbol_details(index: str, strike: int, type: str):
    """Auto-fetches nearest option trading symbol for manual order creation in UI."""
    kite = get_kite_client()
    if not kite:
        return {"status": "ERROR", "message": "API Client Unavailable"}
    
    try:
        exchange = "BFO" if index in ["SENSEX", "BANKEX"] else "NFO"
        instruments = pd.DataFrame(kite.instruments(exchange))

        filtered = instruments[
            (instruments["name"] == index) &
            (instruments["strike"] == float(strike)) &
            (instruments["instrument_type"] == type)
        ].copy()

        if filtered.empty:
            return {"status": "ERROR", "message": "Strike not found"}

        filtered["expiry"] = pd.to_datetime(filtered["expiry"]).dt.date
        today = datetime.now().date()
        valid = filtered[filtered["expiry"] >= today].sort_values(by="expiry")

        if valid.empty:
            return {"status": "ERROR", "message": "No valid active expiry"}

        nearest = valid.iloc[0]
        return {
            "status": "SUCCESS",
            "tradingsymbol": nearest["tradingsymbol"],
            "instrument_token": nearest["instrument_token"],
            "expiry": str(nearest["expiry"])
        }
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


# ==========================================
# 4. INDICATOR ENGINE & REVERSAL SCANNER
# ==========================================
def calculate_rsi(series, period=9):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def check_hm_reversal_signal(df_3m):
    """
    Evaluates 3M Hilega-Milega (HM) logic:
    RSI(9) crossing above EMA(3) of RSI with Volume confirmation.
    """
    if df_3m is None or df_3m.empty or len(df_3m) < 20:
        return False, "⚪ Insufficient Candle Data"

    df = df_3m.copy()
    df["rsi_9"] = calculate_rsi(df["close"], period=9)
    df["rsi_ema_3"] = df["rsi_9"].ewm(span=3, adjust=False).mean()
    df["vol_avg20"] = df["volume"].rolling(20).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    rsi_gt_ema3 = latest["rsi_9"] > latest["rsi_ema_3"]
    fresh_cross = (prev["rsi_9"] <= prev["rsi_ema_3"]) and rsi_gt_ema3
    vol_surge = latest["volume"] >= (1.2 * latest["vol_avg20"])

    if fresh_cross and vol_surge:
        return True, f"🚀 FRESH HM CROSS: RSI(9) [{round(latest['rsi_9'], 1)}] > EMA(3) + Vol Surge"
    elif rsi_gt_ema3 and vol_surge:
        return True, f"🟢 HM CONTINUATION: Holding RSI(9) > EMA(3)"

    return False, "⚪ No Signal"


def scan_and_select_strike(kite, symbol: str):
    """
    Scans live market conditions for mid-day reversals against 15M VWAP
    and fetches nearest active option contract.
    """
    try:
        step = 100 if symbol in ["SENSEX", "BANKNIFTY", "BANKEX"] else 50
        spot_map = {
            "NIFTY": "NSE:NIFTY 50",
            "BANKNIFTY": "NSE:NIFTY BANK",
            "FINNIFTY": "NSE:NIFTY FIN SERVICE",
            "MIDCPNIFTY": "NSE:NIFTY MID SELECT",
            "SENSEX": "BSE:SENSEX",
            "BANKEX": "BSE:BANKEX"
        }
        spot_symbol = spot_map.get(symbol, f"NSE:{symbol}")
        
        quotes = kite.quote([spot_symbol])
        spot_price = quotes.get(spot_symbol, {}).get("last_price", 0.0)

        if spot_price == 0:
            return None

        to_date = datetime.now()
        from_date = to_date.replace(hour=9, minute=15, second=0, microsecond=0)
        spot_candles = kite.historical_data(
            instrument_token=quotes[spot_symbol]["instrument_token"],
            from_date=from_date, to_date=to_date, interval="15minute"
        )

        df_spot = pd.DataFrame(spot_candles)
        df_spot["tp"] = (df_spot["high"] + df_spot["low"] + df_spot["close"]) / 3.0
        df_spot["vwap"] = (df_spot["tp"] * df_spot["volume"]).cumsum() / df_spot["volume"].cumsum()
        
        latest_vwap = df_spot["vwap"].iloc[-1] if not df_spot.empty else spot_price

        if spot_price >= latest_vwap:
            option_type = "CE"
            target_strike = (round(spot_price / step) * step) + step
        else:
            option_type = "PE"
            target_strike = (round(spot_price / step) * step) - step

        exchange = "BFO" if symbol in ["SENSEX", "BANKEX"] else "NFO"
        instruments = pd.DataFrame(kite.instruments(exchange))

        filtered = instruments[
            (instruments["name"] == symbol) &
            (instruments["strike"] == float(target_strike)) &
            (instruments["instrument_type"] == option_type)
        ].copy()

        if filtered.empty:
            return None

        filtered["expiry"] = pd.to_datetime(filtered["expiry"]).dt.date
        today = datetime.now().date()
        valid_contracts = filtered[filtered["expiry"] >= today].sort_values(by="expiry")

        if valid_contracts.empty:
            return None

        nearest = valid_contracts.iloc[0]
        return {
            "symbol": symbol,
            "option_type": option_type,
            "strike": target_strike,
            "tradingsymbol": nearest["tradingsymbol"],
            "instrument_token": nearest["instrument_token"],
            "exchange": exchange,
            "expiry": str(nearest["expiry"]),
            "spot_price": spot_price,
            "vwap": latest_vwap
        }
    except Exception as e:
        print(f"Error scanning market: {e}")
        return None


# ==========================================
# 5. ORDER SUBMISSION & PRE-TRADE GATEKEEPER
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


@app.post("/api/order/submit")
def submit_automated_order(req: OrderRequest):
    global DAILY_TRADE_COUNT, DAILY_CUMULATIVE_PNL, LAST_EXIT_TIMESTAMP

    if DAILY_TRADE_COUNT >= MAX_DAILY_TRADES:
        raise HTTPException(status_code=400, detail=f"Daily trade limit ({MAX_DAILY_TRADES}) reached!")

    if DAILY_CUMULATIVE_PNL <= MAX_DAILY_LOSS:
        raise HTTPException(status_code=400, detail=f"Daily Loss Floor (₹{MAX_DAILY_LOSS}) hit!")

    if LAST_EXIT_TIMESTAMP:
        seconds_elapsed = (datetime.now() - LAST_EXIT_TIMESTAMP).total_seconds()
        if seconds_elapsed < COOLING_PERIOD_SECONDS:
            remaining_mins = int(math.ceil((COOLING_PERIOD_SECONDS - seconds_elapsed) / 60.0))
            raise HTTPException(status_code=400, detail=f"Cooling-off active! Wait {remaining_mins} mins.")

    kite = get_kite_client()
    if not kite:
        raise HTTPException(status_code=500, detail="Zerodha API Client Unavailable")

    initial_sl = round(req.price * 0.85, 2)
    projected_risk = (req.price - initial_sl) * req.quantity

    if projected_risk > req.max_risk_inr:
        raise HTTPException(status_code=400, detail=f"Risk (₹{projected_risk:,.2f}) > Limit (₹{req.max_risk_inr:,.2f})")

    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=req.exchange,
            tradingsymbol=req.tradingsymbol,
            transaction_type=req.transaction_type,
            quantity=req.quantity,
            product=kite.PRODUCT_MIS,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=round(req.price * 1.005, 2)
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
            "current_sl": initial_sl,
            "target_price": round(req.price * 1.40, 2),
            "unrealized_pnl": 0.0,
            "status": "OPEN",
            "breakeven_locked": False,
            "profit_20pct_locked": False,
            "entry_time": datetime.now().strftime("%H:%M:%S")
        }

        DAILY_TRADE_COUNT += 1
        TRADE_LOGS.append(
            f"🟢 [{datetime.now().strftime('%H:%M:%S')}] ORDER EXECUTED ({DAILY_TRADE_COUNT}/{MAX_DAILY_TRADES}): "
            f"{req.transaction_type} {req.quantity}x {req.tradingsymbol} @ ₹{req.price}"
        )
        return {"status": "SUCCESS", "order_id": order_id, "position_id": pos_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def execute_market_exit(pos_id: str, reason: str):
    """Executes market order exit and triggers cooling-off timer."""
    global LAST_EXIT_TIMESTAMP, DAILY_CUMULATIVE_PNL
    pos = ACTIVE_POSITIONS.get(pos_id)
    if not pos or pos["status"] != "OPEN":
        return False

    kite = get_kite_client()
    if not kite:
        return False

    exit_side = kite.TRANSACTION_TYPE_SELL if pos["side"] == "BUY" else kite.TRANSACTION_TYPE_BUY

    try:
        kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=pos["exchange"],
            tradingsymbol=pos["tradingsymbol"],
            transaction_type=exit_side,
            quantity=pos["quantity"],
            product=kite.PRODUCT_MIS,
            order_type=kite.ORDER_TYPE_MARKET
        )

        realized_pnl = round((pos.get("current_ltp", pos["entry_price"]) - pos["entry_price"]) * pos["quantity"], 2)
        pos["status"] = f"CLOSED ({reason})"
        pos["exit_price"] = pos.get("current_ltp", 0.0)

        DAILY_CUMULATIVE_PNL += realized_pnl
        LAST_EXIT_TIMESTAMP = datetime.now()

        TRADE_LOGS.append(
            f"🔴 [{datetime.now().strftime('%H:%M:%S')}] AUTO EXIT: {pos['tradingsymbol']} | "
            f"PnL: ₹{realized_pnl} | Reason: {reason}"
        )
        return True
    except Exception as e:
        TRADE_LOGS.append(f"❌ [{datetime.now().strftime('%H:%M:%S')}] EXIT FAILED: {str(e)}")
        return False


# ==========================================
# 6. BACKGROUND ENGINE: AUTOMATED SCANNER
# ==========================================
def background_market_scanner_loop():
    """Scans market symbols every 3 minutes for automated entries."""
    SYMBOLS_TO_SCAN = ["NIFTY", "BANKNIFTY"]
    
    while True:
        try:
            kite = get_kite_client()
            if kite and DAILY_TRADE_COUNT < MAX_DAILY_TRADES and len(ACTIVE_POSITIONS) == 0:
                for symbol in SYMBOLS_TO_SCAN:
                    strike_data = scan_and_select_strike(kite, symbol)
                    if not strike_data:
                        continue

                    token = strike_data["instrument_token"]
                    to_date = datetime.now()
                    from_date = to_date.replace(hour=9, minute=15, second=0, microsecond=0)
                    candles = kite.historical_data(instrument_token=token, from_date=from_date, to_date=to_date, interval="3minute")
                    
                    if not candles:
                        continue
                        
                    df_3m = pd.DataFrame(candles)
                    has_signal, reason = check_hm_reversal_signal(df_3m)

                    if has_signal:
                        ltp = df_3m.iloc[-1]["close"]
                        lot_size = LOT_SIZES.get(symbol, 50)
                        
                        req = OrderRequest(
                            symbol=symbol,
                            exchange=strike_data["exchange"],
                            tradingsymbol=strike_data["tradingsymbol"],
                            instrument_token=token,
                            transaction_type="BUY",
                            quantity=lot_size,
                            price=ltp,
                            max_risk_inr=2000.0
                        )
                        submit_automated_order(req)
                        break

        except Exception as e:
            print(f"Error in scanner loop: {e}")

        time.sleep(180)  # Scan every 3 minutes


# ==========================================
# 7. BACKGROUND ENGINE: 4-STAGE EXIT LOOP
# ==========================================
def background_trailing_and_exit_loop():
    while True:
        try:
            kite = get_kite_client()
            if kite and ACTIVE_POSITIONS:
                for pos_id, pos in list(ACTIVE_POSITIONS.items()):
                    if pos["status"] != "OPEN":
                        continue

                    token = pos["instrument_token"]
                    entry_price = pos["entry_price"]
                    current_sl = pos["current_sl"]
                    breakeven_locked = pos.get("breakeven_locked", False)
                    profit_20pct_locked = pos.get("profit_20pct_locked", False)

                    quote_key = f"{pos['exchange']}:{pos['tradingsymbol']}"
                    quotes = kite.quote([quote_key])
                    ltp = quotes.get(quote_key, {}).get("last_price", 0.0)

                    if ltp <= 0:
                        continue

                    pos["current_ltp"] = ltp
                    pos["unrealized_pnl"] = round((ltp - entry_price) * pos["quantity"], 2)
                    pnl_pct = (ltp - entry_price) / entry_price

                    if ltp <= current_sl:
                        execute_market_exit(pos_id, reason=f"STOP LOSS BREACHED at ₹{ltp} (Active SL: ₹{current_sl})")
                        continue

                    if pnl_pct >= 0.15 and not breakeven_locked and not profit_20pct_locked:
                        pos["current_sl"] = entry_price
                        pos["breakeven_locked"] = True
                        TRADE_LOGS.append(f"🛡️ [{datetime.now().strftime('%H:%M:%S')}] +15% GAIN! SL set to Entry (₹{entry_price})")

                    if pnl_pct >= 0.50 and not profit_20pct_locked:
                        target_sl_20pct = round(entry_price * 1.20, 2)
                        pos["current_sl"] = target_sl_20pct
                        pos["profit_20pct_locked"] = True
                        TRADE_LOGS.append(f"🔥 [{datetime.now().strftime('%H:%M:%S')}] +50% GAIN! SL Freezed at ₹{target_sl_20pct} (+20%)")

                    to_date = datetime.now()
                    from_date = to_date.replace(hour=9, minute=15, second=0, microsecond=0)
                    candles = kite.historical_data(instrument_token=token, from_date=from_date, to_date=to_date, interval="3minute")

                    if not candles or len(candles) < 10:
                        continue

                    df_3m = pd.DataFrame(candles)
                    df_3m["ema_9"] = df_3m["close"].ewm(span=9, adjust=False).mean()

                    last_completed = df_3m.iloc[-2]
                    latest_close = last_completed["close"]
                    latest_ema9 = round(last_completed["ema_9"], 2)

                    if profit_20pct_locked and latest_close < latest_ema9:
                        execute_market_exit(pos_id, reason=f"🚀 TREND EXIT: 3M Close (₹{latest_close}) < 9 EMA (₹{latest_ema9})")
                        continue

        except Exception as e:
            print(f"Error in trailing thread: {e}")

        time.sleep(3)


# Start both background threads
threading.Thread(target=background_market_scanner_loop, daemon=True).start()
threading.Thread(target=background_trailing_and_exit_loop, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
