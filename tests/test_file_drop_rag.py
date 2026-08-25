from types import SimpleNamespace

from src.file_drop_rag import (
    chunk_text,
    link_player_entities,
    local_hash_embedding,
    process_research_files,
)


def test_text_upload_chunks_embeds_links_and_builds_structured_signal():
    upload = SimpleNamespace(
        name="camp.txt",
        getvalue=lambda: (
            b"Rome Odunze has earned a starting role with first-team reps "
            b"and an increased workload."
        ),
    )

    result = process_research_files((upload,), player_names=("Rome Odunze", "Other"))

    assert len(result.chunks) == 1
    assert len(result.chunks[0].embedding) == 32
    assert result.chunks[0].linked_players == ("Rome Odunze",)
    assert result.documents[0].role_signal > 0
    assert result.documents[0].usage_signal > 0
    assert result.documents[0].metadata["evidence_class"] == "soft_signal"


def test_chunking_overlap_and_embeddings_are_deterministic():
    text = " ".join("word{0}".format(index) for index in range(12))
    chunks = chunk_text(text, chunk_words=5, overlap_words=2)

    assert chunks[0].split()[-2:] == chunks[1].split()[:2]
    assert local_hash_embedding(chunks[0]) == local_hash_embedding(chunks[0])


def test_entity_linking_uses_normalized_full_names_and_bad_files_warn():
    assert link_player_entities("News for A.J. Brown", ("A.J. Brown", "Brown")) == (
        "A.J. Brown",
        "Brown",
    )
    upload = SimpleNamespace(name="image.png", getvalue=lambda: b"data")
    result = process_research_files((upload,), player_names=())
    assert result.documents == ()
    assert "Unsupported" in result.warnings[0]
