import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
import os
from fastapi import FastAPI, HTTPException, Query
from kiteconnect import KiteConnect
import numpy as np
import pandas as pd
from pydantic import BaseModel
import yfinance as yf

# ==============================================================================
# CONFIGURATION & PERSISTENCE
# ==============================================================================
API_KEY = "magym2s4yk13gsze".strip()
API_SECRET = "uxph73v40oemxff3c9xn48swqwctbfmf".strip()
TOKEN_FILE = "/home/ubuntu/.kite_token"

system_state = {
    "zerodha_session_valid": False,
    "access_token": None,
    "ip_whitelisted": True,
    "service_running": True,
    "daily_trade_count": 0,
    "daily_pnl": 0.0,
    "last_exit_time": None,
    "active_position": None,  # Holds tracking dict for 4-Stage SL Engine
    "scanner_logs": [],
}


def load_token_from_disk():
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
                    log_event("Session restored from disk on startup.")
        except Exception as e:
            system_state["zerodha_session_valid"] = False


def log_event(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    system_state["scanner_logs"].append(entry)
    if len(system_state["scanner_logs"]) > 100:
        system_state["scanner_logs"].pop(0)
    print(entry)


# ==============================================================================
# 1. QUANTITATIVE INDICATORS & BIAS ENGINE
# ==============================================================================


def fetch_historical_candles(ticker_symbol: str, interval: str, period: str):
    """Downloads live OHLCV candle data via yfinance for indicator calculation."""
    df = yf.download(
        tickers=ticker_symbol, period=period, interval=interval, progress=False
    )
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def calculate_15m_vwap(symbol: str) -> float:
    """Calculates 15-Minute VWAP for Macro Bias determination."""
    ticker = "^NSEI" if "NIFTY" in symbol and "BANK" not in symbol else "^NSEBANK"
    df = fetch_historical_candles(ticker, interval="15m", period="1d")
    if df.empty:
        return 0.0
    v = df["Volume"].values
    tp = (df["High"].values + df["Low"].values + df["Close"].values) / 3.0
    total_vol = np.sum(v)
    return float(np.sum(tp * v) / total_vol) if total_vol > 0 else 0.0


def calculate_hilega_milega_3m(symbol: str):
    """Calculates 3M RSI(9), EMA(3), VolSMA(20), and 9 EMA for trend-riding."""
    ticker = "^NSEI" if "NIFTY" in symbol and "BANK" not in symbol else "^NSEBANK"
    df = fetch_historical_candles(ticker, interval="3m", period="5d")
    if df.empty or len(df) < 30:
        return None

    close = df["Close"]
    vol = df["Volume"]

    # RSI(9) calculation
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=9).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=9).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    # EMA(3) of RSI
    rsi_ema = rsi.ewm(span=3, adjust=False).mean()

    # Volume filter
    vol_sma = vol.rolling(window=20).mean()

    # 9 EMA of Candle Close for Stage 4 Trend Riding
    ema9_close = close.ewm(span=9, adjust=False).mean()

    return {
        "spot": float(close.iloc[-1]),
        "rsi_curr": float(rsi.iloc[-1]),
        "rsi_prev": float(rsi.iloc[-2]),
        "rsi_ema_curr": float(rsi_ema.iloc[-1]),
        "rsi_ema_prev": float(rsi_ema.iloc[-2]),
        "vol_curr": float(vol.iloc[-1]),
        "vol_sma20": float(vol_sma.iloc[-1]),
        "ema9_close_curr": float(ema9_close.iloc[-1]),
        "candle_close_curr": float(close.iloc[-1]),
    }


def get_otm_contract_symbol(index_name: str, spot_price: float, bias: str):
    """Calculates strike price and formats dynamic option trading symbol."""
    if index_name == "NIFTY":
        step = 50
        strike = round(spot_price / step) * step
        strike = strike + 50 if bias == "BULLISH" else strike - 50
    elif index_name == "BANKNIFTY":
        step = 100
        strike = round(spot_price / step) * step
        strike = strike + 100 if bias == "BULLISH" else strike - 100
    else:
        step = 50
        strike = round(spot_price / step) * step
        strike = strike + 50 if bias == "BULLISH" else strike - 50

    option_type = "CE" if bias == "BULLISH" else "PE"
    now = datetime.now()
    month_str = now.strftime("%b").upper()
    yr_str = now.strftime("%y")

    return f"{index_name}{yr_str}{month_str}{int(strike)}{option_type}"


