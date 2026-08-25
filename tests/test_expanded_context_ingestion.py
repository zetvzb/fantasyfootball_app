from src.expanded_context_ingestion import ContextSignalKind, ingest_structured_context


def test_all_required_context_categories_normalize_to_explainable_documents():
    records = [
        {
            "player_name": "Player A",
            "signal_type": kind.value,
            "direction": -0.8 if kind in (
                ContextSignalKind.INJURY_HISTORY,
                ContextSignalKind.OFF_FIELD,
            ) else 0.8,
            "confidence": 0.9,
            "content": "Structured evidence",
        }
        for kind in ContextSignalKind
    ]

    batch = ingest_structured_context(records)

    assert len(batch.documents) == len(ContextSignalKind)
    assert {document.tags[0] for document in batch.documents} == {
        kind.value for kind in ContextSignalKind
    }
    injury = batch.documents[0]
    assert injury.injury_signal < 0
    assert injury.metadata["direction"] == -0.8
    assert batch.warnings == ()


def test_bad_optional_rows_warn_without_discarding_valid_context():
    batch = ingest_structured_context(
        (
            {"player_name": "", "signal_type": "snap_share", "direction": 1},
            {"player_name": "Player", "signal_type": "unknown", "direction": 1},
            {"player_name": "Player", "signal_type": "target_share", "direction": 0.5},
        )
    )

    assert len(batch.documents) == 1
    assert len(batch.warnings) == 2
    assert batch.documents[0].usage_signal == 0.5
