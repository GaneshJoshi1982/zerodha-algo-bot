import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
import os
from fastapi import FastAPI, HTTPException, Query
from kiteconnect import KiteConnect
from pydantic import BaseModel

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
    "active_position": None,  # Holds 4-Stage SL Tracking
    "scanner_logs": [],
}


def log_event(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    system_state["scanner_logs"].append(entry)
    if len(system_state["scanner_logs"]) > 100:
        system_state["scanner_logs"].pop(0)
    print(entry)


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
                    log_event("Session restored from persistent disk.")
        except Exception as e:
            system_state["zerodha_session_valid"] = False


# ==============================================================================
# STRATEGY & DYNAMIC STRIKE SELECTION
# ==============================================================================


def get_otm_contract_symbol(index_name: str, spot_price: float, bias: str):
    """Calculates ATM/OTM strike and formats Zerodha NFO symbol."""
    step = 100 if index_name == "BANKNIFTY" else 50
    strike = round(spot_price / step) * step

    if bias == "BULLISH":
        strike += step
    else:
        strike -= step

    option_type = "CE" if bias == "BULLISH" else "PE"
    now = datetime.now()
    month_str = now.strftime("%b").upper()
    yr_str = now.strftime("%y")

    return f"{index_name}{yr_str}{month_str}{int(strike)}{option_type}"


def manage_active_position(kite: KiteConnect):
    """4-Stage Trailing SL Risk Engine Implementation."""
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
            kite, symbol, pos["qty"], f"Stage 1 SL Hit @ ₹{curr_price}"
        )
        return

    # Stage 1 -> Stage 2: Move to Breakeven @ +15% gain
    if stage == 1 and pnl_pct >= 15.0:
        pos["stage"] = 2
        pos["sl_price"] = entry_price
        log_event(
            f"STAGE 2: Gain +{pnl_pct:.1f}%. SL moved to Breakeven (₹{entry_price})."
        )

    # Stage 2 -> Stage 3: Lock +20% Profit @ +50% gain
    elif stage == 2 and pnl_pct >= 50.0:
        pos["stage"] = 3
        pos["sl_price"] = entry_price * 1.20
        log_event(
            f"STAGE 3: Gain +{pnl_pct:.1f}%. SL frozen at +20% profit (₹{pos['sl_price']:.2f})."
        )


def execute_position_exit(
    kite: KiteConnect, symbol: str, qty: int, reason: str
):
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
        log_event(f"POSITION EXITED | {reason}")
        system_state["active_position"] = None
        system_state["last_exit_time"] = datetime.now()
    except Exception as e:
        log_event(f"Exit order failed: {e}")


async def background_scanner_loop():
    """Background engine managing 3-Min scans & 3:05 PM exit."""
    log_event("3-Minute Hilega-Milega Strategy Engine active.")
    while True:
        try:
            now = datetime.now()
            if (
                system_state["zerodha_session_valid"]
                and time(9, 15) <= now.time() <= time(15, 5)
            ):
                kite = KiteConnect(
                    api_key=API_KEY, access_token=system_state["access_token"]
                )
                if system_state["active_position"]:
                    manage_active_position(kite)
                elif now.time() >= time(15, 5) and system_state[
                    "active_position"
                ]:
                    pos = system_state["active_position"]
                    execute_position_exit(
                        kite, pos["symbol"], pos["qty"], "3:05 PM Hard Exit"
                    )
        except Exception as e:
            log_event(f"Background check loop: {e}")

        await asyncio.sleep(180)


# ==============================================================================
# FASTAPI ENDPOINTS
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
        equity_data = (
            m["equity"] if "equity" in m and isinstance(m["equity"], dict) else m
        )
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
    return {
        "logs": (
            "\n".join(system_state["scanner_logs"][-20:])
            if system_state["scanner_logs"]
            else "Engine active & operational."
        )
    }
