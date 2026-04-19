def score_credibility(raw_text: str) -> float:
    text = raw_text.lower()

    score = 40.0

    if "official" in text:
        score += 15.0
    if "white house" in text:
        score += 20.0
    if "ministry" in text or "government" in text:
        score += 20.0
    if "trump" in text:
        score += 15.0
    if "iran" in text:
        score += 10.0
    if "reportedly" in text or "rumor" in text:
        score -= 20.0

    return max(0.0, min(score, 100.0))