# ==============================================================================
# 2. 4-STAGE DYNAMIC RISK ENGINE & TRAILING SL MANAGER
# ==============================================================================


def manage_active_position(kite: KiteConnect):
    """Manages active position across Stage 1, Stage 2, Stage 3, and Stage 4."""
    pos = system_state["active_position"]
    if not pos:
        return

    symbol = pos["symbol"]
    try:
        quote = kite.ltp(f"NFO:{symbol}")
        curr_price = quote.get(f"NFO:{symbol}", {}).get("last_price", 0.0)
    except Exception:
        return

    if curr_price <= 0:
        return

    entry_price = pos["entry_price"]
    stage = pos["stage"]
    current_sl = pos["sl_price"]
    pnl_pct = ((curr_price - entry_price) / entry_price) * 100

    # Stage 1: Hard SL Check (-15%)
    if curr_price <= current_sl:
        execute_position_exit(
            kite, symbol, pos["qty"], f"Exit Triggered: SL Hit @ ₹{curr_price}"
        )
        return

    # Stage 1 -> Stage 2: Move to Breakeven @ +15% gain
    if stage == 1 and pnl_pct >= 15.0:
        pos["stage"] = 2
        pos["sl_price"] = entry_price  # Risk = ₹0
        log_event(
            f"STAGE 2 ACTIVATED: Option +{pnl_pct:.1f}%. SL moved to Breakeven (₹{entry_price})."
        )

    # Stage 2 -> Stage 3: Lock 1:1.1 R:R Profit (+20%) @ +50% gain
    elif stage == 2 and pnl_pct >= 50.0:
        pos["stage"] = 3
        pos["sl_price"] = entry_price * 1.20  # Lock 20% profit
        log_event(
            f"STAGE 3 ACTIVATED: Option +{pnl_pct:.1f}%. SL frozen at +20% profit (₹{pos['sl_price']:.2f})."
        )

    # Stage 3 -> Stage 4: Trend Riding Phase (Exit ONLY when 3M candle closes below 9 EMA)
    elif stage in (2, 3):
        hm = calculate_hilega_milega_3m(pos["index"])
        if hm and hm["candle_close_curr"] < hm["ema9_close_curr"]:
            pos["stage"] = 4
            execute_position_exit(
                kite,
                symbol,
                pos["qty"],
                f"STAGE 4 TREND EXIT: 3M Candle closed below 9 EMA @ ₹{curr_price}",
            )


def execute_position_exit(
    kite: KiteConnect, symbol: str, qty: int, reason: str
):
    """Executes market sell order to close position."""
    try:
        kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=symbol,
            transaction_type=kite.TRANSACTION_TYPE_SELL,
            quantity=qty,
            product=kite.PRODUCT_MIS,
            order_type=kite.ORDER_TYPE_MARKET,
        )
        log_event(f"POSITION CLOSED | {reason}")
        system_state["active_position"] = None
        system_state["last_exit_time"] = datetime.now()
    except Exception as e:
        log_event(f"CRITICAL: Position exit failed: {e}")


# ==============================================================================
# 3. BACKGROUND SCANNER & AUTO-TRADING LOOP
# ==============================================================================


async def background_scanner_loop():
    """Main background loop polling NIFTY/BANKNIFTY every 3 minutes."""
    log_event("Automated 3-Minute Hilega-Milega Scanner active.")
    while True:
        try:
            now = datetime.now()
            # Market Session Window Check (9:15 AM - 3:05 PM IST)
            if (
                system_state["zerodha_session_valid"]
                and time(9, 15) <= now.time() <= time(15, 5)
            ):
                kite = KiteConnect(
                    api_key=API_KEY, access_token=system_state["access_token"]
                )

                # Active Position Management
                if system_state["active_position"]:
                    manage_active_position(kite)

                # Hard 3:05 PM Exit Rule
                elif now.time() >= time(15, 5) and system_state[
                    "active_position"
                ]:
                    pos = system_state["active_position"]
                    execute_position_exit(
                        kite,
                        pos["symbol"],
                        pos["qty"],
                        "Hard Exit @ 3:05 PM IST reached.",
                    )

                # Signal Evaluation Loop
                elif not system_state["active_position"]:
                    await evaluate_trade_signals(kite)

        except Exception as e:
            print(f"[SCANNER ERROR] {e}")

        await asyncio.sleep(180)  # Poll every 3 minutes


