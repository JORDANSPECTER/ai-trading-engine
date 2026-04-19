def classify_event(event_summary: str) -> tuple[str, str]:
    text = event_summary.lower()

    # Reopening / relief
    if (
        ("strait" in text or "shipping" in text or "transit" in text)
        and ("open" in text or "reopen" in text or "resume" in text)
    ):
        if "ceasefire" in text or "during" in text or "temporary" in text:
            return "reopening", "conditional_de_escalation"
        return "reopening", "durable_de_escalation"

    # Blockade / maritime disruption
    if "blockade" in text or "closed" in text or "shut" in text:
        return "blockade", "escalation"

    # Military escalation
    if "strike" in text or "missile" in text or "attack" in text or "drone" in text:
        return "military_action", "escalation"

    # Ceasefire / relief
    if "ceasefire" in text:
        if "temporary" in text or "fragile" in text or "while" in text:
            return "ceasefire", "conditional_de_escalation"
        return "ceasefire", "de_escalation"

    # Sanctions
    if "sanction" in text or "export restriction" in text:
        if "lifted" in text or "eased" in text or "relief" in text:
            return "sanctions", "de_escalation"
        return "sanctions", "escalation"

    # Tariffs / trade restrictions
    if "tariff" in text or "trade restriction" in text:
        if "reduced" in text or "removed" in text:
            return "trade_restriction", "de_escalation"
        return "trade_restriction", "escalation"

    # Default
    return "unknown", "unknown"