# =========================================
# AI SYSTEM
# FULL VERSION WITH:
# - LIVE TWELVE DATA
# - SOURCE RANKER
# - FUSION ENGINE
# - UPGRADED ENTRY LOGIC
# =========================================

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import os
import requests

from core.source_ranker import SourceItem, rank_sources, filter_elite_sources
from core.fusion_engine import fuse_elite_sources


# =========================================
# CONFIG
# =========================================

FOCUS_SYMBOLS = ["SPY", "QQQ", "USO"]
MIN_SOURCE_TIER = "B"
MAX_ELITE_SOURCES = 10

SYMBOL = "SPY"
INTERVAL = "1min"
BAR_COUNT = 60
VWAP_LOOKBACK_BARS = 30
RSI_PERIOD = 14

TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "").strip()
TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"


# =========================================
# DATA MODELS
# =========================================

@dataclass
class MarketContext:
    symbol: str = "SPY"
    current_price: float = 0.0
    vwap: float = 0.0
    rsi: float = 50.0
    raw_sources: List[Any] = field(default_factory=list)
    ranked_sources: List[Any] = field(default_factory=list)
    elite_sources: List[Any] = field(default_factory=list)
    source_bias_summary: Dict[str, Any] = field(default_factory=dict)
    fusion_summary: Dict[str, Any] = field(default_factory=dict)
    market_data_debug: Dict[str, Any] = field(default_factory=dict)
    recent_bars: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TradingPlan:
    bias: str = "NEUTRAL"
    confidence: float = 0.0
    status: str = "WAIT"
    reasons: List[str] = field(default_factory=list)


# =========================================
# LOGGING
# =========================================

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


# =========================================
# SAFE DATETIME PARSER
# =========================================

def parse_datetime_safe(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    return None


# =========================================
# RAW SOURCE -> SourceItem
# =========================================

def to_source_item(raw: Any) -> Optional[SourceItem]:
    if isinstance(raw, SourceItem):
        return raw

    if not isinstance(raw, dict):
        return None

    title = str(raw.get("title", "") or "").strip()
    if not title:
        return None

    return SourceItem(
        source_name=str(raw.get("source_name", raw.get("source", "Unknown Source"))),
        title=title,
        content=str(raw.get("content", raw.get("body", raw.get("summary", ""))) or ""),
        published_at=parse_datetime_safe(raw.get("published_at", raw.get("timestamp"))),
        source_type=str(raw.get("source_type", raw.get("type", "news")) or "news"),
        verified_author=bool(raw.get("verified_author", False)),
        follower_count=int(raw.get("follower_count", 0) or 0),
        likes=int(raw.get("likes", 0) or 0),
        reposts=int(raw.get("reposts", raw.get("retweets", 0)) or 0),
        symbols=list(raw.get("symbols", []) or [])
    )


def build_source_items(raw_sources: Optional[List[Any]]) -> List[SourceItem]:
    items: List[SourceItem] = []

    for raw in raw_sources or []:
        try:
            item = to_source_item(raw)
            if item:
                items.append(item)
        except Exception as e:
            log(f"[SOURCE_RANKER] Skipping bad source item: {e}")

    return items


# =========================================
# SAMPLE NEWS FETCHER
# REPLACE LATER WITH YOUR REAL NEWS FEED
# =========================================

def fetch_news() -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)

    return [
        {
            "source_name": "Bloomberg",
            "title": "Oil jumps as Middle East tensions rise",
            "content": "Crude prices climbed on supply disruption concerns.",
            "published_at": now,
            "source_type": "news",
            "symbols": ["USO", "SPY", "QQQ"]
        },
        {
            "source_name": "Reuters",
            "title": "Fed speakers emphasize data dependence ahead of CPI",
            "content": "Markets are watching inflation and rate path expectations.",
            "published_at": now,
            "source_type": "news",
            "symbols": ["SPY", "QQQ"]
        },
        {
            "source_name": "Random Twitter Account",
            "title": "MASSIVE SPY MOVE COMING!!!",
            "content": "Hearing big news tomorrow maybe",
            "published_at": now,
            "source_type": "tweet",
            "follower_count": 3200,
            "likes": 150,
            "reposts": 45,
            "symbols": ["SPY"]
        }
    ]


