import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.models import AnswerWorkspace, HistoryItem, Source


class HistoryStore:
    """SQLite persistence for saved questions, answers, and evidence boards."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def add(
        self,
        *,
        version: str,
        question: str,
        answer: str,
        sources: list[Source],
        workspace: AnswerWorkspace | None,
    ) -> HistoryItem:
        """Save one completed ask response and return the stored item."""
        item = HistoryItem(
            id=uuid4().hex,
            createdAt=datetime.now(timezone.utc).isoformat(),
            version=version,
            question=question,
            answer=answer,
            sources=sources,
            workspace=workspace,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO query_history (
                    id,
                    created_at,
                    version,
                    question,
                    answer,
                    sources_json,
                    workspace_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.createdAt,
                    item.version,
                    item.question,
                    item.answer,
                    self._dump_sources(item.sources),
                    self._dump_workspace(item.workspace),
                ),
            )
        return item

    def list(self, limit: int) -> list[HistoryItem]:
        """Return saved history items, newest first."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, version, question, answer, sources_json, workspace_json
                FROM query_history
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def clear(self) -> None:
        """Delete all saved query history."""
        with self._connect() as connection:
            connection.execute("DELETE FROM query_history")

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS query_history (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    version TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    workspace_json TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_item(self, row: sqlite3.Row) -> HistoryItem:
        sources = [Source.model_validate(source) for source in json.loads(row["sources_json"])]
        workspace_json = row["workspace_json"]
        workspace = self._load_workspace(workspace_json, row["question"])
        return HistoryItem(
            id=row["id"],
            createdAt=row["created_at"],
            version=row["version"],
            question=row["question"],
            answer=row["answer"],
            sources=sources,
            workspace=workspace,
        )

    def _dump_sources(self, sources: list[Source]) -> str:
        return json.dumps([source.model_dump() for source in sources])

    def _dump_workspace(self, workspace: AnswerWorkspace | None) -> str | None:
        if workspace is None:
            return None
        return json.dumps(workspace.model_dump())

    def _load_workspace(self, workspace_json: str | None, question: str) -> AnswerWorkspace | None:
        if not workspace_json:
            return None
        payload = json.loads(workspace_json)
        return AnswerWorkspace.model_validate(self._normalize_workspace(payload, question))

    def _normalize_workspace(self, payload: Any, question: str) -> Any:
        if not isinstance(payload, dict):
            return payload

        task = payload.get("task")
        if not isinstance(task, dict):
            return payload

        steps = task.get("steps")
        if not isinstance(steps, list):
            return payload

        normalized_steps = [
            self._normalize_workspace_step(step, index=index, question=question)
            for index, step in enumerate(steps, start=1)
        ]
        return {
            **payload,
            "task": {
                **task,
                "steps": normalized_steps,
            },
        }

    def _normalize_workspace_step(self, step: Any, *, index: int, question: str) -> Any:
        if not isinstance(step, str):
            return step

        description = " ".join(step.split())
        return {
            "id": f"S{index}",
            "title": description[:80] or f"Step {index}",
            "description": description,
            "retrievalQuery": question,
            "status": "completed",
            "evidence": [],
            "result": description,
            "gaps": [],
        }
