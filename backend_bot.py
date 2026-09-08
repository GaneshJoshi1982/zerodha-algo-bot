from datetime import datetime, time
import os
import threading
import time as ttime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from kiteconnect import KiteConnect
import numpy as np
import pandas as pd
import csv

app = FastAPI(title="Zerodha Algorithmic Trading Terminal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================
API_KEY = "magym2s4yk13gsze"
API_SECRET = "uxph73v40oemxf3c9xn48swqwbfmf"
TOKEN_FILE = "access_token.txt"
TRADE_LOG_FILE = "trade_history.csv"

MAX_TRADES_PER_SESSION = 2
SESSION_STATE = {
    "trades_today": {"NIFTY": 0, "BANKNIFTY": 0, "FINNIFTY": 0},
    "last_trade_time": None,
    "active_signal": "HOLD"
}

ACTIVE_TRADE = {
    "symbol": None,
    "entry_price": 0.0,
    "quantity": 0,
    "initial_sl": 0.0,
    "current_sl": 0.0,
    "trailing_activated": False,
    "transaction_type": None
}

LOT_SIZES = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25
}

INDEX_TOKENS = {
    "NIFTY": {"token": 256265, "symbol": "NSE:NIFTY 50", "lot": 25},
    "BANKNIFTY": {"token": 260105, "symbol": "NSE:NIFTY BANK", "lot": 15},
    "FINNIFTY": {"token": 257801, "symbol": "NSE:NIFTY FIN SERVICE", "lot": 25},
}

def get_saved_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            t = f.read().strip()
            if t: return t
    return None

# ==========================================
# 2. TECHNICAL INDICATORS & CONFLUENCE
# ==========================================
def calculate_rsi(series: pd.Series, period: int = 9) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calculate_wma(series: pd.Series, length: int = 21) -> pd.Series:
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(
        lambda window: np.dot(window, weights) / weights.sum(), raw=True
    )

def calculate_linreg_series(series: pd.Series, length: int = 11) -> pd.Series:
    x = np.arange(length)
    x_mean = x.mean()
    x_var = ((x - x_mean) ** 2).sum()

    def get_linreg_val(window):
        if len(window) < length:
            return np.nan
        y_mean = window.mean()
        slope = ((x - x_mean) * (window - y_mean)).sum() / x_var
        intercept = y_mean - slope * x_mean
        return intercept + slope * (length - 1)

    return series.rolling(window=length).apply(get_linreg_val, raw=True)

def check_hm_linreg_confluence(df: pd.DataFrame) -> str:
    if df.empty or len(df) < 30:
        return "HOLD"

    df = df.copy()
    df["rsi9"] = calculate_rsi(df["close"], period=9)
    df["hm_price_ema3"] = df["rsi9"].ewm(span=3, adjust=False).mean()
    df["hm_strength_wma21"] = calculate_wma(df["rsi9"], length=21)

    df["bopen"] = calculate_linreg_series(df["open"], length=11)
    df["bclose"] = calculate_linreg_series(df["close"], length=11)
    df["signal_line"] = df["bclose"].rolling(window=11).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    linreg_bull_cross = (latest["bclose"] > latest["signal_line"]) and (prev["bclose"] <= prev["signal_line"])
    linreg_bear_cross = (latest["bclose"] < latest["signal_line"]) and (prev["bclose"] >= prev["signal_line"])

    hm_bullish = latest["hm_price_ema3"] > latest["hm_strength_wma21"]
    hm_bearish = latest["hm_price_ema3"] < latest["hm_strength_wma21"]

    if linreg_bull_cross and hm_bullish:
        return "BUY_CE"
    elif linreg_bear_cross and hm_bearish:
        return "BUY_PE"

    return "HOLD"

# ==========================================
# 3. SYNCHRONIZED TWO-STEP STRATEGY
# ==========================================
def evaluate_two_step_signal(kite, symbol_key):
    try:
        idx_info = INDEX_TOKENS.get(symbol_key)
        if not idx_info:
            return "HOLD", None, 0.0

        to_date = datetime.now()
        from_date = to_date - pd.Timedelta(days=3)

        idx_candles = kite.historical_data(idx_info["token"], from_date, to_date, "5minute")
        df_idx = pd.DataFrame(idx_candles)
        index_signal = check_hm_linreg_confluence(df_idx)

        if index_signal == "HOLD":
            return "HOLD", None, 0.0

        trigger_row = df_idx.iloc[-1]
        trigger_time = trigger_row.get('date')

        quote_data = kite.ltp([idx_info["symbol"]])
        ltp = quote_data[idx_info["symbol"]]['last_price']
        strike_step = 50 if symbol_key in ["NIFTY", "FINNIFTY"] else 100
        atm_strike = int(round(ltp / strike_step) * strike_step)
        option_type = "CE" if index_signal == "BUY_CE" else "PE"
        
        opt_symbol = f"{symbol_key}26SEP{atm_strike}{option_type}"

        instruments = kite.instruments("NFO")
        opt_token = next((i["instrument_token"] for i in instruments if i["tradingsymbol"] == opt_symbol), None)

        if opt_token:
            opt_candles = kite.historical_data(opt_token, from_date, to_date, "5minute")
            df_opt = pd.DataFrame(opt_candles)
            if not df_opt.empty and 'date' in df_opt.columns:
                # Strictly synchronize option data up to the index trigger timestamp
                matched_opt = df_opt[df_opt['date'] <= trigger_time]
                if len(matched_opt) >= 30:
                    opt_signal = check_hm_linreg_confluence(matched_opt)
                    if opt_signal != "HOLD" and opt_signal == index_signal:
                        swing_low = float(matched_opt["low"].iloc[-5:].min())
                        return index_signal, opt_symbol, swing_low

        return "HOLD", None, 0.0
    except Exception as e:
        print(f"[Two-Step Evaluation Error]: {e}")
        return "HOLD", None, 0.0

def log_trade(symbol, action, price):
    file_exists = os.path.exists(TRADE_LOG_FILE)
    with open(TRADE_LOG_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Symbol", "Action", "Price"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, action, price])

# ==========================================
# 4. API ENDPOINTS & BACKGROUND ENGINE
# ==========================================
@app.get("/health")
def health_check():
    return {"status": "running", "session_state": SESSION_STATE}

def background_trading_engine():
    token = get_saved_token()
    if not token:
        print("❌ Background Engine Error: No access token available.")
        return

    kite = KiteConnect(api_key=API_KEY)
    kite.set_access_token(token)

    print("🚀 Background Trading Engine Started Successfully.")
    while True:
        try:
            now = datetime.now()
            # Run checks across symbols during market hours (9:15 AM to 3:30 PM)
            if 9 <= now.hour <= 15:
                for symbol_key in INDEX_TOKENS.keys():
                    if SESSION_STATE["trades_today"][symbol_key] < MAX_TRADES_PER_SESSION:
                        signal, opt_symbol, stop_loss = evaluate_two_step_signal(kite, symbol_key)
                        SESSION_STATE["active_signal"] = signal

                        if signal != "HOLD" and opt_symbol:
                            print(f"⚡ Valid Trade Found: {signal} on {opt_symbol}")
                            log_trade(opt_symbol, signal, 0.0)
                            SESSION_STATE["trades_today"][symbol_key] += 1
                            SESSION_STATE["last_trade_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
            ttime.sleep(60)
        except Exception as e:
            print(f"[Engine Loop Error]: {e}")
            ttime.sleep(60)

@app.on_event("startup")
def startup_event():
    engine_thread = threading.Thread(target=background_trading_engine, daemon=True)
    engine_thread.start()
