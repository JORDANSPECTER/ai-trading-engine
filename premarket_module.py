from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime


# =========================
# DATA MODELS
# =========================

@dataclass
class PremarketCompressionContext:
    symbol: str
    current_price: float

    # key levels
    breakout_level: float
    breakout_confirm_level: float
    breakdown_level: float
    breakdown_confirm_level: float

    # structure
    trend_bullish: bool
    near_range_high: bool
    near_range_low: bool
    compression_active: bool
    lower_high_active: bool
    higher_low_active: bool

    # indicators
    above_vwap: bool
    below_vwap: bool
    rsi_5m: float
    rsi_30m: float
    rsi_1h: float
    macd_5m: float
    macd_signal_5m: float
    macd_hist_5m: float
    macd_30m: float
    macd_signal_30m: float
    macd_hist_30m: float
    macd_1h: float
    macd_signal_1h: float
    macd_hist_1h: float

    # confirmation
    breakout_volume_present: bool
    rejection_candle_present: bool
    retest_hold_present: bool
    failed_breakout_present: bool


@dataclass
class PremarketDecision:
    timestamp: str
    symbol: str
    setup_name: str
    market_state: str
    bias: str
    grade: str
    entry_type: str
    should_alert: bool
    chasing_blocked: bool
    trigger_level: Optional[float]
    stop_level: Optional[float]
    target_1: Optional[float]
    target_2: Optional[float]
    target_3: Optional[float]
    reason: str


# =========================
# HELPERS
# =========================

def macd_bearish(macd: float, signal: float, hist: float) -> bool:
    return macd < signal and hist <= 0


def macd_bullish(macd: float, signal: float, hist: float) -> bool:
    return macd > signal and hist >= 0


def rsi_neutral_to_bullish(rsi: float) -> bool:
    return 50 <= rsi <= 68


def rsi_neutral_to_bearish(rsi: float) -> bool:
    return 32 <= rsi <= 50


# =========================
# DETECTION LOGIC
# =========================

def detect_premarket_compression_wait(ctx: PremarketCompressionContext) -> bool:
    """
    No-trade / decision-zone state:
    trend intact, but momentum slowing and price still trapped in range.
    """
    still_inside_range = (
        ctx.current_price < ctx.breakout_level
        and ctx.current_price > ctx.breakdown_level
    )

    momentum_mixed = (
        (
            macd_bearish(ctx.macd_5m, ctx.macd_signal_5m, ctx.macd_hist_5m)
            or ctx.rsi_5m < 55
        )
        and
        (
            ctx.trend_bullish
            or rsi_neutral_to_bullish(ctx.rsi_1h)
        )
    )

    return all([
        ctx.compression_active,
        still_inside_range,
        momentum_mixed,
    ])


def detect_bullish_expansion_call(ctx: PremarketCompressionContext) -> bool:
    """
    Break + hold + volume above resistance.
    """
    return all([
        ctx.current_price >= ctx.breakout_level,
        ctx.trend_bullish,
        ctx.compression_active,
        ctx.breakout_volume_present,
        ctx.retest_hold_present,
        macd_bullish(ctx.macd_5m, ctx.macd_signal_5m, ctx.macd_hist_5m),
        rsi_neutral_to_bullish(ctx.rsi_5m),
    ])


def detect_failed_breakout_put(ctx: PremarketCompressionContext) -> bool:
    """
    Fake breakout, rejection, lower-high continuation.
    """
    return all([
        ctx.failed_breakout_present or ctx.rejection_candle_present,
        ctx.lower_high_active,
        ctx.current_price <= ctx.breakdown_level or ctx.below_vwap,
        macd_bearish(ctx.macd_5m, ctx.macd_signal_5m, ctx.macd_hist_5m),
        rsi_neutral_to_bearish(ctx.rsi_5m),
    ])


def detect_chasing_calls(ctx: PremarketCompressionContext) -> bool:
    return all([
        ctx.current_price > ctx.breakout_confirm_level,
        ctx.rsi_5m >= 68,
        not ctx.retest_hold_present,
    ])


def detect_chasing_puts(ctx: PremarketCompressionContext) -> bool:
    return all([
        ctx.current_price < ctx.breakdown_confirm_level,
        ctx.rsi_5m <= 35,
        not ctx.rejection_candle_present,
    ])


# =========================
# MAIN ANALYZER
# =========================

