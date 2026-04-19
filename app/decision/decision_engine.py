def decide_action(context: dict) -> str:
    surprise = context.get("surprise", 0)
    credibility = context.get("credibility", 0)
    persistence = context.get("persistence", 0)
    transmission = context.get("transmission", 0)
    conflict = context.get("conflict", 0)
    event_type = context.get("event_type", "")
    subtype = context.get("subtype", "")
    market_bias = context.get("market_bias", "unclear")

    # 1. Hard no-trade conditions
    if credibility < 40:
        return "no_trade"

    if transmission < 45:
        return "no_trade"

    if conflict >= 85 and persistence < 45:
        return "no_trade"

    # 2. High-quality act conditions
    if (
        surprise >= 65
        and credibility >= 65
        and transmission >= 75
        and persistence >= 50
        and conflict <= 45
        and market_bias != "unclear"
    ):
        return "act"

    # 3. Escalation events can still be tradable with moderate persistence
    if (
        event_type in ["blockade", "military_action", "sanctions"]
        and subtype == "escalation"
        and credibility >= 60
        and transmission >= 70
        and conflict <= 65
    ):
        return "cautious_act"

    # 4. De-escalation with caveats should usually be cautious, not full act
    if (
        "de_escalation" in subtype
        and credibility >= 55
        and transmission >= 60
        and conflict <= 70
    ):
        if "conditional" in subtype or persistence < 55:
            return "cautious_act"
        return "act"

    # 5. Monitor if event matters but is not clean enough
    if transmission >= 55 or surprise >= 55:
        return "monitor"

    return "no_trade"