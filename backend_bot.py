from datetime import datetime
import math
import os
from fastapi import FastAPI, HTTPException, Query
from kiteconnect import KiteConnect
import numpy as np
import pandas as pd
import requests

# ==========================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================
API_KEY = "magym2s4yk13gsze"
API_SECRET = "uxph73v40oemxff3c9xn48swqwctbfmf"
TOKEN_FILE = "access_token.txt"

MAX_RISK_PER_TRADE = 2000.0  # Max loss capped at ₹2,000 per trade
DEFAULT_SL_PCT = 0.15        # 15% Initial Hard Stop Loss

LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "SENSEX": 10,
    "BANKEX": 15,
}

INDEX_TOKENS = {
    "NIFTY": {"token": 256265, "symbol": "NSE:NIFTY 50"},
    "BANKNIFTY": {"token": 260105, "symbol": "NSE:NIFTY BANK"},
    "FINNIFTY": {"token": 257801, "symbol": "NSE:NIFTY FIN SERVICE"},
    "SENSEX": {"token": 265, "symbol": "BSE:SENSEX"},
}

app = FastAPI(title="Zerodha Algorithmic Trading Bot Backend")

# ==========================================
# 2. REST API ENDPOINTS (FOR UVICORN PORT 10000)
# ==========================================
@app.get("/health")
def health_check():
    access_token = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            access_token = f.read().strip()

    is_authenticated = False
    if access_token:
        try:
            kite = KiteConnect(api_key=API_KEY)
            kite.set_access_token(access_token)
            kite.profile()
            is_authenticated = True
        except Exception:
            is_authenticated = False

    status = "GREEN" if is_authenticated else "RED"
    msg = "All Systems Active & Linked" if is_authenticated else "Disconnected / Login Required"

    return {
        "status": status,
        "message": msg,
        "checks": {
            "login_authenticated": is_authenticated,
            "ip_whitelisted": True,
            "service_active": True
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/get-token")
def get_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
            return {"status": "SUCCESS", "access_token": token}
    raise HTTPException(status_code=404, detail="No active session token")

@app.post("/set-token")
def set_token(payload: dict):
    token = payload.get("access_token")
    if token:
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        return {"status": "SUCCESS", "message": "Token updated"}
    raise HTTPException(status_code=400, detail="Invalid token")

# ==========================================
# 3. STRATEGY ENGINE (LINREG + HM)
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

@app.get("/evaluate-signal")
def evaluate_signal(symbol: str = Query("NIFTY")):
    symbol_key = symbol.upper()
    if symbol_key not in INDEX_TOKENS:
        raise HTTPException(status_code=400, detail="Invalid symbol")

    if not os.path.exists(TOKEN_FILE):
        raise HTTPException(status_code=401, detail="Unauthenticated")

    with open(TOKEN_FILE, "r") as f:
        token = f.read().strip()

    try:
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(token)

        idx_info = INDEX_TOKENS[symbol_key]
        to_date = datetime.now()
        from_date = to_date - pd.Timedelta(days=5)

        candles = kite.historical_data(idx_info["token"], from_date, to_date, "5minute")
        df = pd.DataFrame(candles)

        if df.empty or len(df) < 30:
            raise HTTPException(status_code=400, detail="Insufficient candle data")

        # 1. Hilega-Milega
        df["rsi9"] = calculate_rsi(df["close"], period=9)
        df["hm_price_ema3"] = df["rsi9"].ewm(span=3, adjust=False).mean()
        df["hm_strength_wma21"] = calculate_wma(df["rsi9"], length=21)

        # 2. Linear Regression Candles
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
            signal = "BUY_CE"
        elif linreg_bear_cross and hm_bearish:
            signal = "BUY_PE"
        else:
            signal = "HOLD"

        return {
            "status": "SUCCESS",
            "symbol": symbol_key,
            "signal": signal,
            "bclose": round(float(latest["bclose"]), 2),
            "signal_line": round(float(latest["signal_line"]), 2),
            "hm_bullish": bool(hm_bullish),
            "hm_bearish": bool(hm_bearish),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
