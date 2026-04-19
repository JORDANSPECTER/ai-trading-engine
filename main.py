# =========================================
# MAIN.PY
# RENDER-SAFE LIVE LOOP
# TELEGRAM + ALPACA + DEBUG LOGS
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

LAST_STATUS = None


# =========================================
# TELEGRAM
# =========================================

def send_telegram(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("[TELEGRAM] Missing token or chat ID")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        log("[TELEGRAM] Alert sent")
    except Exception as e:
        log(f"[TELEGRAM ERROR] {e}")


# =========================================
# HELPERS
# =========================================

def extract_setup(plan) -> str:
    for reason in getattr(plan, "reasons", []):
        if "Setup:" in reason:
            return reason.replace("Setup:", "").strip()
    return ""


def build_trade_signal_message(context, plan) -> str:
    setup = extract_setup(plan)

    lines = [
        "🚨 TRADE SIGNAL 🚨",
        "",
        f"Symbol: {context.symbol}",
        f"Status: {plan.status}",
    ]

    if setup:
        lines.append(f"Setup: {setup}")

    lines.extend([
        "",
        f"Price: {context.current_price}",
        f"VWAP: {context.vwap}",
        f"RSI: {round(float(context.rsi), 2)}",
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

    if status != LAST_STATUS:
        print_plan(context, plan)

    if status in ["ENTER_CALLS", "ENTER_PUTS"] and status != LAST_STATUS:
        send_telegram(build_trade_signal_message(context, plan))

        try:
            exec_result = execute_plan(context, plan)
            log(f"[ALPACA] {exec_result}")
            send_telegram(build_execution_message(exec_result))
        except Exception as e:
            log(f"[ALPACA ERROR] {e}")
            send_telegram(f"❌ ALPACA ERROR\n\n{e}")

    LAST_STATUS = status


# =========================================
# MAIN LOOP
# =========================================

def main():
    print("🔥 RENDER ENGINE STARTED 🔥", flush=True)
    log("Starting LIVE AI system with Telegram + Alpaca execution...")

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

        print(f"😴 Sleeping {SCAN_INTERVAL_SECONDS} seconds...", flush=True)
        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()