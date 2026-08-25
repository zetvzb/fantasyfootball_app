from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from src.league_setup_data import LeagueSetupData
from src.league_profile import LeagueProfile


@dataclass(frozen=True)
class WorkbookEnrichmentResult:
    setup_data: LeagueSetupData
    loaded: bool
    error: Optional[str] = None


def enrich_setup_from_optional_workbook(
    baseline: LeagueSetupData,
    league_profile: LeagueProfile,
    workbook_path: Optional[Path],
    loader: Optional[Callable[[str], Any]] = None,
) -> WorkbookEnrichmentResult:
    """Add workbook records when available; never require them to start."""

    if workbook_path is None:
        baseline.warnings.append(
            "No league workbook is configured. Sleeper/default setup is active."
        )
        return WorkbookEnrichmentResult(setup_data=baseline, loaded=False)

    path = Path(workbook_path)
    if not path.exists() and loader is None:
        error = "Workbook not found: {0}".format(path)
        baseline.warnings.append(error)
        return WorkbookEnrichmentResult(
            setup_data=baseline,
            loaded=False,
            error=error,
        )

    try:
        if loader is None:
            # Importing openpyxl and the Bishop workbook parser is deferred
            # until a configured workbook actually exists.
            from src.league_data import LeagueDataLoader

            workbook_data = LeagueDataLoader(path).load()
        else:
            workbook_data = loader(str(path))

        enrichment = LeagueSetupData.from_workbook(
            league_profile=league_profile,
            workbook_data=workbook_data,
        )
        return WorkbookEnrichmentResult(
            setup_data=baseline.merged_with(enrichment),
            loaded=True,
        )
    except Exception as error_value:
        error = str(error_value)
        baseline.warnings.append(
            "Workbook enrichment unavailable; continuing without it: {0}".format(
                error
            )
        )
        return WorkbookEnrichmentResult(
            setup_data=baseline,
            loaded=False,
            error=error,
        )
