# =========================================
# MAIN.PY
# LIVE LOOP + TELEGRAM + DISCORD + ALPACA
# =========================================

import os
import time
import traceback
import requests

from ai_system import (
    build_market_context,
    attach_elite_sources_to_context,
    attach_fusion_to_context,
    make_hybrid_decision,
    print_plan,
    FOCUS_SYMBOLS,
    log,
)

from core.alpaca_execution import execute_plan


# =========================================
# CONFIG
# =========================================

SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "20"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Optional Discord webhook
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

LAST_STATUS = None
STARTUP_ALERT_SENT = False


# =========================================
# TELEGRAM
# =========================================

def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("[TELEGRAM] Missing token or chat ID")
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        log("[TELEGRAM] Alert sent")
        return True
    except Exception as e:
        log(f"[TELEGRAM ERROR] {e}")
        return False


# =========================================
# DISCORD
# =========================================

def send_discord(message: str) -> bool:
    if not DISCORD_WEBHOOK_URL:
        log("[DISCORD] Missing DISCORD_WEBHOOK_URL")
        return False

    try:
        payload = {"content": message}
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        response.raise_for_status()
        log("[DISCORD] Alert sent")
        return True
    except Exception as e:
        log(f"[DISCORD ERROR] {e}")
        return False


# =========================================
# HELPERS
# =========================================

def extract_setup(plan) -> str:
    for reason in getattr(plan, "reasons", []):
        if "Setup:" in reason:
            return reason.replace("Setup:", "").strip()
    return ""


def build_status_message(context, plan) -> str:
    setup = extract_setup(plan)

    lines = [
        "📡 AI STATUS UPDATE",
        "",
        f"Symbol: {getattr(context, 'symbol', 'n/a')}",
        f"Status: {getattr(plan, 'status', 'UNKNOWN')}",
        f"Bias: {getattr(plan, 'bias', 'UNKNOWN')}",
        f"Confidence: {getattr(plan, 'confidence', 'n/a')}",
    ]

    if setup:
        lines.append(f"Setup: {setup}")

    lines.extend([
        "",
        f"Price: {getattr(context, 'current_price', 'n/a')}",
        f"VWAP: {getattr(context, 'vwap', 'n/a')}",
        f"RSI: {round(float(getattr(context, 'rsi', 0)), 2)}",
    ])

    return "\n".join(lines)


def build_trade_signal_message(context, plan) -> str:
    setup = extract_setup(plan)

    lines = [
        "🚨 TRADE SIGNAL 🚨",
        "",
        f"Symbol: {getattr(context, 'symbol', 'n/a')}",
        f"Status: {getattr(plan, 'status', 'UNKNOWN')}",
    ]

    if setup:
        lines.append(f"Setup: {setup}")

    lines.extend([
        "",
        f"Price: {getattr(context, 'current_price', 'n/a')}",
        f"VWAP: {getattr(context, 'vwap', 'n/a')}",
        f"RSI: {round(float(getattr(context, 'rsi', 0)), 2)}",
    ])

    return "\n".join(lines)


def build_execution_message(exec_result) -> str:
    return "\n".join([
        "✅ EXECUTION RESULT",
        "",
        f"Symbol: {exec_result.get('symbol')}",
        f"Action: {exec_result.get('action')}",
        f"Executed: {exec_result.get('executed')}",
        f"Paper: {exec_result.get('paper')}",
        f"Qty: {exec_result.get('qty')}",
        f"Reason: {exec_result.get('reason')}",
        f"Order ID: {exec_result.get('order_id', 'n/a')}",
        f"Order Status: {exec_result.get('order_status', 'n/a')}",
    ])


def send_startup_alerts() -> None:
    startup_message = (
        "🚀 RENDER STARTUP TEST\n\n"
        "AI trading engine is live.\n"
        "Startup ping sent successfully."
    )

    send_telegram(startup_message)
    send_discord(startup_message)


# =========================================
# RUN ONE FULL CYCLE
# =========================================

def run_once():
    print("⏱️ Starting cycle...", flush=True)

    context = build_market_context()

    context = attach_elite_sources_to_context(
        context=context,
        raw_sources=context.raw_sources,
        focus_symbols=FOCUS_SYMBOLS
    )

    context = attach_fusion_to_context(context)

    plan = make_hybrid_decision(context)

    return context, plan


# =========================================
# OUTPUT + ALERTS + EXECUTION
# =========================================

def handle_output(context, plan):
    global LAST_STATUS

    status = getattr(plan, "status", "UNKNOWN")

    print(f"📌 Current status: {status}", flush=True)

    # Print full plan only when status changes
    if status != LAST_STATUS:
        print_plan(context, plan)

        status_message = build_status_message(context, plan)
        send_discord(status_message)

    # Real trade signal alerts
    if status in ["ENTER_CALLS", "ENTER_PUTS"] and status != LAST_STATUS:
        trade_message = build_trade_signal_message(context, plan)

        send_telegram(trade_message)
        send_discord(trade_message)

        try:
            exec_result = execute_plan(context, plan)
            log(f"[ALPACA] {exec_result}")

            exec_message = build_execution_message(exec_result)
            send_telegram(exec_message)
            send_discord(exec_message)

        except Exception as e:
            log(f"[ALPACA ERROR] {e}")
            error_message = f"❌ ALPACA ERROR\n\n{e}"
            send_telegram(error_message)
            send_discord(error_message)

    LAST_STATUS = status


# =========================================
# MAIN LOOP
# =========================================

def main():
    global STARTUP_ALERT_SENT

    print("🔥 RENDER ENGINE STARTED 🔥", flush=True)
    log("Starting LIVE AI system with Telegram + Discord + Alpaca execution...")

    if not STARTUP_ALERT_SENT:
        send_startup_alerts()
        STARTUP_ALERT_SENT = True

    while True:
        try:
            context, plan = run_once()
            handle_output(context, plan)

        except KeyboardInterrupt:
            log("Stopped by user")
            print("🛑 Manual stop received", flush=True)
            break

        except Exception as e:
            log(f"[MAIN ERROR] {e}")
            traceback.print_exc()
            print(f"❌ MAIN ERROR: {e}", flush=True)

            error_message = f"❌ MAIN LOOP ERROR\n\n{e}"
            send_telegram(error_message)
            send_discord(error_message)

        print(f"😴 Sleeping {SCAN_INTERVAL_SECONDS} seconds...", flush=True)
        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()