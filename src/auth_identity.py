from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
from typing import Mapping, Optional


AUTH_MAPPINGS_ENV = "FANTASYFOOTBALL_AUTH_MAPPINGS_JSON"


@dataclass(frozen=True)
class AuthenticatedIdentity:
    provider: str
    subject: str
    username: Optional[str] = None
    email: Optional[str] = None

    @property
    def user_key(self) -> str:
        return "{0}:{1}".format(self.provider, self.subject)


def _casefold_headers(headers: Mapping[str, object]) -> Mapping[str, str]:
    return {
        str(key).strip().lower(): str(value).strip()
        for key, value in headers.items()
        if value is not None
    }


def _decode_jwt_payload(token: str) -> dict:
    parts = str(token).split(".")
    if len(parts) < 2:
        raise ValueError("Connect Cloud session token is not a JWT.")
    encoded = parts[1].replace("-", "+").replace("_", "/")
    encoded += "=" * ((4 - len(encoded) % 4) % 4)
    try:
        payload = json.loads(base64.b64decode(encoded).decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Connect Cloud session token payload is invalid.") from error
    if not isinstance(payload, dict):
        raise ValueError("Connect Cloud session token payload must be an object.")
    return payload


def extract_authenticated_identity(
    headers: Mapping[str, object],
) -> Optional[AuthenticatedIdentity]:
    """Extract a trusted identity supplied by Posit to private content."""

    normalized = _casefold_headers(headers)
    cloud_token = normalized.get("posit-connect-user-session-token")
    if cloud_token:
        payload = _decode_jwt_payload(cloud_token)
        subject = str(payload.get("sub") or "").strip()
        if not subject:
            raise ValueError("Connect Cloud session token has no subject claim.")
        return AuthenticatedIdentity(
            provider="posit-connect-cloud",
            subject=subject,
            username=(str(payload["preferred_username"]) if payload.get("preferred_username") else None),
            email=(str(payload["email"]) if payload.get("email") else None),
        )

    credentials = normalized.get("rstudio-connect-credentials")
    if credentials:
        try:
            payload = json.loads(credentials)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("Posit Connect credentials header is invalid.") from error
        subject = str(
            payload.get("guid")
            or payload.get("user_guid")
            or payload.get("user")
            or ""
        ).strip()
        if not subject:
            raise ValueError("Posit Connect credentials contain no stable identity.")
        return AuthenticatedIdentity(
            provider="posit-connect",
            subject=subject,
            username=(str(payload["user"]) if payload.get("user") else None),
            email=(str(payload["email"]) if payload.get("email") else None),
        )
    return None


def load_authenticated_manager_mappings(
    environ: Optional[Mapping[str, str]] = None,
) -> Mapping[str, Mapping[str, str]]:
    values = os.environ if environ is None else environ
    raw = str(values.get(AUTH_MAPPINGS_ENV) or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Authenticated manager mappings JSON is invalid.") from error
    if not isinstance(payload, dict):
        raise ValueError("Authenticated manager mappings must be an object.")
    result = {}
    for league_key, mappings in payload.items():
        if not isinstance(mappings, dict):
            raise ValueError("Each league authentication mapping must be an object.")
        result[str(league_key)] = {
            str(identity_key): str(manager_id)
            for identity_key, manager_id in mappings.items()
        }
    return result


def resolve_authenticated_manager(
    *,
    league_profile: object,
    managers: Mapping[str, object],
    identity: AuthenticatedIdentity,
    external_mappings: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> str:
    profile_mappings = dict(
        getattr(league_profile, "metadata", {}).get(
            "authenticated_user_mappings", {}
        )
        or {}
    )
    league_mappings = dict(
        (external_mappings or {}).get(str(league_profile.league_key), {})
    )
    mappings = {**profile_mappings, **league_mappings}
    manager_id = mappings.get(identity.user_key) or mappings.get(identity.subject)
    if manager_id is None:
        raise ValueError(
            "Authenticated user is not mapped to a manager in league {0}."
            .format(league_profile.league_key)
        )
    manager_id = str(manager_id)
    if manager_id not in managers:
        raise ValueError(
            "Authenticated identity mapping references unknown manager {0}."
            .format(manager_id)
        )
    return manager_id
