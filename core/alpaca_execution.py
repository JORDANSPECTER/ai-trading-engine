# =========================================
# CORE / ALPACA_EXECUTION.PY
# SAFE PAPER-FIRST EXECUTION ENGINE
# =========================================

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Any

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce


ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "").strip()
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "").strip()
ALPACA_PAPER = os.getenv("ALPACA_PAPER", "true").strip().lower() == "true"

AUTO_EXECUTION_ENABLED = os.getenv("AUTO_EXECUTION_ENABLED", "false").strip().lower() == "true"
MAX_DOLLAR_PER_TRADE = float(os.getenv("MAX_DOLLAR_PER_TRADE", "250"))
ALLOW_SHORT_SELL = os.getenv("ALLOW_SHORT_SELL", "false").strip().lower() == "true"
ALLOWED_SYMBOLS = {
    s.strip().upper()
    for s in os.getenv("ALLOWED_SYMBOLS", "SPY,QQQ").split(",")
    if s.strip()
}


@dataclass
class ExecutionDecision:
    should_execute: bool
    action: str
    symbol: str
    qty: int
    side: str
    reason: str


def get_trading_client() -> TradingClient:
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        raise RuntimeError("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY.")
    return TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=ALPACA_PAPER)


def safe_int_qty(price: float, max_dollars: float) -> int:
    if price <= 0:
        return 0
    return max(int(max_dollars // price), 0)


def build_execution_decision(context, plan) -> ExecutionDecision:
    symbol = str(getattr(context, "symbol", "SPY")).upper()
    price = float(getattr(context, "current_price", 0.0))

    if symbol not in ALLOWED_SYMBOLS:
        return ExecutionDecision(False, "SKIP", symbol, 0, "none", f"{symbol} not allowed")

    if not AUTO_EXECUTION_ENABLED:
        return ExecutionDecision(False, "SKIP", symbol, 0, "none", "AUTO_EXECUTION_ENABLED is false")

    qty = safe_int_qty(price, MAX_DOLLAR_PER_TRADE)
    if qty < 1:
        return ExecutionDecision(False, "SKIP", symbol, 0, "none", "Quantity < 1")

    if plan.status == "ENTER_CALLS":
        return ExecutionDecision(True, "BUY_LONG", symbol, qty, "buy", "Signal is ENTER_CALLS")

    if plan.status == "ENTER_PUTS":
        if not ALLOW_SHORT_SELL:
            return ExecutionDecision(False, "SKIP", symbol, 0, "none", "Short selling disabled")
        return ExecutionDecision(True, "SELL_SHORT", symbol, qty, "sell", "Signal is ENTER_PUTS")

    return ExecutionDecision(False, "SKIP", symbol, 0, "none", f"No executable status: {plan.status}")


def submit_market_order(symbol: str, qty: int, side: str):
    client = get_trading_client()

    order = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )

    return client.submit_order(order_data=order)


def execute_plan(context, plan) -> Dict[str, Any]:
    decision = build_execution_decision(context, plan)

    result: Dict[str, Any] = {
        "executed": False,
        "action": decision.action,
        "symbol": decision.symbol,
        "qty": decision.qty,
        "reason": decision.reason,
        "paper": ALPACA_PAPER,
    }

    if not decision.should_execute:
        return result

    order = submit_market_order(
        symbol=decision.symbol,
        qty=decision.qty,
        side=decision.side,
    )

    result["executed"] = True
    result["order_id"] = str(getattr(order, "id", ""))
    result["order_status"] = str(getattr(order, "status", ""))
    return result