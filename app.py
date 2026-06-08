import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st
from openai import OpenAI
from mixpanel import Mixpanel
import mixpanel

from components.ui import (
    load_css,
    render_hero,
    render_step_card,
    render_step_arrow,
    show_ai_loader,
)

from services.data_loader import load_creator_data
from services.scoring import enrich_creator_data


# --------------------------------------------------
# Page setup
# --------------------------------------------------
st.set_page_config(
    page_title="CampaignPilot AI",
    page_icon="✈️",
    layout="wide",
)

load_css("assets/styles.css")
render_hero()


# --------------------------------------------------
# Secrets
# --------------------------------------------------
def get_required_secret(key: str) -> str:
    """Read required secret from Streamlit secrets."""
    try:
        value = st.secrets[key]
        if not value:
            raise KeyError
        return value
    except Exception:
        st.error(
            f"Missing secret: {key}. "
            "Please add it to .streamlit/secrets.toml locally or Streamlit Cloud Secrets."
        )
        st.stop()


OPENAI_API_KEY = get_required_secret("OPENAI_API_KEY")
MIXPANEL_TOKEN = get_required_secret("MIXPANEL_TOKEN")
MIXPANEL_REGION = st.secrets.get("MIXPANEL_REGION", "US")

openai_client = OpenAI(api_key=OPENAI_API_KEY)


# --------------------------------------------------
# Mixpanel setup
# --------------------------------------------------
def get_mixpanel_client() -> Mixpanel:
    """Create Mixpanel client. Use EU endpoint if configured."""
    if str(MIXPANEL_REGION).upper() == "EU":
        return Mixpanel(
            MIXPANEL_TOKEN,
            consumer=mixpanel.Consumer(api_host="api-eu.mixpanel.com"),
        )

    return Mixpanel(MIXPANEL_TOKEN)


mp = get_mixpanel_client()


def get_distinct_id() -> str:
    """Generate one anonymous demo user ID per Streamlit session."""
    if "distinct_id" not in st.session_state:
        st.session_state["distinct_id"] = f"demo_user_{uuid.uuid4()}"

    return st.session_state["distinct_id"]


