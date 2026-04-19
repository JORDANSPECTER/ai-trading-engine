# =========================================
# MAIN.PY
# REAL-TIME LOOP + TELEGRAM ALERTS
# + OIL / MACRO TRIGGER ALERTS
# =========================================

import time
import traceback
import os
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

# =========================================
# CONFIG
# =========================================

SCAN_INTERVAL_SECONDS = 20

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Oil / macro thresholds
OIL_SYMBOLS = {"USO", "OIL", "WTI", "BRENT"}
OIL_SPIKE_RSI_THRESHOLD = 60
OIL_DUMP_RSI_THRESHOLD = 40
OIL_VWAP_DISTANCE_THRESHOLD = 0.0025  # 0.25%

LAST_STATUS = None
LAST_MACRO_STATE = None


# =========================================
# TELEGRAM SENDER
# =========================================

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("[TELEGRAM] Missing token or chat ID")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }
        requests.post(url, json=payload, timeout=10)
        log("[TELEGRAM] Alert sent")
    except Exception as e:
        log(f"[TELEGRAM ERROR] {e}")


# =========================================
# RUN ONE CYCLE
# =========================================

def run_once():
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
# HELPERS
# =========================================

def extract_setup(plan) -> str:
    for reason in plan.reasons:
        if "Setup:" in reason:
            return reason.replace("Setup:", "").strip()
    return ""


def extract_macro_snapshot(context) -> dict:
    fusion = context.fusion_summary or {}
    source_bias = context.source_bias_summary or {}

    top_topic = fusion.get("top_topic", "")
    overall_bias = fusion.get("overall_bias", "NEUTRAL")
    overall_confidence = float(fusion.get("overall_confidence", 0))
    elite_count = int(source_bias.get("elite_count", 0))

    top_titles = source_bias.get("top_titles", []) or []
    joined_titles = " | ".join(top_titles).lower()

    oil_in_titles = any(sym.lower() in joined_titles for sym in ["oil", "crude", "wti", "brent", "opec", "energy"])
    oil_topic = top_topic == "oil" or oil_in_titles

    return {
        "top_topic": top_topic,
        "overall_bias": overall_bias,
        "overall_confidence": overall_confidence,
        "elite_count": elite_count,
        "oil_topic": oil_topic,
        "titles": top_titles,
    }


def detect_macro_trigger(context, plan) -> str:
    """
    Returns one of:
    - OIL_BEARISH_TRIGGER
    - OIL_BULLISH_TRIGGER
    - MACRO_BEARISH_STACK
    - MACRO_BULLISH_STACK
    - NONE
    """

    macro = extract_macro_snapshot(context)

    price = float(context.current_price)
    vwap = float(context.vwap)
    rsi = float(context.rsi)

    above_vwap = price > vwap
    below_vwap = price < vwap

    vwap_distance = 0.0
    if vwap != 0:
        vwap_distance = abs(price - vwap) / abs(vwap)

    # -------------------------
    # OIL / ENERGY-LED BEARISH TRIGGER
    # -------------------------
    if (
        macro["oil_topic"]
        and macro["overall_bias"] == "BEARISH"
        and macro["overall_confidence"] >= 5
        and below_vwap
        and rsi <= OIL_SPIKE_RSI_THRESHOLD
    ):
        return "OIL_BEARISH_TRIGGER"

    # -------------------------
    # OIL RELIEF / BULLISH TRIGGER
    # -------------------------
    if (
        macro["oil_topic"]
        and macro["overall_bias"] == "BULLISH"
        and macro["overall_confidence"] >= 5
        and above_vwap
        and rsi >= OIL_DUMP_RSI_THRESHOLD
    ):
        return "OIL_BULLISH_TRIGGER"

    # -------------------------
    # BROADER MACRO STACKS
    # -------------------------
    if (
        macro["overall_bias"] == "BEARISH"
        and macro["overall_confidence"] >= 5
        and macro["elite_count"] >= 2
        and below_vwap
        and vwap_distance >= OIL_VWAP_DISTANCE_THRESHOLD
        and rsi < 50
    ):
        return "MACRO_BEARISH_STACK"

    if (
        macro["overall_bias"] == "BULLISH"
        and macro["overall_confidence"] >= 5
        and macro["elite_count"] >= 2
        and above_vwap
        and vwap_distance >= OIL_VWAP_DISTANCE_THRESHOLD
        and rsi > 50
    ):
        return "MACRO_BULLISH_STACK"

    return "NONE"


