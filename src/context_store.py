import json
import sqlite3

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.player_context import (
    ContextDocument,
    build_player_context_summary,
    parse_datetime,
)


# =========================================================
# STORE
# =========================================================

class ContextStore:

    def __init__(
        self,
        db_path="data/player_context.db",
    ):

        self.db_path = Path(
            db_path
        )


        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        self.initialize()


    # =====================================================
    # CONNECTION
    # =====================================================

    def connect(
        self,
    ):

        return sqlite3.connect(
            str(
                self.db_path
            )
        )


    # =====================================================
    # INITIALIZE
    # =====================================================

    def initialize(
        self,
    ):

        with self.connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS context_documents (
                    document_id TEXT PRIMARY KEY,
                    player_name TEXT NOT NULL,
                    position TEXT,
                    nfl_team TEXT,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    published_at TEXT,
                    url TEXT,
                    confidence REAL NOT NULL,
                    role_signal REAL NOT NULL,
                    usage_signal REAL NOT NULL,
                    injury_signal REAL NOT NULL,
                    dynasty_signal REAL NOT NULL,
                    tags_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )


            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_context_player
                ON context_documents(player_name)
                """
            )


            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_context_source
                ON context_documents(source_type)
                """
            )


            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_context_published
                ON context_documents(published_at)
                """
            )


            connection.commit()


    # =====================================================
    # UPSERT
    # =====================================================

    def add_document(
        self,
        document,
    ):

        published_at = None


        if document.published_at:

            published_at = (
                document
                .published_at
                .isoformat()
            )


        now = datetime.utcnow().isoformat()


        with self.connect() as connection:

            connection.execute(
                """
                INSERT INTO context_documents (
                    document_id,
                    player_name,
                    position,
                    nfl_team,
                    source_type,
                    source_name,
                    title,
                    content,
                    published_at,
                    url,
                    confidence,
                    role_signal,
                    usage_signal,
                    injury_signal,
                    dynasty_signal,
                    tags_json,
                    metadata_json,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(document_id)
                DO UPDATE SET
                    player_name = excluded.player_name,
                    position = excluded.position,
                    nfl_team = excluded.nfl_team,
                    source_type = excluded.source_type,
                    source_name = excluded.source_name,
                    title = excluded.title,
                    content = excluded.content,
                    published_at = excluded.published_at,
                    url = excluded.url,
                    confidence = excluded.confidence,
                    role_signal = excluded.role_signal,
                    usage_signal = excluded.usage_signal,
                    injury_signal = excluded.injury_signal,
                    dynasty_signal = excluded.dynasty_signal,
                    tags_json = excluded.tags_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    document.document_id,
                    document.player_name,
                    document.position,
                    document.nfl_team,
                    document.source_type,
                    document.source_name,
                    document.title,
                    document.content,
                    published_at,
                    document.url,
                    document.confidence,
                    document.role_signal,
                    document.usage_signal,
                    document.injury_signal,
                    document.dynasty_signal,
                    json.dumps(
                        document.tags
                    ),
                    json.dumps(
                        document.metadata
                    ),
                    now,
                ),
            )


            connection.commit()


    def add_documents(
        self,
        documents,
    ):

        for document in documents:

            self.add_document(
                document
            )


    # =====================================================
    # ROW → OBJECT
    # =====================================================

    def row_to_document(
        self,
        row,
    ):

        return ContextDocument(
            document_id=row[0],
            player_name=row[1],
            position=row[2],
            nfl_team=row[3],
            source_type=row[4],
            source_name=row[5],
            title=row[6],
            content=row[7],
            published_at=(
                parse_datetime(
                    row[8]
                )
            ),
            url=row[9],
            confidence=row[10],
            role_signal=row[11],
            usage_signal=row[12],
            injury_signal=row[13],
            dynasty_signal=row[14],
            tags=json.loads(
                row[15]
                or "[]"
            ),
            metadata=json.loads(
                row[16]
                or "{}"
            ),
        )


    # =====================================================
    # PLAYER DOCUMENTS
    # =====================================================

    def get_player_documents(
        self,
        player_name,
        limit=50,
    ) -> List[ContextDocument]:

        with self.connect() as connection:

            rows = (
                connection.execute(
                    """
                    SELECT
                        document_id,
                        player_name,
                        position,
                        nfl_team,
                        source_type,
                        source_name,
                        title,
                        content,
                        published_at,
                        url,
                        confidence,
                        role_signal,
                        usage_signal,
                        injury_signal,
                        dynasty_signal,
                        tags_json,
                        metadata_json
                    FROM context_documents
                    WHERE player_name = ?
                    ORDER BY
                        published_at DESC
                    LIMIT ?
                    """,
                    (
                        player_name,
                        int(
                            limit
                        ),
                    ),
                )
                .fetchall()
            )


        return [
            self.row_to_document(
                row
            )

            for row
            in rows
        ]


    # =====================================================
    # KEYWORD / METADATA RETRIEVAL
    # =====================================================

    def search(
        self,
        query,
        player_name=None,
        limit=20,
    ) -> List[ContextDocument]:

        search_value = (
            "%"
            +
            str(
                query
            ).lower()
            +
            "%"
        )


        sql = """
            SELECT
                document_id,
                player_name,
                position,
                nfl_team,
                source_type,
                source_name,
                title,
                content,
                published_at,
                url,
                confidence,
                role_signal,
                usage_signal,
                injury_signal,
                dynasty_signal,
                tags_json,
                metadata_json
            FROM context_documents
            WHERE (
                LOWER(title) LIKE ?
                OR
                LOWER(content) LIKE ?
                OR
                LOWER(tags_json) LIKE ?
            )
        """


        parameters = [
            search_value,
            search_value,
            search_value,
        ]


        if player_name:

            sql += (
                " AND player_name = ? "
            )

            parameters.append(
                player_name
            )


        sql += """
            ORDER BY
                published_at DESC
            LIMIT ?
        """


        parameters.append(
            int(
                limit
            )
        )


        with self.connect() as connection:

            rows = (
                connection.execute(
                    sql,
                    parameters,
                )
                .fetchall()
            )


        return [
            self.row_to_document(
                row
            )

            for row
            in rows
        ]


    # =====================================================
    # PLAYER SUMMARY
    # =====================================================

    def get_player_summary(
        self,
        player_name,
        limit=50,
    ):

        documents = (
            self.get_player_documents(
                player_name=(
                    player_name
                ),
                limit=(
                    limit
                ),
            )
        )


        return (
            build_player_context_summary(
                player_name=(
                    player_name
                ),
                documents=(
                    documents
                ),
            )
        )


    # =====================================================
    # COUNT
    # =====================================================

    def count(
        self,
    ):

        with self.connect() as connection:

            row = (
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM context_documents
                    """
                )
                .fetchone()
            )


        return int(
            row[0]
        )