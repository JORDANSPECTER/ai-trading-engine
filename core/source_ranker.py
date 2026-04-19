# =========================================
# ELITE SOURCE RANKER
# =========================================

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone
import re


@dataclass
class SourceItem:
    source_name: str
    title: str
    content: str = ""
    published_at: Optional[datetime] = None
    source_type: str = "news"
    verified_author: bool = False
    follower_count: int = 0
    likes: int = 0
    reposts: int = 0
    symbols: List[str] = field(default_factory=list)


@dataclass
class RankedSource:
    item: SourceItem
    credibility: float
    recency: float
    relevance: float
    noise: float
    final_score: float
    tier: str


SOURCE_TRUST = {
    "bloomberg": 10.0,
    "reuters": 9.8,
    "sec": 10.0,
    "federal reserve": 10.0,
    "treasury": 9.5,
    "cnbc": 8.7,
    "barrons": 8.5,
    "marketwatch": 8.2,
    "benzinga": 7.8,
    "yahoo": 7.5,
    "twitter": 6.0,
    "x": 6.0,
    "discord": 3.5,
    "telegram": 3.5
}

MARKET_KEYWORDS = [
    "cpi", "fomc", "rates", "inflation", "oil", "war",
    "earnings", "guidance", "downgrade", "upgrade",
    "merger", "acquisition", "bankruptcy", "opec",
    "jobs report", "gdp"
]

RUMOR_WORDS = [
    "rumor", "unconfirmed", "maybe", "possibly",
    "hearing", "reportedly", "speculation"
]


def normalize(text: str) -> str:
    return re.sub(r"\W+", " ", str(text).lower()).strip()


def keyword_hits(text: str, words: List[str]) -> int:
    t = normalize(text)
    return sum(1 for w in words if w in t)


def get_credibility(item: SourceItem) -> float:
    name = normalize(item.source_name)
    base = 5.0

    for k, v in SOURCE_TRUST.items():
        if k in name:
            base = v
            break

    if item.verified_author:
        base += 0.5

    if item.source_type in ["tweet", "discord", "telegram"]:
        if item.follower_count > 500000:
            base += 0.7
        elif item.follower_count > 100000:
            base += 0.3

    return min(base, 10.0)


def get_recency(published: Optional[datetime]) -> float:
    if not published:
        return 5.0

    now = datetime.now(timezone.utc)

    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    age = (now - published).total_seconds() / 60.0

    if age <= 5:
        return 10.0
    if age <= 15:
        return 9.0
    if age <= 30:
        return 8.0
    if age <= 60:
        return 7.0
    if age <= 180:
        return 6.0
    if age <= 1440:
        return 4.5
    return 2.5


def get_relevance(item: SourceItem, focus_symbols=None) -> float:
    text = f"{item.title} {item.content}"
    score = float(keyword_hits(text, MARKET_KEYWORDS))

    if focus_symbols:
        for sym in focus_symbols:
            if str(sym).lower() in text.lower():
                score += 2.0

    if item.symbols:
        score += len(item.symbols) * 0.5

    return min(score, 10.0)


def get_noise(item: SourceItem) -> float:
    text = f"{item.title} {item.content}"
    penalty = 0.0

    if keyword_hits(text, RUMOR_WORDS) > 0:
        penalty += 2.0

    if "!!!" in item.title or "100%" in item.title:
        penalty += 1.0

    if item.source_type in ["tweet", "discord", "telegram"] and item.follower_count < 10000:
        penalty += 1.0

    return penalty


def grade(score: float) -> str:
    if score >= 8.8:
        return "A+"
    if score >= 8.0:
        return "A"
    if score >= 7.0:
        return "B"
    if score >= 5.8:
        return "C"
    return "D"


def rank_sources(sources: List[SourceItem], focus_symbols=None) -> List[RankedSource]:
    ranked = []

    for s in sources:
        cred = get_credibility(s)
        rec = get_recency(s.published_at)
        rel = get_relevance(s, focus_symbols)
        noise = get_noise(s)

        final = (
            cred * 0.45 +
            rec * 0.25 +
            rel * 0.30 -
            noise * 0.40
        )

        final = max(0.0, min(final, 10.0))

        ranked.append(
            RankedSource(
                item=s,
                credibility=round(cred, 2),
                recency=round(rec, 2),
                relevance=round(rel, 2),
                noise=round(noise, 2),
                final_score=round(final, 2),
                tier=grade(final)
            )
        )

    ranked.sort(key=lambda x: x.final_score, reverse=True)
    return ranked


def filter_elite_sources(ranked: List[RankedSource], min_tier: str = "B") -> List[RankedSource]:
    order = {"A+": 5, "A": 4, "B": 3, "C": 2, "D": 1}
    min_val = order[min_tier]
    return [r for r in ranked if order[r.tier] >= min_val]