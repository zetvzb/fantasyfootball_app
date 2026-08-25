from pathlib import Path


def test_streamlit_width_deprecation_removed():
    source_files = [Path("app.py")]
    source_files.extend(Path("src").rglob("*.py"))

    offenders = [
        str(path)
        for path in source_files
        if "use_container_width=" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_live_team_table_sorts_by_existing_cash_column():
    source = Path(
        "src/views/draft_components/live_team_state.py"
    ).read_text(encoding="utf-8")

    assert '"Live Cash": setup.live_cash' in source
    assert 'by="Live Cash"' in source
    assert 'by="Cash"' not in source
