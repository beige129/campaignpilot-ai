from pathlib import Path
import streamlit as st


def load_css(file_path: str) -> None:
    """Load external CSS file into Streamlit."""
    css_path = Path(file_path)

    if not css_path.exists():
        st.warning(f"CSS file not found: {file_path}")
        return

    css = css_path.read_text(encoding="utf-8")

    st.markdown(
        f"<style>{css}</style>",
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">CampaignPilot <span>AI</span></div>
            <div class="hero-subtitle">
                A data-powered assistant that helps influencer marketing teams keep campaigns moving.
                It detects workflow bottlenecks, prioritizes creator actions, and recommends the next best step
                from invitation to publication.
            </div>
            <div class="badge-row">
                <div class="badge">AI NEXT BEST ACTION</div>
                <div class="badge">OPENAI API</div>
                <div class="badge">MIXPANEL TRACKING</div>
                <div class="badge">DATA ENRICHMENT</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_card(step: int, title: str, description: str) -> None:
    """Unified section card for every workflow step."""
    st.markdown(
        f"""
        <div class="step-card">
            <div class="step-badge">STEP {step}</div>
            <h3>{step}. {title}</h3>
            <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_arrow(next_label: str = "") -> None:
    label_html = f"<span>{next_label}</span>" if next_label else ""

    st.markdown(
        f"""
        <div class="step-divider">
            <div class="arrow-line"></div>
            <div class="arrow-circle">↓</div>
            {label_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_ai_loader(placeholder) -> None:
    placeholder.markdown(
        """
        <div class="loader-wrap">
            <div class="loader">
                <p class="loader-text">AI THINKING</p>
                <span class="load"></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )