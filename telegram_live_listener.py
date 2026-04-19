import os
import json
import time
import traceback
from datetime import datetime, timezone

import requests

# =========================================================
# CONFIG
# =========================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

STATE_FILE = "control_state.json"
OFFSET_FILE = "telegram_offset.txt"
STOP_FILE = "stop_bot.txt"
LOCK_FILE = "bot.lock"

TRADE_STATUS_FILE = "trade_status.json"
PNL_SNAPSHOT_FILE = "pnl_snapshot.json"

DEBUG_MODE = os.getenv("DEBUG_MODE", "true").strip().lower() == "true"
BOT_NAME = os.getenv("BOT_NAME", "Heartbeat Live Control Center").strip()
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "2"))

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

START_TIME_UTC = datetime.now(timezone.utc)

# =========================================================
# DEFAULT STATE
# =========================================================
DEFAULT_STATE = {
    "bot_paused": False,
    "kill_switch": False,
    "flatten_requested": False,
    "armed": True,
    "mode": "paper",
    "last_command": "none",
    "last_command_time_utc": None,
    "last_command_from": None,
    "notes": "initialized"
}

DEFAULT_TRADE_STATUS = {
    "symbol": "n/a",
    "direction": "n/a",
    "entry_price": "n/a",
    "contracts": "n/a",
    "status": "n/a",
    "last_trade_time_utc": "n/a"
}

DEFAULT_PNL_SNAPSHOT = {
    "day_pnl": "n/a",
    "open_pnl": "n/a",
    "realized_pnl": "n/a",
    "unrealized_pnl": "n/a",
    "account_value": "n/a",
    "updated_at_utc": "n/a"
}

# =========================================================
# FILE HELPERS
# =========================================================
def load_json_file(path, default_value):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed loading JSON from {path}: {e}")
    return default_value.copy() if isinstance(default_value, dict) else default_value

def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_offset():
    try:
        if os.path.exists(OFFSET_FILE):
            with open(OFFSET_FILE, "r", encoding="utf-8") as f:
                value = f.read().strip()
                return int(value) if value else 0
    except Exception as e:
        print(f"[WARN] Failed loading offset: {e}")
    return 0

def save_offset(offset_value):
    with open(OFFSET_FILE, "w", encoding="utf-8") as f:
        f.write(str(offset_value))

def load_state():
    state = load_json_file(STATE_FILE, DEFAULT_STATE)
    for key, value in DEFAULT_STATE.items():
        if key not in state:
            state[key] = value
    return state

def save_state(state):
    save_json_file(STATE_FILE, state)

def load_trade_status():
    data = load_json_file(TRADE_STATUS_FILE, DEFAULT_TRADE_STATUS)
    for key, value in DEFAULT_TRADE_STATUS.items():
        if key not in data:
            data[key] = value
    return data

def load_pnl_snapshot():
    data = load_json_file(PNL_SNAPSHOT_FILE, DEFAULT_PNL_SNAPSHOT)
    for key, value in DEFAULT_PNL_SNAPSHOT.items():
        if key not in data:
            data[key] = value
    return data

def create_stop_file():
    with open(STOP_FILE, "w", encoding="utf-8") as f:
        f.write("stop")

def remove_stop_file():
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)

def remove_lock_file():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception as e:
            print(f"[WARN] Failed removing lock file: {e}")

# =========================================================
# GENERAL HELPERS
# =========================================================
def utc_now_string():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def format_uptime():
    delta = datetime.now(timezone.utc) - START_TIME_UTC
    total_seconds = int(delta.total_seconds())

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"

