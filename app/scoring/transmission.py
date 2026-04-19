def score_transmission(event_type: str, location: str) -> float:
    loc = location.lower()

    if event_type in ["reopening", "blockade", "sanctions"] and "hormuz" in loc:
        return 90.0

    if event_type in ["reopening", "blockade", "sanctions"]:
        return 75.0

    if event_type == "ceasefire":
        return 55.0

    return 40.0