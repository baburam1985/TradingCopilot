"""
Pure-Python reasoning serializer — zero external dependencies, no LLM.

Converts a structured reasoning dict into ≤2 sentences of human-readable English.
"""


def to_english(reasoning: dict) -> str:
    """
    Convert a structured reasoning dict to human-readable English.

    Expected keys (all optional — degrades gracefully on missing keys):
        signal_type: "buy" | "sell"
        primary_indicator: str    e.g. "RSI(14)"
        indicator_value: float
        threshold: float
        supporting_factors: list[str]
        market_context: str

    Returns ≤2 sentences. Returns "" if the dict is empty or None.
    """
    if not reasoning:
        return ""

    signal_type = reasoning.get("signal_type", "")
    indicator = reasoning.get("primary_indicator", "")
    value = reasoning.get("indicator_value")
    threshold = reasoning.get("threshold")
    context = reasoning.get("market_context", "")
    factors = reasoning.get("supporting_factors") or []

    # Sentence 1 — primary signal description
    parts = []
    if indicator:
        parts.append(indicator)
        if value is not None:
            parts.append(f"= {value}")
        if threshold is not None:
            parts.append(f"(threshold: {threshold})")
    if context:
        sentence1 = " ".join(parts) + (" — " + context if parts else context) + "."
    elif parts:
        action_word = "buy" if signal_type == "buy" else "sell" if signal_type == "sell" else signal_type
        sentence1 = " ".join(parts) + (f" triggered {action_word} signal." if action_word else ".")
    else:
        sentence1 = ""

    # Sentence 2 — supporting factors
    sentence2 = ""
    if factors:
        sentence2 = "Supporting factors: " + ", ".join(str(f) for f in factors) + "."

    result = " ".join(s for s in [sentence1, sentence2] if s).strip()
    return result