def pretty_status(state, trade_status, pnl_snapshot):
    return (
        f"📡 {BOT_NAME}\n"
        f"• Mode: {state.get('mode', 'paper')}\n"
        f"• Armed: {state.get('armed', True)}\n"
        f"• Paused: {state.get('bot_paused', False)}\n"
        f"• Kill Switch: {state.get('kill_switch', False)}\n"
        f"• Flatten Requested: {state.get('flatten_requested', False)}\n"
        f"• Uptime: {format_uptime()}\n"
        f"• Last Command: {state.get('last_command', 'none')}\n"
        f"• Last Command Time: {state.get('last_command_time_utc', 'n/a')}\n"
        f"• Last Command From: {state.get('last_command_from', 'n/a')}\n"
        f"\n"
        f"📈 Last Trade\n"
        f"• Symbol: {trade_status.get('symbol', 'n/a')}\n"
        f"• Direction: {trade_status.get('direction', 'n/a')}\n"
        f"• Entry: {trade_status.get('entry_price', 'n/a')}\n"
        f"• Contracts: {trade_status.get('contracts', 'n/a')}\n"
        f"• Status: {trade_status.get('status', 'n/a')}\n"
        f"• Last Trade Time: {trade_status.get('last_trade_time_utc', 'n/a')}\n"
        f"\n"
        f"💰 PnL Snapshot\n"
        f"• Day PnL: {pnl_snapshot.get('day_pnl', 'n/a')}\n"
        f"• Open PnL: {pnl_snapshot.get('open_pnl', 'n/a')}\n"
        f"• Realized PnL: {pnl_snapshot.get('realized_pnl', 'n/a')}\n"
        f"• Unrealized PnL: {pnl_snapshot.get('unrealized_pnl', 'n/a')}\n"
        f"• Account Value: {pnl_snapshot.get('account_value', 'n/a')}\n"
        f"• Snapshot Time: {pnl_snapshot.get('updated_at_utc', 'n/a')}\n"
        f"\n"
        f"• Notes: {state.get('notes', '')}"
    )

def update_state_command(state, command_name, user_label, note):
    state["last_command"] = command_name
    state["last_command_time_utc"] = utc_now_string()
    state["last_command_from"] = user_label
    state["notes"] = note
    save_state(state)

def normalize_text(text):
    return (text or "").strip()

def extract_user_label(message):
    chat = message.get("chat", {})
    from_user = message.get("from", {})

    username = from_user.get("username")
    first_name = from_user.get("first_name", "")
    last_name = from_user.get("last_name", "")
    chat_id = str(chat.get("id", ""))

    if username:
        return f"@{username} ({chat_id})"

    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return f"{full_name} ({chat_id})"

    return f"unknown ({chat_id})"

def is_authorized_chat(message):
    if not TELEGRAM_CHAT_ID:
        return True
    incoming_chat_id = str(message.get("chat", {}).get("id", ""))
    return incoming_chat_id == str(TELEGRAM_CHAT_ID)

# =========================================================
# TELEGRAM API
# =========================================================
def telegram_request(method, payload=None, timeout=30):
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing.")

    url = f"{TELEGRAM_API_BASE}/{method}"
    response = requests.post(url, json=payload or {}, timeout=timeout)
    response.raise_for_status()

    data = response.json()
    if not data.get("ok", False):
        raise RuntimeError(f"Telegram API error on {method}: {data}")

    return data

def send_telegram_message(text, chat_id=None):
    target_chat_id = str(chat_id or TELEGRAM_CHAT_ID).strip()
    if not target_chat_id:
        print("[WARN] TELEGRAM_CHAT_ID missing, cannot send message")
        return None

    payload = {
        "chat_id": target_chat_id,
        "text": text
    }
    return telegram_request("sendMessage", payload=payload, timeout=30)

def get_telegram_updates(offset=0, timeout=20):
    payload = {
        "offset": offset,
        "timeout": timeout,
        "allowed_updates": ["message"]
    }
    return telegram_request("getUpdates", payload=payload, timeout=timeout + 10)

# =========================================================
# COMMANDS
# =========================================================
def command_menu_text():
    return (
        f"🤖 {BOT_NAME}\n\n"
        "Available commands:\n"
        "/start - Open command center\n"
        "/help - Show commands\n"
        "/ping - Quick connectivity test\n"
        "/heartbeat - Quick alive check\n"
        "/status - Current bot state\n"
        "/pause - Pause bot actions\n"
        "/resume - Resume bot actions\n"
        "/kill - Turn ON kill switch\n"
        "/unkill - Turn OFF kill switch\n"
        "/flatten - Request flatten\n"
        "/clearflatten - Clear flatten request\n"
        "/arm - Allow engine to operate\n"
        "/disarm - Disarm execution engine\n"
        "/mode paper - Set paper mode\n"
        "/mode live - Set live mode\n"
        "/shutdown - Stop bot cleanly\n"
        "/debugstate - Dump raw state"
    )

