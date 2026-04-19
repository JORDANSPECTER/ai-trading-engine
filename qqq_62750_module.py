from dataclasses import dataclass
from typing import List


# =========================
# DATA MODELS
# =========================

@dataclass
class MarketContext:
    symbol: str
    current_price: float
    vwap: float
    rsi: float

    # key institutional / chart levels
    trigger_level: float = 627.50
    resistance_1: float = 629.00
    resistance_2: float = 630.00
    support_1: float = 626.00
    support_2: float = 624.50

    # optional higher-timeframe context
    above_vwap: bool = False
    below_vwap: bool = False
    near_upper_band: bool = False
    near_lower_band: bool = False

    # optional extension / location info
    distance_from_trigger: float = 0.0
    prior_move_extended: bool = False


@dataclass
class StructureState:
    # bullish confirmations
    hold_at_trigger: bool = False
    vwap_reclaimed: bool = False
    vwap_held: bool = False
    higher_low: bool = False
    retest_hold: bool = False
    breakout_candle_with_volume: bool = False

    # bearish confirmations
    rejection_at_resistance: bool = False
    lower_high: bool = False
    clean_break_below_trigger: bool = False
    acceptance_below_trigger: bool = False
    failed_bounce: bool = False

    # chase / discipline filters
    no_retest: bool = False
    multiple_same_color_bars_extended: bool = False
    entering_directly_into_resistance: bool = False
    entering_directly_into_support: bool = False


@dataclass
class TradeDecision:
    ticker: str
    bias: str  # CALL / PUT / NO TRADE
    grade: str  # A+ / A / B / AVOID
    setup_name: str
    trigger_level: float
    entry_zone: str
    targets: List[str]
    invalidation: str
    reason: List[str]
    is_chasing: bool
    alert_text: str


# =========================
# HELPERS
# =========================

def approx_equal(a: float, b: float, tol: float = 0.12) -> bool:
    return abs(a - b) <= tol


def within_range(x: float, low: float, high: float) -> bool:
    return low <= x <= high


def is_testing_trigger(price: float, trigger: float, tol: float = 0.20) -> bool:
    return abs(price - trigger) <= tol


def calls_chasing(ctx: MarketContext, st: StructureState) -> bool:
    flags = 0

    # moved too far away from ideal trigger
    if ctx.current_price > ctx.trigger_level + 0.80:
        flags += 1

    # overextended RSI
    if ctx.rsi >= 72:
        flags += 1

    # extended into outer band
    if ctx.near_upper_band:
        flags += 1

    # no pullback / no retest
    if st.no_retest:
        flags += 1

    # multiple green bars after run
    if st.multiple_same_color_bars_extended:
        flags += 1

    # buying into resistance
    if st.entering_directly_into_resistance:
        flags += 1

    return flags >= 2


def puts_chasing(ctx: MarketContext, st: StructureState) -> bool:
    flags = 0

    if ctx.current_price < ctx.trigger_level - 0.80:
        flags += 1

    if ctx.rsi <= 28:
        flags += 1

    if ctx.near_lower_band:
        flags += 1

    if st.no_retest:
        flags += 1

    if st.multiple_same_color_bars_extended:
        flags += 1

    if st.entering_directly_into_support:
        flags += 1

    return flags >= 2


# =========================
# CORE LOGIC
# =========================

def make_qqq_62750_decision(ctx: MarketContext, st: StructureState) -> TradeDecision:
    """
    Exact setup logic for:
    - Bullish continuation if 627.50 holds and confirms
    - Bearish unwind if 627.50 fails and accepts below
    """

    reasons: List[str] = []

    # -------------------------
    # BULLISH CONDITIONS
    # -------------------------
    bull_confirmations = 0

    if st.hold_at_trigger:
        bull_confirmations += 1
        reasons.append("Price is holding at the 627.50 institutional trigger.")

    if st.vwap_reclaimed or st.vwap_held:
        bull_confirmations += 1
        reasons.append("VWAP is aligned with the long idea.")

    if st.higher_low:
        bull_confirmations += 1
        reasons.append("Higher low confirms buyers defending the level.")

    if st.retest_hold:
        bull_confirmations += 1
        reasons.append("Retest held after initial reaction.")

    if st.breakout_candle_with_volume:
        bull_confirmations += 1
        reasons.append("Breakout candle with volume confirms continuation.")

    bull_chasing = calls_chasing(ctx, st)

    # A+ CALL
    if (
        is_testing_trigger(ctx.current_price, ctx.trigger_level, tol=0.30)
        and bull_confirmations >= 4
        and not bull_chasing
    ):
        return TradeDecision(
            ticker=ctx.symbol,
            bias="CALL",
            grade="A+",
            setup_name="627.50 Hold + VWAP Confirmation",
            trigger_level=ctx.trigger_level,
            entry_zone="627.40 - 627.70 after hold/reclaim confirmation",
            targets=["629.00", "630.00", "631.00+"],
            invalidation="Lose 627.50 cleanly and accept below VWAP",
            reason=reasons,
            is_chasing=False,
            alert_text=(
                "💎 A+ QQQ CALL ALERT\n\n"
                f"Trigger: {ctx.trigger_level:.2f}\n"
                f"Price: {ctx.current_price:.2f}\n"
                "Setup: Institutional hold + VWAP alignment\n\n"
                "Entry Logic:\n"
                "- 627.50 is holding\n"
                "- VWAP confirms\n"
                "- Structure is forming a higher low / retest hold\n\n"
                "Targets:\n"
                "- 629.00\n"
                "- 630.00\n"
                "- 631.00+\n\n"
                "Invalidation:\n"
                "- Clean loss of 627.50\n"
                "- Acceptance below VWAP"
            ),
        )

    # B / A CALL above trigger but not ideal location
    if (
        (ctx.current_price > ctx.trigger_level + 0.30 and ctx.current_price <= ctx.resistance_1)
        and bull_confirmations >= 2
    ):
        return TradeDecision(
            ticker=ctx.symbol,
            bias="CALL",
            grade="B" if bull_chasing else "A",
            setup_name="Late Long Above 627.50",
            trigger_level=ctx.trigger_level,
            entry_zone="Only on pullback, not on extension",
            targets=["629.00", "630.00"],
            invalidation="Loss of intraday support / return under 627.50",
            reason=reasons + [
                "Long idea still has structure, but price is no longer at the best location."
            ],
            is_chasing=bull_chasing,
            alert_text=(
                "⚠️ QQQ LONG SETUP NOT AT IDEAL LOCATION\n\n"
                f"Price is above the key {ctx.trigger_level:.2f} trigger.\n"
                "This can still work, but reward/risk is worse here.\n\n"
                f"Grade: {'B' if bull_chasing else 'A'}\n"
                "Best action: wait for pullback or retest instead of chasing."
            ),
        )

    # -------------------------
    # BEARISH CONDITIONS
    # -------------------------
    bear_reasons: List[str] = []
    bear_confirmations = 0

    if st.clean_break_below_trigger:
        bear_confirmations += 1
        bear_reasons.append("627.50 broke cleanly.")

    if st.acceptance_below_trigger:
        bear_confirmations += 1
        bear_reasons.append("Price is accepting below the trigger, not just wicking it.")

    if st.lower_high:
        bear_confirmations += 1
        bear_reasons.append("Lower high confirms weak bounce structure.")

    if st.rejection_at_resistance:
        bear_confirmations += 1
        bear_reasons.append("Rejection formed before continuation lower.")

    if st.failed_bounce:
        bear_confirmations += 1
        bear_reasons.append("Bounce failed, showing weak demand.")

    bear_chasing = puts_chasing(ctx, st)

    # A+ PUT
    if (
        ctx.current_price < ctx.trigger_level
        and bear_confirmations >= 4
        and not bear_chasing
    ):
        return TradeDecision(
            ticker=ctx.symbol,
            bias="PUT",
            grade="A+",
            setup_name="627.50 Failure + Acceptance Below",
            trigger_level=ctx.trigger_level,
            entry_zone="627.40 down to 627.00 on failed reclaim / acceptance below",
            targets=["626.00", "624.50", "623.50"],
            invalidation="Reclaim of 627.50 and hold above VWAP",
            reason=bear_reasons,
            is_chasing=False,
            alert_text=(
                "💎 A+ QQQ PUT ALERT\n\n"
                f"Trigger: {ctx.trigger_level:.2f}\n"
                f"Price: {ctx.current_price:.2f}\n"
                "Setup: Institutional failure + acceptance below\n\n"
                "Entry Logic:\n"
                "- 627.50 failed\n"
                "- Price accepted below\n"
                "- Bounce is weak / lower high confirmed\n\n"
                "Targets:\n"
                "- 626.00\n"
                "- 624.50\n"
                "- 623.50\n\n"
                "Invalidation:\n"
                "- Strong reclaim of 627.50\n"
                "- Hold back above VWAP"
            ),
        )

    # B / A PUT below trigger but not ideal location
    if (
        ctx.current_price < ctx.trigger_level - 0.50
        and bear_confirmations >= 2
    ):
        return TradeDecision(
            ticker=ctx.symbol,
            bias="PUT",
            grade="B" if bear_chasing else "A",
            setup_name="Late Short Below 627.50",
            trigger_level=ctx.trigger_level,
            entry_zone="Prefer failed reclaim, not extended breakdown",
            targets=["626.00", "624.50"],
            invalidation="Reclaim of 627.50",
            reason=bear_reasons + [
                "Short idea exists, but entry is no longer near the best location."
            ],
            is_chasing=bear_chasing,
            alert_text=(
                "⚠️ QQQ SHORT SETUP NOT AT IDEAL LOCATION\n\n"
                f"Price is already extended below the key {ctx.trigger_level:.2f} trigger.\n"
                f"Grade: {'B' if bear_chasing else 'A'}\n"
                "Best action: wait for failed reclaim instead of chasing breakdown."
            ),
        )

    # -------------------------
    # DEFAULT: NO TRADE
    # -------------------------
    return TradeDecision(
        ticker=ctx.symbol,
        bias="NO TRADE",
        grade="AVOID",
        setup_name="No clean trigger confirmation",
        trigger_level=ctx.trigger_level,
        entry_zone="None",
        targets=[],
        invalidation="None",
        reason=[
            "Price has not confirmed hold or failure at 627.50 with enough structure."
        ],
        is_chasing=False,
        alert_text=(
            "⛔ NO TRADE\n\n"
            "QQQ is around the decision zone, but structure is not clean enough yet.\n"
            "Wait for one of two things:\n"
            "- 627.50 hold + VWAP confirmation for calls\n"
            "- 627.50 failure + acceptance below for puts"
        ),
    )