def analyze_premarket_compression(ctx: PremarketCompressionContext) -> PremarketDecision:
    now = datetime.now().isoformat(timespec="seconds")

    # 1) Wait state
    if detect_premarket_compression_wait(ctx):
        return PremarketDecision(
            timestamp=now,
            symbol=ctx.symbol,
            setup_name="PREMARKET_COMPRESSION_DECISION_ZONE",
            market_state="COMPRESSION",
            bias="SLIGHT_BULLISH_BUT_UNCONFIRMED",
            grade="WAIT",
            entry_type="NO_TRADE",
            should_alert=False,
            chasing_blocked=False,
            trigger_level=None,
            stop_level=None,
            target_1=None,
            target_2=None,
            target_3=None,
            reason=(
                "Trend is still bullish, but momentum is slowing and price remains trapped "
                "inside compression. This is a decision zone, not a clean entry."
            ),
        )

    # 2) Bullish expansion
    if detect_bullish_expansion_call(ctx):
        if detect_chasing_calls(ctx):
            return PremarketDecision(
                timestamp=now,
                symbol=ctx.symbol,
                setup_name="BULLISH_COMPRESSION_EXPANSION",
                market_state="EXPANSION_UP",
                bias="BULLISH",
                grade="AVOID",
                entry_type="WAIT_FOR_RETEST",
                should_alert=False,
                chasing_blocked=True,
                trigger_level=ctx.breakout_level,
                stop_level=ctx.breakout_level - 1.0,
                target_1=631.00,
                target_2=632.00,
                target_3=633.00,
                reason="Breakout is active, but entry is extended. Wait for retest hold. Do not chase.",
            )

        return PremarketDecision(
            timestamp=now,
            symbol=ctx.symbol,
            setup_name="BULLISH_COMPRESSION_EXPANSION",
            market_state="EXPANSION_UP",
            bias="BULLISH",
            grade="A",
            entry_type="CALL",
            should_alert=True,
            chasing_blocked=False,
            trigger_level=ctx.breakout_level,
            stop_level=ctx.breakout_level - 1.0,
            target_1=631.00,
            target_2=632.00,
            target_3=633.00,
            reason="Price broke compression resistance with volume and held the retest. This is bullish expansion.",
        )

    # 3) Failed breakout / bearish rotation
    if detect_failed_breakout_put(ctx):
        if detect_chasing_puts(ctx):
            return PremarketDecision(
                timestamp=now,
                symbol=ctx.symbol,
                setup_name="FAILED_BREAKOUT_BEARISH_ROTATION",
                market_state="EXPANSION_DOWN",
                bias="BEARISH",
                grade="AVOID",
                entry_type="WAIT_FOR_BOUNCE_REJECT",
                should_alert=False,
                chasing_blocked=True,
                trigger_level=ctx.breakdown_level,
                stop_level=ctx.breakout_level,
                target_1=625.00,
                target_2=623.00,
                target_3=621.50,
                reason="Breakdown is extended. Wait for bounce into resistance and rejection. Do not chase puts.",
            )

        return PremarketDecision(
            timestamp=now,
            symbol=ctx.symbol,
            setup_name="FAILED_BREAKOUT_BEARISH_ROTATION",
            market_state="EXPANSION_DOWN",
            bias="BEARISH",
            grade="A-",
            entry_type="PUT",
            should_alert=True,
            chasing_blocked=False,
            trigger_level=ctx.breakdown_level,
            stop_level=ctx.breakout_level,
            target_1=625.00,
            target_2=623.00,
            target_3=621.50,
            reason="Breakout failed, rejection confirmed, and momentum rolled over. This is bearish rotation.",
        )

    return PremarketDecision(
        timestamp=now,
        symbol=ctx.symbol,
        setup_name="NO_CLEAN_PREMARKET_SETUP",
        market_state="NEUTRAL",
        bias="NEUTRAL",
        grade="WAIT",
        entry_type="NO_TRADE",
        should_alert=False,
        chasing_blocked=False,
        trigger_level=None,
        stop_level=None,
        target_1=None,
        target_2=None,
        target_3=None,
        reason="No clean confirmed premarket setup.",
    )


# =========================
# FORMATTERS FOR AI LEARNING
# =========================

