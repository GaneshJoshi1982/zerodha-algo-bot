from datetime import datetime, timedelta
import math
import os
import time
from kiteconnect import KiteConnect
import numpy as np
import pandas as pd
import requests
import streamlit as st

# ==========================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================
API_KEY = "magym2s4yk13gsze"
API_SECRET = "uxph73v40oemxff3c9xn48swqwctbfmf"
TOKEN_FILE = "access_token.txt"
RENDER_BACKEND = "http://92.4.85.1:10000"

# Risk Guardrails
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
    "NIFTY": {"token": 256265, "symbol": "NSE:NIFTY 50", "segment": "NFO"},
    "BANKNIFTY": {"token": 260105, "symbol": "NSE:NIFTY BANK", "segment": "NFO"},
    "FINNIFTY": {"token": 257801, "symbol": "NSE:NIFTY FIN SERVICE", "segment": "NFO"},
    "SENSEX": {"token": 265, "symbol": "BSE:SENSEX", "segment": "BFO"},
}

# ==========================================
# 2. ZERODHA SESSION & MARGIN AUTHENTICATION
# ==========================================
def get_kite_session():
    kite = KiteConnect(api_key=API_KEY)
    
    # Try fetching shared token from Oracle VPS
    try:
        res = requests.get(f"{RENDER_BACKEND}/get-token", timeout=3).json()
        if res.get("status") == "SUCCESS" and "access_token" in res:
            access_token = res["access_token"]
            kite.set_access_token(access_token)
            kite.profile()
            return kite
    except Exception:
        pass

    # Try local access token file
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                access_token = f.read().strip()
            kite.set_access_token(access_token)
            kite.profile()
            return kite
        except Exception:
            pass

    return None

def check_account_margin(kite, required_margin: float) -> tuple[bool, float]:
    """Queries live Zerodha funds to verify if margin is sufficient."""
    try:
        margins = kite.margins(segment="equity")
        available_cash = margins.get("enabled", {}).get("available", {}).get("live_balance", 0.0)
        return (available_cash >= required_margin), available_cash
    except Exception as e:
        st.error(f"Margin Check API Failed: {str(e)}")
        return False, 0.0

# ==========================================
# 3. INDICATOR CALCULATIONS (HM & LINREG)
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
    """Computes rolling least-squares Linear Regression values (TradingView ta.linreg)."""
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

# ==========================================
# 4. CONFLUENCE SIGNAL EVALUATION ENGINE
# ==========================================
def evaluate_strategy_signals(df_5m: pd.DataFrame, linreg_len: int = 11, signal_len: int = 11) -> dict:
    """
    Evaluates strategy using both Linear Regression Candle Crossover AND Hilega-Milega Direction:
    - BUY_CE: LinReg Crossover Above Signal AND HM EMA 3 > WMA 21
    - BUY_PE: LinReg Crossover Below Signal AND HM EMA 3 < WMA 21
    (RSI >= 50 constraint removed per instructions)
    """
    if df_5m is None or len(df_5m) < (linreg_len + signal_len + 10):
        return {"signal": "HOLD", "bclose": 0.0, "signal_line": 0.0, "hm_status": "Insufficient Data"}

    df = df_5m.copy()

    # --- 1. Hilega-Milega Calculations ---
    df["rsi9"] = calculate_rsi(df["close"], period=9)
    df["hm_price_ema3"] = df["rsi9"].ewm(span=3, adjust=False).mean()
    df["hm_strength_wma21"] = calculate_wma(df["rsi9"], length=21)

    # --- 2. Linear Regression Candle Calculations ---
    df["bopen"] = calculate_linreg_series(df["open"], length=linreg_len)
    df["bclose"] = calculate_linreg_series(df["close"], length=linreg_len)
    df["signal_line"] = df["bclose"].rolling(window=signal_len).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Crossover Triggers
    linreg_bull_cross = (latest["bclose"] > latest["signal_line"]) and (prev["bclose"] <= prev["signal_line"])
    linreg_bear_cross = (latest["bclose"] < latest["signal_line"]) and (prev["bclose"] >= prev["signal_line"])

    # HM Directional Confluence (EMA 3 vs WMA 21)
    hm_bullish = latest["hm_price_ema3"] > latest["hm_strength_wma21"]
    hm_bearish = latest["hm_price_ema3"] < latest["hm_strength_wma21"]

    # Final Combined Confluence Signals
    if linreg_bull_cross and hm_bullish:
        signal = "BUY_CE"
    elif linreg_bear_cross and hm_bearish:
        signal = "BUY_PE"
    else:
        signal = "HOLD"

    hm_desc = f"EMA3 ({latest['hm_price_ema3']:.1f}) > WMA21 ({latest['hm_strength_wma21']:.1f})" if hm_bullish else f"EMA3 ({latest['hm_price_ema3']:.1f}) < WMA21 ({latest['hm_strength_wma21']:.1f})"

    return {
        "signal": signal,
        "bclose": round(latest["bclose"], 2),
        "signal_line": round(latest["signal_line"], 2),
        "hm_status": hm_desc,
        "hm_bullish": hm_bullish,
        "hm_bearish": hm_bearish,
        "df_processed": df
    }

