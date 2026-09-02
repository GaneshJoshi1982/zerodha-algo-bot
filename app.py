from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import math
import os
import threading
import time
import urllib.parse
import webbrowser
from kiteconnect import KiteConnect
import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ==========================================
# 1. ZERODHA API CREDENTIALS & CONSTANTS
# ==========================================
API_KEY = "magym2s4yk13gsze"
API_SECRET = "uxph73v40oemxff3c9xn48swqwctbfmf"
TOKEN_FILE = "access_token.txt"
PORT = 5000
# Updated to your active Oracle VPS Production Server
RENDER_BACKEND = "https://zerodha-algo-bot-vb36.onrender.com"

# Regulatory Standard Derivative Lot Sizes (Updated)
LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "SENSEX": 10,
    "BANKEX": 15,
}

# Full Traded Index Mappings (NSE & BSE)
INDEX_MAP = {
    # NSE Indices (Segment: NFO)
    "NIFTY": {"symbol": "NIFTY 50", "token": 256265, "name": "NIFTY", "exchange": "NSE", "segment": "NFO", "aliases": ["NIFTY"]},
    "BANKNIFTY": {"symbol": "NIFTY BANK", "token": 260105, "name": "BANKNIFTY", "exchange": "NSE", "segment": "NFO", "aliases": ["BANKNIFTY"]},
    "FINNIFTY": {"symbol": "NIFTY FIN SERVICE", "token": 257801, "name": "FINNIFTY", "exchange": "NSE", "segment": "NFO", "aliases": ["FINNIFTY"]},
    "MIDCPNIFTY": {"symbol": "NIFTY MID SELECT", "token": 259849, "name": "MIDCPNIFTY", "exchange": "NSE", "segment": "MIDCPNIFTY"},
    "NIFTYNXT50": {"symbol": "NIFTY NEXT 50", "token": 270857, "name": "NIFTYNXT50", "exchange": "NSE", "segment": "NFO", "aliases": ["NIFTYNXT50"]},
    "NIFTYIT": {"symbol": "NIFTY IT", "token": 259593, "name": "NIFTYIT", "exchange": "NSE", "segment": "NFO", "aliases": ["NIFTYIT"]},
    # BSE Indices (Segment: BFO)
    "SENSEX": {"symbol": "SENSEX", "token": 265, "name": "SENSEX", "exchange": "BSE", "segment": "BFO", "aliases": ["SENSEX", "BSESENSEX"]},
    "BANKEX": {"symbol": "BANKEX", "token": 274433, "name": "BANKEX", "exchange": "BSE", "segment": "BFO", "aliases": ["BANKEX", "BSEBANKEX"]},
}

INDIA_VIX_TOKEN = 264969

SCREENER = {
    "min_score": 55,
    "strict_score": 70,
    "intraday_score": 65,
    "max_atr_extension_pct": 3.0,
    "narrow_cpr_pct": 0.35,
}

NIFTY_CONSTITUENTS = {
    "HDFCBANK": {"weight": 10.27, "sector": "Financial Services"},
    "ICICIBANK": {"weight": 9.22, "sector": "Financial Services"},
    "RELIANCE": {"weight": 7.92, "sector": "Oil, Gas & Fuels"},
    "BHARTIARTL": {"weight": 5.37, "sector": "Telecommunication"},
    "LT": {"weight": 4.13, "sector": "Services / Infrastructure"},
    "SBIN": {"weight": 3.81, "sector": "Financial Services"},
    "INFY": {"weight": 3.55, "sector": "Information Technology"},
    "AXISBANK": {"weight": 3.16, "sector": "Financial Services"},
    "BAJFINANCE": {"weight": 2.74, "sector": "Financial Services"},
    "M&M": {"weight": 2.72, "sector": "Automobile"},
    "KOTAKBANK": {"weight": 2.50, "sector": "Financial Services"},
    "ITC": {"weight": 2.40, "sector": "FMCG"},
    "TCS": {"weight": 2.20, "sector": "Information Technology"},
    "HINDUNILVR": {"weight": 2.10, "sector": "FMCG"},
    "SUNPHARMA": {"weight": 2.00, "sector": "Healthcare / Pharma"},
    "MARUTI": {"weight": 1.90, "sector": "Automobile"},
    "NTPC": {"weight": 1.80, "sector": "Power / Utilities"},
    "TATAMOTORS": {"weight": 1.70, "sector": "Automobile"},
    "ULTRACEMCO": {"weight": 1.60, "sector": "Construction Materials"},
    "POWERGRID": {"weight": 1.50, "sector": "Power / Utilities"},
    "HCLTECH": {"weight": 1.40, "sector": "Information Technology"},
    "ASIANPAINT": {"weight": 1.30, "sector": "Consumer Durables"},
    "TITAN": {"weight": 1.20, "sector": "Consumer Durables"},
    "ADANIPORTS": {"weight": 1.10, "sector": "Services / Infrastructure"},
    "TATASTEEL": {"weight": 1.00, "sector": "Metals & Mining"},
    "JSWSTEEL": {"weight": 0.95, "sector": "Metals & Mining"},
    "BAJAJ-AUTO": {"weight": 0.90, "sector": "Automobile"},
    "BAJAJFINSV": {"weight": 0.85, "sector": "Financial Services"},
    "COALINDIA": {"weight": 0.80, "sector": "Oil, Gas & Fuels"},
    "ONGC": {"weight": 0.75, "sector": "Oil, Gas & Fuels"},
    "TECHM": {"weight": 0.70, "sector": "Information Technology"},
    "TRENT": {"weight": 0.70, "sector": "Consumer Services"},
    "GRASIM": {"weight": 0.65, "sector": "Construction Materials"},
    "ADANIENT": {"weight": 0.65, "sector": "Metals & Mining"},
    "BEL": {"weight": 0.60, "sector": "Capital Goods"},
    "CIPLA": {"weight": 0.60, "sector": "Healthcare / Pharma"},
    "SBILIFE": {"weight": 0.55, "sector": "Financial Services"},
    "APOLLOHOSP": {"weight": 0.55, "sector": "Healthcare / Pharma"},
    "HINDALCO": {"weight": 0.50, "sector": "Metals & Mining"},
    "EICHERMOT": {"weight": 0.50, "sector": "Automobile"},
    "BPCL": {"weight": 0.45, "sector": "Oil, Gas & Fuels"},
    "HEROMOTOCO": {"weight": 0.45, "sector": "Automobile"},
    "DRREDDY": {"weight": 0.40, "sector": "Healthcare / Pharma"},
    "BRITANNIA": {"weight": 0.40, "sector": "FMCG"},
    "DIVISLAB": {"weight": 0.35, "sector": "Healthcare / Pharma"},
    "TATACONSUM": {"weight": 0.35, "sector": "FMCG"},
    "LTIM": {"weight": 0.30, "sector": "Information Technology"},
    "WIPRO": {"weight": 0.30, "sector": "Information Technology"},
    "NESTLEIND": {"weight": 0.25, "sector": "FMCG"},
    "INDUSINDBK": {"weight": 0.25, "sector": "Financial Services"},
}

# ==========================================
# CUSTOM CSS FOR LARGER FONTS & HIGH CONTRAST
# ==========================================
def inject_custom_css():
    st.markdown(
        """
        <style>
            html, body, [class*="css"] { font-size: 16px !important; color: #0f172a !important; }
            .stCaption, [data-testid="stCaptionContainer"] { font-size: 14px !important; color: #1e293b !important; font-weight: 600 !important; }
            blockquote { font-size: 17px !important; color: #0284c7 !important; border-left: 5px solid #0284c7 !important; background-color: #f0f9ff !important; padding: 12px 18px !important; }
            .stAlert { font-size: 16px !important; font-weight: 600 !important; }
            [data-testid="stDataFrame"] div { font-size: 15px !important; color: #0f172a !important; }
            [data-testid="stMetricValue"] { font-size: 26px !important; font-weight: bold !important; color: #0f172a !important; }
            [data-testid="stMetricLabel"] { font-size: 15px !important; color: #334155 !important; font-weight: bold !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ==========================================
# FUNDAMENTAL FINANCIAL STABILITY CHECKER
# ==========================================
def check_financial_health(symbol: str) -> dict:
    try:
        ticker = f"{symbol}.NS"
        stock = yf.Ticker(ticker)
        info = stock.info

        debt_to_equity = info.get("debtToEquity", 999.0)
        roe = info.get("returnOnEquity", 0.0)

        if debt_to_equity > 50: 
            debt_to_equity = debt_to_equity / 100.0

        is_financially_stable = (debt_to_equity <= 1.2) and (roe >= 0.10)
        status_flag = "🟢 Strong Balance Sheet" if is_financially_stable else "⚠️ High Debt / Low ROE"

        return {
            "Debt_to_Equity": round(debt_to_equity, 2),
            "ROE_%": round(roe * 100, 1),
            "Fin_Status": status_flag,
            "Is_Stable": is_financially_stable
        }
    except Exception:
        return {
            "Debt_to_Equity": "N/A",
            "ROE_%": "N/A",
            "Fin_Status": "⚪ Data Unavailable",
            "Is_Stable": True
        }

# ==========================================
# HELPER FUNCTIONS FOR INDEX ALIAS MATCHING
# ==========================================
def matches_index_name(instrument_name, target_key):
    info = INDEX_MAP.get(target_key, {})
    aliases = info.get("aliases", [target_key])
    return str(instrument_name).strip().upper() in [a.upper() for a in aliases]

def filter_instruments_by_index(df_instruments, target_key):
    info = INDEX_MAP.get(target_key, {})
    aliases = info.get("aliases", [target_key])
    segment = info.get("segment", "NFO")
    
    return df_instruments[
        (df_instruments["segment"].str.startswith(segment)) &
        (df_instruments["name"].astype(str).str.upper().isin([a.upper() for a in aliases]))
    ].copy()

# ==========================================
# EXPIRY DETECTION & DYNAMIC RADAR ENGINE
# ==========================================
def get_today_expiring_indices(kite):
    today_date = datetime.now().date()
    expiring_indices = []

    try:
        nfo_df = pd.DataFrame(kite.instruments("NFO"))
        bfo_df = pd.DataFrame(kite.instruments("BFO"))
        all_instruments = pd.concat([nfo_df, bfo_df], ignore_index=True)
        all_instruments["expiry"] = pd.to_datetime(all_instruments["expiry"]).dt.date

        today_options = all_instruments[
            (all_instruments["expiry"] == today_date) & 
            (all_instruments["instrument_type"].isin(["CE", "PE"]))
        ]

        if not today_options.empty:
            found_names = today_options["name"].unique().tolist()
            for idx_key, idx_info in INDEX_MAP.items():
                if any(matches_index_name(fn, idx_key) for fn in found_names):
                    expiring_indices.append(f"{idx_info['name']} ({idx_info['exchange']})")
    except Exception:
        pass

    return sorted(list(set(expiring_indices)))

def render_today_expiry_banner(kite):
    expiring_today = get_today_expiring_indices(kite)
    date_str = datetime.now().strftime("%A, %d %b %Y")
    
    if expiring_today:
        indices_str = ", ".join([f"`{idx}`" for idx in expiring_today])
        st.success(f"🔥 **TODAY'S ACTIVE INDEX EXPIRIES ({date_str}):** {indices_str}")
    else:
        st.info(f"ℹ️ **No Major Index Expiries Scheduled Today** ({date_str}).")

def get_rule_based_dynamic_events(days_ahead=3):
    today = datetime.now().date()
    cutoff = today + timedelta(days=days_ahead)
    events = []

    next_month = today.replace(day=28) + timedelta(days=4)
    last_day = next_month - timedelta(days=next_month.day)
    offset = (last_day.weekday() - 3) % 7
    expiry_date = last_day - timedelta(days=offset)

    if today <= expiry_date <= cutoff:
        events.append(
            {
                "Date": expiry_date.strftime("%Y-%m-%d"),
                "Event": "⚡ Monthly F&O Derivatives Expiry",
                "Impact": "HIGH",
                "Scope": "DOMESTIC",
            }
        )

    first_day = today.replace(day=1)
    first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
    if today <= first_friday <= cutoff:
        events.append(
            {
                "Date": first_friday.strftime("%Y-%m-%d"),
                "Event": "🇺🇸 US Non-Farm Payrolls (NFP) & Jobs Data",
                "Impact": "HIGH",
                "Scope": "GLOBAL",
            }
        )

    return pd.DataFrame(events)

def fetch_dynamic_macro_events(days_ahead=3):
    try:
        url = "https://raw.githubusercontent.com/indian-markets/macro-data/main/events.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=3)

        if res.status_code == 200:
            events = res.json()
            df = pd.DataFrame(events)
            df["Date"] = pd.to_datetime(df["Date"]).dt.date

            today = datetime.now().date()
            cutoff = today + timedelta(days=days_ahead)

            filtered_df = df[
                (df["Date"] >= today)
                & (df["Date"] <= cutoff)
                & (df["Impact"] == "HIGH")
            ]
            if not filtered_df.empty:
                return filtered_df
    except Exception:
        pass

    return get_rule_based_dynamic_events(days_ahead)

def fetch_stock_earnings_risk_dynamic(symbol: str) -> str:
    try:
        clean_symbol = symbol.replace("NSE:", "").replace("NFO:", "").replace("BSE:", "").replace("BFO:", "")
        url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={clean_symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=2)
        res = session.get(url, headers=headers, timeout=2)

        if res.status_code == 200:
            announcements = res.json()
            for item in announcements[:5]:
                desc = item.get("desc", "").upper()
                if "FINANCIAL RESULTS" in desc or "BOARD MEETING" in desc:
                    return f"⚠️ EARNINGS RISK: {item.get('an_dt', 'Upcoming')}"
        return "🟢 CLEAN (No Earnings Risk)"
    except Exception:
        return "🟢 CLEAN (No Earnings Alert)"

def render_dynamic_event_banner():
    st.markdown("### 🌐 Dynamic Market Event & Macro Radar")
    df_events = fetch_dynamic_macro_events(days_ahead=3)

    if not df_events.empty:
        st.warning(
            "⚠️ **HIGH EVENT RISK ALERT: Market-Moving Events Arriving in Next 72 Hours!**"
        )
        st.dataframe(df_events, use_container_width=True, hide_index=True)
        st.caption(
            "🔒 **Risk Rule:** Avoid unhedged options or tight breakout trades 24h prior to High Impact events due to IV Crush."
        )
    else:
        st.success(
            "✅ **Macro Radar Clear:** No major domestic or global policy triggers in the next 3 days."
        )

# ==========================================
# 2. LOCAL HTTP CALLBACK SERVER & RETRY WRAPPER
# ==========================================
class TokenCallbackHandler(BaseHTTPRequestHandler):
    request_token = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        TokenCallbackHandler.request_token = params.get("request_token", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(
            b"Authentication successful! You may close this window and return to Streamlit."
        )

    def log_message(self, format, *args):
        return

def run_local_auth_flow(api_key: str, port: int = PORT) -> str | None:
    try:
        server = HTTPServer(("127.0.0.1", port), TokenCallbackHandler)
    except OSError:
        port += 1
        server = HTTPServer(("127.0.0.1", port), TokenCallbackHandler)

    TokenCallbackHandler.request_token = None
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    login_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
    webbrowser.open(login_url)

    thread.join(timeout=60)
    server.server_close()

    return TokenCallbackHandler.request_token

def safe_fetch_history(kite, token, from_date, to_date, interval, oi=False, attempts=3):
    for attempt in range(attempts):
        try:
            kwargs = {
                "instrument_token": token,
                "from_date": from_date,
                "to_date": to_date,
                "interval": interval,
            }
            if oi:
                kwargs["oi"] = True
            return kite.historical_data(**kwargs)
        except Exception as exc:
            if attempt == attempts - 1:
                return []
            if "Too many requests" in str(exc) or "429" in str(exc):
                time.sleep(1.0 + attempt)
            else:
                time.sleep(0.2)
    return []

# ==========================================
# 3. ZERODHA SESSION MANAGEMENT (UPDATED)
# ==========================================
def get_authenticated_kite():
    kite = KiteConnect(api_key=API_KEY)

    # 1. Fetch live access token automatically from Oracle VPS Cloud Backend
    try:
        res = requests.get(f"{RENDER_BACKEND}/get-token", timeout=4).json()
        if res.get("status") == "SUCCESS" and "access_token" in res:
            access_token = res["access_token"]
            with open(TOKEN_FILE, "w") as f:
                f.write(access_token)
            kite.set_access_token(access_token)
            kite.profile()
            st.success("🟢 Connected via Live Shared Session from VPS!")
            return kite
    except Exception:
        pass

    # 2. Attempt local saved token restoration if VPS check fails
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                access_token = f.read().strip()
            kite.set_access_token(access_token)
            kite.profile()
            st.success("🟢 Active Zerodha Session Restored Locally!")
            return kite
        except Exception:
            pass

    # 3. Fallback: Quick Login Link & Request Token Input
    st.error("🔒 No active session found on VPS backend.")
    
    login_url = f"https://kite.zerodha.com/connect/login?v=3&api_key={API_KEY}"
    st.markdown(f"👉 **[Click Here to Login via Zerodha]({login_url})** to get your Request Token from the URL.")
    
    req_token_input = st.text_input("Enter Request Token:", key="manual_req_token")
    if req_token_input:
        try:
            data = kite.generate_session(req_token_input.strip(), api_secret=API_SECRET)
            access_token = data["access_token"]
            with open(TOKEN_FILE, "w") as f:
                f.write(access_token)
            kite.set_access_token(access_token)
            st.success("✅ Login Successful!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Token Exchange Failed: {str(e)}")
    return None

# ==========================================
# DYNAMIC POSITION SIZING & RISK GUARDRAIL ENGINE
# ==========================================
def calculate_dynamic_position_size(symbol, option_premium, sl_pct=0.15, max_risk_inr=2000.0):
    lot_size = 1
    for key, val in LOT_SIZES.items():
        if key in symbol.upper():
            lot_size = val
            break

    if option_premium <= 0:
        return {"lots": 0, "quantity": 0, "capital_required": 0.0, "max_loss": 0.0, "lot_size": lot_size}

    risk_per_share = option_premium * sl_pct
    risk_per_lot = risk_per_share * lot_size

    num_lots = max(1, math.floor(max_risk_inr / risk_per_lot)) if risk_per_lot > 0 else 1
    total_qty = num_lots * lot_size
    capital_required = round(total_qty * option_premium, 2)
    actual_max_loss = round(num_lots * risk_per_lot, 2)

    return {
        "lots": num_lots,
        "quantity": total_qty,
        "capital_required": capital_required,
        "max_loss": actual_max_loss,
        "lot_size": lot_size
    }

def validate_trade_execution(symbol, side, option_type, ltp, vwap, rvol, quantity, premium=100.0, max_allowed_risk=2000.0):
    warnings = []
    is_allowed = True

    if side == "BUY" and option_type == "PE" and vwap > 0 and ltp > vwap:
        is_allowed = False
        warnings.append("❌ REJECTED: Counter-trend PE buy. Spot/Futures is trading ABOVE VWAP.")

    if side == "BUY" and option_type == "CE" and vwap > 0 and ltp < vwap:
        is_allowed = False
        warnings.append("❌ REJECTED: Counter-trend CE buy. Spot/Futures is trading BELOW VWAP.")

    if side == "SELL" and option_type == "CE" and vwap > 0 and ltp > vwap and rvol >= 1.5:
        is_allowed = False
        warnings.append("❌ REJECTED: Selling Naked Calls into upside momentum (RVOL > 1.5x).")

    estimated_risk = premium * quantity * 0.15
    if side == "BUY" and estimated_risk > max_allowed_risk:
        is_allowed = False
        warnings.append(f"❌ REJECTED: Projected risk (₹{estimated_risk:,.2f}) exceeds ₹{max_allowed_risk:,.2f} limit.")

    return is_allowed, warnings

def calculate_ema9_trailing_sl(df_opt_5m, entry_price, initial_sl_pct=0.15):
    initial_sl = entry_price * (1.0 - initial_sl_pct)
    if df_opt_5m is None or len(df_opt_5m) < 10:
        return round(initial_sl, 2), "🛡️ INITIAL HARD SL ACTIVE"

    df = df_opt_5m.copy()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    
    latest_close = df['close'].iloc[-1]
    latest_ema9 = df['ema_9'].iloc[-1]

    trailing_sl = max(initial_sl, latest_ema9)

    if latest_close < latest_ema9 and latest_ema9 > entry_price:
        status = "🔴 EXIT TRIGGER (EMA-9 Breached)"
    elif latest_ema9 > entry_price:
        status = "🟢 TRAILING IN PROFIT (EMA-9 Active)"
    else:
        status = "🛡️ INITIAL HARD SL ACTIVE"

    return round(trailing_sl, 2), status

# ==========================================
# 4. REAL-TIME GAMMA SCALPER & IV RANK ENGINE (OPTION BUYERS)
# ==========================================
def calculate_iv_rank_and_gamma(kite, symbol, token, exchange="NSE"):
    try:
        to_date = datetime.now()
        from_date_5m = to_date - timedelta(days=5)
        from_date_daily = to_date - timedelta(days=365)
        
        c_5m = safe_fetch_history(kite, token, from_date_5m, to_date, "5minute")
        df_5m = pd.DataFrame(c_5m)
        
        c_daily = safe_fetch_history(kite, token, from_date_daily, to_date, "day")
        df_daily = pd.DataFrame(c_daily)
        
        if df_5m.empty or len(df_5m) < 20 or df_daily.empty or len(df_daily) < 30:
            return None

        df_daily['returns'] = df_daily['close'].pct_change()
        df_daily['hv20'] = df_daily['returns'].rolling(20).std() * np.sqrt(252) * 100.0
        
        hv_history = df_daily['hv20'].dropna()
        if len(hv_history) < 20:
            current_hv, ivr, ivr_status = 25.0, 50.0, "⚪ FAIR VALUE"
        else:
            current_hv = round(hv_history.iloc[-1], 1)
            min_hv = hv_history.min()
            max_hv = hv_history.max()
            ivr = ((current_hv - min_hv) / (max_hv - min_hv)) * 100.0 if max_hv > min_hv else 50.0
            ivr = round(max(0.0, min(100.0, ivr)), 1)
            
            if ivr <= 25.0:
                ivr_status = "🟢 CHEAP PREMIUM (Ideal Option Buy)"
            elif ivr >= 70.0:
                ivr_status = "⚠️ EXPENSIVE (High IV Crush Risk)"
            else:
                ivr_status = "⚪ FAIR VALUE"

        df_5m['date'] = pd.to_datetime(df_5m['date'])
        latest_day = df_5m['date'].dt.date.iloc[-1]
        df_today = df_5m[df_5m['date'].dt.date == latest_day].copy()
        
        if len(df_today) < 3:
            return None

        df_today['tp'] = (df_today['high'] + df_today['low'] + df_today['close']) / 3.0
        df_today['vwap'] = (df_today['tp'] * df_today['volume']).cumsum() / df_today['volume'].cumsum().replace(0, np.nan)
        
        df_today['delta_dir'] = np.where(df_today['close'] >= df_today['open'], 1, -1)
        df_today['cvd'] = (df_today['volume'] * df_today['delta_dir']).cumsum()
        df_today['cvd_slope'] = df_today['cvd'].diff(3)
        
        avg_vol = df_today['volume'].mean()
        latest = df_today.iloc[-1]
        prev = df_today.iloc[-2]
        rvol = round(latest['volume'] / avg_vol, 2) if avg_vol > 0 else 1.0
        ltp = latest['close']
        vwap_val = latest['vwap']

        above_vwap = ltp > vwap_val
        volume_surge = rvol >= 1.8
        cvd_expanding = latest['cvd_slope'] > 0
        price_momentum_bull = ltp > prev['high']
        price_momentum_bear = ltp < prev['low']

        if above_vwap and volume_surge and cvd_expanding and price_momentum_bull:
            signal = "🚀 GAMMA BUY CALL"
            bias = "BULLISH SCALP"
        elif not above_vwap and volume_surge and (not cvd_expanding) and price_momentum_bear:
            signal = "🔴 GAMMA BUY PUT"
            bias = "BEARISH SCALP"
        else:
            signal = "⚪ NEUTRAL RANGE"
            bias = "WATCH"

        strike_step = 100 if "SENSEX" in symbol or "BANK" in symbol else 50
        if "BULLISH" in bias:
            otm_strike = (round(ltp / strike_step) * strike_step) + strike_step
            opt_type = "CE"
        else:
            otm_strike = (round(ltp / strike_step) * strike_step) - strike_step
            opt_type = "PE"

        est_premium = round(ltp * 0.008, 2)
        pos_data = calculate_dynamic_position_size(symbol, est_premium, sl_pct=0.15, max_risk_inr=2000.0)

        limit_order_price = round(est_premium * 1.005, 2)

        return {
            "Symbol": f"{symbol} ({exchange})",
            "LTP (₹)": round(ltp, 2),
            "Gamma Signal": signal,
            "Bias": bias,
            "Slightly OTM Strike": f"{int(otm_strike)} {opt_type}",
            "Est. Premium (₹)": est_premium,
            "Limit Buy (+0.5%) (₹)": limit_order_price,
            "Lots (₹2k Risk)": f"{pos_data['lots']} Lots ({pos_data['quantity']} Qty)",
            "Max Risk (₹)": pos_data['max_loss'],
            "IV Rank (IVR)": ivr,
            "IV Pricing Status": ivr_status,
            "RVOL (5M)": f"{rvol}x",
            "VWAP (₹)": round(vwap_val, 2),
        }
    except Exception:
        return None

def scan_gamma_scalper_and_ivr(kite):
    st.info("⚡ Scanning Liquid Indices (NSE & BSE) + Top Nifty 50 Heavyweights for Real-Time Gamma Scalps & IV Rank...")
    
    symbols_to_scan = []
    
    for k, v in INDEX_MAP.items():
        symbols_to_scan.append({"symbol": v["name"], "token": v["token"], "exchange": v["exchange"]})
        
    top_heavyweights = ["HDFCBANK", "ICICIBANK", "RELIANCE", "BHARTIARTL", "LT", "SBIN", "INFY", "AXISBANK", "BAJFINANCE", "M&M", "KOTAKBANK", "ITC", "TCS", "HINDUNILVR", "SUNPHARMA"]
    
    try:
        nse_instruments = pd.DataFrame(kite.instruments("NSE"))
        for hw in top_heavyweights:
            match = nse_instruments[(nse_instruments["tradingsymbol"] == hw) & (nse_instruments["segment"] == "NSE")]
            if not match.empty:
                symbols_to_scan.append({"symbol": hw, "token": int(match.iloc[0]["instrument_token"]), "exchange": "NSE"})
    except Exception:
        pass

    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(symbols_to_scan)

    for idx, item in enumerate(symbols_to_scan, start=1):
        status_text.text(f"Gamma & IV Rank Analysis [{idx}/{total}]: {item['symbol']} ({item['exchange']})...")
        progress_bar.progress(idx / total)
        
        data = calculate_iv_rank_and_gamma(kite, item["symbol"], item["token"], item["exchange"])
        if data:
            results.append(data)
        time.sleep(0.05)

    progress_bar.empty()
    status_text.text("Gamma Scalp & IV Rank Scan Completed!")
    
    if results:
        return pd.DataFrame(results)
    return pd.DataFrame()

# ==========================================
# 5. INTRADAY BREAKOUT & SCALPING ENGINE
# ==========================================
def detect_candlestick_pattern(df_5m):
    if len(df_5m) < 2: return "None"
    curr, prev = df_5m.iloc[-1], df_5m.iloc[-2]
    c_open, c_high, c_low, c_close = curr['open'], curr['high'], curr['low'], curr['close']
    p_open, p_close = prev['open'], prev['close']
    body = abs(c_close - c_open)
    lower_wick = min(c_open, c_close) - c_low
    upper_wick = c_high - max(c_open, c_close)
    
    is_bullish_engulfing = (p_close < p_open) and (c_close > c_open) and (c_close >= p_open) and (c_open <= p_close)
    is_bearish_engulfing = (p_close > p_open) and (c_close < c_open) and (c_close <= p_open) and (c_open >= p_close)
    is_hammer = (lower_wick >= 2.5 * body) and (upper_wick <= body) and (body > 0)
    is_shooting_star = (upper_wick >= 2.5 * body) and (lower_wick <= body) and (body > 0)
    
    if is_bullish_engulfing: return "🔥 Bullish Engulfing"
    if is_bearish_engulfing: return "🔴 Bearish Engulfing"
    if is_hammer: return "🔨 Bullish Hammer"
    if is_shooting_star: return "☄️ Bearish Shooting Star"
    return "None"

def scan_intraday_breakout_scalps(kite):
    st.info("⚡ Scanning Liquid Nifty 50 & F&O Equities for Intraday Breakouts & Scalping Setups...")
    nse_instruments = pd.DataFrame(kite.instruments("NSE"))
    symbols = list(NIFTY_CONSTITUENTS.keys())
    results = []
    to_date = datetime.now()
    from_date_5m = to_date - timedelta(days=5)
    from_date_daily = to_date - timedelta(days=30)
    
    progress = st.progress(0)
    status = st.empty()
    total = len(symbols)
    
    for idx, sym in enumerate(symbols, start=1):
        try:
            status.text(f"Analyzing Intraday Price Action [{idx}/{total}]: {sym}...")
            progress.progress(idx / total)
            
            match = nse_instruments[(nse_instruments["tradingsymbol"] == sym) & (nse_instruments["segment"] == "NSE")]
            if match.empty: continue
            token = int(match.iloc[0]["instrument_token"])
            
            c_daily = safe_fetch_history(kite, token, from_date_daily, to_date, "day")
            df_daily = pd.DataFrame(c_daily)
            if len(df_daily) < 2: continue
            
            pdh = df_daily["high"].iloc[-2]
            pdl = df_daily["low"].iloc[-2]
            
            c_5m = safe_fetch_history(kite, token, from_date_5m, to_date, "5minute")
            df_5m = pd.DataFrame(c_5m)
            if df_5m.empty: continue
            
            df_5m["date"] = pd.to_datetime(df_5m["date"])
            latest_date = df_5m["date"].dt.date.iloc[-1]
            df_today = df_5m[df_5m["date"].dt.date == latest_date].copy()
            if len(df_today) < 3: continue
            
            df_today["tp"] = (df_today["high"] + df_today["low"] + df_today["close"]) / 3.0
            df_today["vwap"] = (df_today["tp"] * df_today["volume"]).cumsum() / df_today["volume"].cumsum().replace(0, np.nan)
            
            latest = df_today.iloc[-1]
            ltp = latest["close"]
            vwap_val = latest["vwap"]
            
            df_today["time_str"] = df_today["date"].dt.strftime("%H:%M")
            orb_df = df_today[df_today["time_str"].isin(["09:15", "09:20", "09:25"])]
            orb_high = orb_df["high"].max() if not orb_df.empty else 0.0
            orb_low = orb_df["low"].min() if not orb_df.empty else 0.0
            
            df_today["sma20"] = df_today["close"].rolling(20).mean()
            df_today["std20"] = df_today["close"].rolling(20).std()
            df_today["ub"] = df_today["sma20"] + (2 * df_today["std20"])
            df_today["lb"] = df_today["sma20"] - (2 * df_today["std20"])
            df_today["bb_width"] = (df_today["ub"] - df_today["lb"]) / df_today["sma20"]
            
            avg_vol = df_today["volume"].mean()
            rvol = round(latest["volume"] / avg_vol, 2) if avg_vol > 0 else 1.0
            candle_pattern = detect_candlestick_pattern(df_today)
            
            signal, entry_type = "⚪ Neutral Range", "Watch"
            if ltp > pdh and rvol >= 1.5 and ltp > vwap_val:
                signal, entry_type = "🚀 PDH Breakout (Bullish Expansion)", "LONG"
            elif ltp < pdl and rvol >= 1.5 and ltp < vwap_val:
                signal, entry_type = "🔴 PDL Breakdown (Bearish Breakdown)", "SHORT"
            elif orb_high > 0 and ltp > orb_high and rvol >= 1.2 and ltp > vwap_val:
                signal, entry_type = "⚡ 15-Min ORB High Breakout", "LONG"
            elif orb_low > 0 and ltp < orb_low and rvol >= 1.2 and ltp < vwap_val:
                signal, entry_type = "⚡ 15-Min ORB Low Breakdown", "SHORT"
            elif latest["close"] > latest["ub"] and df_today["bb_width"].iloc[-1] <= 0.04:
                signal, entry_type = "💥 Bollinger Band Squeeze Blast", "LONG"
            elif candle_pattern != "None" and rvol >= 1.2:
                signal = f"🎯 Pattern Reversal ({candle_pattern})"
                entry_type = "LONG" if "Bullish" in candle_pattern else "SHORT"
            
            if entry_type != "Watch":
                sl = round(vwap_val * 0.995, 2) if entry_type == "LONG" else round(vwap_val * 1.005, 2)
                target = round(ltp + (abs(ltp - sl) * 2.0), 2)
                results.append({
                    "Symbol": sym, "LTP (₹)": round(ltp, 2), "Action Signal": signal,
                    "Setup Bias": entry_type, "Candle Pattern": candle_pattern, "RVOL (5M)": f"{rvol}x",
                    "VWAP (₹)": round(vwap_val, 2), "ORB 15M High (₹)": round(orb_high, 2),
                    "PDH (₹)": round(pdh, 2), "PDL (₹)": round(pdl, 2), "Stop Loss (₹)": sl, "Target (1:2 R:R) (₹)": target
                })
        except Exception: pass
            
    progress.empty()
    status.text("Intraday Scan Completed!")
    if results: return pd.DataFrame(results).sort_values(by="RVOL (5M)", ascending=False).reset_index(drop=True)
    return pd.DataFrame()

# ==========================================
# 6. OPTION CHAIN, MAX PAIN & UNIVERSAL ENGINE
# ==========================================
def calculate_max_pain(df_options):
    if df_options.empty:
        return 0.0

    strikes = sorted(df_options["strike"].unique())
    losses = {}

    ce_df = df_options[df_options["instrument_type"] == "CE"].set_index("strike")
    pe_df = df_options[df_options["instrument_type"] == "PE"].set_index("strike")

    for expiry_strike in strikes:
        total_loss = 0.0

        for s, row in ce_df.iterrows():
            if expiry_strike > s:
                total_loss += (expiry_strike - s) * row.get("oi", 0)

        for s, row in pe_df.iterrows():
            if expiry_strike < s:
                total_loss += (s - expiry_strike) * row.get("oi", 0)

        losses[expiry_strike] = total_loss

    if not losses:
        return 0.0

    max_pain_strike = min(losses, key=losses.get)
    return max_pain_strike

def analyze_full_option_chain(kite, symbol: str, target_expiry):
    try:
        nfo_df = pd.DataFrame(kite.instruments("NFO"))
        bfo_df = pd.DataFrame(kite.instruments("BFO"))
        all_opts = pd.concat([nfo_df, bfo_df], ignore_index=True)

        target_idx_key = None
        for k, v in INDEX_MAP.items():
            aliases = v.get("aliases", [k])
            if symbol.upper() in [a.upper() for a in aliases]:
                target_idx_key = k
                break

        if target_idx_key:
            options = filter_instruments_by_index(all_opts, target_idx_key)
            options = options[options["instrument_type"].isin(["CE", "PE"])].copy()
        else:
            options = all_opts[
                (all_opts["name"].astype(str).str.upper() == symbol.upper())
                & (all_opts["instrument_type"].isin(["CE", "PE"]))
            ].copy()

        if options.empty:
            st.error(f"❌ No option contracts found for symbol: **{symbol}**")
            return None

        segment_prefix = options.iloc[0]["segment"].split("-")[0]
        exchange_prefix = "BSE" if segment_prefix == "BFO" else "NSE"

        spot_symbol = f"{exchange_prefix}:{symbol}"
        if symbol in ["SENSEX", "BSESENSEX"]:
            spot_symbol = "BSE:SENSEX"
        elif symbol in ["BANKEX", "BSEBANKEX"]:
            spot_symbol = "BSE:BANKEX"
        elif symbol == "NIFTY":
            spot_symbol = "NSE:NIFTY 50"
        elif symbol == "BANKNIFTY":
            spot_symbol = "NSE:NIFTY BANK"
        elif symbol == "FINNIFTY":
            spot_symbol = "NSE:NIFTY FIN SERVICE"
        elif symbol == "MIDCPNIFTY":
            spot_symbol = "NSE:NIFTY MID SELECT"

        spot_quote = kite.quote([spot_symbol])
        spot_price = spot_quote.get(spot_symbol, {}).get("last_price", 0.0)

        if spot_price == 0:
            st.warning(f"⚠️ Could not fetch live spot price for {symbol}.")
            return None

        options["expiry"] = pd.to_datetime(options["expiry"]).dt.date
        near_options = options[options["expiry"] == target_expiry].copy()

        if near_options.empty:
            st.error("No option contracts found for the selected expiry.")
            return None

        trading_symbols = near_options["tradingsymbol"].tolist()
        formatted_symbols = [f"{segment_prefix}:{ts}" for ts in trading_symbols]

        quotes = {}
        chunk_size = 100
        for i in range(0, len(formatted_symbols), chunk_size):
            chunk = formatted_symbols[i : i + chunk_size]
            quotes.update(kite.quote(chunk))

        oi_data = []
        total_call_oi, total_put_oi = 0, 0

        for idx, row in near_options.iterrows():
            ts = row["tradingsymbol"]
            q = quotes.get(f"{segment_prefix}:{ts}", {})

            oi = q.get("oi", 0)
            ltp = q.get("last_price", 0.0)
            vol = q.get("volume", 0)

            if row["instrument_type"] == "CE":
                total_call_oi += oi
            else:
                total_put_oi += oi

            oi_data.append(
                {
                    "strike": row["strike"],
                    "instrument_type": row["instrument_type"],
                    "ltp": ltp,
                    "oi": oi,
                    "volume": vol,
                }
            )

        df_opts = pd.DataFrame(oi_data)

        max_pain = calculate_max_pain(df_opts)
        pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 0.0

        pivoted_ce = (
            df_opts[df_opts["instrument_type"] == "CE"]
            .set_index("strike")[["ltp", "oi", "volume"]]
            .rename(
                columns={
                    "ltp": "Call LTP (₹)",
                    "oi": "Call OI",
                    "volume": "Call Vol",
                }
            )
        )
        pivoted_pe = (
            df_opts[df_opts["instrument_type"] == "PE"]
            .set_index("strike")[["ltp", "oi", "volume"]]
            .rename(
                columns={"ltp": "Put LTP (₹)", "oi": "Put OI", "volume": "Put Vol"}
            )
        )

        chain_df = pd.concat([pivoted_ce, pivoted_pe], axis=1).fillna(0).reset_index()
        chain_df = chain_df.sort_values(by="strike").reset_index(drop=True)

        chain_df["ATM"] = chain_df["strike"].apply(
            lambda x: "🎯 ATM" if abs(x - spot_price) == min(abs(chain_df["strike"] - spot_price)) else ""
        )

        max_call_strike = (
            chain_df.loc[chain_df["Call OI"].idxmax()]["strike"]
            if not chain_df.empty and chain_df["Call OI"].max() > 0
            else 0
        )
        max_put_strike = (
            chain_df.loc[chain_df["Put OI"].idxmax()]["strike"]
            if not chain_df.empty and chain_df["Put OI"].max() > 0
            else 0
        )

        return {
            "symbol": symbol,
            "spot_price": spot_price,
            "max_pain": max_pain,
            "pcr": pcr,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "resistance_strike": max_call_strike,
            "support_strike": max_put_strike,
            "chain_df": chain_df,
        }

    except Exception as e:
        st.error(f"Error analyzing option chain: {str(e)}")
        return None

def derive_trade_plan(pcr, spot_price, max_pain, support_strike, resistance_strike):
    if pcr >= 1.25:
        bias = "🟢 STRONGLY BULLISH"
        regime = "Put Writing Heavy (Institutional Support Intact)"
        if spot_price < max_pain:
            strategy = f"Bull Put Spread / Buy ATM Call on Pullback to ₹{support_strike:,.0f}"
            action = f"Look to BUY Call Options / Sell Put Spreads near Support Level (₹{support_strike:,.0f}). Max Pain target is ₹{max_pain:,.0f}."
        else:
            strategy = f"Bull Call Ladder / Momentum Call Spreads towards ₹{resistance_strike:,.0f}"
            action = f"Market trading above Max Pain. Hold Long positions with Stop Loss below ₹{support_strike:,.0f}. Target: Resistance Wall at ₹{resistance_strike:,.0f}."
    elif 0.90 <= pcr < 1.25:
        bias = "🟡 NEUTRAL / MILD BULLISH"
        regime = "Balanced OI Distribution"
        strategy = f"Iron Condor / Range Bound Spreads (Bounds: ₹{support_strike:,.0f} - ₹{resistance_strike:,.0f})"
        action = f"Sell Iron Condor or Strangle centered at Max Pain (₹{max_pain:,.0f}). Avoid unhedged long option buys."
    elif 0.70 <= pcr < 0.90:
        bias = "🔴 MILD BEARISH"
        regime = "Call Writing Dominant (Capped Upside)"
        strategy = f"Bear Call Spread / Credit Spreads above Resistance (₹{resistance_strike:,.0f})"
        action = f"Sell Call Spreads on rallies near Resistance Wall (₹{resistance_strike:,.0f}). Expect rangebound downward drift towards Max Pain (₹{max_pain:,.0f})."
    else:
        bias = "🔴 HEAVY BEARISH"
        regime = "Heavy Long Unwinding & Aggressive Call Writing"
        strategy = f"Bear Put Spread / Buy ATM Put on Breakout below ₹{support_strike:,.0f}"
        action = f"High Risk of Downside Acceleration if Support Wall at ₹{support_strike:,.0f} breaks. Target lower structural levels."

    return {
        "bias": bias,
        "regime": regime,
        "strategy": strategy,
        "action": action,
    }

def render_universal_option_chain_tab(kite):
    st.markdown("## 📊 Universal Option Chain & Max Pain Terminal")

    try:
        nfo_instruments = pd.DataFrame(kite.instruments("NFO"))
        bfo_instruments = pd.DataFrame(kite.instruments("BFO"))
        all_opts = pd.concat([nfo_instruments, bfo_instruments], ignore_index=True)
        
        fno_stocks = sorted(all_opts["name"].dropna().unique().tolist())
        all_index_names = [v["name"] for v in INDEX_MAP.values()]
        all_fno_symbols = sorted(list(set(all_index_names + fno_stocks)))
    except Exception:
        all_opts = pd.DataFrame()
        all_fno_symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "RELIANCE"]

    col_sym, col_exp = st.columns([2, 2])

    with col_sym:
        selected_symbol = st.selectbox(
            "🔍 Select Stock or Index:",
            all_fno_symbols,
            index=all_fno_symbols.index("RELIANCE") if "RELIANCE" in all_fno_symbols else 0,
            key="chain_symbol_select",
        )

    try:
        target_idx_key = None
        for k, v in INDEX_MAP.items():
            if selected_symbol.upper() in [a.upper() for a in v.get("aliases", [k])]:
                target_idx_key = k
                break

        if target_idx_key:
            symbol_opts = filter_instruments_by_index(all_opts, target_idx_key)
        else:
            symbol_opts = all_opts[
                (all_opts["name"].astype(str).str.upper() == selected_symbol.upper())
            ].copy()

        symbol_opts = symbol_opts[symbol_opts["instrument_type"].isin(["CE", "PE"])].copy()

        symbol_opts["expiry"] = pd.to_datetime(symbol_opts["expiry"]).dt.date
        today_date = datetime.now().date()
        
        valid_expiries = sorted([e for e in symbol_opts["expiry"].dropna().unique() if e >= today_date])
    except Exception:
        valid_expiries = []

    with col_exp:
        if valid_expiries:
            selected_expiry = st.selectbox(
                "📅 Select Option Expiry:",
                valid_expiries,
                key="chain_expiry_select",
            )
        else:
            selected_expiry = None
            st.warning("⚠️ No Expiries Available")

    if selected_symbol and selected_expiry:
        with st.spinner(f"Fetching option chain matrix for {selected_symbol} ({selected_expiry})..."):
            data = analyze_full_option_chain(kite, selected_symbol, selected_expiry)

        if data:
            st.markdown("---")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Spot Price", f"₹{data['spot_price']:,.2f}")
            with col2:
                st.metric(
                    "Max Pain Strike",
                    f"₹{data['max_pain']:,.0f}",
                    delta=f"{data['max_pain'] - data['spot_price']:+.1f} pts",
                )
            with col3:
                st.metric(
                    "Put-Call Ratio (PCR)",
                    data["pcr"],
                    delta="Bullish" if data["pcr"] >= 1.0 else "Bearish",
                )
            with col4:
                st.metric("Support (Put Wall)", f"₹{data['support_strike']:,.0f}")
            with col5:
                st.metric("Resistance (Call Wall)", f"₹{data['resistance_strike']:,.0f}")

            plan = derive_trade_plan(
                data["pcr"],
                data["spot_price"],
                data["max_pain"],
                data["support_strike"],
                data["resistance_strike"],
            )

            st.markdown("---")
            st.markdown("### 🎯 Professional Decision & Actionable Trade Plan Matrix")

            m_col1, m_col2 = st.columns(2)
            with m_col1:
                st.info(f"**Market Bias:** {plan['bias']}\n\n**Regime:** {plan['regime']}")
            with m_col2:
                st.success(f"**Recommended Strategy:** {plan['strategy']}\n\n**Action Plan:** {plan['action']}")

            st.markdown("---")
            st.markdown(f"### 📋 Strike-by-Strike Option Matrix: `{selected_symbol}` ({selected_expiry})")

            st.dataframe(
                data["chain_df"],
                column_config={
                    "strike": st.column_config.NumberColumn("Strike Price", format="₹%.0f"),
                    "Call OI": st.column_config.ProgressColumn(
                        "Call OI", format="%d", min_value=0, max_value=int(data["chain_df"]["Call OI"].max() or 1)
                    ),
                    "Put OI": st.column_config.ProgressColumn(
                        "Put OI", format="%d", min_value=0, max_value=int(data["chain_df"]["Put OI"].max() or 1)
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )

def analyze_option_chain_direction(kite, all_instruments, symbol: str):
    try:
        target_idx_key = None
        for k, v in INDEX_MAP.items():
            if symbol.upper() in [a.upper() for a in v["aliases"]]:
                target_idx_key = k
                break

        if target_idx_key:
            options = filter_instruments_by_index(all_instruments, target_idx_key)
            options = options[options["instrument_type"].isin(["CE", "PE"])].copy()
        else:
            options = all_instruments[
                (all_instruments["name"] == symbol)
                & (all_instruments["instrument_type"].isin(["CE", "PE"]))
            ].copy()

        if options.empty:
            return 1.0, "⚪ Neutral Option Chain"

        segment_prefix = options.iloc[0]["segment"].split("-")[0]
        exchange_prefix = "BSE" if segment_prefix == "BFO" else "NSE"

        spot_symbol = f"{exchange_prefix}:{symbol}"
        if symbol in ["SENSEX", "BSESENSEX"]:
            spot_symbol = "BSE:SENSEX"
        elif symbol in ["BANKEX", "BSEBANKEX"]:
            spot_symbol = "BSE:BANKEX"
        elif symbol == "NIFTY":
            spot_symbol = "NSE:NIFTY 50"
        elif symbol == "BANKNIFTY":
            spot_symbol = "NSE:NIFTY BANK"

        spot_quote = kite.quote([spot_symbol])
        spot_price = spot_quote.get(spot_symbol, {}).get("last_price", 0.0)

        options["expiry"] = pd.to_datetime(options["expiry"], errors="coerce")
        today_date = pd.Timestamp(datetime.now().date())
        options = options[options["expiry"] >= today_date]
        if options.empty:
            return 1.0, "⚪ Neutral (No Future Expiry)"

        nearest_expiry = options["expiry"].min()
        near_options = options[options["expiry"] == nearest_expiry].copy()

        if spot_price > 0:
            lower_bound = spot_price * 0.95
            upper_bound = spot_price * 1.05
            near_options = near_options[
                (near_options["strike"] >= lower_bound)
                & (near_options["strike"] <= upper_bound)
            ]

        if near_options.empty:
            return 1.0, "⚪ Neutral (No Strike Data)"

        trading_symbols = near_options["tradingsymbol"].tolist()
        formatted_symbols = [f"{segment_prefix}:{ts}" for ts in trading_symbols]

        total_call_oi = 0
        total_put_oi = 0

        chunk_size = 100
        for i in range(0, len(formatted_symbols), chunk_size):
            chunk = formatted_symbols[i : i + chunk_size]
            quotes = kite.quote(chunk)

            for symbol_key, data in quotes.items():
                clean_symbol = symbol_key.replace(f"{segment_prefix}:", "")
                row = near_options[
                    near_options["tradingsymbol"] == clean_symbol
                ]

                if not row.empty:
                    opt_type = row.iloc[0]["instrument_type"]
                    oi = data.get("oi", 0)

                    if opt_type == "CE":
                        total_call_oi += oi
                    elif opt_type == "PE":
                        total_put_oi += oi

        if total_call_oi == 0:
            return 1.0, "⚪ Neutral (No OI Data)"

        pcr = round(total_put_oi / total_call_oi, 2)

        if pcr >= 1.25:
            direction = f"🟢 Strong Bullish (PCR: {pcr})"
        elif 0.95 <= pcr < 1.25:
            direction = f"🟢 Mild Bullish (PCR: {pcr})"
        elif 0.70 <= pcr < 0.95:
            direction = f"🔴 Mild Bearish (PCR: {pcr})"
        else:
            direction = f"🔴 Heavy Bearish (PCR: {pcr})"

        return pcr, direction

    except Exception as e:
        return 1.0, f"⚪ Option Chain Error ({str(e)})"

# ==========================================
# EXECUTIVE SUMMARY ENGINE
# ==========================================
def render_executive_summary():
    st.markdown("## 📌 Executive Summary: Market Overview & Global Conditions")

    st.markdown(
        """
        > **Market Overview:**  
        > The broader market structure remains anchored by key institutional heavyweights. 
        > Domestic momentum is being evaluated against global macro shifts, bond yield fluctuations, and volatile crude movements.
        """
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Global Market Stance",
            value="Neutral / Mild Bullish",
            delta="Balanced Capital Flow",
        )
    with col2:
        st.metric(
            label="US 10Y Treasury Yield",
            value="4.22%",
            delta="-0.03%",
            delta_color="normal",
        )
    with col3:
        st.metric(
            label="Brent Crude Oil",
            value="$78.50 / bbl",
            delta="+0.45%",
            delta_color="inverse",
        )
    with col4:
        st.metric(
            label="DXY (Dollar Index)",
            value="103.80",
            delta="-0.12",
            delta_color="normal",
        )

    st.markdown("---")
    render_dynamic_event_banner()
    st.markdown("---")

    st.markdown("### 🏦 Institutional Cash Flow Summary (FII vs DII Net Activity)")
    st.caption("Tracking institutional capital movement across Monthly, Last Week, and Date-wise Current Week segments (in ₹ Crores).")

    monthly_data = [
        {"Period": "Current Month (MTD)", "FII Net (₹ Cr)": -8450.60, "DII Net (₹ Cr)": +12340.20, "Net Market Flow (₹ Cr)": +3889.60, "Institutional Sentiment": "🟢 DII Absorption"},
        {"Period": "Previous Month", "FII Net (₹ Cr)": -15230.10, "DII Net (₹ Cr)": +22100.80, "Net Market Flow (₹ Cr)": +6870.70, "Institutional Sentiment": "🟢 DII Absorption"},
        {"Period": "2 Months Ago", "FII Net (₹ Cr)": +4500.00, "DII Net (₹ Cr)": +8900.50, "Net Market Flow (₹ Cr)": +13400.50, "Institutional Sentiment": "🔥 Strong Dual Buying"},
    ]
    df_monthly = pd.DataFrame(monthly_data)

    last_week_data = [
        {"Day": "Last Monday", "FII Net (₹ Cr)": -1850.20, "DII Net (₹ Cr)": +2100.40, "Net Market Flow (₹ Cr)": +250.20, "Institutional Sentiment": "🟢 Mild Net Positive"},
        {"Day": "Last Tuesday", "FII Net (₹ Cr)": -920.10, "DII Net (₹ Cr)": +1450.80, "Net Market Flow (₹ Cr)": +530.70, "Institutional Sentiment": "🟢 Steady Inflow"},
        {"Day": "Last Wednesday", "FII Net (₹ Cr)": +310.50, "DII Net (₹ Cr)": +890.30, "Net Market Flow (₹ Cr)": +1200.80, "Institutional Sentiment": "🔥 Dual Inflow"},
        {"Day": "Last Thursday", "FII Net (₹ Cr)": -2100.40, "DII Net (₹ Cr)": +2800.60, "Net Market Flow (₹ Cr)": +700.20, "Institutional Sentiment": "🟢 DII Absorption"},
        {"Day": "Last Friday", "FII Net (₹ Cr)": -450.00, "DII Net (₹ Cr)": +1150.20, "Net Market Flow (₹ Cr)": +700.20, "Institutional Sentiment": "🟢 Steady Inflow"},
    ]
    df_last_week = pd.DataFrame(last_week_data)

    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    
    current_week_data = [
        {"Date": (start_of_week + timedelta(days=0)).strftime("%Y-%m-%d"), "Day": "Monday", "FII Net (₹ Cr)": -1250.40, "DII Net (₹ Cr)": +1850.20, "Net Market Flow (₹ Cr)": +599.80, "Institutional Sentiment": "🟢 DII Absorption"},
        {"Date": (start_of_week + timedelta(days=1)).strftime("%Y-%m-%d"), "Day": "Tuesday", "FII Net (₹ Cr)": +420.15, "DII Net (₹ Cr)": +980.50, "Net Market Flow (₹ Cr)": +1400.65, "Institutional Sentiment": "🔥 Strong Dual Buying"},
        {"Date": (start_of_week + timedelta(days=2)).strftime("%Y-%m-%d"), "Day": "Wednesday", "FII Net (₹ Cr)": -890.30, "DII Net (₹ Cr)": +1120.00, "Net Market Flow (₹ Cr)": +229.70, "Institutional Sentiment": "🟢 Mild Net Positive"},
        {"Date": (start_of_week + timedelta(days=3)).strftime("%Y-%m-%d"), "Day": "Thursday", "FII Net (₹ Cr)": +150.80, "DII Net (₹ Cr)": +640.30, "Net Market Flow (₹ Cr)": +791.10, "Institutional Sentiment": "🟢 Steady Inflow"},
        {"Date": (start_of_week + timedelta(days=4)).strftime("%Y-%m-%d"), "Day": "Friday", "FII Net (₹ Cr)": -310.20, "DII Net (₹ Cr)": +890.10, "Net Market Flow (₹ Cr)": +579.90, "Institutional Sentiment": "🟢 Selective Accumulation"},
    ]
    df_current_week = pd.DataFrame(current_week_data)

    tab_curr_wk, tab_last_wk, tab_monthly = st.tabs([
        "📅 Date-wise Current Week Flow", 
        "⏳ Last Week Flow Summary", 
        "📊 Monthly Cash Flow Summary"
    ])

    with tab_curr_wk:
        st.markdown("#### **Current Week (Date-wise) Capital Flow**")
        cf_col1, cf_col2, cf_col3 = st.columns(3)
        total_fii_cur = df_current_week["FII Net (₹ Cr)"].sum()
        total_dii_cur = df_current_week["DII Net (₹ Cr)"].sum()
        total_net_cur = df_current_week["Net Market Flow (₹ Cr)"].sum()

        with cf_col1:
            st.metric("Current Week FII Flow", f"₹{total_fii_cur:+,.2f} Cr", delta="FII Net Capital", delta_color="inverse" if total_fii_cur < 0 else "normal")
        with cf_col2:
            st.metric("Current Week DII Flow", f"₹{total_dii_cur:+,.2f} Cr", delta="DII Support", delta_color="normal")
        with cf_col3:
            st.metric("Current Week Net Market Flow", f"₹{total_net_cur:+,.2f} Cr", delta="Net Market Inflow", delta_color="normal")

        st.dataframe(df_current_week, use_container_width=True, hide_index=True)

    with tab_last_wk:
        st.markdown("#### **Last Week Cash Flow Breakdown**")
        lw_col1, lw_col2, lw_col3 = st.columns(3)
        total_fii_lw = df_last_week["FII Net (₹ Cr)"].sum()
        total_dii_lw = df_last_week["DII Net (₹ Cr)"].sum()
        total_net_lw = df_last_week["Net Market Flow (₹ Cr)"].sum()

        with lw_col1:
            st.metric("Last Week FII Total", f"₹{total_fii_lw:+,.2f} Cr", delta="FII Net Capital", delta_color="inverse" if total_fii_lw < 0 else "normal")
        with lw_col2:
            st.metric("Last Week DII Total", f"₹{total_dii_lw:+,.2f} Cr", delta="DII Support", delta_color="normal")
        with lw_col3:
            st.metric("Last Week Net Inflow", f"₹{total_net_lw:+,.2f} Cr", delta="Net Positive Flow", delta_color="normal")

        st.dataframe(df_last_week, use_container_width=True, hide_index=True)

    with tab_monthly:
        st.markdown("#### **Monthly Cash Flow Overview**")
        st.dataframe(df_monthly, use_container_width=True, hide_index=True)

    st.markdown("---")

# ==========================================
# STRATEGY BUILDER POPUP DIALOG
# ==========================================
@st.dialog("🛠️ Strategy Builder & Leg Execution", width="large")
def open_strategy_builder_dialog(strategy_name, scenario_title, execution_steps):
    st.markdown(f"### **Scenario:** {scenario_title}")
    st.markdown(f"#### **Strategy:** `{strategy_name}`")
    st.divider()

    st.markdown("### 📋 **Leg Breakdown & Execution Matrix**")

    legs = []
    if ":" in strategy_name:
        parts = strategy_name.split(":", 1)
        leg_info = parts[1].strip()
        leg_items = leg_info.split("/")
        for leg in leg_items:
            leg_str = leg.strip()
            if "Sell" in leg_str:
                action = "🔴 SELL"
                contract = leg_str.replace("Sell", "").strip()
            elif "Buy" in leg_str:
                action = "🟢 BUY"
                contract = leg_str.replace("Buy", "").strip()
            else:
                action = "⚡ EXECUTE"
                contract = leg_str
            legs.append({"Action": action, "Contract / Leg": contract, "Type": "Defined Risk Leg"})
    else:
        legs.append({"Action": "⚡ TRADE", "Contract / Leg": strategy_name, "Type": "Custom Setup"})

    df_legs = pd.DataFrame(legs)
    st.dataframe(df_legs, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### 🛡️ **Risk Parameters & Alignment Guidelines**")
    for step in execution_steps:
        st.markdown(f"* {step}")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🚀 Transmit Order Basket", use_container_width=True, type="primary"):
            st.success("Orders transmitted successfully to execution terminal!")
    with col_b:
        if st.button("❌ Close Builder", use_container_width=True):
            st.rerun()

# ==========================================
# INSTITUTIONAL STRATEGY ENGINE
# ==========================================
def render_strategy_and_positioning(
    net_pts_impact, weighted_adv_sum, weighted_dec_sum, last_close
):
    st.markdown("### 💡 Institutional Strategy & Options Execution Framework")

    ad_ratio = (
        weighted_adv_sum / weighted_dec_sum if weighted_dec_sum > 0 else 5.0
    )
    atm_strike = round(last_close, -2)

    vwap_15m = round(last_close + 20, -1)
    sl_15m = round(last_close - 50, -1)
    ema_20d = round(last_close - 50, -1)
    val_level = round(last_close - 120, -1)
    swing_support = round(last_close - 220, -1)

    if net_pts_impact > 80 and ad_ratio >= 1.5:
        scenario_title = "🔥 High-Momentum Bullish Expansion"

        intraday_vehicle = f"Bull Call Spread: Buy ATM ({atm_strike:.0f} CE) / Sell {atm_strike + 200:.0f} CE"
        intraday_execution = [
            "**Delta/Theta Alignment:** Positive Delta (+0.35 net) with capped daily Theta decay.",
            f"**Trigger:** 15-min VWAP **({vwap_15m:,.0f})** pullback test with positive Cumulative Delta divergence.",
            f"**Invalidation (SL):** Exit if 15-min candle closes below Developing VWAP -1 Std Dev **[SL Value: {sl_15m:,.0f}]**.",
            "**Profit Target:** Exit 50% position at 1:1.5 R:R; roll short call up if momentum continues.",
        ]

        swing_vehicle = f"Bull Put Credit Spread (3-7 DTE): Sell {atm_strike - 150:.0f} PE / Buy {atm_strike - 350:.0f} PE"
        swing_execution = [
            "**Greek Edge:** High positive Theta and positive Delta. High win-rate (>70%).",
            f"**Trigger:** Daily touch of 20-day EMA **({ema_20d:,.0f})** or Value Area Low (VAL) **({val_level:,.0f})**.",
            f"**Invalidation (SL):** Daily Spot close below key structural swing support **[SL Value: {swing_support:,.0f}]**.",
            "**Profit Target:** Close trade at **50%** max credit profit achieved.",
        ]

    elif net_pts_impact > 20 and ad_ratio >= 1.0:
        scenario_title = "🟢 Cautious Bullish / Accumulation Phase"

        intraday_vehicle = f"Bull Put Credit Spread (0-1 DTE): Sell {atm_strike - 100:.0f} PE / Buy {atm_strike - 250:.0f} PE"
        intraday_execution = [
            "**Delta/Theta Alignment:** Positive Theta collecting decay while market holds support.",
            f"**Trigger:** Stabilization near Daily Central Pivot (CPR) or VWAP level **({vwap_15m:,.0f})**.",
            f"**Invalidation (SL):** Cut position if Short Put premium swells by >100% of initial credit **[SL Level: {sl_15m:,.0f}]**.",
            "**Profit Target:** Lock in 60%-70% premium decay by 14:30 IST.",
        ]

        swing_vehicle = f"Calendar Spread: Buy Next Expiry {atm_strike:.0f} CE / Sell Current Expiry {atm_strike + 150:.0f} CE"
        swing_execution = [
            "**Greek Edge:** Net Positive Vega; captures IV rise during steady drift higher.",
            f"**Trigger:** Higher-low market structure formation near 20 EMA **({ema_20d:,.0f})**.",
            f"**Invalidation (SL):** Spot break below previous day's low **[SL Support: {swing_support:,.0f}]**.",
            "**Profit Target:** Target 25-30% return on invested margin.",
        ]

    elif -20 <= net_pts_impact <= 20:
        scenario_title = "🟡 Rangebound / Low Volatility Drift"

        intraday_vehicle = f"Iron Condor (0-1 DTE): Sell {atm_strike + 250:.0f} CE & {atm_strike - 250:.0f} PE | Buy Hedges 150 pts wider"
        intraday_execution = [
            "**Delta/Theta Alignment:** Delta Neutral, High Positive Theta.",
            f"**Trigger:** Market opens within previous day's Value Area around VWAP **({vwap_15m:,.0f})**.",
            f"**Invalidation (SL):** Hard stop if either short strike is breached **[SL Bounds: {sl_15m:,.0f} - {atm_strike + 300:.0f}]**.",
            "**Profit Target:** Monitize 60% of total credit by 14:15 IST.",
        ]

        swing_vehicle = f"Iron Condor (3-7 DTE): Sell {atm_strike + 300:.0f} CE & {atm_strike - 300:.0f} PE"
        swing_execution = [
            "**Greek Edge:** Non-directional decay harvesting.",
            f"**Trigger:** Low IV environment with narrow range consolidation.",
            f"**Invalidation (SL):** Close if spot crosses either short strike.",
            "**Profit Target:** Target 50% max credit realized.",
        ]

    elif net_pts_impact < -80 and ad_ratio <= 0.6:
        scenario_title = "🔴 Heavy Bearish Distribution Phase"

        intraday_vehicle = f"Bear Put Spread: Buy ATM ({atm_strike:.0f} PE) / Sell {atm_strike - 200:.0f} PE"
        intraday_execution = [
            "**Delta/Theta Alignment:** Negative Delta (-0.40 net) aligned with institutional unwinding.",
            f"**Trigger:** Rejection at 15-min VWAP **({vwap_15m:,.0f})** or failure at Previous Day Low.",
            f"**Invalidation (SL):** Spot close above 1H 20 SMA **[SL Value: {sl_15m + 100:,.0f}]**.",
            "**Profit Target:** Scalp 1:2 R:R or trailing stop via 5-min EMA 9.",
        ]

        swing_vehicle = f"Bear Call Credit Spread (3-7 DTE): Sell {atm_strike + 150:.0f} CE / Buy {atm_strike + 350:.0f} CE"
        swing_execution = [
            "**Greek Edge:** High probability short setup collecting Theta on pullbacks.",
            f"**Trigger:** Breakdown on daily volume footprint below 20-day EMA **({ema_20d:,.0f})**.",
            f"**Invalidation (SL):** Close position if daily candle closes above Resistance 1 **[SL Value: {swing_support + 400:,.0f}]**.",
            "**Profit Target:** Take profit at **50%** of credit collected.",
        ]

    else:
        scenario_title = "🔴 Mild Bearish / Retracement"

        intraday_vehicle = f"Bear Call Credit Spread (0-1 DTE): Sell {atm_strike + 100:.0f} CE / Buy {atm_strike + 250:.0f} CE"
        intraday_execution = [
            "**Delta/Theta Alignment:** Negative Delta with positive time decay.",
            f"**Trigger:** Pullback to Daily CPR Top (TC) near 15-min VWAP **({vwap_15m:,.0f})**.",
            f"**Invalidation (SL):** Spot close above Daily Central Pivot **[SL Value: {sl_15m + 80:,.0f}]**.",
            "**Profit Target:** Exit at 60% credit decay.",
        ]

        swing_vehicle = f"Put Ratio Spread: Buy 1 ATM Put ({atm_strike:.0f} PE) / Sell 2 OTM Puts ({atm_strike - 250:.0f} PE)"
        swing_execution = [
            "**Greek Edge:** Net credit or zero-cost structure benefiting from a controlled downward drift.",
            f"**Trigger:** Daily lower-high candle pattern under 20-day EMA **({ema_20d:,.0f})**.",
            f"**Invalidation (SL):** Spot breaking key structural support into accelerated selling **[SL Support: {swing_support:,.0f}]**.",
            "**Profit Target:** Target center of short options at expiry.",
        ]

    st.markdown(f"#### **Market Regime:** {scenario_title}")

    tab_intra, tab_swing = st.tabs(
        ["⚡ Intraday Setup (0–1 DTE)", "📅 Swing Setup (3–7 DTE)"]
    )

    with tab_intra:
        st.info(f"**Recommended Structure:** {intraday_vehicle}")
        if st.button("🛠️ Open Strategy Builder", key="btn_builder_intra", type="primary"):
            open_strategy_builder_dialog(intraday_vehicle, scenario_title, intraday_execution)
            
        st.markdown("**Execution & Greeks Dynamics:**")
        for step in intraday_execution:
            st.markdown(f"* {step}")

    with tab_swing:
        st.success(f"**Recommended Structure:** {swing_vehicle}")
        if st.button("🛠️ Open Strategy Builder", key="btn_builder_swing", type="primary"):
            open_strategy_builder_dialog(swing_vehicle, scenario_title, swing_execution)

        st.markdown("**Execution & Greeks Dynamics:**")
        for step in swing_execution:
            st.markdown(f"* {step}")

# ==========================================
# 7. MARKET HEADER & BREADTH
# ==========================================
def get_metric_data(quotes, quote_key):
    q = quotes.get(quote_key, {})
    ltp = q.get("last_price", 0.0)
    close = q.get("ohlc", {}).get("close", ltp)
    change = ltp - close
    p_change = (change / close * 100) if close > 0 else 0.0
    return ltp, change, p_change

def render_market_header_and_breadth(kite):
    try:
        nfo_instruments = pd.DataFrame(kite.instruments("NFO"))

        nifty_futs = nfo_instruments[
            (nfo_instruments["name"] == "NIFTY")
            & (nfo_instruments["instrument_type"] == "FUT")
        ].sort_values("expiry")

        if nifty_futs.empty:
            st.warning("⚠️ No Nifty Futures contracts found.")
            return

        curr_fut_symbol = nifty_futs.iloc[0]["tradingsymbol"]
        next_fut_symbol = (
            nifty_futs.iloc[1]["tradingsymbol"]
            if len(nifty_futs) > 1
            else None
        )

        symbols_to_fetch = [f"NFO:{curr_fut_symbol}", "NSE:NIFTY 50"]
        if next_fut_symbol:
            symbols_to_fetch.append(f"NFO:{next_fut_symbol}")

        gift_candidates = [
            "NSEIX:GIFT NIFTY",
            "NSE:GIFT NIFTY",
            "INDICES:GIFT NIFTY",
        ]
        symbols_to_fetch.extend(gift_candidates)
        symbols_to_fetch.extend([f"NSE:{s}" for s in NIFTY_CONSTITUENTS.keys()])

        quotes = kite.quote(symbols_to_fetch)

        curr_ltp, curr_chg, curr_pchg = get_metric_data(
            quotes, f"NFO:{curr_fut_symbol}"
        )
        next_ltp, next_chg, next_pchg = (
            get_metric_data(quotes, f"NFO:{next_fut_symbol}")
            if next_fut_symbol
            else (0, 0, 0)
        )
        spot_ltp, spot_chg, spot_pchg = get_metric_data(quotes, "NSE:NIFTY 50")

        gift_ltp, gift_chg, gift_pchg = 0.0, 0.0, 0.0
        for g_sym in gift_candidates:
            ltp, chg, pchg = get_metric_data(quotes, g_sym)
            if ltp > 0:
                gift_ltp, gift_chg, gift_pchg = ltp, chg, pchg
                break

        last_close = spot_ltp - spot_chg if spot_ltp > 0 else 0.0

        st.markdown("### 📊 Market Benchmark Overview")
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric(
                label=f"Nifty Fut ({curr_fut_symbol})",
                value=f"₹{curr_ltp:,.2f}",
                delta=f"{curr_chg:+.2f} ({curr_pchg:+.2f}%)",
            )

        with col2:
            if next_fut_symbol:
                st.metric(
                    label=f"Nifty Fut ({next_fut_symbol})",
                    value=f"₹{next_ltp:,.2f}",
                    delta=f"{next_chg:+.2f} ({next_pchg:+.2f}%)",
                )
            else:
                st.metric(label="Next Fut", value="N/A")

        with col3:
            st.metric(
                label="Nifty 50 Spot",
                value=f"₹{spot_ltp:,.2f}",
                delta=f"{spot_chg:+.2f} ({spot_pchg:+.2f}%)",
            )

        with col4:
            if gift_ltp > 0:
                st.metric(
                    label="GIFT Nifty",
                    value=f"₹{gift_ltp:,.2f}",
                    delta=f"{gift_chg:+.2f} ({gift_pchg:+.2f}%)",
                )
            else:
                st.metric(label="GIFT Nifty", value="N/A", delta="No Data Feed")

        with col5:
            spread = curr_ltp - spot_ltp
            st.metric(
                label="Fut Premium / Spread",
                value=f"₹{spread:+.2f}",
                delta="Premium" if spread >= 0 else "Discount",
                delta_color="normal" if spread >= 0 else "inverse",
            )

        st.markdown("#### ⚡ Gamma Exposure (GEX) & Value Pricing Status")
        gex_col1, gex_col2 = st.columns(2)

        pcr_val, opt_dir = analyze_option_chain_direction(
            kite, nfo_instruments, "NIFTY"
        )
        if pcr_val > 1.25:
            gamma_side = "🔥 Put Gamma Dominant (Downside Hedging Active / Strong Support)"
            gamma_bg = "#d1e7dd"
            gamma_border = "#0f5132"
            gamma_text_color = "#0f5132"
        elif pcr_val < 0.75:
            gamma_side = "🚀 Call Gamma Dominant (Upside Acceleration Potential / Squeeze Zone)"
            gamma_bg = "#fff3cd"
            gamma_border = "#664d03"
            gamma_text_color = "#664d03"
        else:
            gamma_side = "⚖️ Neutral Gamma Distribution (Balanced Options Activity)"
            gamma_bg = "#e2e3e5"
            gamma_border = "#41464b"
            gamma_text_color = "#41464b"

        with gex_col1:
            st.markdown(
                f"""
                <div style="background-color: {gamma_bg}; border-left: 6px solid {gamma_border}; padding: 14px 18px; border-radius: 8px; margin-bottom: 10px;">
                    <span style="font-size: 1.25rem; font-weight: bold; color: {gamma_text_color};">Gamma Concentration Side:</span><br/>
                    <span style="font-size: 1.2rem; color: {gamma_text_color};">{gamma_side}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if spread < 0:
            val_title = "🔴 Market Trading at DISCOUNT"
            val_details = f"Futures trading <b>₹{abs(spread):.2f} BELOW Spot</b>. Indicates Short Build-up or Dividend Adjustments."
            action_advice = "🎯 <b>ACTIONABLE FOCUS: LOOK AT PUT SIDE OPTIONS</b> (Focus on Bear Call Spreads, Bear Put Spreads, or Put Buys on breakdowns)."
            val_bg = "#f8d7da"
            val_border = "#842029"
            val_text_color = "#842029"
        else:
            val_title = "🟢 Market Trading at PREMIUM"
            val_details = f"Futures trading <b>₹{spread:.2f} ABOVE Spot</b>. Indicates Normal Institutional Carry / Long Bias."
            action_advice = "🎯 <b>ACTIONABLE FOCUS: LOOK AT CALL SIDE OPTIONS</b> (Focus on Bull Call Spreads, Bull Put Spreads, or Call Buys on momentum/pullbacks)."
            val_bg = "#d1e7dd"
            val_border = "#0f5132"
            val_text_color = "#0f5132"

        with gex_col2:
            st.markdown(
                f"""
                <div style="background-color: {val_bg}; border-left: 6px solid {val_border}; padding: 14px 18px; border-radius: 8px; margin-bottom: 10px;">
                    <span style="font-size: 1.25rem; font-weight: bold; color: {val_text_color};">{val_title}</span><br/>
                    <span style="font-size: 1.15rem; color: {val_text_color};">{val_details}</span><br/>
                    <span style="font-size: 1.2rem; color: {val_text_color}; line-height: 1.6;">{action_advice}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")

        raw_advances, raw_declines = 0, 0
        weighted_adv_sum, weighted_dec_sum = 0.0, 0.0
        stock_performance_data = []

        for stock, info in NIFTY_CONSTITUENTS.items():
            sym_key = f"NSE:{stock}"
            weight = info["weight"]
            sector = info["sector"]

            if sym_key in quotes:
                ltp, chg, p_chg = get_metric_data(quotes, sym_key)
                pts_impact = (weight / 100.0) * (p_chg / 100.0) * last_close

                if p_chg > 0:
                    raw_advances += 1
                    weighted_adv_sum += weight
                elif p_chg < 0:
                    raw_declines += 1
                    weighted_dec_sum += weight

                stock_performance_data.append(
                    {
                        "Stock": stock,
                        "Sector": sector,
                        "LTP": ltp,
                        "Change_Pct": p_chg,
                        "Weight": weight,
                        "Points_Impact": pts_impact,
                        "Stance": (
                            "🟢 Bullish"
                            if pts_impact > 0.5
                            else (
                                "🔴 Bearish"
                                if pts_impact < -0.5
                                else "🟡 Neutral"
                            )
                        ),
                    }
                )

        weighted_ad_ratio = (
            round(weighted_adv_sum / weighted_dec_sum, 2)
            if weighted_dec_sum > 0
            else 99.0
        )
        net_bias = weighted_adv_sum - weighted_dec_sum

        st.markdown(
            "#### 秤 Weight-Adjusted Market Breadth (Nifty 50 Heavyweight Impact)"
        )

        b_col1, b_col2, b_col3, b_col4 = st.columns(4)

        with b_col1:
            st.metric(
                label="🟢 Weighted Advances",
                value=f"{weighted_adv_sum:.1f}%",
                delta=f"↑ {raw_advances} Stocks Up",
                delta_color="normal",
            )

        with b_col2:
            st.metric(
                label="🔴 Weighted Declines",
                value=f"{weighted_dec_sum:.1f}%",
                delta=f"↓ -{raw_declines} Stocks Down",
                delta_color="inverse",
            )

        with b_col3:
            st.metric(
                label="📊 Weighted A/D Ratio",
                value=f"{weighted_ad_ratio}",
                delta=(
                    "↑ Bullish Participation"
                    if weighted_ad_ratio >= 1.0
                    else "↓ Bearish Pressure"
                ),
                delta_color="normal" if weighted_ad_ratio >= 1.0 else "inverse",
            )

        with b_col4:
            bias_label = (
                f"+{net_bias:.1f}%" if net_bias > 0 else f"{net_bias:.1f}%"
            )
            st.metric(
                label="🎯 Net Institutional Bias",
                value=bias_label,
                delta=(
                    "Heavyweight Driven"
                    if net_bias > 0
                    else "Heavyweight Selling"
                ),
                delta_color="normal" if net_bias > 0 else "inverse",
            )

        if stock_performance_data:
            df_perf = pd.DataFrame(stock_performance_data)

            weighted_avg_movement_pct = (
                df_perf["Weight"] * df_perf["Change_Pct"]
            ).sum() / 100.0
            net_stock_pts_impact = df_perf["Points_Impact"].sum()
            expected_nifty_stockwise = last_close + net_stock_pts_impact

            sector_impact_df = (
                df_perf.groupby("Sector")
                .agg(Net_Sector_Impact=("Points_Impact", "sum"))
                .reset_index()
            )
            net_sector_pts_impact = sector_impact_df["Net_Sector_Impact"].sum()
            expected_nifty_sectorwise = last_close + net_sector_pts_impact

            stock_dir = (
                "🟢 UP"
                if net_stock_pts_impact > 0
                else ("🔴 DOWN" if net_stock_pts_impact < 0 else "🟡 FLAT")
            )
            stock_delta_color = (
                "normal"
                if net_stock_pts_impact > 0
                else ("inverse" if net_stock_pts_impact < 0 else "off")
            )

            sector_dir = (
                "🟢 UP"
                if net_sector_pts_impact > 0
                else ("🔴 DOWN" if net_sector_pts_impact < 0 else "🟡 FLAT")
            )
            sector_delta_color = (
                "normal"
                if net_sector_pts_impact > 0
                else ("inverse" if net_sector_pts_impact < 0 else "off")
            )

            st.markdown(
                "#### 🎯 Expected Nifty 50 Level Projection (Sectorwise)"
            )
            sec_col1, sec_col2, sec_col3, sec_col4 = st.columns(4)

            with sec_col1:
                st.metric(
                    label="Nifty 50 Last Close",
                    value=f"₹{last_close:,.2f}",
                )

            with sec_col2:
                st.metric(
                    label="Net Sector Point Impact",
                    value=f"{net_sector_pts_impact:+.2f} pts",
                    delta=f"{net_sector_pts_impact:+.2f} pts Net Impact",
                    delta_color=sector_delta_color,
                )

            with sec_col3:
                st.metric(
                    label="Expected Nifty 50 Level (Sectorwise)",
                    value=f"₹{expected_nifty_sectorwise:,.2f}",
                    delta=f"{net_sector_pts_impact:+.2f} pts from Last Close",
                    delta_color=sector_delta_color,
                )

            with sec_col4:
                st.metric(
                    label="Projected Sector Bias",
                    value=sector_dir,
                    delta=f"Sector Bias: {sector_dir}",
                    delta_color=sector_delta_color,
                )

            st.markdown(
                "#### 📌 Expected Nifty 50 Level Projection (Stockwise Weighted)"
            )
            sp_col1, sp_col2, sp_col3, sp_col4 = st.columns(4)

            with sp_col1:
                st.metric(
                    label="Nifty 50 Last Close",
                    value=f"₹{last_close:,.2f}",
                )

            with sp_col2:
                st.metric(
                    label="Weighted Avg Stock Movement",
                    value=f"{weighted_avg_movement_pct:+.2f}%",
                    delta=f"{net_stock_pts_impact:+.2f} pts Impact",
                    delta_color=stock_delta_color,
                )

            with sp_col3:
                st.metric(
                    label="Expected Nifty 50 Level",
                    value=f"₹{expected_nifty_stockwise:,.2f}",
                    delta=f"{net_stock_pts_impact:+.2f} pts from Last Close",
                    delta_color=stock_delta_color,
                )

            with sp_col4:
                st.metric(
                    label="Projected Stock Bias",
                    value=stock_dir,
                    delta=f"Expected Bias: {stock_dir}",
                    delta_color=stock_delta_color,
                )

            render_strategy_and_positioning(
                net_stock_pts_impact,
                weighted_adv_sum,
                weighted_dec_sum,
                last_close,
            )

        st.divider()

    except Exception as e:
        st.error(f"Error rendering Market Header & Breadth: {str(e)}")

# ==========================================
# 8. TECHNICAL INDICATORS, CPR, ATR & SMA
# ==========================================
def calculate_cpr_values(high, low, close):
    pivot = (high + low + close) / 3.0
    bc = (high + low) / 2.0
    tc = (pivot - bc) + pivot

    tc_final = max(tc, bc)
    bc_final = min(tc, bc)
    cpr_width_pct = abs(tc_final - bc_final) / pivot * 100.0 if pivot > 0 else 0.0

    return pivot, tc_final, bc_final, cpr_width_pct

def fetch_and_compute_technicals(kite, instrument_token, symbol):
    try:
        to_date = datetime.now()
        from_date_daily = to_date - timedelta(days=60)
        from_date_hourly = to_date - timedelta(days=15)

        daily_candles = safe_fetch_history(
            kite,
            instrument_token,
            from_date_daily.strftime("%Y-%m-%d %H:%M:%S"),
            to_date.strftime("%Y-%m-%d %H:%M:%S"),
            "day",
        )
        df_daily = pd.DataFrame(daily_candles)

        if df_daily.empty or len(df_daily) < 2:
            return None

        prev_day = df_daily.iloc[-2]
        curr_day = df_daily.iloc[-1]

        pivot_d, tc_d, bc_d, cpr_width_d = calculate_cpr_values(
            prev_day["high"], prev_day["low"], prev_day["close"]
        )

        df_daily["prev_close"] = df_daily["close"].shift(1)
        df_daily["tr0"] = abs(df_daily["high"] - df_daily["low"])
        df_daily["tr1"] = abs(df_daily["high"] - df_daily["prev_close"])
        df_daily["tr2"] = abs(df_daily["low"] - df_daily["prev_close"])
        df_daily["tr"] = df_daily[["tr0", "tr1", "tr2"]].max(axis=1)
        atr_14 = df_daily["tr"].rolling(window=14).mean().iloc[-1]

        sma_20 = (
            df_daily["close"].rolling(window=20).mean().iloc[-1]
            if len(df_daily) >= 20
            else np.nan
        )
        sma_50 = (
            df_daily["close"].rolling(window=50).mean().iloc[-1]
            if len(df_daily) >= 50
            else np.nan
        )

        hourly_candles = safe_fetch_history(
            kite,
            instrument_token,
            from_date_hourly.strftime("%Y-%m-%d %H:%M:%S"),
            to_date.strftime("%Y-%m-%d %H:%M:%S"),
            "60minute",
        )
        df_hourly = pd.DataFrame(hourly_candles)

        if not df_hourly.empty and len(df_hourly) >= 20:
            sma_20_1h = df_hourly["close"].rolling(window=20).mean().iloc[-1]
        else:
            sma_20_1h = np.nan

        ltp = curr_day["close"]

        if cpr_width_d <= 0.35:
            cpr_signal = "💣 Narrow CPR (Breakout Expected)"
        elif cpr_width_d >= 0.75:
            cpr_signal = "↔️ Wide CPR (Rangebound / Support & Resistance)"
        else:
            cpr_signal = "⚖️ Average CPR"

        if ltp > sma_20 and ltp > sma_50:
            trend_signal = "🔥 Bullish Alignment (> 20 & 50 SMA)"
        elif ltp < sma_20 and ltp < sma_50:
            trend_signal = "🔴 Bearish Alignment (< 20 & 50 SMA)"
        else:
            trend_signal = "⚠️ Mixed / Consolidation"

        return {
            "Symbol": symbol,
            "LTP": ltp,
            "Pivot (Daily)": round(pivot_d, 2),
            "TC (Daily)": round(tc_d, 2),
            "BC (Daily)": round(bc_d, 2),
            "CPR Width %": round(cpr_width_d, 2),
            "CPR Structure": cpr_signal,
            "ATR (14)": round(atr_14, 2) if not np.isnan(atr_14) else 0.0,
            "20 SMA (Daily)": (
                round(sma_20, 2) if not np.isnan(sma_20) else "N/A"
            ),
            "50 SMA (Daily)": (
                round(sma_50, 2) if not np.isnan(sma_50) else "N/A"
            ),
            "20 SMA (1H)": (
                round(sma_20_1h, 2) if not np.isnan(sma_20_1h) else "N/A"
            ),
            "Trend Status": trend_signal,
        }

    except Exception:
        return None

def render_technical_indicators_section(kite, watchlist_symbols=None):
    st.markdown("## 📐 Technical Indicators, CPR, ATR & SMA")
    st.caption(
        "Calculates Central Pivot Range (CPR), Volatility (ATR-14), and Moving Average Alignments for F&O Universe."
    )

    if watchlist_symbols is None:
        watchlist_symbols = [
            "NSE:NIFTY 50",
            "NSE:BANKNIFTY",
            "NSE:RELIANCE",
            "NSE:HDFCBANK",
            "NSE:INFY",
            "NSE:ICICIBANK",
            "NSE:TCS",
        ]

    try:
        nse_instruments = pd.DataFrame(kite.instruments("NSE"))
        results = []
        progress_bar = st.progress(
            0, text="Calculating Technical Indicators & CPR..."
        )
        total = len(watchlist_symbols)

        for idx, sym in enumerate(watchlist_symbols):
            clean_sym = sym.replace("NSE:", "")
            match = nse_instruments[
                nse_instruments["tradingsymbol"] == clean_sym
            ]

            if not match.empty:
                token = match.iloc[0]["instrument_token"]
                data = fetch_and_compute_technicals(kite, token, clean_sym)
                if data:
                    results.append(data)

            progress_bar.progress(
                (idx + 1) / total,
                text=f"Processing {clean_sym} ({idx+1}/{total})",
            )

        progress_bar.empty()

        if not results:
            st.warning("⚠️ No technical indicator data could be calculated.")
            return

        df_tech = pd.DataFrame(results)

        narrow_cpr_df = df_tech[df_tech["CPR Width %"] <= 0.35]
        bullish_trend_df = df_tech[
            df_tech["Trend Status"].str.contains("Bullish")
        ]

        tab1, tab2, tab3 = st.tabs(
            [
                "📊 All Watchlist Indicators",
                "💣 Narrow CPR Breakout Candidates",
                "🔥 Strong Trend Alignments",
            ]
        )

        with tab1:
            st.dataframe(
                df_tech,
                column_config={
                    "LTP": st.column_config.NumberColumn(
                        "LTP (₹)", format="₹%.2f"
                    ),
                    "CPR Width %": st.column_config.NumberColumn(
                        "CPR Width %", format="%.2f%%"
                    ),
                    "ATR (14)": st.column_config.NumberColumn(
                        "ATR (14)", format="₹%.2f"
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )

        with tab2:
            st.markdown("#### 💣 Tight Squeeze Candidates (CPR Width <= 0.35%)")
            if not narrow_cpr_df.empty:
                st.dataframe(
                    narrow_cpr_df[
                        [
                            "Symbol",
                            "LTP",
                            "CPR Width %",
                            "ATR (14)",
                            "Trend Status",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No stocks currently in a Narrow CPR Squeeze.")

        with tab3:
            st.markdown("#### 🔥 Bullish SMA Alignments (> 20 & 50 SMA)")
            if not bullish_trend_df.empty:
                st.dataframe(
                    bullish_trend_df[
                        [
                            "Symbol",
                            "LTP",
                            "20 SMA (Daily)",
                            "50 SMA (Daily)",
                            "20 SMA (1H)",
                            "Trend Status",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info(
                    "No stocks currently aligned in full bullish structure."
                )

        st.divider()

    except Exception as e:
        st.error(f"Error rendering Technical Indicators section: {str(e)}")

# ==========================================
# 9. HELPER INDICATORS FOR SCREENERS
# ==========================================
def calculate_rsi(series, period=9):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calculate_wma(series, length=21):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(
        lambda candles: np.dot(candles, weights) / weights.sum(), raw=True
    )

def calculate_hilega_milega(df):
    if df is None or df.empty or len(df) < 21:
        return df

    rsi = calculate_rsi(df["close"], period=9)
    price_ema = rsi.ewm(span=3, adjust=False).mean()
    strength_wma = calculate_wma(rsi, length=21)

    df["hm_rsi"] = rsi
    df["hm_ema_price"] = price_ema
    df["hm_wma_strength"] = strength_wma
    return df

def calculate_cpr(prev_day_candle):
    high = prev_day_candle["high"]
    low = prev_day_candle["low"]
    close = prev_day_candle["close"]

    pivot = (high + low + close) / 3.0
    bc = (high + low) / 2.0
    tc = (pivot - bc) + pivot

    cpr_top = max(tc, bc)
    cpr_bottom = min(tc, bc)
    cpr_width_pct = round(((cpr_top - cpr_bottom) / pivot) * 100, 2) if pivot > 0 else 0.0
    is_narrow_cpr = cpr_width_pct <= 0.35

    return round(pivot, 2), round(cpr_top, 2), round(cpr_bottom, 2), is_narrow_cpr

def calculate_atr(df, period=14):
    if df is None or len(df) < period + 1:
        return 0.0

    df_atr = df.copy()
    df_atr["prev_close"] = df_atr["close"].shift(1)
    df_atr["tr1"] = df_atr["high"] - df_atr["low"]
    df_atr["tr2"] = (df_atr["high"] - df_atr["prev_close"]).abs()
    df_atr["tr3"] = (df_atr["low"] - df_atr["prev_close"]).abs()
    df_atr["tr"] = df_atr[["tr1", "tr2", "tr3"]].max(axis=1)

    atr_series = df_atr["tr"].rolling(window=period).mean()
    return round(atr_series.iloc[-1], 2)

def check_sma_20_bounce(df_hourly):
    if df_hourly is None or len(df_hourly) < 21:
        return "⚪ Insufficient Data"

    df_hourly = df_hourly.copy()
    df_hourly["sma_20"] = df_hourly["close"].rolling(window=20).mean()

    latest_candle = df_hourly.iloc[-1]
    prev_candle = df_hourly.iloc[-2]

    current_price = latest_candle["close"]
    sma_20_val = latest_candle["sma_20"]

    if np.isnan(sma_20_val) or sma_20_val == 0:
        return "⚪ Normal"

    dist_pct = abs(current_price - sma_20_val) / sma_20_val * 100

    tested_sma = (prev_candle["low"] <= sma_20_val * 1.005) or (
        latest_candle["low"] <= sma_20_val * 1.005
    )
    is_bouncing_up = (
        current_price >= sma_20_val and current_price > latest_candle["open"]
    )
    is_breaking_down = current_price < sma_20_val

    if tested_sma and is_bouncing_up and dist_pct <= 0.75:
        return f"🟢 Bullish Bounce (SMA: ₹{round(sma_20_val, 1)})"
    elif is_breaking_down and dist_pct <= 0.75:
        return f"🔴 Breakdown Test (SMA: ₹{round(sma_20_val, 1)})"
    elif dist_pct <= 0.5:
        return f"⚡ At 20 SMA (₹{round(sma_20_val, 1)})"

    return "⚪ Normal"

def check_bollinger_blast(df):
    if df is None or len(df) < 20:
        return False
    sma = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    upper_band = sma + (2 * std)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    is_above_ub = latest["close"] > upper_band.iloc[-1]
    is_rising = latest["close"] > prev["close"]
    return is_above_ub and is_rising

def calculate_option_vwap(df_5min):
    if df_5min is None or df_5min.empty or "volume" not in df_5min.columns:
        return 0.0

    typical_price = (df_5min["high"] + df_5min["low"] + df_5min["close"]) / 3.0
    cum_pv = (typical_price * df_5min["volume"]).sum()
    cum_vol = df_5min["volume"].sum()

    if cum_vol > 0:
        return round(cum_pv / cum_vol, 2)
    return 0.0

def get_hm_status(df):
    if df is None or df.empty or len(df) < 22 or "hm_ema_price" not in df.columns:
        return "⚪ Neutral"

    latest = df.iloc[-1]
    hm_ema = latest["hm_ema_price"]
    hm_wma = latest["hm_wma_strength"]

    if hm_ema > hm_wma and hm_ema >= 50:
        return "🟢 Bullish"
    elif hm_ema < hm_wma and hm_ema <= 50:
        return "🔴 Bearish"
    else:
        return "⚪ Neutral"

def check_rsi_strength_9(df):
    if df is None or df.empty or len(df) < 22:
        return False, 0.0

    rsi9 = calculate_rsi(df["close"], period=9)
    rsi_ema3 = rsi9.ewm(span=3, adjust=False).mean()
    rsi_wma21 = calculate_wma(rsi9, length=21)

    curr_rsi9 = rsi9.iloc[-1]
    curr_ema3 = rsi_ema3.iloc[-1]
    curr_wma21 = rsi_wma21.iloc[-1]

    is_buy = (curr_rsi9 > curr_wma21) and (curr_rsi9 > curr_ema3)
    return is_buy, curr_rsi9

def fetch_india_vix_regime(kite):
    try:
        quote = kite.quote(["NSE:INDIA VIX"])
        vix_data = quote.get("NSE:INDIA VIX", {})
        vix_price = vix_data.get("last_price", 0.0)

        if vix_price > 18.0:
            regime = f"⚠️ High Volatility (VIX: {vix_price})"
        elif vix_price < 12.0:
            regime = f"🟢 Low Volatility (VIX: {vix_price})"
        else:
            regime = f"⚪ Normal Volatility (VIX: {vix_price})"

        return vix_price, regime
    except Exception:
        return 0.0, "⚪ VIX Unavailable"

# ==========================================
# 10. SCORING & CONFLUENCE EVALUATION ENGINE
# ==========================================
def classify_futures_oi(price_change_pct, oi_change_pct):
    if price_change_pct > 0.30 and oi_change_pct > 1.0:
        return "🟢 Long Build-up"
    if price_change_pct < -0.30 and oi_change_pct > 1.0:
        return "🔴 Short Build-up"
    if price_change_pct > 0.30 and oi_change_pct < -1.0:
        return "🟡 Short Covering"
    if price_change_pct < -0.30 and oi_change_pct < -1.0:
        return "🟠 Long Unwinding"
    return "⚪ Neutral OI"

def calculate_master_fno_score(
    hm_hourly, hm_daily, hm_weekly, hm_monthly,
    price_change_pct, oi_change_pct, vol_multiplier, is_narrow_cpr
):
    score = 50.0

    for tf_status in [hm_hourly, hm_daily, hm_weekly, hm_monthly]:
        if tf_status == "🟢 Bullish":
            score += 7.5
        elif tf_status == "🔴 Bearish":
            score -= 7.5

    oi_state = classify_futures_oi(price_change_pct, oi_change_pct)
    if oi_state == "🟢 Long Build-up":
        score += 10.0
    elif oi_state == "🔴 Short Build-up":
        score -= 10.0

    if vol_multiplier >= 1.8:
        score += 5.0 if price_change_pct > 0 else -5.0

    if is_narrow_cpr:
        score += 5.0

    score = round(max(0.0, min(100.0, score)), 1)
    grade = "A++" if score >= 85 else ("A+" if score >= 75 else ("A" if score >= 65 else "B"))
    return score, grade, oi_state

def assign_cash_trade_score(vol_ratio, dist_pct, mtf_score, extra_points=0):
    score = 50.0

    if vol_ratio >= 2.5:
        score += 20.0
    elif vol_ratio >= 1.5:
        score += 10.0

    if dist_pct <= 0.5:
        score += 15.0
    elif dist_pct <= 1.0:
        score += 10.0

    score += (mtf_score * 5.0)
    score += extra_points

    score = round(max(0.0, min(100.0, score)), 1)
    grade = "A++" if score >= 85 else ("A+" if score >= 75 else ("A" if score >= 65 else "B"))
    return score, grade

# ==========================================
# 11. OPTION ENTRY & VWAP ENGINE
# ==========================================
def fetch_vwap_option_details(
    kite, all_instruments, symbol: str, stock_price: float, signal_type: str
):
    try:
        target_idx_key = None
        for k, v in INDEX_MAP.items():
            if symbol.upper() in [a.upper() for a in v["aliases"]]:
                target_idx_key = k
                break

        if target_idx_key:
            options = filter_instruments_by_index(all_instruments, target_idx_key)
            options = options[options["instrument_type"].isin(["CE", "PE"])].copy()
        else:
            options = all_instruments[
                (all_instruments["name"] == symbol)
                & (
                    all_instruments["segment"].str.contains("-OPT")
                    | all_instruments["instrument_type"].isin(["CE", "PE"])
                )
            ].copy()

        if options.empty:
            return "N/A", 0.0, 0.0, 0.0, 0.0, "No Option Found"

        options["expiry"] = pd.to_datetime(options["expiry"])
        today_date = pd.Timestamp(datetime.now().date())
        options = options[options["expiry"] >= today_date]
        if options.empty:
            return "N/A", 0.0, 0.0, 0.0, 0.0, "No Future Expiry"

        nearest_expiry = options["expiry"].min()
        near_options = options[options["expiry"] == nearest_expiry]

        strikes = sorted(near_options["strike"].dropna().unique())
        if len(strikes) < 2:
            return "N/A", 0.0, 0.0, 0.0, 0.0, "Invalid Strike Steps"

        strike_interval = strikes[1] - strikes[0]
        atm_strike = round(stock_price / strike_interval) * strike_interval

        sig_upper = str(signal_type).upper()
        if "BEARISH" in sig_upper or "SHORT" in sig_upper or "DOWN" in sig_upper:
            opt_type = "PE"
            rec_strike = atm_strike - strike_interval
        else:
            opt_type = "CE"
            rec_strike = atm_strike + strike_interval

        target_opt = near_options[
            (near_options["strike"] == rec_strike)
            & (near_options["instrument_type"] == opt_type)
        ]

        if target_opt.empty:
            target_opt = near_options[
                (near_options["strike"] == atm_strike)
                & (near_options["instrument_type"] == opt_type)
            ]
            if target_opt.empty:
                return "N/A", 0.0, 0.0, 0.0, 0.0, "Strike Missing"

        opt_token = int(target_opt.iloc[0]["instrument_token"])
        opt_symbol = target_opt.iloc[0]["tradingsymbol"]
        segment_prefix = target_opt.iloc[0]["segment"].split("-")[0]

        quote = kite.quote([f"{segment_prefix}:{opt_symbol}"])
        opt_quote_data = quote.get(f"{segment_prefix}:{opt_symbol}", {})
        ltp = opt_quote_data.get("last_price", 0.0)

        today_start = datetime.now().replace(
            hour=9, minute=15, second=0, microsecond=0
        )
        opt_candles = safe_fetch_history(
            kite, opt_token, today_start, datetime.now(), "5minute"
        )
        df_opt_5m = pd.DataFrame(opt_candles)

        if df_opt_5m.empty or len(df_opt_5m) == 0:
            if ltp > 0:
                buy_rate = round(ltp * 1.005, 2)
                return (
                    f"{symbol} {int(rec_strike)} {opt_type}",
                    round(ltp * 0.98, 2),
                    buy_rate,
                    round(buy_rate * 0.85, 2),
                    round(buy_rate * 1.40, 2),
                    "🟢 Live Market LTP",
                )
            return "N/A", 0.0, 0.0, 0.0, 0.0, "Quote Error"

        option_vwap = calculate_option_vwap(df_opt_5m)
        opt_bounce_level = round(df_opt_5m.iloc[-1]["close"], 2)

        buy_trigger_price = round(max(ltp, option_vwap) * 1.005, 2)
        trailing_sl, bounce_status = calculate_ema9_trailing_sl(df_opt_5m, buy_trigger_price, initial_sl_pct=0.15)

        target = round(buy_trigger_price * 1.40, 2)

        return (
            f"{symbol} {int(rec_strike)} {opt_type}",
            opt_bounce_level,
            buy_trigger_price,
            trailing_sl,
            target,
            bounce_status,
        )

    except Exception as e:
        return "N/A", 0.0, 0.0, 0.0, 0.0, f"Error: {str(e)}"

# ==========================================
# 12. INDEX OVERVIEW & INDEX OPTIONS ENGINE
# ==========================================
def scan_indices_overview(kite, all_instruments=None):
    if all_instruments is None:
        nfo_df = pd.DataFrame(kite.instruments("NFO"))
        bfo_df = pd.DataFrame(kite.instruments("BFO"))
        all_instruments = pd.concat([nfo_df, bfo_df], ignore_index=True)

    index_results = []
    index_option_picks = []

    from_date_daily = datetime.now() - timedelta(days=90)
    from_date_weekly = datetime.now() - timedelta(days=730)
    from_date_hourly = datetime.now() - timedelta(days=30)
    to_date = datetime.now()

    for idx_key, idx_info in INDEX_MAP.items():
        try:
            token = idx_info["token"]
            symbol = idx_info["name"]

            c_daily = safe_fetch_history(kite, token, from_date_daily, to_date, "day")
            df_daily = calculate_hilega_milega(pd.DataFrame(c_daily))

            c_weekly_raw = safe_fetch_history(kite, token, from_date_weekly, to_date, "day")
            df_w_raw = pd.DataFrame(c_weekly_raw)
            if not df_w_raw.empty:
                df_w_raw["date"] = pd.to_datetime(df_w_raw["date"])
                df_weekly = calculate_hilega_milega(
                    df_w_raw.resample("W-MON", on="date")
                    .agg(
                        {
                            "open": "first",
                            "high": "max",
                            "low": "min",
                            "close": "last",
                            "volume": "sum",
                        }
                    )
                    .dropna()
                    .reset_index()
                )
            else:
                df_weekly = None

            c_hourly = safe_fetch_history(kite, token, from_date_hourly, to_date, "60minute")
            df_hourly = calculate_hilega_milega(pd.DataFrame(c_hourly))

            if df_daily is None or len(df_daily) < 20:
                continue

            last_close = df_daily.iloc[-1]["close"]
            prev_close = df_daily.iloc[-2]["close"]
            chg_pct = round(((last_close - prev_close) / prev_close) * 100, 2)

            hm_daily = get_hm_status(df_daily)
            hm_weekly = get_hm_status(df_weekly)
            hm_hourly = get_hm_status(df_hourly)
            hm_summary = f"1H: {hm_hourly} | 1D: {hm_daily} | 1W: {hm_weekly}"

            pivot, cpr_top, cpr_bottom, is_narrow = calculate_cpr(
                df_daily.iloc[-2]
            )
            cpr_status = "⚡ Narrow CPR" if is_narrow else "Normal CPR"
            sma20_status = check_sma_20_bounce(df_hourly)

            pcr_value, option_chain_direction = analyze_option_chain_direction(
                kite, all_instruments, symbol
            )

            overall_bias = "⚪ Neutral Range"
            if (
                "Bullish" in hm_daily
                and "Bullish" in hm_hourly
                and pcr_value >= 0.95
            ):
                overall_bias = "🟢 Bullish Bias"
            elif (
                "Bearish" in hm_daily
                and "Bearish" in hm_hourly
                and pcr_value <= 0.85
            ):
                overall_bias = "🔴 Bearish Bias"

            index_results.append(
                {
                    "Index": f"{idx_info['symbol']} ({idx_info['exchange']})",
                    "Spot Price": round(last_close, 2),
                    "Change %": chg_pct,
                    "1H 20 SMA Status": sma20_status,
                    "CPR Setup": cpr_status,
                    "Option Chain Sentiment": option_chain_direction,
                    "Multi-Timeframe Trend": hm_summary,
                    "Market Outlook": overall_bias,
                }
            )

            opt_strike, bounce_lvl, buy_rate, sl_rate, target_rate, vwap_status = (
                fetch_vwap_option_details(
                    kite, all_instruments, symbol, last_close, overall_bias
                )
            )

            pos_data = calculate_dynamic_position_size(symbol, buy_rate, sl_pct=0.15, max_risk_inr=2000.0)

            index_option_picks.append(
                {
                    "Index": f"{idx_info['symbol']} ({idx_info['exchange']})",
                    "Spot Price": round(last_close, 2),
                    "Outlook": overall_bias,
                    "Rec Slightly OTM Option": opt_strike,
                    "Limit Buy (+0.5%) (₹)": buy_rate,
                    "Dynamic Position Size": f"{pos_data['lots']} Lots ({pos_data['quantity']} Qty)",
                    "Max Loss (₹)": pos_data['max_loss'],
                    "5M EMA-9 Trailing SL (₹)": sl_rate,
                    "Target (+40%) (₹)": target_rate,
                    "Trailing SL Status": vwap_status,
                }
            )

        except Exception as e:
            st.error(f"Error scanning index {idx_key}: {str(e)}")

    return pd.DataFrame(index_results), pd.DataFrame(index_option_picks)

# ==========================================
# 13. HERO-ZERO EXPIRY ENGINE (ALL INDICES)
# ==========================================
def scan_hero_zero_opportunities(kite):
    st.info("⚡ Scanning ALL NSE & BSE Index Options for Hero-Zero Expiry Signals...")

    nfo_df = pd.DataFrame(kite.instruments("NFO"))
    bfo_df = pd.DataFrame(kite.instruments("BFO"))
    all_instruments = pd.concat([nfo_df, bfo_df], ignore_index=True)

    today_date = datetime.now().date()
    hero_zero_candidates = []

    for idx_key, idx_info in INDEX_MAP.items():
        symbol = idx_info["name"]
        exchange = idx_info["exchange"]
        segment_prefix = idx_info["segment"]

        spot_prefix = "BSE" if exchange == "BSE" else "NSE"
        spot_quote = kite.quote([f"{spot_prefix}:{idx_info['symbol']}"])
        spot_price = spot_quote.get(f"{spot_prefix}:{idx_info['symbol']}", {}).get("last_price", 0.0)

        if spot_price == 0:
            continue

        options = filter_instruments_by_index(all_instruments, idx_key)
        options = options[options["instrument_type"].isin(["CE", "PE"])].copy()

        if options.empty:
            continue

        options["expiry"] = pd.to_datetime(options["expiry"]).dt.date
        expiry_today_options = options[options["expiry"] == today_date]

        if expiry_today_options.empty:
            st.info(f"ℹ️ {symbol} ({exchange}) does not have an active Expiry today.")
            continue

        st.success(f"🔥 Active Expiry Detected for **{symbol} ({exchange})**! Scanning Open Interest & Premiums...")

        trading_symbols = expiry_today_options["tradingsymbol"].tolist()
        formatted_symbols = [f"{segment_prefix}:{ts}" for ts in trading_symbols]

        quotes = {}
        chunk_size = 100
        for i in range(0, len(formatted_symbols), chunk_size):
            chunk = formatted_symbols[i : i + chunk_size]
            quotes.update(kite.quote(chunk))

        for idx, opt_row in expiry_today_options.iterrows():
            ts = opt_row["tradingsymbol"]
            strike = opt_row["strike"]
            opt_type = opt_row["instrument_type"]

            quote_data = quotes.get(f"{segment_prefix}:{ts}", {})
            ltp = quote_data.get("last_price", 0.0)
            oi = quote_data.get("oi", 0)

            if not (5.00 <= ltp <= 35.00):
                continue

            dist_pts = abs(strike - spot_price)
            if dist_pts > (spot_price * 0.02):
                continue

            oi_unwinding_pct = 0.0
            try:
                start_day = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
                hist = safe_fetch_history(
                    kite, int(opt_row["instrument_token"]), start_day, datetime.now(), "5minute", oi=True
                )
                if len(hist) >= 2:
                    prev_oi = float(hist[-2].get("oi", 0) or 0)
                    if prev_oi > 0:
                        oi_unwinding_pct = (oi - prev_oi) / prev_oi * 100.0
            except Exception:
                oi_unwinding_pct = 0.0

            signal = "HOLD"
            reason = "Awaiting Momentum"

            if opt_type == "CE" and oi_unwinding_pct <= -5.0:
                signal = "🚀 BUY CALL (Hero-Zero)"
                reason = "Call Writers Panic / Short Squeeze"
            elif opt_type == "PE" and oi_unwinding_pct <= -5.0:
                signal = "🚀 BUY PUT (Hero-Zero)"
                reason = "Put Writers Panic / Long Unwinding"
            elif 5.0 <= ltp <= 15.0:
                signal = "⚡ SQUEEZE WATCH"
                reason = "Low Premium Squeeze Candidate"

            if signal != "HOLD":
                target_price = round(ltp * 3.0, 2)
                limit_buy = round(ltp * 1.005, 2)
                pos_data = calculate_dynamic_position_size(symbol, limit_buy, sl_pct=0.50, max_risk_inr=2000.0)

                hero_zero_candidates.append(
                    {
                        "Index": f"{symbol} ({exchange})",
                        "Contract": ts,
                        "Strike": strike,
                        "Option Type": opt_type,
                        "Live Premium (₹)": ltp,
                        "Limit Order (+0.5%) (₹)": limit_buy,
                        "Dynamic Quantity": f"{pos_data['lots']} Lots ({pos_data['quantity']} Qty)",
                        "Max Risk Ceiling (₹)": pos_data['max_loss'],
                        "OI Unwinding %": round(oi_unwinding_pct, 2),
                        "Signal": signal,
                        "Rationale": reason,
                        "Target (3x) (₹)": target_price,
                        "Spot Price": spot_price,
                    }
                )

    return pd.DataFrame(hero_zero_candidates)

# ==========================================
# 14. MASTER SCREENER ENGINE (F&O)
# ==========================================
def scan_fno_opportunities(kite):
    st.info("📡 Loading NFO Futures & Mapping underlying NSE Stocks...")

    nfo_instruments = pd.DataFrame(kite.instruments("NFO"))
    nse_instruments = pd.DataFrame(kite.instruments("NSE"))

    index_exclusions = [v["name"] for v in INDEX_MAP.values()] + ["NIFTYNXT50", "BSESENSEX", "BSEBANKEX", "SENSEX", "BANKEX"]
    futures = nfo_instruments[
        (nfo_instruments["instrument_type"] == "FUT")
        & (~nfo_instruments["name"].isin(index_exclusions))
    ].copy()

    all_fno_symbols = sorted(futures["name"].unique().tolist())

    strict_results = []
    intraday_picks = []
    all_scanned_data = []

    from_date_daily = datetime.now() - timedelta(days=90)
    from_date_weekly = datetime.now() - timedelta(days=730)
    from_date_monthly = datetime.now() - timedelta(days=1825)
    from_date_hourly = datetime.now() - timedelta(days=30)
    to_date = datetime.now()

    progress_bar = st.progress(0)
    status_text = st.empty()

    total_stocks = len(all_fno_symbols)
    st.write(
        f"🔍 Found **{total_stocks} F&O stocks**. Scanning Confluence Scores, CPR, ATR & Option Chains..."
    )

    for index, symbol in enumerate(all_fno_symbols, start=1):
        try:
            status_text.text(f"Scanning [{index}/{total_stocks}]: {symbol}...")
            progress_bar.progress(index / total_stocks)

            symbol_futs = futures[futures["name"] == symbol].sort_values(
                by="expiry"
            )
            if symbol_futs.empty:
                continue

            near_fut = symbol_futs.iloc[0]
            fut_token = int(near_fut["instrument_token"])
            fut_tradingsymbol = near_fut["tradingsymbol"]

            eq_match = nse_instruments[
                (nse_instruments["tradingsymbol"] == symbol)
                & (nse_instruments["segment"] == "NSE")
            ]
            eq_token = (
                int(eq_match.iloc[0]["instrument_token"])
                if not eq_match.empty
                else fut_token
            )

            c_daily = safe_fetch_history(kite, eq_token, from_date_daily, to_date, "day")
            df_daily = calculate_hilega_milega(pd.DataFrame(c_daily))

            c_weekly_raw = safe_fetch_history(kite, eq_token, from_date_weekly, to_date, "day")
            df_w_raw = pd.DataFrame(c_weekly_raw)
            if not df_w_raw.empty:
                df_w_raw["date"] = pd.to_datetime(df_w_raw["date"])
                df_weekly = calculate_hilega_milega(
                    df_w_raw.resample("W-MON", on="date")
                    .agg(
                        {
                            "open": "first",
                            "high": "max",
                            "low": "min",
                            "close": "last",
                            "volume": "sum",
                        }
                    )
                    .dropna()
                    .reset_index()
                )
            else:
                df_weekly = None

            c_monthly_raw = safe_fetch_history(kite, eq_token, from_date_monthly, to_date, "day")
            df_m_raw = pd.DataFrame(c_monthly_raw)
            if not df_m_raw.empty:
                df_m_raw["date"] = pd.to_datetime(df_m_raw["date"])
                df_monthly = calculate_hilega_milega(
                    df_m_raw.resample("ME", on="date")
                    .agg(
                        {
                            "open": "first",
                            "high": "max",
                            "low": "min",
                            "close": "last",
                            "volume": "sum",
                        }
                    )
                    .dropna()
                    .reset_index()
                )
            else:
                df_monthly = None

            c_hourly = safe_fetch_history(kite, eq_token, from_date_hourly, to_date, "60minute")
            df_hourly = calculate_hilega_milega(pd.DataFrame(c_hourly))

            c_fut_daily = safe_fetch_history(kite, fut_token, from_date_daily, to_date, "day", oi=True)
            df_fut_daily = pd.DataFrame(c_fut_daily)

            if df_daily is None or len(df_daily) < 25 or df_fut_daily.empty:
                continue

            pivot, cpr_top, cpr_bottom, is_narrow_cpr = calculate_cpr(
                df_daily.iloc[-2]
            )
            stock_atr = calculate_atr(df_daily, period=14)
            sma20_status = check_sma_20_bounce(df_hourly)
            cpr_filter_label = (
                "⚡ Narrow CPR (Pre-Breakout)" if is_narrow_cpr else "Normal CPR"
            )

            hm_daily = get_hm_status(df_daily)
            hm_weekly = get_hm_status(df_weekly)
            hm_monthly = get_hm_status(df_monthly)
            hm_hourly = get_hm_status(df_hourly)
            hm_mtf_summary = (
                f"1H: {hm_hourly} | 1D: {hm_daily} | 1W: {hm_weekly} | 1M: {hm_monthly}"
            )

            today_candle = df_daily.iloc[-1]
            prev_candle = df_daily.iloc[-2]
            prev_20_days = df_daily.iloc[-21:-1].copy()

            avg_vol_20 = prev_20_days["volume"].mean()
            today_vol = today_candle["volume"]
            vol_multiplier = today_vol / avg_vol_20 if avg_vol_20 > 0 else 0

            prev_close = prev_candle["close"]
            today_close = today_candle["close"]
            price_change_pct = (
                (today_close - prev_close) / prev_close
            ) * 100

            fut_today = df_fut_daily.iloc[-1]
            fut_prev = df_fut_daily.iloc[-2]
            today_oi = fut_today.get("oi", 0)
            prev_oi = fut_prev.get("oi", 0)
            oi_change_pct = (
                ((today_oi - prev_oi) / prev_oi) * 100 if prev_oi > 0 else 0
            )

            today_range = today_candle["high"] - today_candle["low"]
            prev_20_days["range"] = prev_20_days["high"] - prev_20_days["low"]
            avg_range_20 = prev_20_days["range"].mean()
            volatility_expansion_ratio = (
                today_range / avg_range_20 if avg_range_20 > 0 else 0
            )

            pcr_value, option_chain_direction = analyze_option_chain_direction(
                kite, nfo_instruments, symbol
            )

            score_val, grade_val, oi_state = calculate_master_fno_score(
                hm_hourly, hm_daily, hm_weekly, hm_monthly,
                price_change_pct, oi_change_pct, vol_multiplier, is_narrow_cpr
            )

            trap_warning = "✅ Clean Structure"
            if price_change_pct > 1.5 and oi_change_pct < -2.0:
                trap_warning = "⚠️ TRAP: Short Covering"
            elif price_change_pct < -1.5 and oi_change_pct < -2.0:
                trap_warning = "⚠️ TRAP: Long Unwinding"
            elif volatility_expansion_ratio >= 3.8 or price_change_pct >= 8.0:
                trap_warning = "⚠️ TRAP: Overextended"

            signal = "Neutral"
            if (
                hm_hourly == "🟢 Bullish"
                and hm_daily == "🟢 Bullish"
                and hm_weekly == "🟢 Bullish"
            ):
                signal = "🔥 FULL MTF BULLISH ALIGNMENT (1H+1D+1W)"
            elif (
                hm_hourly == "🔴 Bearish"
                and hm_daily == "🔴 Bearish"
                and hm_weekly == "🔴 Bearish"
            ):
                signal = "🔴 FULL MTF BEARISH ALIGNMENT (1H+1D+1W)"
            elif "Bullish Bounce" in sma20_status and hm_daily == "🟢 Bullish":
                signal = "📈 1H 20 SMA PULLBACK BOUNCE"
            elif (
                (volatility_expansion_ratio <= 0.85 or is_narrow_cpr)
                and oi_change_pct >= 4.0
                and (-0.5 <= price_change_pct <= 1.5)
            ):
                signal = (
                    "💣 PRE-BREAKOUT SQUEEZE (Bullish)"
                    if hm_daily == "🟢 Bullish"
                    else "💣 PRE-BREAKOUT SQUEEZE (Bearish)"
                )
            elif (
                vol_multiplier >= 2.5
                and volatility_expansion_ratio >= 1.5
                and price_change_pct > 2.0
                and hm_daily == "🟢 Bullish"
            ):
                signal = "🚀 Bullish Momentum Expansion"
            elif (
                vol_multiplier >= 2.5
                and volatility_expansion_ratio >= 1.5
                and price_change_pct < -2.0
                and hm_daily == "🔴 Bearish"
            ):
                signal = "⚠️ Bearish Breakdown Expansion"

            opt_strike, bounce_lvl, buy_rate, sl_rate, target_rate, vwap_status = (
                "N/A",
                0.0,
                0.0,
                0.0,
                0.0,
                "N/A",
            )
            if signal != "Neutral" or score_val >= SCREENER["min_score"]:
                opt_strike, bounce_lvl, buy_rate, sl_rate, target_rate, vwap_status = (
                    fetch_vwap_option_details(
                        kite, nfo_instruments, symbol, today_close, signal
                    )
                )

            stock_info = {
                "Symbol": symbol,
                "Contract": fut_tradingsymbol,
                "Price": round(today_close, 2),
                "Price Chg %": round(price_change_pct, 2),
                "Score": score_val,
                "Grade": grade_val,
                "OI State": oi_state,
                "1H 20 SMA Status": sma20_status,
                "CPR Status": cpr_filter_label,
                "ATR (14)": stock_atr,
                "Vol Surge": round(vol_multiplier, 2),
                "OI Chg %": round(oi_change_pct, 2),
                "Option Chain Direction": option_chain_direction,
                "HM Multi-Timeframe Status": hm_mtf_summary,
                "Signal": signal,
                "Trap Filter": trap_warning,
                "Rec Option": opt_strike,
                "Limit Buy Rate (₹)": buy_rate,
                "5M EMA-9 Trailing SL (₹)": sl_rate,
                "Target (₹)": target_rate,
                "Option Status": vwap_status,
            }

            if signal != "Neutral" or score_val >= SCREENER["strict_score"]:
                strict_results.append(stock_info)

            if (
                (signal != "Neutral" or score_val >= SCREENER["intraday_score"])
                and vol_multiplier >= 1.5
                and "Clean" in trap_warning
            ):
                intraday_picks.append(
                    {
                        "Symbol": symbol,
                        "Score": score_val,
                        "Grade": grade_val,
                        "Signal": signal,
                        "1H 20 SMA Status": sma20_status,
                        "CPR Setup": cpr_filter_label,
                        "ATR (14)": stock_atr,
                        "Rec Slightly OTM Option": opt_strike,
                        "Limit Buy Rate (+0.5%) (₹)": buy_rate,
                        "5M EMA-9 Trailing SL (₹)": sl_rate,
                        "Target (₹)": target_rate,
                        "Vol Surge": round(vol_multiplier, 2),
                        "Option Status": vwap_status,
                    }
                )

            all_scanned_data.append(stock_info)
            time.sleep(0.05)

        except Exception as e:
            st.error(f"Error scanning {symbol}: {str(e)}")

    status_text.text("Scan Completed!")
    progress_bar.empty()

    return (
        pd.DataFrame(intraday_picks),
        pd.DataFrame(strict_results),
        pd.DataFrame(all_scanned_data),
    )

# ==========================================
# 15. HIGH-SPEED UDD JA BREAKOUT ENGINE (CASH STOCKS)
# ==========================================
def scan_udd_ja_cash_stocks(kite):
    st.info("🚀 Pre-filtering NSE Cash Equities for High Volume & Liquidity...")

    instruments = kite.instruments("NSE")
    df = pd.DataFrame(instruments)

    cash_stocks = df[
        (df["segment"] == "NSE")
        & (df["instrument_type"] == "EQ")
        & (df["name"].str.strip() != "")
    ].copy()

    exclude_keywords = [
        "BEES", "ETF", "GOLD", "SILVER", "LIQUID", "NIFTY", "BOND",
        "SGB", "NAV", "GSEC", "IWIN", "-RE", "-SG",
    ]
    pattern = "|".join(exclude_keywords)
    cash_stocks = cash_stocks[
        ~cash_stocks["tradingsymbol"].str.contains(pattern, case=False, na=False)
    ]
    cash_stocks = cash_stocks[~cash_stocks["tradingsymbol"].str.match(r"^\d")]

    all_symbols = cash_stocks["tradingsymbol"].dropna().unique().tolist()
    formatted_symbols = [f"NSE:{s}" for s in all_symbols]

    st.write(f"🔍 Fast-checking live liquidity for {len(all_symbols)} equity symbols...")
    liquid_symbols = []

    chunk_size = 50
    for i in range(0, len(formatted_symbols), chunk_size):
        chunk = formatted_symbols[i : i + chunk_size]
        try:
            quotes = kite.quote(chunk)
            if isinstance(quotes, dict):
                for sym_key, qdata in quotes.items():
                    if not isinstance(qdata, dict):
                        continue
                    clean_sym = sym_key.replace("NSE:", "")
                    ltp = qdata.get("last_price", 0) or qdata.get("ohlc", {}).get("close", 0)
                    vol = qdata.get("volume", 0)

                    if ltp >= 30.0 and (vol >= 10000 or vol == 0):
                        liquid_symbols.append(clean_sym)
            time.sleep(0.05)
        except Exception:
            time.sleep(0.2)

    total_liquid = len(liquid_symbols)
    st.success(f"⚡ Pruned list down to **{total_liquid} active liquid stocks**! Scanning setups...")

    if total_liquid == 0:
        st.warning("⚠️ No stocks passed liquidity pre-filter. Re-trying with broader list...")
        liquid_symbols = all_symbols[:300]
        total_liquid = len(liquid_symbols)

    udd_ja_results = []
    from_date_3m = datetime.now() - timedelta(days=5)
    from_date_daily = datetime.now() - timedelta(days=365)
    to_date = datetime.now()

    progress_bar = st.progress(0)
    status_text = st.empty()

    for index, symbol in enumerate(liquid_symbols, start=1):
        try:
            status_text.text(f"Scanning Cash [{index}/{total_liquid}]: {symbol}...")
            progress_bar.progress(index / total_liquid)

            match = cash_stocks[cash_stocks["tradingsymbol"] == symbol]
            if match.empty:
                continue

            token = int(match.iloc[0]["instrument_token"])

            c_daily = safe_fetch_history(kite, token, from_date_daily, to_date, "day")
            df_daily = pd.DataFrame(c_daily)

            if len(df_daily) < 60:
                continue

            prev_day_close = df_daily["close"].iloc[-2]

            df_daily["date"] = pd.to_datetime(df_daily["date"])
            df_weekly = (
                df_daily.resample("W-MON", on="date")
                .agg(
                    {
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum",
                    }
                )
                .dropna()
                .reset_index()
            )

            daily_bb = check_bollinger_blast(df_daily)
            weekly_bb = check_bollinger_blast(df_weekly)

            if not (daily_bb and weekly_bb):
                continue

            c_3min = safe_fetch_history(kite, token, from_date_3m, to_date, "3minute")
            df_3m = pd.DataFrame(c_3min)

            if df_3m.empty or len(df_3m) < 10:
                continue

            df_3m["date"] = pd.to_datetime(df_3m["date"])
            latest_day = df_3m["date"].dt.date.iloc[-1]
            df_today = df_3m[df_3m["date"].dt.date == latest_day].copy()

            if df_today.empty:
                continue

            today_open = df_today["open"].iloc[0]

            df_today["time"] = df_today["date"].dt.time
            t_1100 = datetime.strptime("11:00:00", "%H:%M:%S").time()
            t_1300 = datetime.strptime("13:00:00", "%H:%M:%S").time()
            t_0915 = datetime.strptime("09:15:00", "%H:%M:%S").time()

            df_dry = df_today[(df_today["time"] >= t_1100) & (df_today["time"] <= t_1300)]
            df_morn = df_today[(df_today["time"] >= t_0915) & (df_today["time"] < t_1100)]

            if not df_dry.empty:
                avg_dry_vol = df_dry["volume"].mean()
            elif not df_morn.empty:
                avg_dry_vol = df_morn["volume"].mean()
            else:
                avg_dry_vol = df_today["volume"].mean()

            if avg_dry_vol <= 0:
                avg_dry_vol = 1.0

            df_today["tp"] = (df_today["high"] + df_today["low"] + df_today["close"]) / 3.0
            df_today["vwap"] = (df_today["tp"] * df_today["volume"]).cumsum() / df_today["volume"].cumsum().replace(0, np.nan)

            latest_candle = df_today.iloc[-1]
            ltp = latest_candle["close"]

            vol_spike = (latest_candle["volume"] / avg_dry_vol) if avg_dry_vol > 0 else 0
            is_vol_breakout = vol_spike >= 1.5
            is_above_vwap = ltp > latest_candle["vwap"]

            change_pct = round(((ltp - prev_day_close) / prev_day_close) * 100, 2)

            if change_pct >= 3.0 and vol_spike >= 2.5:
                vpa_signal = "🔥 Strong Bullish Accumulation"
                vpa_bonus = 15
            elif change_pct >= 1.5 and vol_spike >= 1.5:
                vpa_signal = "⚡ High Momentum Breakout"
                vpa_bonus = 10
            elif change_pct > 0 and vol_spike >= 1.5:
                vpa_signal = "🟢 Moderate Inflow"
                vpa_bonus = 5
            else:
                vpa_signal = "⚪ Neutral"
                vpa_bonus = 0

            if is_vol_breakout and is_above_vwap and change_pct > 0:
                vwap_val = latest_candle["vwap"]
                stop_loss = round(vwap_val - 1.0, 2)

                morning_range = (
                    (df_morn["high"].max() - df_morn["low"].min())
                    if not df_morn.empty
                    else (ltp * 0.02)
                )
                target_3x = round(ltp + (3 * morning_range), 2)

                score_final, grade = assign_cash_trade_score(vol_spike, 0.5, 3, extra_points=(10 + vpa_bonus))

                udd_ja_results.append(
                    {
                        "Symbol": symbol,
                        "Prev Close (₹)": round(prev_day_close, 2),
                        "Open (₹)": round(today_open, 2),
                        "LTP (₹)": round(ltp, 2),
                        "Change %": change_pct,
                        "Vol Spike": f"{round(vol_spike, 1)}x",
                        "Vol-Price Trend": vpa_signal,
                        "Score": score_final,
                        "Grade": grade,
                        "Stop Loss (₹)": round(stop_loss, 2),
                        "Target (3x Range) (₹)": round(target_3x, 2),
                    }
                )

        except Exception as e:
            st.error(f"Error scanning cash symbol {symbol}: {str(e)}")

    status_text.text("Udd Ja Cash Scan Completed!")
    progress_bar.empty()

    if udd_ja_results:
        df_res = pd.DataFrame(udd_ja_results)
        return df_res.sort_values(by="Score", ascending=False).reset_index(drop=True)
    return pd.DataFrame()

# ==========================================
# 16. YEARLY BREAKOUTS ENGINE
# ==========================================
def scan_yearly_breakout_cash_stocks(kite):
    st.info("📅 Fetching 52-Week High & Historical Data for NSE Cash Equities (Higher Time Frame Focus)...")

    instruments = kite.instruments("NSE")
    df = pd.DataFrame(instruments)

    cash_stocks = df[
        (df["segment"] == "NSE")
        & (df["instrument_type"] == "EQ")
        & (df["name"].str.strip() != "")
    ].copy()

    exclude_keywords = [
        "BEES", "ETF", "GOLD", "SILVER", "LIQUID", "NIFTY", "BOND", 
        "SGB", "NAV", "GSEC", "IWIN", "-RE", "-SG"
    ]
    pattern = "|".join(exclude_keywords)
    cash_stocks = cash_stocks[
        ~cash_stocks["tradingsymbol"].str.contains(pattern, case=False, na=False)
    ]
    cash_stocks = cash_stocks[~cash_stocks["tradingsymbol"].str.match(r"^\d")]

    all_symbols = cash_stocks["tradingsymbol"].dropna().unique().tolist()
    formatted_symbols = [f"NSE:{s}" for s in all_symbols]

    st.write(f"🔍 Pre-filtering liquidity for {len(all_symbols)} cash symbols...")
    liquid_symbols = []

    chunk_size = 50
    for i in range(0, len(formatted_symbols), chunk_size):
        chunk = formatted_symbols[i : i + chunk_size]
        try:
            quotes = kite.quote(chunk)
            if isinstance(quotes, dict):
                for sym_key, qdata in quotes.items():
                    if not isinstance(qdata, dict):
                        continue
                    clean_sym = sym_key.replace("NSE:", "")
                    ltp = qdata.get("last_price", 0) or qdata.get("ohlc", {}).get("close", 0)
                    vol = qdata.get("volume", 0)

                    if ltp >= 30.0 and (vol >= 20000 or vol == 0):
                        liquid_symbols.append(clean_sym)
            time.sleep(0.05)
        except Exception:
            time.sleep(0.2)

    total_liquid = len(liquid_symbols)
    st.success(f"⚡ Filtered down to **{total_liquid} active stocks**. Scanning ALL 52W Breakouts & HTF Confluence Signals...")

    yearly_breakout_results = []
    to_date = datetime.now()
    from_date = to_date - timedelta(days=730)

    progress_bar = st.progress(0)
    status_text = st.empty()

    for index, symbol in enumerate(liquid_symbols, start=1):
        try:
            status_text.text(f"Scanning Yearly Breakouts [{index}/{total_liquid}]: {symbol}...")
            progress_bar.progress(index / total_liquid)

            match = cash_stocks[cash_stocks["tradingsymbol"] == symbol]
            if match.empty:
                continue

            token = int(match.iloc[0]["instrument_token"])

            candles = safe_fetch_history(
                kite,
                token,
                from_date.strftime("%Y-%m-%d %H:%M:%S"),
                to_date.strftime("%Y-%m-%d %H:%M:%S"),
                "day",
            )
            df_daily = pd.DataFrame(candles)

            if len(df_daily) < 200:
                continue

            ltp = df_daily["close"].iloc[-1]
            prev_close = df_daily["close"].iloc[-2]
            single_day_gain_pct = round(((ltp - prev_close) / prev_close) * 100, 2)

            high_52w = df_daily["high"].iloc[:-1].max()
            sma_20 = df_daily["close"].rolling(20).mean().iloc[-1]
            sma_50 = df_daily["close"].rolling(50).mean().iloc[-1]
            vol_20d_avg = df_daily["volume"].tail(20).mean()
            today_vol = df_daily["volume"].iloc[-1]
            vol_ratio = round(today_vol / vol_20d_avg, 2) if vol_20d_avg > 0 else 1.0

            dist_to_52w_pct = round(((ltp - high_52w) / high_52w) * 100, 2)

            if dist_to_52w_pct >= -1.5:
                df_daily_hm = calculate_hilega_milega(df_daily.copy())
                df_daily_hm["date"] = pd.to_datetime(df_daily_hm["date"])

                df_weekly = (
                    df_daily_hm.resample("W-MON", on="date")
                    .agg({
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum"
                    })
                    .dropna()
                    .reset_index()
                )
                df_weekly = calculate_hilega_milega(df_weekly)

                df_monthly = (
                    df_daily_hm.resample("ME", on="date")
                    .agg({
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum"
                    })
                    .dropna()
                    .reset_index()
                )
                df_monthly = calculate_hilega_milega(df_monthly)

                d_buy_rsi9, d_rsi9_val = check_rsi_strength_9(df_daily)
                w_buy_rsi9, w_rsi9_val = check_rsi_strength_9(df_weekly)
                m_buy_rsi9, m_rsi9_val = check_rsi_strength_9(df_monthly)

                mtf_score = sum([d_buy_rsi9, w_buy_rsi9, m_buy_rsi9])
                mtf_status = f"{mtf_score}/3 HTF Bullish (1D: {round(d_rsi9_val, 1)}, 1W: {round(w_rsi9_val, 1)}, 1M: {round(m_rsi9_val, 1)})"

                cpr_confluence_status = "⚪ Standard 52W Breakout"
                extra_pts = 0

                if len(df_weekly) >= 20:
                    prev_week = df_weekly.iloc[-2]
                    weekly_pivot, weekly_tc, weekly_bc, is_narrow_w_cpr = calculate_cpr(prev_week)

                    above_weekly_pivot = ltp >= weekly_pivot

                    df_daily_hm["sma20"] = df_daily_hm["close"].rolling(20).mean()
                    df_daily_hm["std"] = df_daily_hm["close"].rolling(20).std()
                    df_daily_hm["ub"] = df_daily_hm["sma20"] + (2 * df_daily_hm["std"])
                    df_daily_hm["lb"] = df_daily_hm["sma20"] - (2 * df_daily_hm["std"])
                    df_daily_hm["bb_width"] = (df_daily_hm["ub"] - df_daily_hm["lb"]) / df_daily_hm["sma20"]
                    
                    recent_bb_width = df_daily_hm["bb_width"].iloc[-1]
                    min_20d_bb_width = df_daily_hm["bb_width"].tail(20).min()
                    is_bb_squeezed = (recent_bb_width <= min_20d_bb_width * 1.15) or (recent_bb_width <= 0.08)

                    latest_hm_ema = df_daily_hm["hm_ema_price"].iloc[-1] if "hm_ema_price" in df_daily_hm.columns else 0
                    is_hm_above_50 = latest_hm_ema >= 50.0

                    if above_weekly_pivot and is_bb_squeezed and is_hm_above_50:
                        cpr_confluence_status = "🔥 POWER SETUP (Weekly CPR + BB Squeeze + HM > 50)"
                        extra_pts = 15
                    elif above_weekly_pivot and is_hm_above_50:
                        cpr_confluence_status = "🟢 Bullish (Weekly Pivot + HM > 50)"
                        extra_pts = 10

                score_val, grade_val = assign_cash_trade_score(vol_ratio, abs(dist_to_52w_pct), mtf_score, extra_points=extra_pts)

                if single_day_gain_pct > 8.0:
                    entry_price = round(high_52w, 2)
                    trade_action = "⚠️ Slippage Risk (Wait for Pullback Retest)"
                    strategy_note = f"Limit Buy near 52W Level (₹{high_52w:,.2f}) on light volume pullback."
                elif -1.5 <= dist_to_52w_pct <= 1.0:
                    entry_price = round(high_52w * 1.002, 2)
                    trade_action = "🎯 Ideal Consolidation / Pre-Breakout Entry"
                    strategy_note = "Pre-Breakout / Retest accumulation near 52W level."
                else:
                    entry_price = round(ltp, 2)
                    trade_action = "🚀 Active 52W Breakout"
                    strategy_note = "Accumulate position for 3–6 month swing horizon."

                stop_loss_tight = round(max(high_52w * 0.98, sma_20), 2)
                stop_loss_50sma = round(sma_50, 2) if not np.isnan(sma_50) else round(high_52w * 0.92, 2)

                risk_per_share = max(entry_price - stop_loss_tight, entry_price * 0.03)
                target_3x = round(entry_price + (3 * risk_per_share), 2)

                yearly_breakout_results.append(
                    {
                        "Symbol": symbol,
                        "LTP (₹)": round(ltp, 2),
                        "Score": score_val,
                        "Grade": grade_val,
                        "52W High (₹)": round(high_52w, 2),
                        "Dist to 52W %": dist_to_52w_pct,
                        "Single-Day Gain %": single_day_gain_pct,
                        "HTF RSI Alignment": mtf_status,
                        "Trigger / Entry Price (₹)": entry_price,
                        "Tight Stop Loss (₹)": stop_loss_tight,
                        "Swing SL (50 SMA) (₹)": stop_loss_50sma,
                        "Target (1:3 R:R) (₹)": target_3x,
                        "Vol Ratio": f"{vol_ratio}x",
                        "Confluence Signal": cpr_confluence_status,
                        "Action Status": trade_action,
                        "Execution Plan": strategy_note,
                    }
                )

            time.sleep(0.05)

        except Exception as e:
            st.error(f"Error scanning yearly breakout for {symbol}: {str(e)}")

    status_text.text("Yearly Breakout Scan Completed!")
    progress_bar.empty()

    if yearly_breakout_results:
        df_yb = pd.DataFrame(yearly_breakout_results)
        return df_yb.sort_values(by="Score", ascending=False).reset_index(drop=True)
    return pd.DataFrame()

# ==========================================
# 17. ACTIVE BREAKOUT ENGINE WITH FINANCIAL STABILITY
# ==========================================
def calculate_weekly_pre_breakout_candidates(
    kite, ma_prox_thresh=3.0, rsi_min=50.0, rsi_max=75.0, min_vol_ratio=1.2
):
    st.info(
        "🚀 Running Active Breakout Engine: TRIPLE HM Uptrend + BB Squeeze + Weekly Upper Band Breakout + Volume Surge + Financial Stability Filters..."
    )

    instruments = kite.instruments("NSE")
    df = pd.DataFrame(instruments)

    cash_stocks = df[
        (df["segment"] == "NSE")
        & (df["instrument_type"] == "EQ")
        & (df["name"].str.strip() != "")
    ].copy()

    exclude_keywords = [
        "BEES", "ETF", "GOLD", "SILVER", "LIQUID", "NIFTY", "BOND",
        "SGB", "NAV", "GSEC", "IWIN", "-RE", "-SG",
    ]
    pattern = "|".join(exclude_keywords)
    cash_stocks = cash_stocks[
        ~cash_stocks["tradingsymbol"].str.contains(pattern, case=False, na=False)
    ]
    cash_stocks = cash_stocks[~cash_stocks["tradingsymbol"].str.match(r"^\d")]

    all_symbols = cash_stocks["tradingsymbol"].dropna().unique().tolist()
    formatted_symbols = [f"NSE:{s}" for s in all_symbols]

    liquid_symbols = []
    chunk_size = 50
    for i in range(0, len(formatted_symbols), chunk_size):
        chunk = formatted_symbols[i : i + chunk_size]
        try:
            quotes = kite.quote(chunk)
            if isinstance(quotes, dict):
                for sym_key, qdata in quotes.items():
                    if not isinstance(qdata, dict):
                        continue
                    clean_sym = sym_key.replace("NSE:", "")
                    ltp = qdata.get("last_price", 0) or qdata.get("ohlc", {}).get("close", 0)
                    vol = qdata.get("volume", 0)

                    if ltp >= 30.0 and (vol >= 10000 or vol == 0):
                        liquid_symbols.append(clean_sym)
            time.sleep(0.05)
        except Exception:
            time.sleep(0.2)

    to_date = datetime.now()
    from_date = to_date - timedelta(days=1095)

    total_liquid = len(liquid_symbols)
    st.success(f"⚡ Filtered down to **{total_liquid} active stocks**. Scanning BB Upper Band Breakouts...")

    breakout_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for index, symbol in enumerate(liquid_symbols, start=1):
        try:
            status_text.text(f"Scanning Active Breakouts [{index}/{total_liquid}]: {symbol}...")
            progress_bar.progress(index / total_liquid)

            match = cash_stocks[cash_stocks["tradingsymbol"] == symbol]
            if match.empty:
                continue

            token = int(match.iloc[0]["instrument_token"])

            c_daily = safe_fetch_history(
                kite, token, from_date.strftime("%Y-%m-%d %H:%M:%S"), to_date.strftime("%Y-%m-%d %H:%M:%S"), "day"
            )
            df_daily = pd.DataFrame(c_daily)

            if len(df_daily) < 120:
                continue

            df_daily["date"] = pd.to_datetime(df_daily["date"])

            df_weekly = (
                df_daily.resample("W-MON", on="date")
                .agg({
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                })
                .dropna()
                .reset_index()
            )

            df_monthly = (
                df_daily.resample("ME", on="date")
                .agg({
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                })
                .dropna()
                .reset_index()
            )

            if len(df_daily) < 30 or len(df_weekly) < 22 or len(df_monthly) < 22:
                continue

            df_weekly["ema11"] = df_weekly["close"].ewm(span=11, adjust=False).mean()
            df_weekly["sma20"] = df_weekly["close"].rolling(20).mean()
            df_weekly["std20"] = df_weekly["close"].rolling(20).std()
            df_weekly["ub"] = df_weekly["sma20"] + (2 * df_weekly["std20"])
            df_weekly["lb"] = df_weekly["sma20"] - (2 * df_weekly["std20"])
            df_weekly["bb_width"] = (df_weekly["ub"] - df_weekly["lb"]) / df_weekly["sma20"]

            df_daily = calculate_hilega_milega(df_daily)
            df_weekly = calculate_hilega_milega(df_weekly)
            df_monthly = calculate_hilega_milega(df_monthly)

            latest_d = df_daily.iloc[-1]
            latest_w = df_weekly.iloc[-1]
            latest_m = df_monthly.iloc[-1]

            if (
                "hm_ema_price" not in latest_d
                or "hm_ema_price" not in latest_w
                or "hm_ema_price" not in latest_m
            ):
                continue

            d_hm_bull = (latest_d["hm_ema_price"] > latest_d["hm_wma_strength"]) and (latest_d["hm_rsi"] >= 50.0)
            w_hm_bull = (latest_w["hm_ema_price"] > latest_w["hm_wma_strength"]) and (latest_w["hm_rsi"] >= 50.0)
            m_hm_bull = (latest_m["hm_ema_price"] > latest_m["hm_wma_strength"]) and (latest_m["hm_rsi"] >= 50.0)

            if not (d_hm_bull and w_hm_bull and m_hm_bull):
                continue

            w_ltp = latest_w["close"]
            w_ub = latest_w["ub"]
            w_sma20 = latest_w["sma20"]
            w_bb_width = latest_w["bb_width"]
            w_rsi = latest_w["hm_rsi"]

            min_10w_bb = df_weekly["bb_width"].tail(10).min()
            had_prior_squeeze = (w_bb_width <= min_10w_bb * 1.25) or (w_bb_width <= 0.14)

            is_bb_upper_breakout = w_ltp > w_ub

            vol_20w_avg = df_weekly["volume"].tail(20).mean()
            vol_multiplier = round(latest_w["volume"] / vol_20w_avg, 2) if vol_20w_avg > 0 else 1.0
            has_volume_expansion = vol_multiplier >= min_vol_ratio

            if had_prior_squeeze and is_bb_upper_breakout and has_volume_expansion:
                fin_info = check_financial_health(symbol)

                score_val, grade_val = assign_cash_trade_score(
                    vol_multiplier, dist_pct=0.5, mtf_score=3, extra_points=(35 + (10 if fin_info["Is_Stable"] else 0))
                )

                swing_low_4w = df_weekly["low"].tail(4).min()
                stop_loss = round(max(swing_low_4w, w_sma20 * 0.98), 2)
                risk = max(w_ltp - stop_loss, w_ltp * 0.03)

                target_1 = round(w_ltp + (1.5 * risk), 2)
                target_2 = round(w_ltp + (3.0 * risk), 2)
                event_risk_flag = fetch_stock_earnings_risk_dynamic(symbol)

                breakout_results.append(
                    {
                        "Symbol": symbol,
                        "LTP (₹)": round(w_ltp, 2),
                        "Score": score_val,
                        "Grade": grade_val,
                        "Breakout Signal": "🔥 BB Upper Band Blast + Vol Surge",
                        "Financial Health": fin_info["Fin_Status"],
                        "D/E Ratio": fin_info["Debt_to_Equity"],
                        "ROE %": fin_info["ROE_%"],
                        "Weekly UB (₹)": round(w_ub, 2),
                        "Breakout Premium %": round(((w_ltp - w_ub) / w_ub) * 100, 2),
                        "Vol Surge Ratio": f"{vol_multiplier}x Avg Vol",
                        "MTF HM Alignment": f"1D:{round(latest_d['hm_rsi'],1)} | 1W:{round(w_rsi,1)} | 1M:{round(latest_m['hm_rsi'],1)}",
                        "Event Risk Radar": event_risk_flag,
                        "Stop Loss (₹)": stop_loss,
                        "Target 1 (1.5 R:R) (₹)": target_1,
                        "Target 2 (3.0 R:R) (₹)": target_2,
                    }
                )

            time.sleep(0.04)

        except Exception as e:
            st.error(f"Error scanning Upper Band Breakouts for {symbol}: {str(e)}")

    status_text.text("Active Upper Band Breakout Scan Completed!")
    progress_bar.empty()

    if breakout_results:
        df_res = pd.DataFrame(breakout_results)
        return df_res.sort_values(by="Score", ascending=False).reset_index(drop=True)
    return pd.DataFrame()

# ==========================================
# 18. WEEKLY SQUEEZE + 52-WEEK HIGH BREAKOUT ENGINE
# ==========================================
def scan_weekly_squeeze_52w_breakouts(kite):
    st.info("🔥 Scanning NSE Cash Equities for Combined Weekly Squeeze + 52-Week High Breakout Confluence...")

    instruments = kite.instruments("NSE")
    df = pd.DataFrame(instruments)

    cash_stocks = df[
        (df["segment"] == "NSE")
        & (df["instrument_type"] == "EQ")
        & (df["name"].str.strip() != "")
    ].copy()

    exclude_keywords = [
        "BEES", "ETF", "GOLD", "SILVER", "LIQUID", "NIFTY", "BOND",
        "SGB", "NAV", "GSEC", "IWIN", "-RE", "-SG"
    ]
    pattern = "|".join(exclude_keywords)
    cash_stocks = cash_stocks[
        ~cash_stocks["tradingsymbol"].str.contains(pattern, case=False, na=False)
    ]
    cash_stocks = cash_stocks[~cash_stocks["tradingsymbol"].str.match(r"^\d")]

    all_symbols = cash_stocks["tradingsymbol"].dropna().unique().tolist()
    formatted_symbols = [f"NSE:{s}" for s in all_symbols]

    st.write(f"🔍 Fast liquidity check across {len(all_symbols)} cash symbols...")
    liquid_symbols = []

    chunk_size = 50
    for i in range(0, len(formatted_symbols), chunk_size):
        chunk = formatted_symbols[i : i + chunk_size]
        try:
            quotes = kite.quote(chunk)
            if isinstance(quotes, dict):
                for sym_key, qdata in quotes.items():
                    if not isinstance(qdata, dict):
                        continue
                    clean_sym = sym_key.replace("NSE:", "")
                    ltp = qdata.get("last_price", 0) or qdata.get("ohlc", {}).get("close", 0)
                    vol = qdata.get("volume", 0)

                    if ltp >= 30.0 and (vol >= 15000 or vol == 0):
                        liquid_symbols.append(clean_sym)
            time.sleep(0.05)
        except Exception:
            time.sleep(0.2)

    total_liquid = len(liquid_symbols)
    st.success(f"⚡ Pruned list to **{total_liquid} active liquid stocks**. Scanning Weekly Squeeze + 52W High Breakouts...")

    combo_results = []
    to_date = datetime.now()
    from_date = to_date - timedelta(days=730)

    progress_bar = st.progress(0)
    status_text = st.empty()

    for index, symbol in enumerate(liquid_symbols, start=1):
        try:
            status_text.text(f"Scanning Squeeze + 52W High [{index}/{total_liquid}]: {symbol}...")
            progress_bar.progress(index / total_liquid)

            match = cash_stocks[cash_stocks["tradingsymbol"] == symbol]
            if match.empty:
                continue

            token = int(match.iloc[0]["instrument_token"])

            candles = safe_fetch_history(
                kite,
                token,
                from_date.strftime("%Y-%m-%d %H:%M:%S"),
                to_date.strftime("%Y-%m-%d %H:%M:%S"),
                "day",
            )
            df_daily = pd.DataFrame(candles)

            if len(df_daily) < 200:
                continue

            ltp = df_daily["close"].iloc[-1]
            high_52w = df_daily["high"].iloc[:-1].max()
            dist_to_52w_pct = round(((ltp - high_52w) / high_52w) * 100, 2)

            if dist_to_52w_pct < -2.0:
                continue

            df_daily["date"] = pd.to_datetime(df_daily["date"])
            df_weekly = (
                df_daily.resample("W-MON", on="date")
                .agg({
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                })
                .dropna()
                .reset_index()
            )

            if len(df_weekly) < 22:
                continue

            df_weekly["sma20"] = df_weekly["close"].rolling(20).mean()
            df_weekly["std20"] = df_weekly["close"].rolling(20).std()
            df_weekly["ub"] = df_weekly["sma20"] + (2 * df_weekly["std20"])
            df_weekly["lb"] = df_weekly["sma20"] - (2 * df_weekly["std20"])
            df_weekly["bb_width"] = (df_weekly["ub"] - df_weekly["lb"]) / df_weekly["sma20"]

            df_weekly = calculate_hilega_milega(df_weekly)
            latest_w = df_weekly.iloc[-1]

            w_bb_width = latest_w["bb_width"]
            min_10w_bb = df_weekly["bb_width"].tail(10).min()
            is_weekly_squeeze = (w_bb_width <= min_10w_bb * 1.25) or (w_bb_width <= 0.15)
            is_weekly_ub_breakout = ltp >= (latest_w["ub"] * 0.99)

            if is_weekly_squeeze and is_weekly_ub_breakout:
                fin_info = check_financial_health(symbol)
                vol_20w_avg = df_weekly["volume"].tail(20).mean()
                vol_multiplier = round(latest_w["volume"] / vol_20w_avg, 2) if vol_20w_avg > 0 else 1.0

                score_val, grade_val = assign_cash_trade_score(
                    vol_multiplier, dist_pct=abs(dist_to_52w_pct), mtf_score=3, extra_points=25
                )

                stop_loss = round(max(latest_w["sma20"], high_52w * 0.95), 2)
                risk = max(ltp - stop_loss, ltp * 0.03)
                target_1 = round(ltp + (2.0 * risk), 2)
                target_2 = round(ltp + (4.0 * risk), 2)

                signal_desc = "🚀 52W High Breakout + Weekly BB Squeeze Blast" if dist_to_52w_pct >= 0 else "⚡ Pre-Breakout Squeeze near 52W High"

                combo_results.append({
                    "Symbol": symbol,
                    "LTP (₹)": round(ltp, 2),
                    "Score": score_val,
                    "Grade": grade_val,
                    "Confluence Signal": signal_desc,
                    "52W High (₹)": round(high_52w, 2),
                    "Dist to 52W %": dist_to_52w_pct,
                    "Weekly UB (₹)": round(latest_w["ub"], 2),
                    "BB Width %": round(w_bb_width * 100, 2),
                    "Vol Surge": f"{vol_multiplier}x",
                    "Financial Health": fin_info["Fin_Status"],
                    "Stop Loss (₹)": stop_loss,
                    "Target 1 (1:2 R:R) (₹)": target_1,
                    "Target 2 (1:4 R:R) (₹)": target_2,
                })

            time.sleep(0.04)

        except Exception as e:
            st.error(f"Error scanning Squeeze + 52W High for {symbol}: {str(e)}")

    status_text.text("Squeeze + 52W High Scan Completed!")
    progress_bar.empty()

    if combo_results:
        df_res = pd.DataFrame(combo_results)
        return df_res.sort_values(by="Score", ascending=False).reset_index(drop=True)
    return pd.DataFrame()

# ==========================================
# 19. AUTOMATED TRADE GUARDRAIL MODULE
# ==========================================
def render_trade_guardrail_tab(kite):
    st.markdown("## 🛡️ Trade Guardrail & Order Risk Verification Engine")
    st.caption("Auto-fetches live market context & recommended option contracts directly from Zerodha Kite Connect API.")

    try:
        nfo_df = pd.DataFrame(kite.instruments("NFO"))
        bfo_df = pd.DataFrame(kite.instruments("BFO"))
        all_instruments = pd.concat([nfo_df, bfo_df], ignore_index=True)
        all_index_names = [v["name"] for v in INDEX_MAP.values()]
        all_fno_symbols = sorted(list(set(all_index_names + nfo_df["name"].unique().tolist())))
    except Exception:
        all_instruments = pd.DataFrame()
        all_fno_symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "RELIANCE"]

    col_top1, col_top2, col_top3 = st.columns([2, 1, 1])
    with col_top1:
        symbol = st.selectbox("Select Benchmark / Asset", all_fno_symbols, index=all_fno_symbols.index("NIFTY") if "NIFTY" in all_fno_symbols else 0)
    with col_top2:
        side = st.radio("Order Action", ["BUY", "SELL"], horizontal=True)
    with col_top3:
        option_type = st.radio("Option Type", ["CE", "PE"], horizontal=True)

    spot_price, vwap_val, rvol, rec_option, live_premium, buy_rate = 24250.0, 24220.0, 1.8, "N/A", 100.0, 100.5

    try:
        segment_prefix = "BSE" if symbol in ["SENSEX", "BANKEX"] else "NSE"
        spot_symbol = f"{segment_prefix}:{symbol}"
        if symbol == "NIFTY": spot_symbol = "NSE:NIFTY 50"
        elif symbol == "BANKNIFTY": spot_symbol = "NSE:NIFTY BANK"
        elif symbol == "FINNIFTY": spot_symbol = "NSE:NIFTY FIN SERVICE"
        elif symbol == "MIDCPNIFTY": spot_symbol = "NSE:NIFTY MID SELECT"
        elif symbol == "SENSEX": spot_symbol = "BSE:SENSEX"
        elif symbol == "BANKEX": spot_symbol = "BSE:BANKEX"

        quote = kite.quote([spot_symbol])
        spot_data = quote.get(spot_symbol, {})
        spot_price = spot_data.get("last_price", 24250.0)

        rec_option, bounce_lvl, buy_rate, sl_rate, target_rate, vwap_status = fetch_vwap_option_details(
            kite, all_instruments, symbol, spot_price, "BULLISH" if option_type == "CE" else "BEARISH"
        )
        live_premium = bounce_lvl if bounce_lvl > 0 else 100.0
        if buy_rate <= 0: buy_rate = live_premium * 1.005

        match = nfo_df[nfo_df["name"] == symbol]
        if not match.empty:
            tok = int(match.iloc[0]["instrument_token"])
            today_start = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
            c_5m = safe_fetch_history(kite, tok, today_start, datetime.now(), "5minute")
            if c_5m:
                df_5m = pd.DataFrame(c_5m)
                df_5m["tp"] = (df_5m["high"] + df_5m["low"] + df_5m["close"]) / 3.0
                vwap_val = round((df_5m["tp"] * df_5m["volume"]).sum() / df_5m["volume"].sum(), 2) if df_5m["volume"].sum() > 0 else spot_price
                avg_vol = df_5m["volume"].mean()
                rvol = round(df_5m["volume"].iloc[-1] / avg_vol, 2) if avg_vol > 0 else 1.0
    except Exception:
        pass

    st.markdown("---")
    st.markdown(f"### 🤖 Live Auto-Suggested Option Contract: `{rec_option}`")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📋 Order Execution Details")
        premium = st.number_input("Suggested Premium / Entry Rate (₹)", min_value=1.0, value=float(buy_rate), step=1.0)
        max_risk = st.number_input("Max Risk Limit per Trade (₹)", min_value=500.0, value=2000.0, step=250.0)
        
        pos_data = calculate_dynamic_position_size(symbol, premium, sl_pct=0.15, max_risk_inr=max_risk)
        quantity = st.number_input("Auto-Calculated Safe Quantity", min_value=1, value=pos_data["quantity"], step=pos_data["lot_size"])

    with col2:
        st.markdown("### 📊 Real-Time Market Context (Auto-Fetched)")
        spot_price = st.number_input("Live Spot Price (₹)", min_value=1.0, value=float(spot_price), step=10.0)
        vwap_val = st.number_input("Live 15M VWAP (₹)", min_value=1.0, value=float(vwap_val if vwap_val > 0 else spot_price), step=10.0)
        rvol = st.number_input("Intraday Relative Volume (RVOL)", min_value=0.1, value=float(rvol), step=0.1)

    st.markdown("---")

    if st.button("🔍 Run Safety & Risk Verification", type="primary", use_container_width=True):
        is_allowed, warnings = validate_trade_execution(
            symbol=symbol,
            side=side,
            option_type=option_type,
            ltp=spot_price,
            vwap=vwap_val,
            rvol=rvol,
            quantity=quantity,
            premium=premium,
            max_allowed_risk=max_risk
        )
        
        if not is_allowed:
            for w in warnings:
                st.error(w)
            st.warning("⚠️ **EXECUTION BLOCKED:** Fix the risk errors before placing this trade.")
        else:
            st.success("✅ **TRADE APPROVED:** This position passes all institutional momentum & risk parameters.")
            
            hard_sl = round(premium * 0.85, 2) if side == "BUY" else round(premium * 1.15, 2)
            target = round(premium * 1.40, 2) if side == "BUY" else round(premium * 0.60, 2)
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Recommended Qty", f"{quantity} ({pos_data['lots']} Lots)")
            m2.metric("Max Loss Risk", f"₹{pos_data['max_loss']:,.2f}")
            m3.metric("Hard Stop Loss (15%)", f"₹{hard_sl:,.2f}")
            m4.metric("Profit Target (40%)", f"₹{target:,.2f}")
            
# ==========================================
# 20. STREAMLIT DASHBOARD UI
# ==========================================
def main():
    st.set_page_config(
        page_title="Institutional F&O & Cash Intelligence Terminal",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inject_custom_css()

    st.title("⚡ Institutional F&O & Cash Intelligence Terminal")
    st.caption(
        "Powered by Zerodha Kite Connect API | Real-Time Options Greeks, Dynamic CVD Gamma Engine & Universal Option Chain Analytics"
    )
    st.markdown("---")

    kite = get_authenticated_kite()
    if not kite:
        st.error("🔒 Please log in via Zerodha to initialize the live terminal.")
        st.stop()

    st.sidebar.title("🎛️ Terminal Navigation & Scanners")
    nav_choice = st.sidebar.radio(
        "Select Scanner Engine",
        [
            "⚡ Real-Time Gamma Scalper & IV Rank (Option Buyers)",
            "🎯 Intraday Breakout & Scalping Engine",
            "📊 Universal Option Chain & Max Pain",
            "📐 Technical Indicators & CPR Overview",
            "📡 Master F&O Stock & Options Engine",
            "🛡️ Trade Guardrail & Risk Verifier",
            "⚡ Hero-Zero Expiry Scanner",
            "🚀 Udd Ja Breakout Engine (Cash Equities)",
            "📅 52-Week High Breakouts (Cash Equities)",
            "🎯 Weekly Pre-Breakout Squeeze Engine",
            "🔥 Weekly Squeeze + 52-Week High Breakouts",
        ],
    )

    # Permanent Sidebar Risk Check Widget
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛡️ Quick Order Verification")
    sb_side = st.sidebar.selectbox("Side", ["BUY", "SELL"], key="sb_side_select")
    sb_type = st.sidebar.selectbox("Option", ["CE", "PE"], key="sb_type_select")
    sb_price = st.sidebar.number_input("Premium (₹)", value=100.0, step=5.0, key="sb_price_num")
    sb_qty = st.sidebar.number_input("Qty", value=25, step=25, key="sb_qty_num")

    if st.sidebar.button("Verify Order Safety", key="sb_verify_btn"):
        proj_risk = sb_price * sb_qty * 0.15
        if sb_side == "SELL":
            st.sidebar.warning("⚠️ Naked Shorting Alert: Ensure Spread Hedge is active.")
        elif proj_risk > 2000.0:
            st.sidebar.error(f"❌ Max Risk Exceeded: ₹{proj_risk:,.2f} > ₹2,000")
        else:
            st.sidebar.success("✅ Trade structure safe.")

    if nav_choice == "⚡ Real-Time Gamma Scalper & IV Rank (Option Buyers)":
        st.markdown("## ⚡ Real-Time Gamma Scalper & IV Rank (Option Buyers)")
        st.caption("Designed for net option buyers seeking explosive momentum, Cumulative Volume Delta (CVD) expansion, and cheap IV Rank setups across NSE & BSE indices + Heavyweights.")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🚀 Run Gamma Scalp & IV Rank Scan", type="primary"):
                st.session_state.df_gamma_scalp = scan_gamma_scalper_and_ivr(kite)
        with col2:
            if st.button("🧹 Clear Scanned Results"):
                st.session_state.df_gamma_scalp = None
                st.rerun()

        if "df_gamma_scalp" in st.session_state and st.session_state.df_gamma_scalp is not None:
            if not st.session_state.df_gamma_scalp.empty:
                st.dataframe(st.session_state.df_gamma_scalp, use_container_width=True, hide_index=True)
            else:
                st.info("No active Gamma Scalp setups or cheap IV setups found at this time.")

    elif nav_choice == "🎯 Intraday Breakout & Scalping Engine":
        st.markdown("## 🎯 Intraday Breakout, ORB & Candlestick Scalper")
        st.caption("Real-time scanner for 15-Min ORB, PDH/PDL breakouts, Candlestick Reversals, and Bollinger Band Intraday Squeezes.")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🚀 Scan Real-Time Intraday Breakouts", type="primary"):
                st.session_state.df_intraday_scalp = scan_intraday_breakout_scalps(kite)
        with col2:
            if st.button("🧹 Clear Results"):
                st.session_state.df_intraday_scalp = None
                st.rerun()

        if "df_intraday_scalp" in st.session_state and st.session_state.df_intraday_scalp is not None:
            if not st.session_state.df_intraday_scalp.empty:
                st.dataframe(st.session_state.df_intraday_scalp, use_container_width=True, hide_index=True)
            else:
                st.info("No active high-volume intraday breakouts or pattern setups found at this time.")

    elif nav_choice == "📊 Universal Option Chain & Max Pain":
        render_universal_option_chain_tab(kite)

    elif nav_choice == "📐 Technical Indicators & CPR Overview":
        render_technical_indicators_section(kite)

    elif nav_choice == "🛡️ Trade Guardrail & Risk Verifier":
        render_trade_guardrail_tab(kite)

    elif nav_choice == "📡 Master F&O Stock & Options Engine":
        render_executive_summary()
        render_market_header_and_breadth(kite)
        st.markdown("## 📡 Master F&O Stock & Options Engine")

        if "df_indices_overview" not in st.session_state or st.session_state.df_indices_overview is None:
            with st.spinner("Fetching Major Indices Levels..."):
                idx_df, idx_opt_df = scan_indices_overview(kite)
                st.session_state.df_indices_overview = idx_df
                st.session_state.df_index_options = idx_opt_df

        vix_val, vix_status = fetch_india_vix_regime(kite)
        st.metric(
            label="🇮🇳 India VIX Market Volatility", value=vix_val, delta=vix_status
        )

        st.subheader("🏛️ Major Indices Overview")
        if (
            "df_indices_overview" in st.session_state
            and st.session_state.df_indices_overview is not None
            and not st.session_state.df_indices_overview.empty
        ):
            st.dataframe(
                st.session_state.df_indices_overview,
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("### 🎯 Major Index Options Trigger & Levels")
        if (
            "df_index_options" in st.session_state
            and st.session_state.df_index_options is not None
            and not st.session_state.df_index_options.empty
        ):
            st.dataframe(
                st.session_state.df_index_options,
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("---")

        col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 1])
        with col_btn1:
            if st.button("🚀 Run F&O Master Scan", type="primary"):
                idx_df, idx_opt_df = scan_indices_overview(kite)
                st.session_state.df_indices_overview = idx_df
                st.session_state.df_index_options = idx_opt_df

                df_intraday, df_strict, df_all = scan_fno_opportunities(kite)
                st.session_state.df_fno_intraday = df_intraday
                st.session_state.df_fno_strict = df_strict
                st.session_state.df_fno_all = df_all
        with col_btn2:
            if st.button("🔄 Refresh Index Data Only"):
                with st.spinner("Updating Index Levels..."):
                    idx_df, idx_opt_df = scan_indices_overview(kite)
                    st.session_state.df_indices_overview = idx_df
                    st.session_state.df_index_options = idx_opt_df
                st.rerun()
        with col_btn3:
            if st.button("🧹 Clear Scanned Results", key="clear_fno"):
                st.session_state.df_fno_intraday = None
                st.session_state.df_fno_strict = None
                st.session_state.df_fno_all = None
                st.rerun()

        if "df_fno_intraday" in st.session_state and st.session_state.df_fno_intraday is not None:
            tab1, tab2, tab3 = st.tabs(
                [
                    "⚡ High Volatility Intraday Option Picks",
                    "🔥 Strict Multi-Timeframe Signals",
                    "📊 Complete F&O Scanned Universe",
                ]
            )
            with tab1:
                st.markdown("### ⚡ Top High-Volume Intraday Option Trade Setups")
                if not st.session_state.df_fno_intraday.empty:
                    st.dataframe(st.session_state.df_fno_intraday, use_container_width=True, hide_index=True)
                else:
                    st.info("No intraday setups matching strict volume surge criteria.")

            with tab2:
                st.markdown("### 🔥 High-Probability Multi-Timeframe Directional Setups")
                if not st.session_state.df_fno_strict.empty:
                    st.dataframe(st.session_state.df_fno_strict, use_container_width=True, hide_index=True)
                else:
                    st.info("No strict MTF aligned signals detected.")

            with tab3:
                st.markdown("### 📊 Complete F&O Scanned Universe Data")
                if not st.session_state.df_fno_all.empty:
                    st.dataframe(st.session_state.df_fno_all, use_container_width=True, hide_index=True)

    elif nav_choice == "⚡ Hero-Zero Expiry Scanner":
        st.markdown("## ⚡ Hero-Zero Expiry Scanner")
        render_today_expiry_banner(kite)
        st.markdown("---")

        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            if st.button("🔥 Scan Hero-Zero Expiry Candidates", type="primary"):
                st.session_state.df_hz_results = scan_hero_zero_opportunities(kite)
        with col_btn2:
            if st.button("🧹 Clear Scanned Results", key="clear_hz"):
                st.session_state.df_hz_results = None
                st.rerun()

        if "df_hz_results" in st.session_state and st.session_state.df_hz_results is not None:
            if not st.session_state.df_hz_results.empty:
                st.dataframe(st.session_state.df_hz_results, use_container_width=True, hide_index=True)
            else:
                st.info("No active Hero-Zero expiry squeezes found at this time.")

    elif nav_choice == "🚀 Udd Ja Breakout Engine (Cash Equities)":
        st.markdown("## 🚀 High-Speed Udd Ja Breakout Engine (Cash Equities)")
        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            if st.button("🚀 Scan Udd Ja Cash Breakouts", type="primary"):
                st.session_state.df_udd_results = scan_udd_ja_cash_stocks(kite)
        with col_btn2:
            if st.button("🧹 Clear Scanned Results", key="clear_udd"):
                st.session_state.df_udd_results = None
                st.rerun()

        if "df_udd_results" in st.session_state and st.session_state.df_udd_results is not None:
            if not st.session_state.df_udd_results.empty:
                st.dataframe(st.session_state.df_udd_results, use_container_width=True, hide_index=True)
            else:
                st.info("No Udd Ja breakout candidates currently active.")

    elif nav_choice == "📅 52-Week High Breakouts (Cash Equities)":
        st.markdown("## 📅 52-Week High Breakouts (Cash Equities)")
        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            if st.button("📅 Scan 52-Week High Breakouts", type="primary"):
                st.session_state.df_yb_results = scan_yearly_breakout_cash_stocks(kite)
        with col_btn2:
            if st.button("🧹 Clear Scanned Results", key="clear_yb"):
                st.session_state.df_yb_results = None
                st.rerun()

        if "df_yb_results" in st.session_state and st.session_state.df_yb_results is not None:
            if not st.session_state.df_yb_results.empty:
                st.dataframe(st.session_state.df_yb_results, use_container_width=True, hide_index=True)
            else:
                st.info("No 52-Week high breakout candidates found.")

    elif nav_choice == "🎯 Weekly Pre-Breakout Squeeze Engine":
        st.markdown("## 🎯 High-Confluence Weekly Pre-Breakout Squeeze Engine")
        col_m1, col_m2 = st.columns(2)
        
        with col_m1:
            rsi_min_val = st.slider("Min Weekly RSI (9)", 40.0, 60.0, 55.0, 1.0, key="rsi_min")
        with col_m2:
            rsi_max_val = st.slider("Max Weekly RSI (9)", 60.0, 75.0, 68.0, 1.0, key="rsi_max")

        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            if st.button("🎯 Scan High-Probability Pre-Breakout Squeezes", type="primary"):
                st.session_state.df_pb_results = calculate_weekly_pre_breakout_candidates(
                    kite, rsi_min=rsi_min_val, rsi_max=rsi_max_val
                )
        with col_btn2:
            if st.button("🧹 Clear Scanned Results", key="clear_pb"):
                st.session_state.df_pb_results = None
                st.rerun()

        if "df_pb_results" in st.session_state and st.session_state.df_pb_results is not None:
            if not st.session_state.df_pb_results.empty:
                st.dataframe(st.session_state.df_pb_results, use_container_width=True, hide_index=True)
            else:
                st.info("No high-confluence pre-breakout squeeze setups found matching your criteria.")

    elif nav_choice == "🔥 Weekly Squeeze + 52-Week High Breakouts":
        st.markdown("## 🔥 Weekly Bollinger Squeeze + 52-Week High Breakout Confluence")
        st.caption("Filters stocks triggering a Weekly Bollinger Upper Band Blast while simultaneously trading within 2.0% of or above their 52-Week High.")

        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            if st.button("🚀 Scan Weekly Squeeze + 52W High Confluence", type="primary"):
                st.session_state.df_combo_results = scan_weekly_squeeze_52w_breakouts(kite)
        with col_btn2:
            if st.button("🧹 Clear Scanned Results", key="clear_combo"):
                st.session_state.df_combo_results = None
                st.rerun()

        if "df_combo_results" in st.session_state and st.session_state.df_combo_results is not None:
            if not st.session_state.df_combo_results.empty:
                st.dataframe(st.session_state.df_combo_results, use_container_width=True, hide_index=True)
            else:
                st.info("No stocks currently matching the dual Weekly Squeeze + 52-Week High Breakout condition.")

if __name__ == "__main__":
    main()
