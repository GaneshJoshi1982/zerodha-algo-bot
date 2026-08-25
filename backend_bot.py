from datetime import datetime
import asyncio
import threading
import time
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from kiteconnect import KiteConnect
import pandas as pd
import numpy as np

# ==========================================
# 1. ZERODHA CONFIGURATION & CONSTANTS
# ==========================================
API_KEY = "magym2s4yk13gsze"
API_SECRET = "83cuxyx91lv9ae371ogcs6ckvu5kto8q"
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

app = FastAPI(title="Zerodha Automated Execution Bot Backend")

# System Active Position Memory State
ACTIVE_POSITIONS = {}
TRADE_LOGS = []

def get_kite_client():
    kite = KiteConnect(api_key=API_KEY)
    try:
        with open(TOKEN_FILE, "r") as f:
            access_token = f.read().strip()
        kite.set_access_token(access_token)
        return kite
    except Exception as e:
        print(f"Error restoring Kite Client: {e}")
        return None

# ==========================================
# 2. INDICATOR LOGIC (VWAP & EMA-9)
# ==========================================
def calculate_vwap_and_ema9(df_5m):
    """
    Computes real-time VWAP and 5-minute EMA-9 for dynamic stop-loss trailing.
    """
    if df_5m is None or df_5m.empty or len(df_5m) < 10:
        return 0.0, 0.0

    df = df_5m.copy()
    
    # Calculate VWAP
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3.0
    df['vwap'] = (df['tp'] * df['volume']).cumsum() / df['volume'].cumsum().replace(0, np.nan)
    
    # Calculate 5-Min EMA-9
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()

    latest_vwap = round(df['vwap'].iloc[-1], 2)
    latest_ema9 = round(df['ema_9'].iloc[-1], 2)
    return latest_vwap, latest_ema9

# ==========================================
# 3. BACKGROUND AUTOMATED TRAILING ENGINE
# ==========================================
def background_trailing_loop():
    """
    Continuous background daemon running every 3 seconds to update EMA-9 
    trailing stops and trigger exits.
    """
    print("⚡ Background Execution Engine & Dynamic Trailing Engine Started.")
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
                    pos["unrealized_pnl"] = round((ltp - pos["entry_price"]) * pos["quantity"], 2)

                    # 1. Target Hit Check
                    if ltp >= pos["target_price"]:
                        execute_market_exit(pos_id, reason="TARGET HIT (40%+)")
                        continue

                    # 2. Hard Stop Loss Check
                    if ltp <= pos["current_sl"]:
                        execute_market_exit(pos_id, reason="HARD STOP LOSS BREACHED")
                        continue

                    # 3. Dynamic EMA-9 Trailing Calculation
                    to_date = datetime.now()
                    from_date = to_date.replace(hour=9, minute=15, second=0)
                    candles = kite.historical_data(
                        instrument_token=token,
                        from_date=from_date,
                        to_date=to_date,
                        interval="5minute"
                    )
                    df_5m = pd.DataFrame(candles)

                    if not df_5m.empty:
                        _, ema9_val = calculate_vwap_and_ema9(df_5m)
                        
                        # Trail SL higher if EMA-9 moves above entry and initial SL
                        if ema9_val > pos["current_sl"] and ltp > pos["entry_price"]:
                            pos["current_sl"] = ema9_val
                            TRADE_LOGS.append(
                                f"📈 [{datetime.now().strftime('%H:%M:%S')}] TRAILING SL RAISED to ₹{ema9_val} for {tradingsymbol}"
                            )

                        # Auto-Exit on Candle Breach below EMA-9
                        latest_close = df_5m["close"].iloc[-1]
                        if latest_close < ema9_val and ema9_val > pos["entry_price"]:
                            execute_market_exit(pos_id, reason="5M EMA-9 BREACH (PROFIT LOCKED)")

        except Exception as e:
            print(f"Error in trailing loop: {e}")

        time.sleep(3)

# Start Background Thread on Launch
trailing_thread = threading.Thread(target=background_trailing_loop, daemon=True)
trailing_thread.start()

# ==========================================
# 4. FASTAPI ENDPOINTS FOR MOBILE APP CONTROL
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
    exit_side = kite.TRANSACTION_TYPE_SELL if pos["side"] == "BUY" else kite.TRANSACTION_TYPE_BUY
    
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=pos["exchange"],
            tradingsymbol=pos["tradingsymbol"],
            transaction_type=exit_side,
            quantity=pos["quantity"],
            product=kite.PRODUCT_MIS,
            order_type=kite.ORDER_TYPE_MARKET
        )
        pos["status"] = f"CLOSED ({reason})"
        pos["exit_price"] = pos.get("current_ltp", 0.0)
        TRADE_LOGS.append(f"🔴 [{datetime.now().strftime('%H:%M:%S')}] AUTO EXIT: {pos['tradingsymbol']} | Reason: {reason}")
        return True
    except Exception as e:
        TRADE_LOGS.append(f"❌ [{datetime.now().strftime('%H:%M:%S')}] EXIT FAILED: {str(e)}")
        return False

@app.post("/api/order/submit")
def submit_automated_order(req: OrderRequest):
    kite = get_kite_client()
    if not kite:
        raise HTTPException(status_code=500, detail="Zerodha API Client Unavailable")

    # Safety Risk Check: Max Loss <= Cap
    initial_sl = round(req.price * 0.85, 2)
    target_price = round(req.price * 1.40, 2)
    projected_risk = (req.price - initial_sl) * req.quantity

    if projected_risk > req.max_risk_inr:
        raise HTTPException(
            status_code=400,
            detail=f"Projected Risk (₹{projected_risk:,.2f}) exceeds Max Risk Limit (₹{req.max_risk_inr:,.2f})"
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
            price=req.price
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
            "unrealized_pnl": 0.0
        }

        TRADE_LOGS.append(f"🟢 [{datetime.now().strftime('%H:%M:%S')}] ORDER FIRED: {req.transaction_type} {req.quantity}x {req.tradingsymbol} @ ₹{req.price}")
        return {"status": "SUCCESS", "order_id": order_id, "position_id": pos_id}
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
    uvicorn.run(app, host="0.0.0.0", port=8000)