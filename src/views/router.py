from __future__ import annotations

import streamlit as st

from src.app_runtime import AppRuntimeContext

from .draft_history import (
    render_draft_history_view,
)
from .draft_mode import (
    render_draft_mode_view,
)
from .league_setup import (
    render_league_setup_view,
)
from .pre_draft import (
    render_pre_draft_view,
)


VIEW_RENDERERS = {
    "🏠 League Setup": render_league_setup_view,
    "🧭 Pre-Draft": render_pre_draft_view,
    "🚨 Draft Mode": render_draft_mode_view,
    "📚 Draft History": render_draft_history_view,
}


def render_active_view(
    view_name: str,
    context: AppRuntimeContext,
) -> None:

    renderer = VIEW_RENDERERS.get(
        view_name
    )

    if renderer is None:

        st.error(
            f"Unknown app view: {view_name}"
        )

        return

    renderer(
        context
    )