def track_event(event_name: str, properties: Optional[Dict[str, Any]] = None) -> None:
    """Track user behavior in Mixpanel without breaking the app if tracking fails."""
    properties = properties or {}

    base_properties = {
        "project": "CampaignPilot AI",
        "environment": "portfolio_demo",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    try:
        mp.track(
            get_distinct_id(),
            event_name,
            {**base_properties, **properties},
        )
    except Exception as error:
        st.warning(f"Mixpanel tracking failed: {error}")


if "app_loaded_tracked" not in st.session_state:
    track_event("app_loaded")
    st.session_state["app_loaded_tracked"] = True


# --------------------------------------------------
# Data loading
# --------------------------------------------------
raw_df = load_creator_data("data/creators.csv")
df = enrich_creator_data(raw_df)


# --------------------------------------------------
# OpenAI recommendation logic
# --------------------------------------------------
def generate_ai_recommendation(
    campaign_brief: Dict[str, Any],
    creator: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate structured next-best-action recommendation using OpenAI API."""

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "campaign_health": {
                "type": "string",
                "enum": ["Healthy", "At Risk", "Critical"],
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
                    "no_action_needed",
                ],
            },
            "priority": {
                "type": "string",
                "enum": ["Low", "Medium", "High"],
            },
            "reason": {
                "type": "string",
            },
            "risk_signals": {
                "type": "array",
                "items": {"type": "string"},
            },
            "suggested_message": {
                "type": "string",
            },
        },
        "required": [
            "campaign_health",
            "recommended_action",
            "priority",
            "reason",
            "risk_signals",
            "suggested_message",
        ],
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
- If no message is needed, return a short operational note in suggested_message.
- Do not invent data that is not provided.
- Return JSON only.
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate structured JSON next-best-action recommendations "
                    "for influencer campaign managers."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "next_best_action_recommendation",
                "strict": True,
                "schema": schema,
            },
        },
    )

    content = response.choices[0].message.content
    return json.loads(content)


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def format_int(value: Any) -> str:
    """Format integer-like values with commas."""
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def parse_budget(value: str) -> int:
    """Parse budget string like 3,000 or €3,000 into int."""
    try:
        cleaned = value.replace(",", "").replace("€", "").strip()
        return int(cleaned)
    except ValueError:
        return 3000


def format_action_label(action: str) -> str:
    """Convert snake_case action into readable label."""
    return action.replace("_", " ").title()


# --------------------------------------------------
# 1. Campaign setup
# --------------------------------------------------
render_step_card(
    1,
    "Campaign Setup",
    "Define the campaign context so the AI can understand the brand, market, goal, and operating constraints.",
)

col1, col2, col3 = st.columns(3)

with col1:
    brand = st.text_input("Brand", "COSRX")
    market = st.selectbox("Target Market", ["France", "Korea", "US", "Global"])

with col2:
    campaign_goal = st.selectbox(
        "Campaign Goal",
        [
            "Product awareness",
            "UGC creation",
            "Affiliate conversion",
            "Product launch",
        ],
    )
    product_type = st.text_input("Product Type", "Skincare")

with col3:
    timeline = st.slider("Timeline - days", 7, 30, 14)
    budget_input = st.text_input("Budget EUR", "3,000")

budget = parse_budget(budget_input)

campaign_brief = {
    "brand": brand,
    "market": market,
    "campaign_goal": campaign_goal,
    "product_type": product_type,
    "timeline_days": timeline,
    "budget_eur": budget,
}


# --------------------------------------------------
# Arrow to Step 2
# --------------------------------------------------
render_step_arrow("Campaign Health check")


# --------------------------------------------------
# 2. Campaign health
# --------------------------------------------------
render_step_card(
    2,
    "Campaign Health check",
    "Track creator progress from form sent to publication, and identify where the campaign may be slowing down.",
)

stage_counts = df["campaign_stage"].value_counts().to_dict()

form_sent_count = stage_counts.get("Form Sent", 0)
shortlisted_count = stage_counts.get("Shortlisted", 0)
shipped_count = stage_counts.get("Product Shipped", 0)
draft_requested_count = stage_counts.get("Draft Requested", 0)
published_count = stage_counts.get("Published", 0)
paid_count = stage_counts.get("Paid", 0)

metric_cols = st.columns(6)

metric_cols[0].metric("Form Sent", form_sent_count)
metric_cols[1].metric("Shortlisted", shortlisted_count)
metric_cols[2].metric("Shipped", shipped_count)
metric_cols[3].metric("Drafted", draft_requested_count)
metric_cols[4].metric("Published", published_count)
metric_cols[5].metric("Paid", paid_count)


# --------------------------------------------------
# Arrow to Step 3
# --------------------------------------------------
render_step_arrow("Creator Action Table")


# --------------------------------------------------
# 3. Creator action table
# --------------------------------------------------
render_step_card(
    3,
    "Creator Action Table",
    "Review enriched creator workflow data, including response status, deadline risk, and priority score.",
)

table_columns = [
    "creator_name",
    "platform",
    "country",
    "niche",
    "followers",
    "engagement_rate",
    "audience_fit",
    "campaign_stage",
    "response_status",
    "shipping_status",
    "deadline_days_left",
    "brand_safety_risk",
    "priority_score",
    "priority_level",
]

available_columns = [col for col in table_columns if col in df.columns]
creator_table = df[available_columns].copy()

if "followers" in creator_table.columns:
    creator_table["followers"] = creator_table["followers"].apply(format_int)

if "engagement_rate" in creator_table.columns:
    creator_table["engagement_rate"] = creator_table["engagement_rate"].apply(
        lambda x: f"{x}%"
    )

if "audience_fit" in creator_table.columns:
    creator_table["audience_fit"] = creator_table["audience_fit"].apply(
        lambda x: f"{x}/100"
    )

if "deadline_days_left" in creator_table.columns:
    creator_table["deadline_days_left"] = creator_table["deadline_days_left"].apply(
        lambda x: f"{x} days"
    )

display_column_names = {
    "creator_name": "Creator",
    "platform": "Platform",
    "country": "Country",
    "niche": "Niche",
    "followers": "Followers",
    "engagement_rate": "Engagement",
    "audience_fit": "Audience Fit",
    "campaign_stage": "Stage",
    "response_status": "Response",
    "shipping_status": "Shipping",
    "deadline_days_left": "Deadline",
    "brand_safety_risk": "Brand Risk",
    "priority_score": "Priority Score",
    "priority_level": "Priority",
}

creator_table = creator_table.rename(columns=display_column_names)

st.markdown(
    f"""
    <div class="table-card">
        {creator_table.to_html(index=False, classes="pretty-table", border=0)}
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# Arrow to Step 4
# --------------------------------------------------
render_step_arrow("AI Recommendation")


# --------------------------------------------------
# 4. AI recommendation
# --------------------------------------------------
render_step_card(
    4,
    "AI Next-Best-Action Recommendation",
    "Generate an explainable AI recommendation based on campaign context and creator workflow signals.",
)

creator_names = df["creator_name"].tolist()

select_left, select_mid, select_right = st.columns([1, 1.15, 1])

with select_mid:
    selected_creator_name = st.selectbox(
        "Select creator",
        creator_names,
        key="selected_creator_name",
    )

selected_creator_row = df[df["creator_name"] == selected_creator_name].iloc[0]
selected_creator = selected_creator_row.to_dict()

if st.session_state.get("last_selected_creator") != selected_creator_name:
    track_event(
        "creator_selected",
        {
            "creator_id": selected_creator["creator_id"],
            "creator_name": selected_creator["creator_name"],
            "campaign_stage": selected_creator["campaign_stage"],
            "priority_score": selected_creator["priority_score"],
            "priority_level": selected_creator["priority_level"],
        },
    )
    st.session_state["last_selected_creator"] = selected_creator_name


creator_summary_cols = st.columns(4)

creator_summary_cols[0].metric(
    "Priority Score",
    selected_creator["priority_score"],
)

creator_summary_cols[1].metric(
    "Priority Level",
    selected_creator["priority_level"],
)

creator_summary_cols[2].metric(
    "Audience Fit",
    f'{selected_creator["audience_fit"]}/100',
)

creator_summary_cols[3].metric(
    "Deadline Left",
    f'{selected_creator["deadline_days_left"]} days',
)


button_left, button_mid, button_right = st.columns([1.3, 1, 1.3])

with button_mid:
    generate_button = st.button(
        "Generate AI Recommendation",
        type="primary",
        use_container_width=True,
    )

    st.markdown(
        """
        <div class="ai-cta-note">
            Click to generate an AI-powered next-best-action recommendation.<br>
            <span>OpenAI API will be called and usage cost may occur.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

if generate_button:
    track_event(
        "ai_recommendation_requested",
        {
            "creator_id": selected_creator["creator_id"],
            "creator_name": selected_creator["creator_name"],
            "campaign_stage": selected_creator["campaign_stage"],
            "priority_score": selected_creator["priority_score"],
            "priority_level": selected_creator["priority_level"],
        },
    )

    loader_placeholder = st.empty()
    show_ai_loader(loader_placeholder)

    try:
        recommendation = generate_ai_recommendation(
            campaign_brief=campaign_brief,
            creator=selected_creator,
        )

        st.session_state["recommendation"] = recommendation
        st.session_state["recommendation_creator_id"] = selected_creator["creator_id"]
        st.session_state["recommendation_creator_name"] = selected_creator["creator_name"]

        loader_placeholder.empty()

        track_event(
            "ai_recommendation_generated",
            {
                "creator_id": selected_creator["creator_id"],
                "creator_name": selected_creator["creator_name"],
                "recommended_action": recommendation["recommended_action"],
                "priority": recommendation["priority"],
                "campaign_health": recommendation["campaign_health"],
            },
        )

    except Exception as error:
        loader_placeholder.empty()

        st.error(f"OpenAI API failed: {error}")

        track_event(
            "ai_recommendation_failed",
            {
                "creator_id": selected_creator["creator_id"],
                "creator_name": selected_creator["creator_name"],
                "error": str(error),
            },
        )


# --------------------------------------------------
# Display AI recommendation
# --------------------------------------------------
recommendation = st.session_state.get("recommendation")
recommendation_creator_id = st.session_state.get("recommendation_creator_id")

if recommendation and recommendation_creator_id == selected_creator["creator_id"]:
    st.markdown("### AI Recommendation")

    rec_cols = st.columns(3)

    rec_cols[0].metric(
        "Campaign Health",
        recommendation["campaign_health"],
    )

    rec_cols[1].metric(
        "Priority",
        recommendation["priority"],
    )

    rec_cols[2].metric(
        "Recommended Action",
        format_action_label(recommendation["recommended_action"]),
    )

    st.markdown("#### Reason")
    st.write(recommendation["reason"])

    st.markdown("#### Risk Signals")

    if recommendation["risk_signals"]:
        for risk in recommendation["risk_signals"]:
            st.write(f"- {risk}")
    else:
        st.write("- No major risk signal detected.")

    st.markdown("#### Suggested Message")

    edited_message = st.text_area(
        "AI-generated message",
        value=recommendation["suggested_message"],
        height=150,
        key=f"suggested_message_{selected_creator['creator_id']}",
    )

    accept_col, reject_col = st.columns(2)

    with accept_col:
        if st.button("Accept AI Recommendation"):
            track_event(
                "ai_recommendation_accepted",
                {
                    "creator_id": selected_creator["creator_id"],
                    "creator_name": selected_creator["creator_name"],
                    "recommended_action": recommendation["recommended_action"],
                    "priority": recommendation["priority"],
                    "campaign_health": recommendation["campaign_health"],
                    "message_edited": edited_message
                    != recommendation["suggested_message"],
                },
            )

            st.success("Recommendation accepted. Event sent to Mixpanel.")

    with reject_col:
        if st.button("Reject AI Recommendation"):
            track_event(
                "ai_recommendation_rejected",
                {
                    "creator_id": selected_creator["creator_id"],
                    "creator_name": selected_creator["creator_name"],
                    "recommended_action": recommendation["recommended_action"],
                    "priority": recommendation["priority"],
                    "campaign_health": recommendation["campaign_health"],
                },
            )

            st.info("Recommendation rejected. Event sent to Mixpanel.")

elif recommendation and recommendation_creator_id != selected_creator["creator_id"]:
    st.info(
        "A recommendation was generated for another creator. "
        "Click the button above to generate a new recommendation for the selected creator."
    )


# --------------------------------------------------
# Arrow to Step 5
# --------------------------------------------------
render_step_arrow("Product Analytics")


# --------------------------------------------------
# 5. Analytics tracking plan
# --------------------------------------------------
render_step_card(
    5,
    "Product Analytics Tracking",
    "Mixpanel tracks how users interact with the AI feature, so the product team can measure adoption, trust, and workflow impact.",
)

tracking_plan = pd.DataFrame(
    [
        {
            "Event Name": "app_loaded",
            "When It Fires": "User opens the demo app",
            "Key Properties": "project, environment, timestamp_utc",
        },
        {
            "Event Name": "creator_selected",
            "When It Fires": "User selects a creator",
            "Key Properties": "creator_id, creator_name, campaign_stage, priority_score",
        },
        {
            "Event Name": "ai_recommendation_requested",
            "When It Fires": "User clicks Get AI Recommendation",
            "Key Properties": "creator_id, campaign_stage, priority_score",
        },
        {
            "Event Name": "ai_recommendation_generated",
            "When It Fires": "OpenAI returns a structured recommendation",
            "Key Properties": "recommended_action, priority, campaign_health",
        },
        {
            "Event Name": "ai_recommendation_accepted",
            "When It Fires": "User accepts the AI recommendation",
            "Key Properties": "recommended_action, priority, message_edited",
        },
        {
            "Event Name": "ai_recommendation_rejected",
            "When It Fires": "User rejects the AI recommendation",
            "Key Properties": "recommended_action, priority, campaign_health",
        },
        {
            "Event Name": "ai_recommendation_failed",
            "When It Fires": "OpenAI API request fails",
            "Key Properties": "creator_id, error",
        },
    ]
)

st.markdown(
    f"""
    <div class="table-card">
        {tracking_plan.to_html(index=False, classes="pretty-table", border=0)}
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# Footer
# --------------------------------------------------
st.markdown(
    """
    <br>
    <div class="project-focus-card">
        <h3>Project Focus</h3>
        <p>
            CampaignPilot AI demonstrates how creator workflow data, campaign funnel status,
            OpenAI-generated recommendations, and Mixpanel event tracking can work together
            to support scalable influencer campaign operations.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)