def process_command(text, state, user_label):
    cmd = normalize_text(text)
    cmd_lower = cmd.lower()

    if cmd_lower == "/start":
        update_state_command(state, "/start", user_label, "command center opened")
        return command_menu_text(), False

    if cmd_lower == "/help":
        update_state_command(state, "/help", user_label, "help requested")
        return command_menu_text(), False

    if cmd_lower == "/ping":
        update_state_command(state, "/ping", user_label, "ping ok")
        return f"🏓 Pong\n{utc_now_string()}", False

    if cmd_lower == "/heartbeat":
        update_state_command(state, "/heartbeat", user_label, "heartbeat checked")
        return (
            f"💓 {BOT_NAME} is alive\n"
            f"Time: {utc_now_string()}\n"
            f"Uptime: {format_uptime()}\n"
            f"Mode: {state.get('mode', 'paper')}\n"
            f"Armed: {state.get('armed', True)}\n"
            f"Paused: {state.get('bot_paused', False)}\n"
            f"Kill: {state.get('kill_switch', False)}"
        ), False

    if cmd_lower == "/status":
        update_state_command(state, "/status", user_label, "status checked")
        trade_status = load_trade_status()
        pnl_snapshot = load_pnl_snapshot()
        return pretty_status(state, trade_status, pnl_snapshot), False

    if cmd_lower == "/pause":
        state["bot_paused"] = True
        update_state_command(state, "/pause", user_label, "bot paused")
        return "⏸ Bot paused.", False

    if cmd_lower == "/resume":
        state["bot_paused"] = False
        update_state_command(state, "/resume", user_label, "bot resumed")
        return "▶️ Bot resumed.", False

    if cmd_lower == "/kill":
        state["kill_switch"] = True
        update_state_command(state, "/kill", user_label, "kill switch turned ON")
        return "🛑 Kill switch is now ON.", False

    if cmd_lower == "/unkill":
        state["kill_switch"] = False
        update_state_command(state, "/unkill", user_label, "kill switch turned OFF")
        return "✅ Kill switch is now OFF.", False

    if cmd_lower == "/flatten":
        state["flatten_requested"] = True
        update_state_command(state, "/flatten", user_label, "flatten requested")
        return "📉 Flatten request has been set to TRUE.", False

    if cmd_lower == "/clearflatten":
        state["flatten_requested"] = False
        update_state_command(state, "/clearflatten", user_label, "flatten request cleared")
        return "✅ Flatten request cleared.", False

    if cmd_lower == "/arm":
        state["armed"] = True
        update_state_command(state, "/arm", user_label, "engine armed")
        return "🟢 Engine armed.", False

    if cmd_lower == "/disarm":
        state["armed"] = False
        update_state_command(state, "/disarm", user_label, "engine disarmed")
        return "🔒 Engine disarmed.", False

    if cmd_lower == "/mode paper":
        state["mode"] = "paper"
        update_state_command(state, "/mode paper", user_label, "mode set to paper")
        return "🧪 Mode set to PAPER.", False

    if cmd_lower == "/mode live":
        state["mode"] = "live"
        update_state_command(state, "/mode live", user_label, "mode set to live")
        return "💸 Mode set to LIVE.", False

    if cmd_lower == "/shutdown":
        update_state_command(state, "/shutdown", user_label, "shutdown requested")
        create_stop_file()
        return "🛑 Shutdown requested. Bot is stopping cleanly.", True

    if cmd_lower == "/debugstate":
        update_state_command(state, "/debugstate", user_label, "raw state requested")
        return "Raw state:\n" + json.dumps(state, indent=2), False

    update_state_command(state, cmd, user_label, "unknown command received")
    return f"❓ Unknown command: {cmd}\n\nUse /help to see available commands.", False