def format_premarket_learning_summary(decision: PremarketDecision) -> str:
    return (
        f"Symbol: {decision.symbol}\n"
        f"Setup: {decision.setup_name}\n"
        f"Market State: {decision.market_state}\n"
        f"Bias: {decision.bias}\n"
        f"Grade: {decision.grade}\n"
        f"Entry Type: {decision.entry_type}\n"
        f"Should Alert: {decision.should_alert}\n"
        f"Chasing Blocked: {decision.chasing_blocked}\n"
        f"Trigger: {decision.trigger_level}\n"
        f"Stop: {decision.stop_level}\n"
        f"Targets: {decision.target_1} / {decision.target_2} / {decision.target_3}\n"
        f"Reason: {decision.reason}"
    )


def build_premarket_learning_record(
    ctx: PremarketCompressionContext,
    decision: PremarketDecision
) -> dict:
    return {
        "timestamp": decision.timestamp,
        "symbol": decision.symbol,
        "module": "PREMARKET_COMPRESSION_EXPANSION",
        "current_price": ctx.current_price,
        "breakout_level": ctx.breakout_level,
        "breakout_confirm_level": ctx.breakout_confirm_level,
        "breakdown_level": ctx.breakdown_level,
        "breakdown_confirm_level": ctx.breakdown_confirm_level,
        "trend_bullish": ctx.trend_bullish,
        "near_range_high": ctx.near_range_high,
        "near_range_low": ctx.near_range_low,
        "compression_active": ctx.compression_active,
        "lower_high_active": ctx.lower_high_active,
        "higher_low_active": ctx.higher_low_active,
        "above_vwap": ctx.above_vwap,
        "below_vwap": ctx.below_vwap,
        "rsi_5m": ctx.rsi_5m,
        "rsi_30m": ctx.rsi_30m,
        "rsi_1h": ctx.rsi_1h,
        "macd_5m": ctx.macd_5m,
        "macd_signal_5m": ctx.macd_signal_5m,
        "macd_hist_5m": ctx.macd_hist_5m,
        "macd_30m": ctx.macd_30m,
        "macd_signal_30m": ctx.macd_signal_30m,
        "macd_hist_30m": ctx.macd_hist_30m,
        "macd_1h": ctx.macd_1h,
        "macd_signal_1h": ctx.macd_signal_1h,
        "macd_hist_1h": ctx.macd_hist_1h,
        "breakout_volume_present": ctx.breakout_volume_present,
        "rejection_candle_present": ctx.rejection_candle_present,
        "retest_hold_present": ctx.retest_hold_present,
        "failed_breakout_present": ctx.failed_breakout_present,
        "setup_name": decision.setup_name,
        "market_state": decision.market_state,
        "bias": decision.bias,
        "grade": decision.grade,
        "entry_type": decision.entry_type,
        "should_alert": decision.should_alert,
        "chasing_blocked": decision.chasing_blocked,
        "trigger_level": decision.trigger_level,
        "stop_level": decision.stop_level,
        "target_1": decision.target_1,
        "target_2": decision.target_2,
        "target_3": decision.target_3,
        "reason": decision.reason,
    }


# =========================
# TEST BLOCK
# =========================

if __name__ == "__main__":
    ctx = PremarketCompressionContext(
        symbol="QQQ",
        current_price=627.96,
        breakout_level=629.50,
        breakout_confirm_level=630.00,
        breakdown_level=627.20,
        breakdown_confirm_level=626.80,
        trend_bullish=True,
        near_range_high=True,
        near_range_low=False,
        compression_active=True,
        lower_high_active=False,
        higher_low_active=True,
        above_vwap=True,
        below_vwap=False,
        rsi_5m=39.56,
        rsi_30m=55.52,
        rsi_1h=60.29,
        macd_5m=-0.04,
        macd_signal_5m=0.01,
        macd_hist_5m=-0.05,
        macd_30m=0.28,
        macd_signal_30m=0.48,
        macd_hist_30m=-0.20,
        macd_1h=1.78,
        macd_signal_1h=2.32,
        macd_hist_1h=-0.54,
        breakout_volume_present=False,
        rejection_candle_present=False,
        retest_hold_present=False,
        failed_breakout_present=False,
    )

    decision = analyze_premarket_compression(ctx)

    print("=== DECISION OBJECT ===")
    print(asdict(decision))
    print()
    print("=== LEARNING SUMMARY ===")
    print(format_premarket_learning_summary(decision))
    print()
    print("=== LEARNING RECORD ===")
    print(build_premarket_learning_record(ctx, decision))