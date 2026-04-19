# =========================================
# FUSION ENGINE
# CLUSTERS ELITE SOURCES INTO ONE MARKET STORY
# WITH MULTI-SOURCE CONFIRMATION LOGIC
# =========================================

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class FusedNarrative:
    topic: str
    bias: str
    confidence: float
    source_count: int
    titles: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)


def _text_of_ranked_source(ranked) -> str:
    title = getattr(ranked.item, "title", "") or ""
    content = getattr(ranked.item, "content", "") or ""
    return f"{title} {content}".lower()


def _symbols_of_ranked_source(ranked) -> List[str]:
    return list(getattr(ranked.item, "symbols", []) or [])


def _detect_topics(text: str) -> List[str]:
    topic_map = {
        "oil": ["oil", "crude", "wti", "brent", "opec", "energy"],
        "fed": ["fed", "fomc", "rates", "rate cut", "rate hike", "powell"],
        "inflation": ["inflation", "cpi", "ppi", "jobs report", "gdp"],
        "geopolitics": ["war", "missile", "middle east", "hormuz", "geopolitical"],
        "earnings": ["earnings", "guidance", "beat", "miss"],
        "credit": ["treasury", "yield", "bond", "liquidity", "credit"],
    }

    hits = []
    for topic, words in topic_map.items():
        if any(word in text for word in words):
            hits.append(topic)

    if not hits:
        hits.append("general_macro")

    return hits


def _score_bias(text: str) -> Dict[str, int]:
    bullish_words = [
        "upgrade", "buyback", "cooling inflation", "rate cut",
        "beat", "strong guidance", "rebound", "relief",
        "disinflation", "soft landing", "dovish", "easing"
    ]

    bearish_words = [
        "downgrade", "war", "inflation", "rate hike",
        "miss", "weak guidance", "selloff", "bankruptcy",
        "oil jumps", "opec cuts", "geopolitical risk",
        "yield spike", "hawkish", "higher for longer",
        "hot cpi", "sticky inflation"
    ]

    bull = sum(1 for word in bullish_words if word in text)
    bear = sum(1 for word in bearish_words if word in text)

    return {"bull": bull, "bear": bear}


def _topic_bias_override(topic: str, text: str) -> Dict[str, int]:
    bull = 0
    bear = 0

    if topic == "oil":
        if any(x in text for x in [
            "oil jumps", "crude rises", "crude jumps",
            "opec cuts", "supply disruption", "energy spike"
        ]):
            bear += 2
        if any(x in text for x in [
            "oil falls", "crude falls", "energy relief"
        ]):
            bull += 2

    if topic == "fed":
        if any(x in text for x in [
            "rate cut", "dovish", "policy easing", "cooling inflation"
        ]):
            bull += 2
        if any(x in text for x in [
            "rate hike", "hawkish", "higher for longer"
        ]):
            bear += 2

    if topic == "inflation":
        if any(x in text for x in [
            "cooling inflation", "cpi cools", "ppi cools", "disinflation"
        ]):
            bull += 2
        if any(x in text for x in [
            "hot cpi", "hot inflation", "sticky inflation"
        ]):
            bear += 2

    if topic == "geopolitics":
        if any(x in text for x in [
            "war", "missile", "strait of hormuz", "supply disruption", "middle east tensions"
        ]):
            bear += 2

    if topic == "earnings":
        if any(x in text for x in [
            "beat", "strong guidance", "raised guidance"
        ]):
            bull += 2
        if any(x in text for x in [
            "miss", "cut guidance", "weak guidance"
        ]):
            bear += 2

    if topic == "credit":
        if any(x in text for x in [
            "yield spike", "liquidity stress", "credit stress"
        ]):
            bear += 2
        if any(x in text for x in [
            "yield falls", "liquidity improves", "credit stabilizes"
        ]):
            bull += 2

    return {"bull": bull, "bear": bear}


def fuse_elite_sources(elite_sources: List[Any]) -> Dict[str, Any]:
    topic_buckets: Dict[str, Dict[str, Any]] = {}

    for ranked in elite_sources:
        text = _text_of_ranked_source(ranked)
        topics = _detect_topics(text)
        base_bias = _score_bias(text)
        title = getattr(ranked.item, "title", "") or ""
        symbols = _symbols_of_ranked_source(ranked)
        source_name = getattr(ranked.item, "source_name", "") or ""

        for topic in topics:
            if topic not in topic_buckets:
                topic_buckets[topic] = {
                    "bull": 0,
                    "bear": 0,
                    "titles": [],
                    "symbols": set(),
                    "sources": set(),
                    "scores": [],
                }

            override = _topic_bias_override(topic, text)

            topic_buckets[topic]["bull"] += base_bias["bull"] + override["bull"]
            topic_buckets[topic]["bear"] += base_bias["bear"] + override["bear"]
            topic_buckets[topic]["titles"].append(title)
            topic_buckets[topic]["symbols"].update(symbols)
            topic_buckets[topic]["scores"].append(float(getattr(ranked, "final_score", 0.0)))
            topic_buckets[topic]["sources"].add(source_name.lower())

    fused_narratives: List[FusedNarrative] = []

    for topic, data in topic_buckets.items():
        source_count = len(data["sources"])
        bull = data["bull"]
        bear = data["bear"]
        avg_score = sum(data["scores"]) / max(len(data["scores"]), 1)

        if bear > bull:
            bias = "BEARISH"
            edge = bear - bull
        elif bull > bear:
            bias = "BULLISH"
            edge = bull - bear
        else:
            bias = "NEUTRAL"
            edge = 0

        # =========================================
        # MULTI-SOURCE CONFIRMATION RULE
        # =========================================
        if source_count < 2:
            confidence = round((avg_score * 0.5) + (edge * 0.4), 2)
        else:
            confidence = round((avg_score * 0.7) + (source_count * 1.2) + (edge * 0.6), 2)

        confidence = min(10.0, confidence)

        reasons = [
            f"Topic cluster: {topic}",
            f"Unique confirming sources: {source_count}",
            f"Cluster bull score: {bull}",
            f"Cluster bear score: {bear}",
            f"Average source quality: {round(avg_score, 2)}"
        ]

        if source_count < 2:
            reasons.append("Confidence capped by lack of multi-source confirmation.")
        else:
            reasons.append("Multi-source confirmation present.")

        fused_narratives.append(
            FusedNarrative(
                topic=topic,
                bias=bias,
                confidence=confidence,
                source_count=source_count,
                titles=data["titles"][:5],
                reasons=reasons,
                symbols=sorted(list(data["symbols"]))
            )
        )

    fused_narratives.sort(key=lambda x: (x.confidence, x.source_count), reverse=True)

    overall_bias = "NEUTRAL"
    overall_confidence = 4.0
    top_topic = None
    top_reasons: List[str] = []

    if fused_narratives:
        top_topic_obj = fused_narratives[0]
        top_topic = top_topic_obj.topic
        overall_bias = top_topic_obj.bias
        overall_confidence = top_topic_obj.confidence
        top_reasons = top_topic_obj.reasons[:]

    return {
        "overall_bias": overall_bias,
        "overall_confidence": overall_confidence,
        "top_topic": top_topic,
        "top_titles": fused_narratives[0].titles[:3] if fused_narratives else [],
        "narratives": fused_narratives,
        "reasons": top_reasons
    }