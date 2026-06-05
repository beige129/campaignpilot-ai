import json
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st
from openai import OpenAI
from mixpanel import Mixpanel
import mixpanel


# -----------------------------
# App setup
# -----------------------------
st.set_page_config(
    page_title="CampaignPilot AI",
    page_icon="✈️",
    layout="wide"
)

st.title("CampaignPilot AI")
st.caption("AI-powered next-best-action assistant for influencer campaign operations")


# -----------------------------
# Secrets
# -----------------------------
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
MIXPANEL_TOKEN = st.secrets["MIXPANEL_TOKEN"]
MIXPANEL_REGION = st.secrets.get("MIXPANEL_REGION", "US")

client = OpenAI(api_key=OPENAI_API_KEY)


# -----------------------------
# Mixpanel setup
# -----------------------------
def get_mixpanel_client():
    if MIXPANEL_REGION.upper() == "EU":
        return Mixpanel(
            MIXPANEL_TOKEN,
            consumer=mixpanel.Consumer(api_host="api-eu.mixpanel.com")
        )
    return Mixpanel(MIXPANEL_TOKEN)


mp = get_mixpanel_client()


def get_distinct_id():
    if "distinct_id" not in st.session_state:
        st.session_state["distinct_id"] = f"demo_user_{uuid.uuid4()}"
    return st.session_state["distinct_id"]


def track_event(event_name, properties=None):
    """Send an event to Mixpanel."""
    properties = properties or {}
    base_properties = {
        "project": "CampaignPilot AI",
        "environment": "portfolio_demo",
        "timestamp_readable": datetime.utcnow().isoformat(),
    }

    try:
        mp.track(
            get_distinct_id(),
            event_name,
            {**base_properties, **properties}
        )
    except Exception as e:
        # Do not break the app if analytics fails.
        st.warning(f"Mixpanel tracking failed: {e}")


if "app_loaded_tracked" not in st.session_state:
    track_event("app_loaded")
    st.session_state["app_loaded_tracked"] = True


# -----------------------------
# Mock creator data
# -----------------------------
creator_data = [
    {
        "creator_id": "cr_001",
        "creator_name": "MarieSkinLab",
        "platform": "Instagram",
        "country": "France",
        "niche": "Skincare",
        "followers": 85000,
        "engagement_rate": 4.8,
        "audience_fit": 92,
        "response_status": "No reply",
        "days_since_last_action": 3,
        "campaign_stage": "Form Sent",
        "shipping_status": "Not shipped",
        "deadline_days_left": 10,
        "brand_safety_risk": "Low",
    },
    {
        "creator_id": "cr_002",
        "creator_name": "GlowWithEmma",
        "platform": "TikTok",
        "country": "France",
        "niche": "Beauty Lifestyle",
        "followers": 120000,
        "engagement_rate": 3.2,
        "audience_fit": 80,
        "response_status": "Replied",
        "days_since_last_action": 1,
        "campaign_stage": "Shortlisted",
        "shipping_status": "Pending",
        "deadline_days_left": 6,
        "brand_safety_risk": "Medium",
    },
    {
        "creator_id": "cr_003",
        "creator_name": "KBeautyLina",
        "platform": "Instagram",
        "country": "France",
        "niche": "K-beauty",
        "followers": 54000,
        "engagement_rate": 5.6,
        "audience_fit": 88,
        "response_status": "No reply",
        "days_since_last_action": 5,
        "campaign_stage": "Form Sent",
        "shipping_status": "Not shipped",
        "deadline_days_left": 8,
        "brand_safety_risk": "Low",
    },
    {
        "creator_id": "cr_004",
        "creator_name": "ParisDailyStyle",
        "platform": "Instagram",
        "country": "France",
        "niche": "Lifestyle",
        "followers": 210000,
        "engagement_rate": 1.9,
        "audience_fit": 62,
        "response_status": "Replied",
        "days_since_last_action": 4,
        "campaign_stage": "Draft Requested",
        "shipping_status": "Delivered",
        "deadline_days_left": 2,
        "brand_safety_risk": "Medium",
    },
]

df = pd.DataFrame(creator_data)


# -----------------------------
# Rule-based enrichment
# -----------------------------
def calculate_priority_score(row):
    audience_component = row["audience_fit"] * 0.4
    engagement_component = min(row["engagement_rate"] * 10, 50) * 0.2

    response_risk = 0
    if row["response_status"] == "No reply":
        response_risk += 30
    if row["days_since_last_action"] >= 3:
        response_risk += 20

    deadline_risk = 0
    if row["deadline_days_left"] <= 3:
        deadline_risk += 30
    elif row["deadline_days_left"] <= 7:
        deadline_risk += 15

    stage_weight = {
        "Form Sent": 20,
        "Shortlisted": 15,
        "Draft Requested": 25,
        "Published": 5,
        "Paid": 0,
    }.get(row["campaign_stage"], 10)

    priority = audience_component + engagement_component + response_risk + deadline_risk + stage_weight
    return round(min(priority, 100), 1)


df["priority_score"] = df.apply(calculate_priority_score, axis=1)


# -----------------------------
# Campaign setup
# -----------------------------
st.subheader("1. Campaign Setup")

col1, col2, col3 = st.columns(3)

with col1:
    brand = st.text_input("Brand", "COSRX")
    market = st.selectbox("Target Market", ["France", "Korea", "US", "Global"])

with col2:
    campaign_goal = st.selectbox(
        "Campaign Goal",
        ["Product awareness", "UGC creation", "Affiliate conversion", "Product launch"]
    )
    product_type = st.text_input("Product Type", "Skincare")

