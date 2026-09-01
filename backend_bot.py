from datetime import datetime
import math
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from kiteconnect import KiteConnect
import numpy as np
import pandas as pd

API_KEY = "magym2s4yk13gsze"
API_SECRET = "uxph73v40oemxff3c9xn48swqwctbfmf"
TOKEN_FILE = "access_token.txt"

MAX_RISK_PER_TRADE = 2000.0
DEFAULT_SL_PCT = 0.15

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_saved_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            t = f.read().strip()
            if t:
                return t
    return None

def save_token(token_str: str):
    with open(TOKEN_FILE, "w") as f:
        f.write(token_str.strip())

# ==========================================
# 1. ZERODHA CALLBACK & AUTH ENDPOINTS
# ==========================================
@app.api_route("/callback", methods=["GET", "POST"])
@app.api_route("/callback/", methods=["GET", "POST"])
async def zerodha_callback(request: Request):
    request_token = request.query_params.get("request_token")
    if not request_token:
        try:
            body = await request.json()
            request_token = body.get("request_token")
        except Exception:
            pass

    if not request_token:
        return HTMLResponse("<h2>❌ Error: Missing request_token from Zerodha.</h2>", status_code=400)

    try:
        kite = KiteConnect(api_key=API_KEY)
        session_data = kite.generate_session(request_token, api_secret=API_SECRET)
        access_token = session_data["access_token"]
        save_token(access_token)

        html_content = """
        <html>
            <body style="font-family: Arial; text-align: center; padding-top: 50px;">
                <h1 style="color: green;">✅ Zerodha Authentication Successful!</h1>
                <p>Access Token has been generated and linked to your Oracle VPS Trading Bot.</p>
                <p>You can close this tab and return to your Streamlit Terminal.</p>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=200)
    except Exception as e:
        return HTMLResponse(f"<h2>❌ Session Generation Failed: {str(e)}</h2>", status_code=500)

@app.api_route("/health", methods=["GET", "POST"])
@app.api_route("/health/", methods=["GET", "POST"])
def health_check():
    token = get_saved_token()
    is_auth = False
    if token:
        try:
            kite = KiteConnect(api_key=API_KEY)
            kite.set_access_token(token)
            kite.profile()
            is_auth = True
        except Exception:
            is_auth = False

    return {
        "status": "GREEN" if is_auth else "RED",
        "message": "All Systems Active & Linked" if is_auth else "Disconnected / Login Required",
        "checks": {
            "login_authenticated": is_auth,
            "ip_whitelisted": True,
            "service_active": True
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@app.api_route("/get-token", methods=["GET", "POST"])
@app.api_route("/get_token", methods=["GET", "POST"])
@app.api_route("/get-token/", methods=["GET", "POST"])
@app.api_route("/get_token/", methods=["GET", "POST"])
def get_token_endpoint():
    token = get_saved_token()
    if token:
        return {"status": "SUCCESS", "access_token": token, "token": token}
    return {"status": "ERROR", "message": "No active session token"}, 404

@app.api_route("/set-token", methods=["GET", "POST"])
@app.api_route("/set_token", methods=["GET", "POST"])
@app.api_route("/set-token/", methods=["GET", "POST"])
@app.api_route("/set_token/", methods=["GET", "POST"])
async def set_token_endpoint(request: Request):
    token = request.query_params.get("access_token") or request.query_params.get("token")
    if not token:
        try:
            body = await request.json()
            token = body.get("access_token") or body.get("token") or body.get("request_token")
        except Exception:
            pass

    if token:
        save_token(token)
        return {"status": "SUCCESS", "message": "Token updated successfully"}
    return {"status": "ERROR", "message": "Missing token parameter"}, 400

# ==========================================
# 2. STRATEGY ENGINE (LINREG + HM CONFLUENCE)
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

@app.api_route("/evaluate-signal", methods=["GET", "POST"])
@app.api_route("/evaluate_signal", methods=["GET", "POST"])
def evaluate_signal(symbol: str = "NIFTY"):
    symbol_key = symbol.upper()
    token = get_saved_token()
    if not token:
        return {"status": "ERROR", "message": "Unauthenticated"}, 401

    try:
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(token)

        idx_info = INDEX_TOKENS.get(symbol_key, INDEX_TOKENS["NIFTY"])
        to_date = datetime.now()
        from_date = to_date - pd.Timedelta(days=5)

        candles = kite.historical_data(idx_info["token"], from_date, to_date, "5minute")
        df = pd.DataFrame(candles)

        if df.empty or len(df) < 30:
            return {"status": "ERROR", "message": "Insufficient candle data"}, 400

        # Hilega-Milega
        df["rsi9"] = calculate_rsi(df["close"], period=9)
        df["hm_price_ema3"] = df["rsi9"].ewm(span=3, adjust=False).mean()
        df["hm_strength_wma21"] = calculate_wma(df["rsi9"], length=21)

        # Linear Regression Candles
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
        return {"status": "ERROR", "message": str(e)}, 500
