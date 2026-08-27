from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping


@dataclass(frozen=True)
class FantasyProsBundle:
    data: Mapping[str, Any]
    errors: Mapping[str, str]


def load_fantasypros_bundle(
    loaders: Mapping[str, Callable[[], Any]],
    max_workers: int = 3,
) -> FantasyProsBundle:
    """Fetch independent FantasyPros resources concurrently and preserve partial data."""

    if not loaders:
        return FantasyProsBundle(data={}, errors={})
    data: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    worker_count = max(1, min(int(max_workers), len(loaders)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_names = {
            executor.submit(loader): name for name, loader in loaders.items()
        }
        for future in as_completed(future_names):
            name = future_names[future]
            try:
                data[name] = future.result()
            except Exception as error:
                data[name] = {}
                errors[name] = str(error)
    return FantasyProsBundle(data=data, errors=errors)
