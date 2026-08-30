from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path, PurePosixPath
import threading
from typing import Mapping, Optional, Sequence, Tuple
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

import requests


STATE_URL_ENV = "FANTASYFOOTBALL_STATE_URL"
STATE_TOKEN_ENV = "FANTASYFOOTBALL_STATE_TOKEN"

PERSISTED_ROOT_FILES = {"draft_state.db"}
PERSISTED_DIRECTORIES = {
    "draft_states",
    "league_setup",
    "leagues",
    "my_guys",
    "planning_preferences",
    "strategy_profiles",
}


class ProductionPersistenceError(OSError):
    pass


class ProductionPersistenceConflict(ProductionPersistenceError):
    pass


class DurableStateArchive:
    """Mirror durable application state to an authenticated HTTP object."""

    def __init__(
        self,
        *,
        data_root: Path,
        state_url: Optional[str],
        state_token: Optional[str] = None,
        session: Optional[object] = None,
        timeout: int = 20,
    ):
        self.data_root = Path(data_root)
        self.state_url = str(state_url or "").strip() or None
        self.state_token = str(state_token or "").strip() or None
        self.session = session or requests.Session()
        self.timeout = int(timeout)
        self.remote_etag = None  # type: Optional[str]
        self.last_digest = None  # type: Optional[str]

    @classmethod
    def from_environment(
        cls,
        data_root: Path,
        environ: Optional[Mapping[str, str]] = None,
        session: Optional[object] = None,
    ) -> "DurableStateArchive":
        values = os.environ if environ is None else environ
        return cls(
            data_root=data_root,
            state_url=values.get(STATE_URL_ENV),
            state_token=values.get(STATE_TOKEN_ENV),
            session=session,
        )

    @property
    def configured(self) -> bool:
        return self.state_url is not None

    def _headers(self) -> dict:
        if not self.state_token:
            return {}
        return {"Authorization": "Bearer {0}".format(self.state_token)}

    @staticmethod
    def _raise_for_status(response: object, operation: str) -> None:
        status = int(getattr(response, "status_code", 500))
        if status == 412:
            raise ProductionPersistenceConflict(
                "Durable state changed remotely during {0}; refusing overwrite."
                .format(operation)
            )
        if status < 200 or status >= 300:
            raise ProductionPersistenceError(
                "Durable state {0} failed with HTTP {1}.".format(
                    operation, status
                )
            )

    def _persisted_files(self) -> Tuple[Path, ...]:
        if not self.data_root.exists():
            return ()
        files = []
        for path in self.data_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(self.data_root)
            if path.name.endswith((".tmp", "-wal", "-shm", "-journal", ".restore")):
                continue
            if (
                str(relative) in PERSISTED_ROOT_FILES
                or relative.parts[0] in PERSISTED_DIRECTORIES
            ):
                files.append(path)
        return tuple(sorted(files))

    def _build_archive(self) -> bytes:
        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            for path in self._persisted_files():
                try:
                    content = path.read_bytes()
                except FileNotFoundError:
                    # A concurrent write replaced this file (e.g. another
                    # checkpoint's own temp-file rename) between the
                    # directory scan above and this read -- it'll be
                    # picked up whole on the next checkpoint, so skipping
                    # it here beats failing the whole snapshot over one
                    # file that was mid-write anyway.
                    continue
                relative = path.relative_to(self.data_root).as_posix()
                member = ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                member.compress_type = ZIP_DEFLATED
                archive.writestr(member, content)
        return buffer.getvalue()

    @staticmethod
    def _validate_member(name: str) -> PurePosixPath:
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ProductionPersistenceError("Durable state archive path is unsafe.")
        if (
            str(relative) not in PERSISTED_ROOT_FILES
            and relative.parts[0] not in PERSISTED_DIRECTORIES
        ):
            raise ProductionPersistenceError(
                "Durable state archive contains an unsupported path."
            )
        return relative

    def restore(self) -> bool:
        if not self.configured:
            return False
        try:
            response = self.session.get(
                self.state_url,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise ProductionPersistenceError(
                "Durable state restore request failed."
            ) from error
        if int(getattr(response, "status_code", 500)) == 404:
            return False
        self._raise_for_status(response, "restore")
        content = bytes(getattr(response, "content", b""))
        if not content:
            return False
        try:
            with ZipFile(BytesIO(content), "r") as archive:
                members = [
                    (member, self._validate_member(member.filename))
                    for member in archive.infolist()
                    if not member.is_dir()
                ]
                self.data_root.mkdir(parents=True, exist_ok=True)
                for member, relative in members:
                    target = self.data_root.joinpath(*relative.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_suffix(target.suffix + ".restore")
                    temporary.write_bytes(archive.read(member))
                    temporary.replace(target)
        except (BadZipFile, OSError, ValueError) as error:
            raise ProductionPersistenceError(
                "Durable state archive could not be restored."
            ) from error
        self.remote_etag = getattr(response, "headers", {}).get("ETag")
        self.last_digest = sha256(content).hexdigest()
        return True

    def checkpoint(self) -> bool:
        if not self.configured:
            return False
        content = self._build_archive()
        digest = sha256(content).hexdigest()
        if digest == self.last_digest:
            return False
        headers = {
            **self._headers(),
            "Content-Type": "application/zip",
        }
        if self.remote_etag:
            headers["If-Match"] = self.remote_etag
        try:
            response = self.session.put(
                self.state_url,
                data=content,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise ProductionPersistenceError(
                "Durable state checkpoint request failed."
            ) from error
        self._raise_for_status(response, "checkpoint")
        self.remote_etag = getattr(response, "headers", {}).get("ETag")
        self.last_digest = digest
        return True


class BackgroundCheckpointer:
    """Run ``DurableStateArchive.checkpoint()`` off the caller's thread.

    The local SQLite/JSON write that triggers a checkpoint has already
    succeeded by the time we get here -- mirroring it to durable storage
    is not on the critical path of a Streamlit rerun, and a synchronous
    multi-hundred-KB HTTP upload on every recorded sale is what made the
    live-draft cockpit crawl. A single daemon worker coalesces bursts of
    requests (a live draft can fire several a second) into one upload per
    idle moment. ``checkpoint()`` already no-ops when the archived bytes
    are unchanged, so a redundant trailing upload is cheap.
    """

    def __init__(self, archive: DurableStateArchive, idle_wait: float = 30.0):
        self._archive = archive
        self._idle_wait = float(idle_wait)
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._pending = False
        self._last_error = None  # type: Optional[str]
        self._worker = None  # type: Optional[threading.Thread]

    @property
    def configured(self) -> bool:
        return self._archive.configured

    def request(self) -> None:
        """Signal that durable state changed; upload happens in the background."""

        if not self._archive.configured:
            return
        with self._lock:
            self._pending = True
        self._ensure_worker()
        self._wake.set()

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._run,
                name="durable-state-checkpoint",
                daemon=True,
            )
            self._worker.start()

    def _run(self) -> None:
        while True:
            self._wake.wait(timeout=self._idle_wait)
            self._wake.clear()
            with self._lock:
                if not self._pending:
                    continue
                self._pending = False
            self._checkpoint_once()

    def _checkpoint_once(self) -> None:
        try:
            self._archive.checkpoint()
            self._last_error = None
        except ProductionPersistenceConflict:
            self._last_error = "conflict"
        except ProductionPersistenceError as error:
            self._last_error = str(error)
        except Exception as error:  # noqa: BLE001 - the worker must never die
            self._last_error = str(error)

    def flush(self) -> None:
        """Best-effort synchronous drain -- registered at interpreter exit."""

        if not self._archive.configured:
            return
        with self._lock:
            pending = self._pending
            self._pending = False
        if pending:
            self._checkpoint_once()

    def consume_error(self) -> Optional[str]:
        """Return the most recent background failure once, then clear it."""

        error, self._last_error = self._last_error, None
        return error