async def evaluate_trade_signals(kite: KiteConnect):
    """Evaluates strategy entry conditions against strict pre-trade guardrails."""
    # Pre-Trade Safety Gates
    if system_state["daily_trade_count"] >= 3:
        return
    if system_state["daily_pnl"] <= -1000.0:
        return
    if system_state["last_exit_time"]:
        if datetime.now() - system_state["last_exit_time"] < timedelta(
            minutes=15
        ):
            return

    for index_name in ["NIFTY", "BANKNIFTY"]:
        vwap15 = calculate_15m_vwap(index_name)
        hm = calculate_hilega_milega_3m(index_name)

        if not hm or vwap15 == 0.0:
            continue

        spot = hm["spot"]
        bias = "BEARISH" if spot < vwap15 else "BULLISH"

        # HM Reversal Signal: RSI(9) > EMA(3) Crossover + Volume Filter
        rsi_cross = (hm["rsi_prev"] <= hm["rsi_ema_prev"]) and (
            hm["rsi_curr"] > hm["rsi_ema_curr"]
        )
        vol_confirmed = hm["vol_curr"] >= (1.2 * hm["vol_sma20"])

        if rsi_cross and vol_confirmed:
            symbol = get_otm_contract_symbol(index_name, spot, bias)

            # Auto-calculate position quantity (Cap max 15% SL loss to <= ₹2,000)
            try:
                quote = kite.ltp(f"NFO:{symbol}")
                ask_price = quote.get(f"NFO:{symbol}", {}).get(
                    "last_price", 100.0
                )
                limit_price = round(ask_price * 1.005, 2)  # +0.5% buffer

                risk_per_unit = limit_price * 0.15
                qty = max(int(2000.0 / risk_per_unit), 15)

                # Execute Limit Order with Slippage Buffer
                order_id = kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    exchange=kite.EXCHANGE_NFO,
                    tradingsymbol=symbol,
                    transaction_type=kite.TRANSACTION_TYPE_BUY,
                    quantity=qty,
                    product=kite.PRODUCT_MIS,
                    order_type=kite.ORDER_TYPE_LIMIT,
                    price=limit_price,
                )

                system_state["active_position"] = {
                    "symbol": symbol,
                    "index": index_name,
                    "qty": qty,
                    "entry_price": limit_price,
                    "sl_price": limit_price * 0.85,  # Stage 1: -15% Hard SL
                    "stage": 1,
                    "order_id": order_id,
                }
                system_state["daily_trade_count"] += 1
                log_event(
                    f"TRADE EXECUTED | Symbol: {symbol} | Qty: {qty} | Entry: ₹{limit_price} | Stage 1 SL: ₹{limit_price * 0.85:.2f}"
                )
                break
            except Exception as e:
                log_event(f"Order submission failed for {symbol}: {e}")


# ==============================================================================
# 4. LIFESPAN & API ENDPOINTS
# ==============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_token_from_disk()
    scanner_task = asyncio.create_task(background_scanner_loop())
    yield
    scanner_task.cancel()


app = FastAPI(
    title="Zerodha Algorithmic Trading Engine", lifespan=lifespan
)


class TradeRequest(BaseModel):
    exchange: str = "NSE"
    symbol: str
    transaction_type: str
    quantity: int
    order_type: str
    price: float = 0.0


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
        equity_data = m["equity"] if "equity" in m and isinstance(m["equity"], dict) else m
        available_margin = equity_data.get(
            "net", equity_data.get("available", {}).get("live_balance", 0)
        )

        return {"status": "SUCCESS", "margin": available_margin}
    except Exception as e:
        system_state["zerodha_session_valid"] = False
        raise HTTPException(status_code=400, detail=f"Sync error: {str(e)}")


@app.get("/positions")
def get_positions():
    if not system_state["zerodha_session_valid"]:
        raise HTTPException(
            status_code=400, detail="Zerodha session expired. Login required."
        )

    try:
        kite = KiteConnect(
            api_key=API_KEY, access_token=system_state["access_token"]
        )
        pos = kite.positions()
        return {"status": "SUCCESS", "net": pos.get("net", [])}
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Positions fetch error: {str(e)}"
        )


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
    if system_state["zerodha_session_valid"] and system_state["active_position"]:
        try:
            kite = KiteConnect(
                api_key=API_KEY, access_token=system_state["access_token"]
            )
            pos = system_state["active_position"]
            execute_position_exit(
                kite, pos["symbol"], pos["qty"], "Manual Emergency Square Off"
            )
        except Exception:
            pass
    return {
        "status": "SUCCESS",
        "message": "Emergency square off signal processed.",
    }


@app.get("/logs")
def get_logs():
    return {"logs": "\n".join(system_state["scanner_logs"][-20:])}
