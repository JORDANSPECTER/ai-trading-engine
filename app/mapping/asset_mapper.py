from app.models.schemas import AssetImpact


def map_assets(event_type: str, subtype: str = "") -> list[AssetImpact]:
    # Reopening / de-escalation
    if event_type == "reopening":
        if "conditional" in subtype:
            return [
                AssetImpact(asset="WTI", bias="bearish_initial", confidence="moderate"),
                AssetImpact(asset="Brent", bias="bearish_initial", confidence="moderate"),
                AssetImpact(asset="JETS", bias="bullish_initial", confidence="moderate"),
                AssetImpact(asset="SPY", bias="bullish_relief", confidence="moderate"),
                AssetImpact(asset="VIX", bias="bearish_but_sticky", confidence="low_to_moderate"),
            ]

        return [
            AssetImpact(asset="WTI", bias="bearish", confidence="moderate_to_high"),
            AssetImpact(asset="Brent", bias="bearish", confidence="moderate_to_high"),
            AssetImpact(asset="JETS", bias="bullish", confidence="moderate"),
            AssetImpact(asset="SPY", bias="bullish", confidence="moderate"),
            AssetImpact(asset="VIX", bias="bearish", confidence="moderate"),
        ]

    # Blockade / escalation
    if event_type == "blockade":
        return [
            AssetImpact(asset="WTI", bias="bullish", confidence="moderate_to_high"),
            AssetImpact(asset="Brent", bias="bullish", confidence="moderate_to_high"),
            AssetImpact(asset="VIX", bias="bullish", confidence="moderate"),
            AssetImpact(asset="JETS", bias="bearish", confidence="moderate"),
            AssetImpact(asset="SPY", bias="bearish", confidence="low_to_moderate"),
            AssetImpact(asset="XLE", bias="bullish", confidence="moderate"),
        ]

    # Ceasefire
    if event_type == "ceasefire":
        if "conditional" in subtype:
            return [
                AssetImpact(asset="WTI", bias="bearish_relief", confidence="low_to_moderate"),
                AssetImpact(asset="SPY", bias="bullish_relief", confidence="low_to_moderate"),
                AssetImpact(asset="VIX", bias="bearish_relief", confidence="low_to_moderate"),
            ]

        return [
            AssetImpact(asset="WTI", bias="bearish", confidence="moderate"),
            AssetImpact(asset="SPY", bias="bullish", confidence="moderate"),
            AssetImpact(asset="VIX", bias="bearish", confidence="moderate"),
            AssetImpact(asset="JETS", bias="bullish", confidence="low_to_moderate"),
        ]

    # Sanctions
    if event_type == "sanctions":
        if subtype == "de_escalation":
            return [
                AssetImpact(asset="WTI", bias="bearish", confidence="moderate"),
                AssetImpact(asset="Brent", bias="bearish", confidence="moderate"),
                AssetImpact(asset="XLE", bias="bearish", confidence="low_to_moderate"),
                AssetImpact(asset="SPY", bias="bullish_relief", confidence="low_to_moderate"),
            ]

        return [
            AssetImpact(asset="WTI", bias="bullish", confidence="moderate"),
            AssetImpact(asset="Brent", bias="bullish", confidence="moderate"),
            AssetImpact(asset="XLE", bias="bullish", confidence="moderate"),
            AssetImpact(asset="SPY", bias="mixed", confidence="low"),
        ]

    # Trade restrictions / tariffs
    if event_type == "trade_restriction":
        if subtype == "de_escalation":
            return [
                AssetImpact(asset="SPY", bias="bullish_relief", confidence="moderate"),
                AssetImpact(asset="QQQ", bias="bullish_relief", confidence="moderate"),
                AssetImpact(asset="VIX", bias="bearish", confidence="low_to_moderate"),
            ]

        return [
            AssetImpact(asset="SPY", bias="bearish", confidence="low_to_moderate"),
            AssetImpact(asset="QQQ", bias="bearish", confidence="low_to_moderate"),
            AssetImpact(asset="VIX", bias="bullish", confidence="low_to_moderate"),
        ]

    # Military escalation
    if event_type == "military_action":
        return [
            AssetImpact(asset="WTI", bias="bullish", confidence="moderate"),
            AssetImpact(asset="Brent", bias="bullish", confidence="moderate"),
            AssetImpact(asset="VIX", bias="bullish", confidence="moderate_to_high"),
            AssetImpact(asset="SPY", bias="bearish", confidence="moderate"),
            AssetImpact(asset="JETS", bias="bearish", confidence="moderate"),
            AssetImpact(asset="XLE", bias="bullish", confidence="moderate"),
        ]

    return []