from pprint import pprint

from app.classification.event_classifier import classify_event
from app.decision.decision_engine import decide_action
from app.extraction.event_parser import (
    detect_actors,
    detect_location,
    detect_targets,
    parse_event,
)
from app.mapping.asset_mapper import map_assets
from app.scoring.credibility import score_credibility
from app.scoring.conflict import score_conflict
from app.scoring.surprise import score_surprise
from app.scoring.transmission import score_transmission


def score_persistence(raw_text: str, event_type: str) -> float:
    text = raw_text.lower()
    score = 45.0

    if event_type in ["reopening", "blockade", "sanctions", "military_action"]:
        score += 10.0

    if "temporary" in text or "during" in text or "while" in text:
        score -= 15.0

    if "ceasefire" in text:
        score -= 10.0

    if "confirmed" in text or "official" in text:
        score += 10.0

    return max(0.0, min(score, 100.0))


def score_fragility(conflict_score: float, persistence_score: float) -> float:
    base = 30.0
    base += conflict_score * 0.5
    base += max(0.0, 50.0 - persistence_score) * 0.6
    return max(0.0, min(base, 100.0))


def build_market_bias(event_type: str, subtype: str) -> str:
    if event_type in ["reopening", "ceasefire"] and "de_escalation" in subtype:
        return "risk_on"

    if event_type in ["blockade", "military_action"] and subtype == "escalation":
        return "risk_off"

    if event_type == "sanctions" and subtype == "escalation":
        return "commodity_up_risk_off"

    if event_type == "sanctions" and subtype == "de_escalation":
        return "commodity_down_risk_on"

    if event_type == "trade_restriction" and subtype == "escalation":
        return "growth_risk_off"

    if event_type == "trade_restriction" and subtype == "de_escalation":
        return "growth_relief"

    return "unclear"


def build_time_horizon_view(event) -> dict[str, str]:
    if event.event_type == "reopening":
        return {
            "next_15m": "Initial relief reaction likely dominates, especially in crude and risk assets.",
            "next_1d": "Follow-through depends on confirmation and whether reopening is durable or conditional.",
            "next_1w": "Persistence depends on whether the geopolitical condition holds.",
        }

    if event.event_type == "blockade":
        return {
            "next_15m": "Immediate risk premium likely rises in oil and volatility.",
            "next_1d": "Follow-through depends on enforcement credibility.",
            "next_1w": "Persistence depends on sustained disruption.",
        }

    if event.event_type == "ceasefire":
        return {
            "next_15m": "Relief response possible but fragile.",
            "next_1d": "Continuation depends on compliance.",
            "next_1w": "Effect may fade without structural change.",
        }

    if event.event_type == "sanctions":
        return {
            "next_15m": "Immediate repricing in exposed assets.",
            "next_1d": "Depends on enforcement details.",
            "next_1w": "Persistence depends on real supply impact.",
        }

    if event.event_type == "military_action":
        return {
            "next_15m": "Immediate risk-off + volatility spike.",
            "next_1d": "Depends on escalation path.",
            "next_1w": "Depends on containment vs expansion.",
        }

    return {
        "next_15m": "Initial reaction uncertain.",
        "next_1d": "Depends on confirmation.",
        "next_1w": "Depends on persistence.",
    }


def build_reversal_risk(conflict_score: float, fragility_score: float) -> str:
    if conflict_score >= 70 or fragility_score >= 75:
        return "High"
    if conflict_score >= 45 or fragility_score >= 55:
        return "Moderate"
    return "Low"


def build_confidence(event) -> str:
    if event.scores.transmission >= 80 and event.scores.credibility >= 70 and event.scores.conflict <= 40:
        return "high"
    if event.scores.transmission >= 60 and event.scores.credibility >= 55:
        return "moderate"
    return "low"


def run_pipeline(raw_text: str):
    event = parse_event(raw_text)

    event_type, subtype = classify_event(event.event_summary)
    event.event_type = event_type
    event.subtype = subtype

    if not event.location:
        event.location = detect_location(raw_text)

    if not event.actors:
        event.actors = detect_actors(raw_text)

    if not event.targets:
        event.targets = detect_targets(raw_text)

    event.scores.surprise = score_surprise(raw_text)
    event.scores.credibility = score_credibility(raw_text)
    event.scores.transmission = score_transmission(event.event_type, event.location)
    event.scores.conflict = score_conflict(raw_text)
    event.scores.persistence = score_persistence(raw_text, event.event_type)
    event.scores.fragility = score_fragility(
        event.scores.conflict,
        event.scores.persistence,
    )

    event.affected_assets = map_assets(event.event_type, event.subtype)

    event.time_horizon_view = build_time_horizon_view(event)
    event.reversal_risk = build_reversal_risk(
        event.scores.conflict,
        event.scores.fragility,
    )

    market_bias = build_market_bias(event.event_type, event.subtype)

    event.action_state = decide_action(
        {
            "surprise": event.scores.surprise,
            "credibility": event.scores.credibility,
            "persistence": event.scores.persistence,
            "transmission": event.scores.transmission,
            "conflict": event.scores.conflict,
            "event_type": event.event_type,
            "subtype": event.subtype,
            "market_bias": market_bias,
        }
    )

    event.confidence = build_confidence(event)

    existing_notes = event.notes.strip()
    event.notes = f"{existing_notes} Market bias: {market_bias}.".strip()

    return event


if __name__ == "__main__":
    raw_text = input("Paste geopolitical headline or event text: ").strip()

    if not raw_text:
        raw_text = """
        Iran says the Strait of Hormuz is open during the ceasefire period.
        Trump says the naval blockade remains in full force against Iran.
        Oil falls on reopening hopes.
        """

    result = run_pipeline(raw_text)
    pprint(result)