# =========================================================
# TELEGRAM UPDATE PROCESSOR
# =========================================================
def process_updates_once():
    state = load_state()
    last_offset = load_offset()

    if DEBUG_MODE:
        print(f"[DEBUG] Polling Telegram with offset={last_offset}")

    updates_data = get_telegram_updates(offset=last_offset, timeout=20)
    results = updates_data.get("result", [])

    if DEBUG_MODE and results:
        print(f"[DEBUG] Received {len(results)} update(s)")

    for item in results:
        update_id = item.get("update_id")
        message = item.get("message", {})
        text = normalize_text(message.get("text", ""))

        if update_id is not None:
            save_offset(update_id + 1)

        if not message:
            continue

        incoming_chat_id = str(message.get("chat", {}).get("id", ""))
        user_label = extract_user_label(message)

        if DEBUG_MODE:
            print(f"[DEBUG] update_id={update_id} chat_id={incoming_chat_id} text={text!r}")

        if not is_authorized_chat(message):
            try:
                send_telegram_message(
                    "⛔ This chat is not authorized for command control.",
                    chat_id=incoming_chat_id
                )
            except Exception as e:
                print(f"[WARN] Failed unauthorized notice: {e}")
            continue

        if not text:
            continue

        if not text.startswith("/"):
            try:
                send_telegram_message(
                    f"📝 Received: {text}\n\nSend /help for available commands.",
                    chat_id=incoming_chat_id
                )
            except Exception as e:
                print(f"[WARN] Failed replying to text: {e}")
            continue

        try:
            if DEBUG_MODE:
                send_telegram_message(
                    f"🛠 Debug:\nReceived command: {text}",
                    chat_id=incoming_chat_id
                )

            state = load_state()
            reply, should_shutdown = process_command(text, state, user_label)
            send_telegram_message(reply, chat_id=incoming_chat_id)

            if DEBUG_MODE:
                print(f"[DEBUG] Command handled successfully: {text}")

            if should_shutdown:
                return "shutdown"

        except Exception as command_error:
            print("[ERROR] Command processing failed")
            print(traceback.format_exc())
            try:
                send_telegram_message(
                    f"❌ Command failed: {text}\nError: {str(command_error)}",
                    chat_id=incoming_chat_id
                )
            except Exception:
                print("[ERROR] Failed to send Telegram error message")

    return None

# =========================================================
# BOOTSTRAP
# =========================================================
def ensure_files_exist():
    if not os.path.exists(STATE_FILE):
        save_state(DEFAULT_STATE)
    if not os.path.exists(OFFSET_FILE):
        save_offset(0)

def startup_message():
    state = load_state()
    trade_status = load_trade_status()
    pnl_snapshot = load_pnl_snapshot()

    return (
        f"🚀 {BOT_NAME} ONLINE\n"
        f"Time: {utc_now_string()}\n"
        f"Mode: {state.get('mode')}\n"
        f"Armed: {state.get('armed')}\n"
        f"Paused: {state.get('bot_paused')}\n"
        f"Kill: {state.get('kill_switch')}\n"
        f"Flatten: {state.get('flatten_requested')}\n"
        f"Uptime: {format_uptime()}\n"
        f"Last Trade: {trade_status.get('symbol', 'n/a')} / {trade_status.get('direction', 'n/a')} / {trade_status.get('status', 'n/a')}\n"
        f"Day PnL: {pnl_snapshot.get('day_pnl', 'n/a')}"
    )

# =========================================================
# MAIN LIVE LOOP
# =========================================================
if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing.")

    ensure_files_exist()

    print("[BOOT] Starting live Telegram listener...")
    print(f"[BOOT] Poll interval: {POLL_INTERVAL_SECONDS}s")
    print(f"[BOOT] Debug mode: {DEBUG_MODE}")

    try:
        send_telegram_message(startup_message())
    except Exception as e:
        print(f"[WARN] Could not send startup message: {e}")

    while True:
        try:
            if os.path.exists(STOP_FILE):
                print("[STOP] stop_bot.txt detected. Exiting listener.")
                remove_lock_file()
                break

            result = process_updates_once()
            if result == "shutdown":
                print("[STOP] Shutdown command received. Exiting listener.")
                remove_lock_file()
                break

            time.sleep(POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("[STOP] Listener stopped by user.")
            try:
                send_telegram_message(f"🛑 {BOT_NAME} stopped manually.\n{utc_now_string()}")
            except Exception:
                pass
            remove_lock_file()
            break

        except Exception as e:
            err_text = str(e)
            print("[FATAL LOOP ERROR]")
            print(err_text)
            print(traceback.format_exc())

            if "409" in err_text and "Conflict" in err_text:
                print("[STOP] Another Telegram listener is already running. Exiting.")
                remove_lock_file()
                break

            try:
                send_telegram_message(
                    f"🚨 {BOT_NAME} loop error\n{err_text}\nRetrying in 5 seconds."
                )
            except Exception:
                print("[WARN] Failed to send loop error alert")

            time.sleep(5)