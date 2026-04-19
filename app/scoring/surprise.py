def score_surprise(raw_text: str) -> float:
    text = raw_text.lower()

    score = 50.0

    if "suddenly" in text or "unexpected" in text:
        score += 20.0
    if "reopened" in text or "open" in text:
        score += 15.0
    if "ceasefire" in text:
        score += 10.0
    if "confirmed" in text:
        score += 10.0

    return max(0.0, min(score, 100.0))