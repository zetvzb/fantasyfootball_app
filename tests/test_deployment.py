from pathlib import Path

from src.deployment import check_deployment_health, load_deployment_settings


def test_deployment_settings_use_explicit_runtime_data_directory(tmp_path):
    app_root = tmp_path / "app"
    app_root.mkdir()
    configured = tmp_path / "persistent-data"
    settings = load_deployment_settings(
        app_root,
        {
            "FANTASYFOOTBALL_DATA_DIR": str(configured),
            "FANTASYPROS_API_KEY": "secret-not-exposed",
            "FANTASYFOOTBALL_STATE_URL": "https://state.example/object",
        },
    )
    assert settings.data_root == configured.resolve()
    assert settings.fantasypros_configured is True
    assert settings.durable_state_configured is True
    assert settings.connect_cloud_runtime is False


def test_deployment_health_checks_python_dependencies_and_writable_storage(tmp_path):
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "requirements.txt").write_text("streamlit\n", encoding="utf-8")
    settings = load_deployment_settings(
        app_root,
        {"FANTASYFOOTBALL_DATA_DIR": str(tmp_path / "state")},
    )
    health = check_deployment_health(settings, python_version=(3, 9, 20))
    assert health.ready is True
    assert "Python 3.9 runtime" in health.checks
    assert "Runtime data directory writable" in health.checks


def test_wrong_python_version_fails_deployment_health(tmp_path):
    (tmp_path / "requirements.txt").write_text("streamlit\n", encoding="utf-8")
    settings = load_deployment_settings(tmp_path, {})
    health = check_deployment_health(settings, python_version=(3, 11, 0))
    assert health.ready is False
    assert "Python 3.9 is required" in health.errors[0]


def test_connect_cloud_requires_external_durable_state(tmp_path):
    (tmp_path / "requirements.txt").write_text("streamlit\n", encoding="utf-8")
    settings = load_deployment_settings(
        tmp_path,
        {
            "QUARTO_PROFILE": "connect_cloud",
            "FANTASYFOOTBALL_DATA_DIR": str(tmp_path / "runtime"),
        },
    )
    health = check_deployment_health(settings, python_version=(3, 9, 20))
    assert health.ready is False
    assert "FANTASYFOOTBALL_STATE_URL is required" in health.errors[-1]


def test_connect_cloud_accepts_configured_durable_state(tmp_path):
    (tmp_path / "requirements.txt").write_text("streamlit\n", encoding="utf-8")
    settings = load_deployment_settings(
        tmp_path,
        {
            "QUARTO_PROFILE": "connect_cloud",
            "FANTASYFOOTBALL_DATA_DIR": str(tmp_path / "runtime"),
            "FANTASYFOOTBALL_STATE_URL": "https://state.example/object",
        },
    )
    health = check_deployment_health(settings, python_version=(3, 9, 20))
    assert health.ready is True
    assert "Durable state archive configured" in health.checks
