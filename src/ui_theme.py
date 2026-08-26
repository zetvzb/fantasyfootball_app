from __future__ import annotations

import streamlit as st

_ACCENT = "#6C6CF5"
_ACCENT_SOFT = "rgba(108, 108, 245, 0.16)"
_SURFACE = "#171B26"
_SURFACE_BORDER = "rgba(231, 233, 242, 0.10)"

_CSS = """
<style>
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
    background: {surface};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 0.85rem 1rem 0.7rem 1rem;
}}
[data-testid="stMetricLabel"] {{
    opacity: 0.75;
}}

/* ---- Primary buttons: a touch more presence ---- */
button[kind="primary"], button[data-testid="baseButton-primary"] {{
    box-shadow: 0 1px 0 rgba(0,0,0,0.25);
    transition: transform 80ms ease, box-shadow 120ms ease;
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
</style>
"""


def inject_global_styles() -> None:
    """Apply a light layer of shared CSS on top of the .streamlit theme.

    Call once, right after st.set_page_config. Only touches spacing/borders/
    hover states -- no per-view markup changes required, so it's safe to
    apply globally without auditing every view.
    """

    st.markdown(
        _CSS.format(
            accent=_ACCENT,
            accent_soft=_ACCENT_SOFT,
            surface=_SURFACE,
            border=_SURFACE_BORDER,
        ),
        unsafe_allow_html=True,
    )