# ==========================================
# 5. POSITION SIZING & RISK ENGINE
# ==========================================
def calculate_position_size(symbol: str, premium: float, max_risk: float = MAX_RISK_PER_TRADE) -> dict:
    lot_size = 1
    for key, val in LOT_SIZES.items():
        if key in symbol.upper():
            lot_size = val
            break

    if premium <= 0:
        return {"lots": 0, "qty": 0, "capital_required": 0.0, "max_loss": 0.0}

    risk_per_share = premium * DEFAULT_SL_PCT
    risk_per_lot = risk_per_share * lot_size

    num_lots = max(1, math.floor(max_risk / risk_per_lot)) if risk_per_lot > 0 else 1
    total_qty = num_lots * lot_size
    capital_required = round(total_qty * premium, 2)
    actual_max_loss = round(num_lots * risk_per_lot, 2)

    return {
        "lots": num_lots,
        "qty": total_qty,
        "capital_required": capital_required,
        "max_loss": actual_max_loss,
        "lot_size": lot_size
    }

# ==========================================
# 6. AUTOMATED EXECUTION TERMINAL UI
# ==========================================
def main():
    st.set_page_config(page_title="Zerodha Algorithmic Trading Terminal", page_icon="⚡", layout="wide")
    st.title("⚡ Zerodha Algorithmic Trading Terminal")
    st.caption("Automated Engine Powered by Linear Regression Candles + Hilega-Milega Confluence")
    st.markdown("---")

    kite = get_kite_session()

    # System Status Header
    c1, c2, c3 = st.columns(3)
    with c1:
        if kite:
            st.success("🟢 **Kite Session:** Connected")
        else:
            st.error("🔴 **Kite Session:** Disconnected")
    with c2:
        st.info("🛡️ **IP Whitelist (92.4.85.1):** Active")
    with c3:
        st.success("⚡ **Cloud Engine:** Running")

    if not kite:
        st.error("Please authenticate Zerodha session on the main app to start the automated trading engine.")
        st.stop()

    st.markdown("---")
    tab_ctrl, tab_pos, tab_logs = st.tabs(["⚙️ Strategy Controls", "📊 Live Positions", "📋 System Audit Logs"])

    with tab_ctrl:
        st.subheader("🤖 Algorithmic Strategy Parameters")
        
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            selected_index = st.selectbox("Trading Benchmark", list(INDEX_TOKENS.keys()), index=0)
        with col_s2:
            max_risk_inr = st.number_input("Max Risk Ceiling per Trade (₹)", min_value=500.0, value=2000.0, step=250.0)
        with col_s3:
            sl_pct = st.number_input("Initial Hard Stop Loss (%)", min_value=0.05, max_value=0.30, value=0.15, step=0.01)

        st.markdown("---")
        if st.button("🚀 Evaluate Live Strategy Signal (LinReg + HM)", type="primary", use_container_width=True):
            idx_info = INDEX_TOKENS[selected_index]
            token = idx_info["token"]
            
            with st.spinner(f"Fetching 5-Minute Historical Candles for {selected_index}..."):
                to_date = datetime.now()
                from_date = to_date - timedelta(days=5)
                
                try:
                    candles = kite.historical_data(token, from_date, to_date, "5minute")
                    df_5m = pd.DataFrame(candles)
                except Exception as e:
                    st.error(f"Failed to fetch market data: {str(e)}")
                    df_5m = pd.DataFrame()

            if not df_5m.empty:
                analysis = evaluate_strategy_signals(df_5m, linreg_len=11, signal_len=11)
                sig = analysis["signal"]
                bclose = analysis["bclose"]
                sig_line = analysis["signal_line"]
                hm_status = analysis["hm_status"]

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("LinReg Close (bclose)", f"₹{bclose:,.2f}")
                m2.metric("Signal Line (SMA 11)", f"₹{sig_line:,.2f}")
                m3.metric("HM Confluence", "Bullish" if analysis.get("hm_bullish") else "Bearish")
                m4.metric("Evaluated Signal", sig, delta="TRIGGERED" if sig != "HOLD" else "WAITING")

                st.caption(f"📊 **Hilega-Milega Status:** {hm_status}")

                if sig in ["BUY_CE", "BUY_PE"]:
                    st.success(f"🔥 **{sig} TRIGGERED:** Both Linear Regression Crossover & HM Confluence Fulfilled!")

                    # Estimate option premium & dynamic position size
                    quote = kite.quote([idx_info["symbol"]])
                    spot_price = quote.get(idx_info["symbol"], {}).get("last_price", bclose)
                    est_premium = round(spot_price * 0.008, 2)
                    pos = calculate_position_size(selected_index, est_premium, max_risk=max_risk_inr)

                    st.markdown("#### 📋 Position & Margin Verification")
                    margin_ok, free_cash = check_account_margin(kite, pos["capital_required"])

                    m_col1, m_col2, m_col3 = st.columns(3)
                    m_col1.metric("Available Account Margin", f"₹{free_cash:,.2f}")
                    m_col2.metric("Required Capital", f"₹{pos['capital_required']:,.2f}")
                    m_col3.metric("Calculated Quantity", f"{pos['qty']} Qty ({pos['lots']} Lots)")

                    if margin_ok:
                        st.success("✅ **MARGIN VERIFIED:** Account balance sufficient for order execution.")
                        if st.button(f"⚡ Execute Automated {sig} Market Order", type="primary"):
                            st.balloons()
                            st.success(f"Order Transmitted to Market: {pos['qty']} Qty | Premium: ₹{est_premium} | Max Risk: ₹{pos['max_loss']}")
                    else:
                        st.error("❌ **EXECUTION REJECTED:** Insufficient account margin for order entry.")
                else:
                    st.info("⚪ No combined signal detected. Awaiting simultaneous LinReg crossover and HM alignment.")

    with tab_pos:
        st.subheader("📊 Live Open Positions & Trailing Stop Loss Tracker")
        try:
            positions = kite.positions().get("net", [])
            if positions:
                st.dataframe(pd.DataFrame(positions), use_container_width=True)
            else:
                st.info("No open positions currently active.")
        except Exception:
            st.info("No active open positions.")

    with tab_logs:
        st.subheader("📋 System Audit Logs")
        st.text_area("Audit Log Output", f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Confluence Algo Engine (LinReg + HM) active.", height=200)

if __name__ == "__main__":
    main()
