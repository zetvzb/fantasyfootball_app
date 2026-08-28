from __future__ import annotations

from html import escape

import streamlit as st

_ACCENT = "#6C6CF5"
_ACCENT_SOFT = "rgba(108, 108, 245, 0.16)"
_SURFACE = "#171B26"
_SURFACE_BORDER = "rgba(231, 233, 242, 0.10)"
_TEXT_MUTED = "#A7ADBE"

_CSS = """
<style>
/* ---- App shell: denser, calmer, and responsive on laptop screens ---- */
.stApp {{
    background:
        radial-gradient(circle at 76% -12%, {accent_soft}, transparent 28rem),
        #0F1117;
}}
.block-container {{
    max-width: 1500px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}}
section[data-testid="stSidebar"] {{
    border-right: 1px solid {border};
}}
section[data-testid="stSidebar"] > div {{
    background: linear-gradient(180deg, rgba(108, 108, 245, 0.07), transparent 14rem);
}}

/* ---- Product identity and active-view context ---- */
.copilot-brand {{
    display: flex;
    align-items: center;
    gap: 0.65rem;
    margin: 0.25rem 0 0.8rem;
}}
.copilot-brand-mark {{
    display: grid;
    width: 2rem;
    height: 2rem;
    place-items: center;
    border: 1px solid rgba(108, 108, 245, 0.45);
    border-radius: 0.65rem;
    background: {accent_soft};
}}
.copilot-brand-name {{
    color: #F7F8FC;
    font-size: 0.95rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    line-height: 1.1;
}}
.copilot-brand-tagline {{
    color: {text_muted};
    font-size: 0.72rem;
    line-height: 1.3;
}}
.copilot-page-header {{
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
    margin: 0 0 1.5rem;
    padding: 0 0 1.1rem;
    border-bottom: 1px solid {border};
}}
.copilot-eyebrow {{
    color: #9B9BFF;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.11em;
    text-transform: uppercase;
}}
.copilot-page-title {{
    margin: 0.2rem 0 0;
    color: #F7F8FC;
    font-size: clamp(1.65rem, 3vw, 2.35rem);
    font-weight: 750;
    letter-spacing: -0.035em;
    line-height: 1.08;
}}
.copilot-page-meta {{
    color: {text_muted};
    font-size: 0.8rem;
    text-align: right;
    white-space: nowrap;
}}

/* ---- Headings: consistent rhythm + a quiet accent rule under h2 ---- */
h1, h2, h3 {{
    letter-spacing: -0.01em;
}}
h2 {{
    padding-bottom: 0.35rem;
    border-bottom: 1px solid {border};
    margin-bottom: 0.9rem !important;
}}

/* ---- st.metric: give each stat a card instead of bare text ---- */
[data-testid="stMetric"] {{
    background: linear-gradient(145deg, rgba(255,255,255,0.025), transparent), {surface};
    border: 1px solid {border};
    border-radius: 12px;
    padding: 0.9rem 1rem 0.8rem 1rem;
    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
}}
[data-testid="stMetricLabel"] {{
    opacity: 0.75;
}}

/* ---- Primary buttons: a touch more presence ---- */
button[kind="primary"], button[data-testid="baseButton-primary"] {{
    box-shadow: 0 1px 0 rgba(0,0,0,0.25);
    transition: transform 80ms ease, box-shadow 120ms ease;
}}
button:focus-visible, [role="tab"]:focus-visible, input:focus-visible {{
    outline: 2px solid #9B9BFF !important;
    outline-offset: 2px;
}}
button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover {{
    box-shadow: 0 2px 10px {accent_soft};
}}

/* ---- Tabs: clearer active state ---- */
[data-baseweb="tab-list"] {{
    gap: 0.25rem;
}}
[data-baseweb="tab-highlight"] {{
    background-color: {accent} !important;
}}

/* ---- Expanders: subtle card treatment so sections read as grouped ---- */
[data-testid="stExpander"] {{
    border: 1px solid {border};
    border-radius: 10px;
}}

/* ---- Sidebar: tighten vertical rhythm across the many captions/expanders ---- */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
    gap: 0.5rem;
}}
section[data-testid="stSidebar"] hr {{
    margin: 0.6rem 0;
}}

/* ---- Dataframes: soften the hard edge ---- */
[data-testid="stDataFrame"] {{
    border-radius: 8px;
    overflow: hidden;
}}

/* ---- Forms and status messages: consistent production surfaces ---- */
[data-testid="stForm"], [data-testid="stAlert"] {{
    border-radius: 12px;
}}
[data-baseweb="select"] > div, [data-baseweb="input"] > div {{
    border-radius: 9px;
}}

@media (max-width: 900px) {{
    .block-container {{
        padding-top: 1.25rem;
    }}
    .copilot-page-header {{
        align-items: flex-start;
        flex-direction: column;
    }}
    .copilot-page-meta {{
        text-align: left;
        white-space: normal;
    }}
}}

@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
    }}
}}
</style>
"""


def build_global_css() -> str:
    """Return the shared CSS so it can be validated without Streamlit."""

    return _CSS.format(
        accent=_ACCENT,
        accent_soft=_ACCENT_SOFT,
        surface=_SURFACE,
        border=_SURFACE_BORDER,
        text_muted=_TEXT_MUTED,
    )


def inject_global_styles() -> None:
    """Apply a light layer of shared CSS on top of the .streamlit theme.

    Call once, right after st.set_page_config. Only touches spacing/borders/
    hover states -- no per-view markup changes required, so it's safe to
    apply globally without auditing every view.
    """

    st.markdown(
        build_global_css(),
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    """Render the compact product identity at the top of the sidebar."""

    st.sidebar.markdown(
        """
        <div class="copilot-brand">
          <div class="copilot-brand-mark" aria-hidden="true">🏈</div>
          <div>
            <div class="copilot-brand-name">Draft Copilot</div>
            <div class="copilot-brand-tagline">Fast, explainable draft decisions</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_product_header(league_name: str, season: int, view_name: str) -> None:
    """Render the current workspace context as a production-style header."""

    safe_league_name = escape(str(league_name))
    safe_view_name = escape(str(view_name).lstrip("🏠🧭🚨🐍📚🧠🔎📋 "))
    st.markdown(
        """
        <header class="copilot-page-header">
          <div>
            <div class="copilot-eyebrow">Fantasy Draft Copilot</div>
            <div class="copilot-page-title">{0}</div>
          </div>
          <div class="copilot-page-meta">{1} season&nbsp;&nbsp;·&nbsp;&nbsp;{2}</div>
        </header>
        """.format(safe_league_name, int(season), safe_view_name),
        unsafe_allow_html=True,
    )