# =========================
# OPTIONAL: DISCORD FORMATTER
# =========================

def format_discord_alert(decision: TradeDecision) -> str:
    reasons_text = "\n".join([f"- {r}" for r in decision.reason]) if decision.reason else "- None"
    targets_text = "\n".join([f"- {t}" for t in decision.targets]) if decision.targets else "- None"
    chasing_text = "YES" if decision.is_chasing else "NO"

    return (
        f"{decision.alert_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Ticker: {decision.ticker}\n"
        f"Bias: {decision.bias}\n"
        f"Grade: {decision.grade}\n"
        f"Setup: {decision.setup_name}\n"
        f"Trigger Level: {decision.trigger_level:.2f}\n"
        f"Entry Zone: {decision.entry_zone}\n"
        f"Targets:\n{targets_text}\n"
        f"Invalidation: {decision.invalidation}\n"
        f"Chasing: {chasing_text}\n"
        f"Reasons:\n{reasons_text}"
    )


# =========================
# EXAMPLE SCENARIOS
# =========================

if __name__ == "__main__":
    # A+ CALL example
    ctx_call = MarketContext(
        symbol="QQQ",
        current_price=627.56,
        vwap=627.42,
        rsi=64.8,
        above_vwap=True,
        near_upper_band=False,
    )

    st_call = StructureState(
        hold_at_trigger=True,
        vwap_reclaimed=True,
        vwap_held=True,
        higher_low=True,
        retest_hold=True,
        breakout_candle_with_volume=True,
        no_retest=False,
        multiple_same_color_bars_extended=False,
        entering_directly_into_resistance=False,
    )

    decision_call = make_qqq_62750_decision(ctx_call, st_call)
    print(format_discord_alert(decision_call))
    print("\n" + "=" * 80 + "\n")

    # B / chasing CALL example
    ctx_b = MarketContext(
        symbol="QQQ",
        current_price=628.72,
        vwap=627.95,
        rsi=77.5,
        above_vwap=True,
        near_upper_band=True,
    )

    st_b = StructureState(
        hold_at_trigger=True,
        vwap_held=True,
        higher_low=True,
        no_retest=True,
        multiple_same_color_bars_extended=True,
        entering_directly_into_resistance=True,
    )

    decision_b = make_qqq_62750_decision(ctx_b, st_b)
    print(format_discord_alert(decision_b))