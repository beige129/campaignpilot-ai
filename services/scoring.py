import pandas as pd


def calculate_priority_score(row: pd.Series) -> float:
    """Calculate a rule-based action priority score."""

    audience_component = row["audience_fit"] * 0.38
    engagement_component = min(row["engagement_rate"] * 10, 60) * 0.18

    response_risk = 0
    if row["response_status"] == "No reply":
        response_risk += 26
    if row["days_since_last_action"] >= 3:
        response_risk += 16

    deadline_risk = 0
    if row["deadline_days_left"] <= 3:
        deadline_risk += 28
    elif row["deadline_days_left"] <= 7:
        deadline_risk += 14

    stage_weight = {
        "Form Sent": 18,
        "Shortlisted": 14,
        "Product Shipped": 20,
        "Draft Requested": 24,
        "Published": 5,
        "Paid": 0,
    }.get(row["campaign_stage"], 10)

    brand_safety_penalty = {
        "Low": 0,
        "Medium": -5,
        "High": -15,
    }.get(row["brand_safety_risk"], 0)

    priority = (
        audience_component
        + engagement_component
        + response_risk
        + deadline_risk
        + stage_weight
        + brand_safety_penalty
    )

    return round(max(0, min(priority, 100)), 1)


def classify_priority(score: float) -> str:
    if score >= 75:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"


def enrich_creator_data(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Add calculated product signals to raw creator data."""

    enriched = dataframe.copy()
    enriched["priority_score"] = enriched.apply(calculate_priority_score, axis=1)
    enriched["priority_level"] = enriched["priority_score"].apply(classify_priority)

    return enriched