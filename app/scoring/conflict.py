def score_conflict(raw_text: str) -> float:
    text = raw_text.lower()

    score = 20.0

    if "but" in text:
        score += 15.0
    if "however" in text:
        score += 15.0
    if "while" in text:
        score += 10.0
    if "ceasefire" in text and "blockade" in text:
        score += 25.0
    if "open" in text and "blockade remains" in text:
        score += 30.0

    return max(0.0, min(score, 100.0))