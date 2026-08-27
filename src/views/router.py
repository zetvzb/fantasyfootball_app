from __future__ import annotations

from importlib import import_module
from typing import Callable

import streamlit as st

from src.app_runtime import AppRuntimeContext

VIEW_RENDERERS = {
    "🏠 League Setup": ("src.views.league_setup", "render_league_setup_view"),
    "🧭 Pre-Draft": ("src.views.pre_draft", "render_pre_draft_view"),
    "🚨 Draft Mode": ("src.views.draft_mode", "render_draft_mode_view"),
    "🐍 Snake Draft": ("src.views.snake_draft", "render_snake_draft_view"),
    "📚 Draft History": ("src.views.draft_history", "render_draft_history_view"),
    "🧠 Manager Intelligence": (
        "src.views.manager_intelligence",
        "render_manager_intelligence_view",
    ),
    "🔎 Player Context": ("src.views.player_context", "render_player_context_view"),
    "📋 NFL Depth Charts": ("src.views.depth_charts", "render_depth_charts_view"),
}


def load_view_renderer(view_name: str) -> Callable[[AppRuntimeContext], None]:
    """Import only the renderer selected for this Streamlit rerun."""

    module_path, function_name = VIEW_RENDERERS[view_name]
    module = import_module(module_path)
    return getattr(module, function_name)


def render_active_view(
    view_name: str,
    context: AppRuntimeContext,
) -> None:

    if view_name not in VIEW_RENDERERS:

        st.error(
            f"Unknown app view: {view_name}"
        )

        return

    load_view_renderer(view_name)(
        context
    )
