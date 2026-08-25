import base64
import json
from types import SimpleNamespace

import pytest

from src.auth_identity import (
    extract_authenticated_identity,
    load_authenticated_manager_mappings,
    resolve_authenticated_manager,
)
from src.runtime_identity import resolve_runtime_identity


def _token(payload):
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return "header.{0}.signature".format(encoded)


def _profile(metadata=None):
    return SimpleNamespace(
        league_key="league",
        sleeper_league_id="sleeper-league",
        sleeper_draft_id="draft",
        season=2026,
        metadata=metadata or {},
    )


def test_connect_cloud_identity_uses_stable_subject_claim():
    identity = extract_authenticated_identity(
        {
            "Posit-Connect-User-Session-Token": _token(
                {"sub": "stable-123", "preferred_username": "Zach"}
            )
        }
    )
    assert identity.provider == "posit-connect-cloud"
    assert identity.subject == "stable-123"
    assert identity.user_key == "posit-connect-cloud:stable-123"


def test_connect_server_credentials_are_supported_and_missing_headers_are_local():
    identity = extract_authenticated_identity(
        {"Rstudio-Connect-Credentials": json.dumps({"guid": "guid-1", "user": "zach"})}
    )
    assert identity.provider == "posit-connect"
    assert identity.subject == "guid-1"
    assert extract_authenticated_identity({}) is None


def test_authenticated_runtime_mapping_is_explicit_and_fails_closed():
    identity = extract_authenticated_identity(
        {"posit-connect-user-session-token": _token({"sub": "stable-123"})}
    )
    managers = {"manager": SimpleNamespace(sleeper_user_id=None)}
    mappings = {
        "league": {"posit-connect-cloud:stable-123": "manager"}
    }
    runtime = resolve_runtime_identity(
        _profile(),
        managers,
        sleeper_user_id=None,
        fallback_manager_id="manager",
        authenticated_identity=identity,
        authenticated_manager_mappings=mappings,
    )
    assert runtime.current.manager_id == "manager"
    assert runtime.current.resolution_source == "authenticated_mapping"
    assert runtime.current.user_key == "posit-connect-cloud:stable-123"

    with pytest.raises(ValueError, match="not mapped"):
        resolve_authenticated_manager(
            league_profile=_profile(),
            managers=managers,
            identity=identity,
            external_mappings={},
        )


def test_mapping_environment_is_validated_and_scoped_by_league():
    mappings = load_authenticated_manager_mappings(
        {
            "FANTASYFOOTBALL_AUTH_MAPPINGS_JSON": json.dumps(
                {"league": {"posit-connect-cloud:subject": "manager"}}
            )
        }
    )
    assert mappings["league"]["posit-connect-cloud:subject"] == "manager"
    with pytest.raises(ValueError, match="JSON is invalid"):
        load_authenticated_manager_mappings(
            {"FANTASYFOOTBALL_AUTH_MAPPINGS_JSON": "not-json"}
        )
