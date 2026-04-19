from app.models.schemas import PoliticalEvent


def normalize_text(raw_text: str) -> str:
    return " ".join(raw_text.strip().split())


def detect_location(text: str) -> str:
    lowered = text.lower()

    location_keywords = {
        "strait of hormuz": "Strait of Hormuz",
        "hormuz": "Strait of Hormuz",
        "red sea": "Red Sea",
        "taiwan strait": "Taiwan Strait",
        "gaza": "Gaza",
        "iran": "Iran",
        "israel": "Israel",
        "ukraine": "Ukraine",
        "russia": "Russia",
        "china": "China",
        "saudi": "Saudi Arabia",
        "opec": "OPEC Region",
    }

    for key, value in location_keywords.items():
        if key in lowered:
            return value

    return ""


def detect_actors(text: str) -> list[str]:
    lowered = text.lower()
    actors = []

    actor_keywords = {
        "trump": "Trump",
        "white house": "White House",
        "iran": "Iran",
        "iranian ministry": "Iranian Ministry",
        "ministry": "Ministry",
        "opec": "OPEC",
        "israel": "Israel",
        "russia": "Russia",
        "china": "China",
        "united states": "United States",
        "u.s.": "United States",
        "navy": "Navy",
    }

    for key, value in actor_keywords.items():
        if key in lowered and value not in actors:
            actors.append(value)

    return actors


def detect_targets(text: str) -> list[str]:
    lowered = text.lower()
    targets = []

    if "oil" in lowered or "crude" in lowered or "brent" in lowered or "wti" in lowered:
        targets.append("oil")

    if "shipping" in lowered or "transit" in lowered or "tanker" in lowered or "maritime" in lowered:
        targets.append("shipping")

    if "ceasefire" in lowered or "strike" in lowered or "attack" in lowered:
        targets.append("conflict")

    if "blockade" in lowered or "open" in lowered or "reopen" in lowered:
        targets.append("maritime_access")

    if "sanction" in lowered or "tariff" in lowered or "export restriction" in lowered:
        targets.append("trade_restriction")

    return targets


def detect_implementation_status(text: str) -> str:
    lowered = text.lower()

    if "confirmed" in lowered or "official" in lowered:
        return "confirmed"

    if "temporary" in lowered or "during" in lowered or "while" in lowered:
        return "conditional"

    if "reportedly" in lowered or "rumor" in lowered:
        return "unconfirmed"

    return "unknown"


def detect_condition_flags(text: str) -> list[str]:
    lowered = text.lower()
    flags = []

    if "during" in lowered:
        flags.append("time_limited")

    if "while" in lowered:
        flags.append("coexisting_conditions")

    if "temporary" in lowered:
        flags.append("temporary")

    if "confirmed" in lowered:
        flags.append("confirmed")

    if "reportedly" in lowered or "rumor" in lowered:
        flags.append("weak_confirmation")

    if "ceasefire" in lowered:
        flags.append("ceasefire_condition")

    if "blockade remains" in lowered:
        flags.append("contradiction_risk")

    return flags


def build_notes(text: str, condition_flags: list[str]) -> str:
    notes = []

    if "open" in text.lower() and "blockade remains" in text.lower():
        notes.append("Headline contains both relief and restriction language.")

    if "ceasefire" in text.lower():
        notes.append("Ceasefire language may reduce persistence of the event effect.")

    if "reportedly" in text.lower() or "rumor" in text.lower():
        notes.append("Source language lowers confidence.")

    if condition_flags:
        notes.append(f"Condition flags: {', '.join(condition_flags)}.")

    return " ".join(notes).strip()


def parse_event(raw_text: str) -> PoliticalEvent:
    summary = normalize_text(raw_text)
    location = detect_location(summary)
    actors = detect_actors(summary)
    targets = detect_targets(summary)
    implementation_status = detect_implementation_status(summary)
    condition_flags = detect_condition_flags(summary)
    notes = build_notes(summary, condition_flags)

    return PoliticalEvent(
        event_id="evt_placeholder",
        event_summary=summary[:300],
        event_type="unclassified",
        subtype="unknown",
        actors=actors,
        location=location,
        targets=targets,
        implementation_status=implementation_status,
        notes=notes,
    )