with col3:
    timeline = st.slider("Timeline - days", 7, 30, 14)
    budget = st.number_input("Budget EUR", value=3000, step=500)

campaign_brief = {
    "brand": brand,
    "market": market,
    "campaign_goal": campaign_goal,
    "product_type": product_type,
    "timeline_days": timeline,
    "budget_eur": budget,
}


# -----------------------------
# Dashboard
# -----------------------------
st.subheader("2. Campaign Funnel Health")

funnel_col1, funnel_col2, funnel_col3, funnel_col4, funnel_col5 = st.columns(5)
funnel_col1.metric("Form Sent", 3)
funnel_col2.metric("Shortlisted", 1)
funnel_col3.metric("Shipped", 1)
funnel_col4.metric("Drafted", 1)
funnel_col5.metric("Published", 0)

st.subheader("3. Creator Action Table")
st.dataframe(
    df[
        [
            "creator_name",
            "platform",
            "niche",
            "audience_fit",
            "engagement_rate",
            "campaign_stage",
            "response_status",
            "deadline_days_left",
            "priority_score",
        ]
    ],
    use_container_width=True
)


# -----------------------------
# Creator selection
# -----------------------------
st.subheader("4. AI Next-Best-Action Recommendation")

creator_name = st.selectbox("Select creator", df["creator_name"].tolist())
selected_creator = df[df["creator_name"] == creator_name].iloc[0].to_dict()

track_event(
    "creator_selected",
    {
        "creator_id": selected_creator["creator_id"],
        "creator_name": selected_creator["creator_name"],
        "campaign_stage": selected_creator["campaign_stage"],
        "priority_score": selected_creator["priority_score"],
    },
)


def generate_ai_recommendation(campaign_brief, creator):
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "campaign_health": {
                "type": "string",
                "enum": ["Healthy", "At Risk", "Critical"]
            },
            "recommended_action": {
                "type": "string",
                "enum": [
                    "send_follow_up",
                    "prepare_shipment",
                    "request_draft",
                    "review_draft",
                    "replace_creator",
                    "track_performance",
                    "no_action_needed"
                ]
            },
            "priority": {
                "type": "string",
                "enum": ["Low", "Medium", "High"]
            },
            "reason": {
                "type": "string"
            },
            "risk_signals": {
                "type": "array",
                "items": {"type": "string"}
            },
            "suggested_message": {
                "type": "string"
            }
        },
        "required": [
            "campaign_health",
            "recommended_action",
            "priority",
            "reason",
            "risk_signals",
            "suggested_message"
        ]
    }

    prompt = f"""
You are an AI product assistant for influencer campaign operations.

Analyze the campaign brief and creator workflow data.
Recommend the next best action for the campaign manager.

Campaign brief:
{json.dumps(campaign_brief, indent=2)}

Creator data:
{json.dumps(creator, indent=2)}

Rules:
- Be practical and specific.
- Explain why the action is recommended.
- Mention operational risks if any.
- Generate a short follow-up message if relevant.
- Do not invent data that is not provided.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You generate structured next-best-action recommendations for influencer campaign managers."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "next_best_action_recommendation",
                "strict": True,
                "schema": schema
            }
        }
    )

    return json.loads(response.choices[0].message.content)


if st.button("Generate AI Recommendation"):
    track_event(
        "ai_recommendation_requested",
        {
            "creator_id": selected_creator["creator_id"],
            "campaign_stage": selected_creator["campaign_stage"],
            "priority_score": selected_creator["priority_score"],
        },
    )

    with st.spinner("Generating AI recommendation..."):
        try:
            recommendation = generate_ai_recommendation(campaign_brief, selected_creator)
            st.session_state["recommendation"] = recommendation

            track_event(
                "ai_recommendation_generated",
                {
                    "creator_id": selected_creator["creator_id"],
                    "recommended_action": recommendation["recommended_action"],
                    "priority": recommendation["priority"],
                    "campaign_health": recommendation["campaign_health"],
                },
            )

        except Exception as e:
            st.error(f"OpenAI API failed: {e}")
            track_event(
                "ai_recommendation_failed",
                {
                    "creator_id": selected_creator["creator_id"],
                    "error": str(e),
                },
            )


# -----------------------------
# Display recommendation
# -----------------------------
if "recommendation" in st.session_state:
    rec = st.session_state["recommendation"]

    st.markdown("### AI Recommendation")

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Campaign Health", rec["campaign_health"])
    col_b.metric("Priority", rec["priority"])
    col_c.metric("Recommended Action", rec["recommended_action"])

    st.markdown("**Reason**")
    st.write(rec["reason"])

    st.markdown("**Risk Signals**")
    for risk in rec["risk_signals"]:
        st.write(f"- {risk}")

    st.markdown("**Suggested Message**")
    st.text_area("AI-generated follow-up message", rec["suggested_message"], height=140)

    accept_col, reject_col = st.columns(2)

    with accept_col:
        if st.button("Accept AI Recommendation"):
            track_event(
                "ai_recommendation_accepted",
                {
                    "creator_id": selected_creator["creator_id"],
                    "recommended_action": rec["recommended_action"],
                    "priority": rec["priority"],
                    "campaign_health": rec["campaign_health"],
                },
            )
            st.success("Recommendation accepted. Event sent to Mixpanel.")

    with reject_col:
        if st.button("Reject AI Recommendation"):
            track_event(
                "ai_recommendation_rejected",
                {
                    "creator_id": selected_creator["creator_id"],
                    "recommended_action": rec["recommended_action"],
                    "priority": rec["priority"],
                    "campaign_health": rec["campaign_health"],
                },
            )
            st.info("Recommendation rejected. Event sent to Mixpanel.")