# =========================================
# TWELVE DATA HELPERS
# =========================================

def td_get(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not TWELVE_DATA_API_KEY:
        raise RuntimeError("Missing TWELVE_DATA_API_KEY environment variable.")

    payload = dict(params)
    payload["apikey"] = TWELVE_DATA_API_KEY

    url = f"{TWELVE_DATA_BASE_URL}/{endpoint}"
    response = requests.get(url, params=payload, timeout=20)
    response.raise_for_status()

    data = response.json()

    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Twelve Data error: {data.get('message', 'Unknown error')}")

    return data


def fetch_live_time_series(symbol: str, interval: str = "1min", outputsize: int = 60) -> List[Dict[str, Any]]:
    data = td_get(
        "time_series",
        {
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "format": "JSON",
            "timezone": "America/New_York",
        },
    )

    values = data.get("values", [])
    if not values:
        raise RuntimeError(f"No time series values returned for {symbol}.")

    values.reverse()
    return values


def fetch_live_rsi(symbol: str, interval: str = "1min", period: int = 14, outputsize: int = 2) -> float:
    data = td_get(
        "rsi",
        {
            "symbol": symbol,
            "interval": interval,
            "time_period": period,
            "outputsize": outputsize,
            "format": "JSON",
            "timezone": "America/New_York",
        },
    )

    values = data.get("values", [])
    if not values:
        raise RuntimeError(f"No RSI values returned for {symbol}.")

    rsi_value = values[0].get("rsi")
    if rsi_value is None:
        raise RuntimeError(f"RSI response missing 'rsi' value for {symbol}.")

    return float(rsi_value)


def compute_vwap_from_bars(bars: List[Dict[str, Any]], lookback: int = 30) -> float:
    if not bars:
        raise RuntimeError("Cannot compute VWAP with no bars.")

    recent = bars[-lookback:] if len(bars) >= lookback else bars

    total_pv = 0.0
    total_vol = 0.0

    for bar in recent:
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        volume = float(bar.get("volume", 0) or 0)

        typical_price = (high + low + close) / 3.0
        total_pv += typical_price * volume
        total_vol += volume

    if total_vol <= 0:
        closes = [float(bar["close"]) for bar in recent]
        return sum(closes) / len(closes)

    return total_pv / total_vol


def normalize_bar(bar: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "datetime": bar.get("datetime"),
        "open": float(bar["open"]),
        "high": float(bar["high"]),
        "low": float(bar["low"]),
        "close": float(bar["close"]),
        "volume": float(bar.get("volume", 0) or 0),
    }


def fetch_live_market_snapshot(symbol: str) -> Dict[str, Any]:
    raw_bars = fetch_live_time_series(
        symbol=symbol,
        interval=INTERVAL,
        outputsize=max(BAR_COUNT, VWAP_LOOKBACK_BARS, RSI_PERIOD + 5)
    )

    bars = [normalize_bar(b) for b in raw_bars]
    last_bar = bars[-1]

    current_price = float(last_bar["close"])
    vwap = compute_vwap_from_bars(bars, lookback=VWAP_LOOKBACK_BARS)
    rsi = fetch_live_rsi(symbol=symbol, interval=INTERVAL, period=RSI_PERIOD)

    return {
        "symbol": symbol,
        "current_price": round(current_price, 4),
        "vwap": round(vwap, 4),
        "rsi": round(rsi, 4),
        "last_bar_time": last_bar.get("datetime"),
        "bar_count": len(bars),
        "bars": bars,
    }


# =========================================
# SOURCE RANKER LAYER
# =========================================

def attach_elite_sources_to_context(
    context: MarketContext,
    raw_sources: Optional[List[Any]],
    focus_symbols: Optional[List[str]] = None
) -> MarketContext:
    source_items = build_source_items(raw_sources)

    if not source_items:
        context.ranked_sources = []
        context.elite_sources = []
        context.source_bias_summary = {
            "bias": "NEUTRAL",
            "bull_score": 0,
            "bear_score": 0,
            "elite_count": 0,
            "top_titles": [],
            "reasons": []
        }
        return context

    ranked_sources = rank_sources(
        source_items,
        focus_symbols=focus_symbols or FOCUS_SYMBOLS
    )

    elite_sources = filter_elite_sources(
        ranked_sources,
        min_tier=MIN_SOURCE_TIER
    )[:MAX_ELITE_SOURCES]

    context.ranked_sources = ranked_sources
    context.elite_sources = elite_sources

    bullish_words = [
        "upgrade", "buyback", "cooling inflation", "rate cut",
        "beat", "strong guidance", "rebound", "relief",
        "soft landing", "disinflation"
    ]

    bearish_words = [
        "downgrade", "war", "inflation", "rate hike",
        "miss", "weak guidance", "selloff", "bankruptcy",
        "oil jumps", "opec cuts", "geopolitical risk",
        "hawkish", "yield spike"
    ]

    bull_score = 0
    bear_score = 0
    reasons: List[str] = []

    for ranked in elite_sources:
        text = f"{ranked.item.title} {ranked.item.content}".lower()

        for word in bullish_words:
            if word in text:
                bull_score += 1
                reasons.append(f"Bullish theme: {word}")

        for word in bearish_words:
            if word in text:
                bear_score += 1
                reasons.append(f"Bearish theme: {word}")

    if bear_score > bull_score:
        bias = "BEARISH"
    elif bull_score > bear_score:
        bias = "BULLISH"
    else:
        bias = "NEUTRAL"

    context.source_bias_summary = {
        "bias": bias,
        "bull_score": bull_score,
        "bear_score": bear_score,
        "elite_count": len(elite_sources),
        "top_titles": [r.item.title for r in elite_sources[:5]],
        "reasons": reasons[:8]
    }

    log(f"[SOURCE_RANKER] ranked={len(ranked_sources)} elite={len(elite_sources)} bias={bias}")

    for r in elite_sources[:5]:
        log(
            f"[SOURCE_RANKER] {r.tier} | {r.final_score} | "
            f"{r.item.source_name} | {r.item.title}"
        )

    return context


# =========================================
# FUSION LAYER
# =========================================

def attach_fusion_to_context(context: MarketContext) -> MarketContext:
    try:
        fusion_summary = fuse_elite_sources(context.elite_sources)
    except Exception as e:
        log(f"[FUSION] Failed to build fusion summary: {e}")
        fusion_summary = {
            "overall_bias": "NEUTRAL",
            "overall_confidence": 4.0,
            "top_topic": None,
            "top_titles": [],
            "narratives": [],
            "reasons": []
        }

    context.fusion_summary = fusion_summary

    log(
        f"[FUSION] bias={fusion_summary.get('overall_bias')} "
        f"confidence={fusion_summary.get('overall_confidence')} "
        f"top_topic={fusion_summary.get('top_topic')}"
    )

    for narrative in fusion_summary.get("narratives", [])[:3]:
        log(
            f"[FUSION] topic={narrative.topic} | "
            f"bias={narrative.bias} | "
            f"confidence={narrative.confidence} | "
            f"sources={narrative.source_count}"
        )

    return context


# =========================================
# BAR HELPERS
# =========================================

def is_green(bar: Dict[str, Any]) -> bool:
    return float(bar["close"]) > float(bar["open"])


def is_red(bar: Dict[str, Any]) -> bool:
    return float(bar["close"]) < float(bar["open"])


def body_size(bar: Dict[str, Any]) -> float:
    return abs(float(bar["close"]) - float(bar["open"]))


def upper_wick(bar: Dict[str, Any]) -> float:
    return float(bar["high"]) - max(float(bar["open"]), float(bar["close"]))


def lower_wick(bar: Dict[str, Any]) -> float:
    return min(float(bar["open"]), float(bar["close"])) - float(bar["low"])


def near_level(price: float, level: float, tolerance: float = 0.0015) -> bool:
    if level == 0:
        return False
    return abs(price - level) / abs(level) <= tolerance


# =========================================
# STRATEGY ENTRY SETUPS
# =========================================

def detect_bearish_vwap_rejection(bars: List[Dict[str, Any]], vwap: float, rsi: float) -> Optional[List[str]]:
    if len(bars) < 2:
        return None

    prev_bar = bars[-2]
    last_bar = bars[-1]

    tolerance = vwap * 0.002

    near_vwap = abs(float(last_bar["high"]) - vwap) <= tolerance or abs(float(prev_bar["high"]) - vwap) <= tolerance
    closed_below = float(last_bar["close"]) < vwap
    red_close = is_red(last_bar)
    weak_momentum = rsi < 55
    wick_rejection = upper_wick(last_bar) > body_size(last_bar) * 0.5

    if near_vwap and closed_below and red_close and weak_momentum and wick_rejection:
        return [
            "Bearish VWAP rejection detected",
            "Price tested near VWAP and failed",
            "Upper wick shows rejection pressure",
            "Close remained below VWAP",
            "RSI supports bearish timing",
        ]

    return None


def detect_failed_bounce_rejection(bars: List[Dict[str, Any]], vwap: float, rsi: float) -> Optional[List[str]]:
    if len(bars) < 3:
        return None

    bar_1 = bars[-3]
    bar_2 = bars[-2]
    bar_3 = bars[-1]

    bounce_attempt = is_green(bar_2) and float(bar_2["close"]) <= vwap * 1.0015
    lower_high = float(bar_3["high"]) < max(float(bar_2["high"]), float(bar_1["high"]))
    rejected_below_vwap = float(bar_3["close"]) < vwap and is_red(bar_3)
    bearish_momentum = rsi < 54

    if bounce_attempt and lower_high and rejected_below_vwap and bearish_momentum:
        return [
            "Failed bounce / lower-high rejection detected",
            "Bounce attempt could not reclaim structure",
            "Lower high formed under pressure",
            "Price remains below VWAP",
            "RSI supports bearish continuation",
        ]

    return None


def detect_bullish_vwap_reclaim(bars: List[Dict[str, Any]], vwap: float, rsi: float) -> Optional[List[str]]:
    if len(bars) < 2:
        return None

    prev_bar = bars[-2]
    last_bar = bars[-1]

    was_below = float(prev_bar["close"]) <= vwap or float(prev_bar["low"]) <= vwap
    now_above = float(last_bar["close"]) > vwap
    green_close = is_green(last_bar)
    bullish_momentum = rsi > 45

    if was_below and now_above and green_close and bullish_momentum:
        return [
            "Bullish VWAP reclaim detected",
            "Price moved from below VWAP to above VWAP",
            "Bullish candle closed with acceptance",
            "RSI supports bullish timing",
        ]

    return None


def detect_bullish_retest_hold(bars: List[Dict[str, Any]], vwap: float, rsi: float) -> Optional[List[str]]:
    if len(bars) < 3:
        return None

    bar_1 = bars[-3]
    bar_2 = bars[-2]
    bar_3 = bars[-1]

    prior_acceptance_above = float(bar_1["close"]) > vwap or float(bar_2["close"]) > vwap
    retest_tag = near_level(float(bar_3["low"]), vwap, tolerance=0.0025) or float(bar_2["low"]) <= vwap
    held_above = float(bar_3["close"]) > vwap
    green_response = is_green(bar_3)
    bullish_momentum = rsi > 48

    if prior_acceptance_above and retest_tag and held_above and green_response and bullish_momentum:
        return [
            "Bullish retest hold detected",
            "Price accepted above VWAP first",
            "Retest held without losing VWAP",
            "Response candle closed strong",
            "RSI supports bullish continuation",
        ]

    return None


# =========================================
# ENTRY ENGINE
# =========================================

def evaluate_entry(context: MarketContext) -> Dict[str, Any]:
    fusion = context.fusion_summary or {}
    bias = fusion.get("overall_bias", "NEUTRAL")
    confidence = float(fusion.get("overall_confidence", 0))

    price = float(context.current_price)
    vwap = float(context.vwap)
    rsi = float(context.rsi)
    bars = context.recent_bars or []

    decision = {
        "entry": False,
        "direction": None,
        "setup": None,
        "reason": []
    }

    if len(bars) < 3:
        decision["reason"].append("Not enough recent bars for setup confirmation")
        return decision

    if bias == "BEARISH" and confidence >= 5:
        bearish_rejection = detect_bearish_vwap_rejection(bars, vwap, rsi)
        failed_bounce = detect_failed_bounce_rejection(bars, vwap, rsi)

        if bearish_rejection:
            decision["entry"] = True
            decision["direction"] = "PUTS"
            decision["setup"] = "VWAP_REJECTION"
            decision["reason"] = bearish_rejection + [
                f"Live price: {price}",
                f"VWAP: {vwap}",
                f"RSI: {round(rsi, 2)}",
            ]
            return decision

        if failed_bounce:
            decision["entry"] = True
            decision["direction"] = "PUTS"
            decision["setup"] = "FAILED_BOUNCE_REJECTION"
            decision["reason"] = failed_bounce + [
                f"Live price: {price}",
                f"VWAP: {vwap}",
                f"RSI: {round(rsi, 2)}",
            ]
            return decision

        decision["reason"].append("Bearish bias present, but no clean rejection entry yet")
        return decision

    if bias == "BULLISH" and confidence >= 5:
        bullish_reclaim = detect_bullish_vwap_reclaim(bars, vwap, rsi)
        bullish_retest = detect_bullish_retest_hold(bars, vwap, rsi)

        if bullish_retest:
            decision["entry"] = True
            decision["direction"] = "CALLS"
            decision["setup"] = "RETEST_HOLD"
            decision["reason"] = bullish_retest + [
                f"Live price: {price}",
                f"VWAP: {vwap}",
                f"RSI: {round(rsi, 2)}",
            ]
            return decision

        if bullish_reclaim:
            decision["entry"] = True
            decision["direction"] = "CALLS"
            decision["setup"] = "VWAP_RECLAIM"
            decision["reason"] = bullish_reclaim + [
                f"Live price: {price}",
                f"VWAP: {vwap}",
                f"RSI: {round(rsi, 2)}",
            ]
            return decision

        decision["reason"].append("Bullish bias present, but no clean reclaim/retest entry yet")
        return decision

    decision["reason"].append("Bias or confidence not strong enough for entry")
    return decision


# =========================================
# MARKET CONTEXT
# =========================================

def build_market_context() -> MarketContext:
    context = MarketContext()
    context.symbol = SYMBOL
    context.raw_sources = fetch_news()

    snapshot = fetch_live_market_snapshot(SYMBOL)
    context.current_price = snapshot["current_price"]
    context.vwap = snapshot["vwap"]
    context.rsi = snapshot["rsi"]
    context.market_data_debug = {
        "symbol": snapshot["symbol"],
        "current_price": snapshot["current_price"],
        "vwap": snapshot["vwap"],
        "rsi": snapshot["rsi"],
        "last_bar_time": snapshot["last_bar_time"],
        "bar_count": snapshot["bar_count"],
    }
    context.recent_bars = snapshot["bars"]

    log(
        f"[LIVE_DATA] symbol={SYMBOL} price={context.current_price} "
        f"vwap={context.vwap} rsi={context.rsi} "
        f"last_bar={snapshot.get('last_bar_time')} bars={snapshot.get('bar_count')}"
    )

    return context


# =========================================
# DECISION ENGINE
# =========================================

def make_hybrid_decision(context: MarketContext) -> TradingPlan:
    plan = TradingPlan()

    fusion_summary = context.fusion_summary or {}
    overall_bias = fusion_summary.get("overall_bias", "NEUTRAL")
    overall_confidence = float(fusion_summary.get("overall_confidence", 4.0))
    top_topic = fusion_summary.get("top_topic", None)

    if len(context.elite_sources) >= 2:
        if overall_bias == "BULLISH":
            plan.bias = "BULLISH"
            plan.confidence = overall_confidence
            plan.status = "WATCH_CALLS"
            plan.reasons.append("Fusion engine supports bullish conditions.")
        elif overall_bias == "BEARISH":
            plan.bias = "BEARISH"
            plan.confidence = overall_confidence
            plan.status = "WATCH_PUTS"
            plan.reasons.append("Fusion engine supports bearish conditions.")
        else:
            plan.bias = "NEUTRAL"
            plan.confidence = max(4.0, overall_confidence)
            plan.status = "WAIT"
            plan.reasons.append("Fusion engine is neutral.")
    else:
        plan.bias = "NEUTRAL"
        plan.confidence = 4.0
        plan.status = "WAIT"
        plan.reasons.append("Not enough elite sources for fused directional conviction.")

    if top_topic:
        plan.reasons.append(f"Top fused topic: {top_topic}")

    for reason in fusion_summary.get("reasons", [])[:5]:
        plan.reasons.append(reason)

    entry_decision = evaluate_entry(context)

    if entry_decision["entry"]:
        if entry_decision["direction"] == "CALLS":
            plan.status = "ENTER_CALLS"
        elif entry_decision["direction"] == "PUTS":
            plan.status = "ENTER_PUTS"

        if entry_decision.get("setup"):
            plan.reasons.append(f"Setup: {entry_decision['setup']}")

        for r in entry_decision["reason"]:
            plan.reasons.append(r)
    else:
        for r in entry_decision["reason"]:
            plan.reasons.append(r)

    return plan


# =========================================
# OUTPUT
# =========================================

def print_plan(context: MarketContext, plan: TradingPlan) -> None:
    log("========== AI SYSTEM REPORT ==========")
    log(f"Symbol: {context.symbol}")
    log(f"Price: {context.current_price}")
    log(f"VWAP: {context.vwap}")
    log(f"RSI: {context.rsi}")
    log(f"Bias: {plan.bias}")
    log(f"Confidence: {plan.confidence}")
    log(f"Status: {plan.status}")

    if context.market_data_debug:
        log(f"Live Data Debug: {context.market_data_debug}")

    if context.source_bias_summary:
        log(f"Source Bias Summary: {context.source_bias_summary}")

    if context.fusion_summary:
        log(
            f"Fusion Summary: bias={context.fusion_summary.get('overall_bias')} "
            f"confidence={context.fusion_summary.get('overall_confidence')} "
            f"top_topic={context.fusion_summary.get('top_topic')}"
        )

    if plan.reasons:
        for reason in plan.reasons:
            log(f"- {reason}")

    log("======================================")


# =========================================
# MAIN
# =========================================

def main() -> None:
    log("Starting AI system...")

    context = build_market_context()

    context = attach_elite_sources_to_context(
        context=context,
        raw_sources=context.raw_sources,
        focus_symbols=FOCUS_SYMBOLS
    )

    context = attach_fusion_to_context(context)

    plan = make_hybrid_decision(context)

    print_plan(context, plan)


if __name__ == "__main__":
    main()