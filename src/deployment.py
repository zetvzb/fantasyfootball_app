from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Mapping, Optional, Sequence, Tuple


DATA_DIR_ENV = "FANTASYFOOTBALL_DATA_DIR"


@dataclass(frozen=True)
class DeploymentSettings:
    app_root: Path
    data_root: Path
    fantasypros_configured: bool


@dataclass(frozen=True)
class DeploymentHealth:
    ready: bool
    checks: Tuple[str, ...]
    warnings: Tuple[str, ...]
    errors: Tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "checks": list(self.checks),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def load_deployment_settings(
    app_root: Path,
    environ: Optional[Mapping[str, str]] = None,
) -> DeploymentSettings:
    values = os.environ if environ is None else environ
    configured_data_root = str(values.get(DATA_DIR_ENV) or "").strip()
    data_root = (
        Path(configured_data_root).expanduser()
        if configured_data_root
        else Path(app_root) / "data"
    )
    if not data_root.is_absolute():
        data_root = Path(app_root) / data_root
    return DeploymentSettings(
        app_root=Path(app_root).resolve(),
        data_root=data_root.resolve(),
        fantasypros_configured=bool(
            str(values.get("FANTASYPROS_API_KEY") or "").strip()
        ),
    )


def check_deployment_health(
    settings: DeploymentSettings,
    python_version: Optional[Sequence[int]] = None,
) -> DeploymentHealth:
    version = tuple(python_version or sys.version_info[:3])
    checks = []
    warnings = []
    errors = []
    if tuple(version[:2]) == (3, 9):
        checks.append("Python 3.9 runtime")
    else:
        errors.append(
            "Python 3.9 is required; detected {0}.{1}.".format(
                version[0], version[1]
            )
        )

    requirements_path = settings.app_root / "requirements.txt"
    if requirements_path.is_file():
        checks.append("requirements.txt present beside app.py")
    else:
        errors.append("requirements.txt is missing beside app.py.")

    try:
        settings.data_root.mkdir(parents=True, exist_ok=True)
        probe = settings.data_root / ".deployment-write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as error:
        errors.append("Runtime data directory is not writable: {0}".format(error))
    else:
        checks.append("Runtime data directory writable")

    if settings.fantasypros_configured:
        checks.append("FantasyPros environment variable configured")
    else:
        warnings.append(
            "FANTASYPROS_API_KEY is absent; optional rankings/context will degrade."
        )
    if not os.environ.get(DATA_DIR_ENV):
        warnings.append(
            "FANTASYFOOTBALL_DATA_DIR is unset; local app data may be ephemeral "
            "on hosted deployments."
        )
    return DeploymentHealth(
        ready=not errors,
        checks=tuple(checks),
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def main() -> int:
    app_root = Path(__file__).resolve().parents[1]
    health = check_deployment_health(load_deployment_settings(app_root))
    print(json.dumps(health.to_dict(), indent=2))
    return 0 if health.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