def build_trade_signal_message(context, plan) -> str:
    setup = extract_setup(plan)

    return (
        f"🚨 TRADE SIGNAL 🚨\n\n"
        f"Symbol: {context.symbol}\n"
        f"Status: {plan.status}\n"
        f"{'Setup: ' + setup if setup else ''}\n\n"
        f"Price: {context.current_price}\n"
        f"VWAP: {context.vwap}\n"
        f"RSI: {round(context.rsi, 2)}"
    )


def build_macro_trigger_message(context, plan, trigger_state: str) -> str:
    fusion = context.fusion_summary or {}
    source_bias = context.source_bias_summary or {}

    emoji = "🌍"
    title = trigger_state

    if trigger_state == "OIL_BEARISH_TRIGGER":
        emoji = "🛢️"
        title = "OIL BEARISH TRIGGER"
    elif trigger_state == "OIL_BULLISH_TRIGGER":
        emoji = "🛢️"
        title = "OIL BULLISH TRIGGER"
    elif trigger_state == "MACRO_BEARISH_STACK":
        emoji = "📉"
        title = "MACRO BEARISH STACK"
    elif trigger_state == "MACRO_BULLISH_STACK":
        emoji = "📈"
        title = "MACRO BULLISH STACK"

    top_topic = fusion.get("top_topic", "unknown")
    confidence = fusion.get("overall_confidence", 0)
    titles = source_bias.get("top_titles", [])[:2]

    title_block = "\n".join([f"- {t}" for t in titles]) if titles else "- No headline titles found"

    return (
        f"{emoji} {title} {emoji}\n\n"
        f"Symbol: {context.symbol}\n"
        f"Bias: {plan.bias}\n"
        f"Status: {plan.status}\n"
        f"Top Topic: {top_topic}\n"
        f"Fusion Confidence: {round(float(confidence), 2)}\n\n"
        f"Price: {context.current_price}\n"
        f"VWAP: {context.vwap}\n"
        f"RSI: {round(context.rsi, 2)}\n\n"
        f"Top Headlines:\n{title_block}"
    )


# =========================================
# HANDLE OUTPUT + ALERTS
# =========================================

def handle_output(context, plan):
    global LAST_STATUS, LAST_MACRO_STATE

    status = plan.status

    # Print only if trade status changed
    if status != LAST_STATUS:
        print_plan(context, plan)

    # ---------------------------------
    # TRADE ENTRY ALERTS
    # ---------------------------------
    if status in ["ENTER_CALLS", "ENTER_PUTS"] and status != LAST_STATUS:
        send_telegram(build_trade_signal_message(context, plan))

    LAST_STATUS = status

    # ---------------------------------
    # OIL / MACRO TRIGGER ALERTS
    # ---------------------------------
    macro_state = detect_macro_trigger(context, plan)

    if macro_state != "NONE" and macro_state != LAST_MACRO_STATE:
        send_telegram(build_macro_trigger_message(context, plan, macro_state))
        log(f"[MACRO ALERT] {macro_state}")

    LAST_MACRO_STATE = macro_state


# =========================================
# MAIN LOOP
# =========================================

def main():
    log("Starting LIVE AI system with Telegram + oil/macro alerts...")

    while True:
        try:
            context, plan = run_once()
            handle_output(context, plan)

        except KeyboardInterrupt:
            log("Stopped by user")
            break

        except Exception as e:
            log(f"[ERROR] {e}")
            traceback.print_exc()

        log(f"Sleeping {SCAN_INTERVAL_SECONDS} seconds...\n")
        time.sleep(SCAN_INTERVAL_SECONDS)


# =========================================
# START
# =========================================

if __name__ == "__main__":
    main()