from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from math import sqrt
import re
from typing import Any, Sequence, Tuple

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from src.auction_pool import normalize_player_name
from src.fantasypros_context import infer_news_signals
from src.player_context import ContextDocument


@dataclass(frozen=True)
class ResearchChunk:
    chunk_id: str
    filename: str
    text: str
    embedding: Tuple[float, ...]
    linked_players: Tuple[str, ...]


@dataclass(frozen=True)
class FileRagResult:
    chunks: Tuple[ResearchChunk, ...]
    documents: Tuple[ContextDocument, ...]
    warnings: Tuple[str, ...]


def extract_uploaded_text(filename: str, content: bytes) -> str:
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension == "pdf":
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if extension in ("txt", "md", "csv", "tsv", "json"):
        return content.decode("utf-8-sig", errors="replace")
    raise ValueError("Unsupported research file type: {0}".format(extension or "unknown"))


def chunk_text(text: str, chunk_words: int = 180, overlap_words: int = 30) -> Tuple[str, ...]:
    if chunk_words <= 0 or overlap_words < 0 or overlap_words >= chunk_words:
        raise ValueError("Chunk size must exceed a non-negative overlap.")
    words = text.split()
    step = chunk_words - overlap_words
    return tuple(
        " ".join(words[start:start + chunk_words])
        for start in range(0, len(words), step)
        if words[start:start + chunk_words]
    )


def local_hash_embedding(text: str, dimensions: int = 32) -> Tuple[float, ...]:
    values = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:2], "big") % dimensions
        values[bucket] += 1.0 if digest[2] % 2 else -1.0
    magnitude = sqrt(sum(value * value for value in values))
    if magnitude:
        values = [value / magnitude for value in values]
    return tuple(round(value, 6) for value in values)


def link_player_entities(text: str, player_names: Sequence[str]) -> Tuple[str, ...]:
    normalized_text = " {0} ".format(normalize_player_name(text))
    matches = []
    for player_name in sorted(player_names, key=len, reverse=True):
        normalized = normalize_player_name(player_name)
        if normalized and " {0} ".format(normalized) in normalized_text:
            matches.append(player_name)
    return tuple(dict.fromkeys(matches))


def process_research_files(
    files: Sequence[Any],
    *,
    player_names: Sequence[str],
) -> FileRagResult:
    chunks = []
    documents = []
    warnings = []
    for file_index, uploaded in enumerate(files):
        filename = str(getattr(uploaded, "name", "upload.txt"))
        content = uploaded.getvalue() if hasattr(uploaded, "getvalue") else bytes(uploaded)
        try:
            text = extract_uploaded_text(filename, content)
        except (ValueError, OSError, PdfReadError) as error:
            warnings.append("{0}: {1}".format(filename, error))
            continue
        for chunk_index, chunk_content in enumerate(chunk_text(text)):
            chunk_id = "upload:{0}:{1}:{2}".format(
                sha256(content).hexdigest()[:16], file_index, chunk_index
            )
            linked = link_player_entities(chunk_content, player_names)
            chunk = ResearchChunk(
                chunk_id=chunk_id,
                filename=filename,
                text=chunk_content,
                embedding=local_hash_embedding(chunk_content),
                linked_players=linked,
            )
            chunks.append(chunk)
            signals = infer_news_signals(chunk_content)
            for player_name in linked:
                documents.append(
                    ContextDocument(
                        document_id="{0}:{1}".format(
                            chunk_id,
                            normalize_player_name(player_name).replace(" ", "-"),
                        ),
                        player_name=player_name,
                        position=None,
                        nfl_team=None,
                        source_type="user_upload",
                        source_name=filename,
                        title="Uploaded research: {0}".format(filename),
                        content=chunk_content,
                        confidence=0.65,
                        role_signal=signals["role_signal"],
                        usage_signal=signals["usage_signal"],
                        injury_signal=signals["injury_signal"],
                        dynasty_signal=signals["dynasty_signal"],
                        tags=["user_upload", "rag"],
                        metadata={
                            "chunk_id": chunk_id,
                            "embedding": chunk.embedding,
                            "evidence_class": "soft_signal",
                        },
                    )
                )
    return FileRagResult(tuple(chunks), tuple(documents), tuple(warnings))
