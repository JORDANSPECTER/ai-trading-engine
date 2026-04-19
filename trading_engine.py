import time
import requests
import pandas as pd
from datetime import datetime, timedelta

# ======================================================
# GLOBAL STATE
# ======================================================
SESSION_STATE = {
    "trading_locked": False,
    "lock_reason": None,
    "aes_stage": "NORMAL",
    "realized_pnl": 0.0,
    "consecutive_losses": 0,
    "open_trades": [],
    "manual_override": False,
    "manual_override_reason": None,
    "pending_orders": [],
    "equity_curve": [],
    "peak_equity": 0.0,
    "current_drawdown": 0.0,
    "drawdown_state": "NORMAL",
    "recovery_mode": False,
    "recovery_trades_taken": 0,
    "api_locked_until": None,
    "confidence_history": [],
}

HEALTH_STATE = {
    "last_heartbeat": None,
    "last_heartbeat_ok": True,
    "last_latency_ms": None,
    "consecutive_heartbeat_failures": 0,
    "consecutive_latency_spikes": 0,
    "auto_kill_triggered": False,
    "auto_kill_reason": None,
}

# ======================================================
# CONFIG
# ======================================================
API_KEY = "9693e9006e454766ab2a0bfc5527d263"
print("API KEY LOADED:", API_KEY[:6], "...")
TELEGRAM_BOT_TOKEN = "8636128819:AAFT9ibrwatP7O6wsTQi7wJVeQcuNqMLv4I"
TELEGRAM_CHAT_ID = "8661143355"

RISK_POLICY = {
    "max_daily_realized_loss": 250.0,
    "max_realized_loss_per_trade": 100.0,
    "max_consecutive_losses": 3,
    "cooldown_minutes_after_loss": 15,
    "max_open_trades": 1,
    "min_risk_dollars": 25.0,
    "base_risk_dollars": 100.0,
    "block_if_chasing": True,
    "block_if_not_confirmed": True,
    "block_if_confidence_below": 65,
    "max_unrealized_drawdown_per_trade_pct": 0.25,
    "stop_buffer_points": 0.05,
}

DRAWDOWN_POLICY = {
    "warning_drawdown_dollars": 150.0,
    "shutdown_drawdown_dollars": 250.0,
    "recovery_mode_risk_multiplier": 0.5,
    "recovery_mode_max_trades": 2,
}

AUTO_KILL_POLICY = {
    "heartbeat_interval_seconds": 60,
    "max_consecutive_heartbeat_failures": 3,
    "latency_warning_ms": 1500,
    "latency_kill_ms": 3000,
    "max_consecutive_latency_spikes": 3,
}

LAST_UPDATE_ID = None

# ======================================================
# TELEGRAM
# ======================================================
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    response = requests.post(url, json=payload, timeout=15)
    return response

def activate_manual_override(reason="TELEGRAM_KILL_COMMAND"):
    SESSION_STATE["manual_override"] = True
    SESSION_STATE["manual_override_reason"] = reason
    SESSION_STATE["trading_locked"] = True
    SESSION_STATE["lock_reason"] = reason
    print(f"🚫 Manual override active: {reason}")

def deactivate_manual_override():
    SESSION_STATE["manual_override"] = False
    SESSION_STATE["manual_override_reason"] = None
    SESSION_STATE["trading_locked"] = False
    SESSION_STATE["lock_reason"] = None
    print("✅ Manual override removed")

def safe_flatten_all_positions():
    closed_ids = []
    for trade in SESSION_STATE["open_trades"][:]:
        trade["status"] = "CLOSED"
        closed_ids.append(trade.get("trade_id"))
    SESSION_STATE["open_trades"] = []
    return closed_ids

def safe_get_risk_status():
    return {
        "status": "LOCKED" if SESSION_STATE["trading_locked"] else "NORMAL",
        "realized_pnl": SESSION_STATE["realized_pnl"],
        "consecutive_losses": SESSION_STATE["consecutive_losses"],
        "open_trades": len(SESSION_STATE["open_trades"]),
        "peak_equity": SESSION_STATE["peak_equity"],
        "current_drawdown": SESSION_STATE["current_drawdown"],
        "drawdown_state": SESSION_STATE["drawdown_state"],
        "recovery_mode": SESSION_STATE["recovery_mode"],
        "recovery_trades_taken": SESSION_STATE["recovery_trades_taken"],
    }

def safe_get_drawdown_status():
    return {
        "peak_equity": SESSION_STATE["peak_equity"],
        "current_drawdown": SESSION_STATE["current_drawdown"],
        "drawdown_state": SESSION_STATE["drawdown_state"],
        "recovery_mode": SESSION_STATE["recovery_mode"],
        "recovery_trades_taken": SESSION_STATE["recovery_trades_taken"],
    }

def handle_telegram_command(text):
    text = (text or "").strip().lower()

    if text == "/kill":
        activate_manual_override("TELEGRAM_KILL_COMMAND")
        closed = safe_flatten_all_positions()
        SESSION_STATE["aes_stage"] = "HARD_STOP"
        SESSION_STATE["trading_locked"] = True
        SESSION_STATE["lock_reason"] = "TELEGRAM_KILL_SWITCH"
        send_to_telegram(
            f"🚨 SYSTEM KILL SWITCH ACTIVATED\n\nTrading LOCKED\nAES Stage: HARD_STOP\n\nClosed Trades: {closed if closed else 'None'}\n\nManual review required."
        )

    elif text == "/status":
        risk = safe_get_risk_status()
        dd = safe_get_drawdown_status()
        msg = (
            "📊 SYSTEM STATUS\n\n"
            f"Risk State: {risk.get('status')}\n"
            f"AES Stage: {SESSION_STATE.get('aes_stage')}\n"
            f"PnL: {risk.get('realized_pnl')}\n"
            f"Open Trades: {risk.get('open_trades')}\n"
            f"Drawdown: {dd.get('current_drawdown')}\n"
        )
        send_to_telegram(msg)

    elif text == "/unlock":
        deactivate_manual_override()
        send_to_telegram("✅ SYSTEM UNLOCKED\nTrading resumed.")

    elif text == "/flatten":
        closed = safe_flatten_all_positions()
        send_to_telegram(f"📉 ALL POSITIONS CLOSED\nTrades: {closed}")

    else:
        send_to_telegram("❓ Unknown command\n\n/status\n/kill\n/unlock\n/flatten")

def check_telegram_commands():
    global LAST_UPDATE_ID

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {}
    if LAST_UPDATE_ID is not None:
        params["offset"] = LAST_UPDATE_ID + 1

    response = requests.get(url, params=params, timeout=15)
    data = response.json()

    if not data.get("ok"):
        return

    for update in data.get("result", []):
        LAST_UPDATE_ID = update["update_id"]
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = str(message.get("chat", {}).get("id", ""))

        if chat_id != str(TELEGRAM_CHAT_ID):
            continue

        print(f"📩 Telegram command received: {text}")
        handle_telegram_command(text)

# ======================================================
# MARKET DATA
# ======================================================
def td_get_candles(symbol="QQQ", interval="1min", outputsize=5):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": API_KEY
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    if "values" not in data:
        raise ValueError(f"Twelve Data error for {symbol}: {data}")

    cleaned = []
    for c in data["values"]:
        cleaned.append({
            "time": c["datetime"],
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
            "volume": float(c.get("volume", 0) or 0),
        })

    return cleaned

# ======================================================
# HEALTH CHECK
# ======================================================
def get_live_latency_snapshot(symbol="QQQ"):
    start = time.time()
    candles = td_get_candles(symbol)
    last_price = candles[0]["close"]
    latency_ms = round((time.time() - start) * 1000, 2)

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "last_price": last_price,
        "latency_ms": latency_ms,
    }

def run_health_check(symbol="QQQ"):
    snap = get_live_latency_snapshot(symbol)

    HEALTH_STATE["last_heartbeat"] = snap["timestamp"]
    HEALTH_STATE["last_heartbeat_ok"] = True
    HEALTH_STATE["last_latency_ms"] = snap["latency_ms"]
    HEALTH_STATE["consecutive_heartbeat_failures"] = 0

    if snap["latency_ms"] >= AUTO_KILL_POLICY["latency_kill_ms"]:
        HEALTH_STATE["consecutive_latency_spikes"] += 1
    else:
        HEALTH_STATE["consecutive_latency_spikes"] = 0

    print(
        f"[{snap['timestamp']}] Heartbeat OK | "
        f"{symbol}={snap['last_price']} | "
        f"Latency={snap['latency_ms']}ms | "
        f"HB Failures={HEALTH_STATE['consecutive_heartbeat_failures']} | "
        f"Latency Spikes={HEALTH_STATE['consecutive_latency_spikes']}"
    )

# ======================================================
# YOUR REAL ENGINE HOOK
# Replace this function body with your real notebook logic
# ======================================================
def build_risk_first_trade_plan(symbol="QQQ"):
    candles = td_get_candles(symbol)

    data = {
        "symbol": symbol,
        "grade": "A",
        "trade_allowed": not SESSION_STATE["trading_locked"],
        "confirmed": True,
        "confidence_score": 90,
        "confidence_label": "HIGH",
    }

    setup = {
        "setup": "BREAK_AND_HOLD_CALL",
        "bias": "CALL",
    }

    return data, setup, candles