"""File-based memory store (YAML index + Markdown content)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any
import math
import yaml
from re import sub

from nexus.memory.types import (
    MemoryEntry,
    MemoryContent,
    MemoryQuery,
    MemoryRelation,
    MemoryType,
    RecordStatus,
    RecallResult,
    RecallScoreBreakdown,
    DroppedCandidate,
    utc_now,
)
from nexus.memory.paths import get_memory_entrypoint


# Schema version for index format
CURRENT_INDEX_SCHEMA_VERSION = "1.0"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _slugify(text: str) -> str:
    return sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_") or "memory"


def _graph_score(entry: MemoryEntry) -> float:
    if not entry.relations:
        return 0.0
    return min(1.0, math.log1p(len(entry.relations)) / 2.0)


def _recency_score(entry: MemoryEntry, now: datetime) -> float:
    base_time = entry.event_time or entry.created_at
    delta_days = abs((now - base_time).days)
    return max(0.0, 1.0 - delta_days / 365.0)


def _priority_score(entry: MemoryEntry) -> float:
    return max(0.0, min(1.0, entry.priority / 100.0))


def _lexical_score(query_tokens: set[str], text: str) -> float:
    if not query_tokens or not text:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for token in query_tokens if token in text_lower)
    return min(1.0, hits / len(query_tokens))


def _tokenize(text: str) -> set[str]:
    """Tokenize text into searchable tokens."""
    import re
    ascii_tokens = {t for t in re.findall(r"[A-Za-z0-9_]+", text.lower()) if len(t) >= 2}
    han_chars = set(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))
    return ascii_tokens | han_chars


class FileIndexStore:
    """YAML-based index store for memory entries."""

    def __init__(self, index_path: str | Path) -> None:
        self._path = Path(index_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, MemoryEntry] = {}
        self._load()

    def upsert(self, entry: MemoryEntry) -> None:
        self._entries[entry.id] = entry
        self._persist()

    def get(self, memory_id: str) -> MemoryEntry | None:
        return self._entries.get(memory_id)

    def list(self) -> Iterable[MemoryEntry]:
        return self._entries.values()

    def delete(self, memory_id: str) -> bool:
        if memory_id not in self._entries:
            return False
        del self._entries[memory_id]
        self._persist()
        return True

    def search(self, query: MemoryQuery) -> list[tuple[MemoryEntry, float]]:
        """Search entries by text query, returning scored results."""
        query_tokens = _tokenize(query.text)
        candidates: list[tuple[MemoryEntry, float]] = []

        for entry in self._entries.values():
            if entry.status != RecordStatus.ACTIVE:
                continue

            if query.required_tags and not query.required_tags.issubset(set(entry.tags)):
                continue

            if query.memory_types and entry.memory_type.value not in query.memory_types:
                continue

            # Compute lexical score
            text_for_search = f"{entry.name} {entry.summary} {' '.join(entry.tags)}"
            lexical = _lexical_score(query_tokens, text_for_search)

            # If no query text, just return active entries
            if not query.text and not query.required_tags:
                candidates.append((entry, 0.5))
                continue

            if lexical <= 0 and query.text:
                continue

            # Compute composite score
            recency = _recency_score(entry, query.now)
            priority = _priority_score(entry)
            graph = _graph_score(entry)

            # Weighted fusion
            final = 0.30 * lexical + 0.25 * recency + 0.25 * priority + 0.20 * graph

            candidates.append((entry, final))

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[: query.limit * 4]

    def _load(self) -> None:
        if not self._path.exists():
            return

        with self._path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        memories = data.get("memories", [])
        for item in memories:
            entry = self._entry_from_dict(item)
            self._entries[entry.id] = entry

    def _persist(self) -> None:
        payload = {
            "schema_version": CURRENT_INDEX_SCHEMA_VERSION,
            "memories": [self._entry_to_dict(entry) for entry in self._entries.values()],
        }
        with self._path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)

    @staticmethod
    def _entry_to_dict(entry: MemoryEntry) -> dict[str, Any]:
        return {
            "id": entry.id,
            "name": entry.name,
            "memory_type": entry.memory_type.value,
            "summary": entry.summary,
            "tags": entry.tags,
            "confidence": entry.confidence,
            "priority": entry.priority,
            "status": entry.status.value,
            "relations": [
                {"target_id": r.target_id, "relation": r.relation, "weight": r.weight}
                for r in entry.relations
            ],
            "source": entry.source,
            "event_time": _format_datetime(entry.event_time),
            "ttl_days": entry.ttl_days,
            "metadata": entry.metadata,
            "created_at": _format_datetime(entry.created_at),
            "updated_at": _format_datetime(entry.updated_at),
        }

    @staticmethod
    def _entry_from_dict(item: dict[str, Any]) -> MemoryEntry:
        relations = [
            MemoryRelation(
                target_id=r["target_id"],
                relation=r["relation"],
                weight=float(r.get("weight", 1.0)),
            )
            for r in item.get("relations", [])
        ]

        return MemoryEntry(
            id=item["id"],
            name=item.get("name", ""),
            memory_type=MemoryType(item.get("memory_type", MemoryType.FACT.value)),
            summary=item.get("summary", ""),
            tags=list(item.get("tags", [])),
            confidence=float(item.get("confidence", 0.5)),
            priority=int(item.get("priority", 50)),
            status=RecordStatus(item.get("status", RecordStatus.ACTIVE.value)),
            relations=relations,
            source=item.get("source", "manual"),
            event_time=_parse_datetime(item.get("event_time")),
            ttl_days=item.get("ttl_days"),
            metadata=dict(item.get("metadata", {})),
            created_at=_parse_datetime(item.get("created_at")) or utc_now(),
            updated_at=_parse_datetime(item.get("updated_at")) or utc_now(),
        )


class FileContentStore:
    """Markdown-based content store for memory bodies."""

    def __init__(self, content_dir: str | Path) -> None:
        self._dir = Path(content_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def upsert(self, content: MemoryContent) -> None:
        path = self._path_for(content.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.body, encoding="utf-8")

        if content.metadata:
            meta_path = self._metadata_path_for(content.id)
            meta_path.write_text(
                yaml.safe_dump(content.metadata, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
        elif self._metadata_path_for(content.id).exists():
            self._metadata_path_for(content.id).unlink()

    def get(self, memory_id: str) -> MemoryContent | None:
        path = self._path_for(memory_id)
        meta_path = self._metadata_path_for(memory_id)
        if not path.exists():
            return None

        metadata: dict[str, Any] = {}
        if meta_path.exists():
            loaded = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                metadata = loaded

        return MemoryContent(
            id=memory_id,
            body=path.read_text(encoding="utf-8"),
            metadata=metadata,
        )

    def delete(self, memory_id: str) -> bool:
        path = self._path_for(memory_id)
        meta_path = self._metadata_path_for(memory_id)
        deleted = False
        if path.exists():
            path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()
        return deleted

    def _path_for(self, memory_id: str) -> Path:
        return self._dir / f"{memory_id}.md"

    def _metadata_path_for(self, memory_id: str) -> Path:
        return self._dir / f"{memory_id}.meta.yaml"


class MemoryStore:
    """Combined index + content store for memories."""

    def __init__(self, cwd: str | Path | None = None) -> None:
        from nexus.memory.paths import get_project_memory_dir
        if cwd is None:
            from pathlib import Path
            cwd = Path.cwd()
        memory_dir = get_project_memory_dir(cwd)
        index_path = get_memory_entrypoint(cwd)
        # Ensure index is in memory_dir
        index_path = memory_dir / "index" / "root.yaml"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        self._index = FileIndexStore(index_path)
        content_dir = memory_dir / "content"
        self._content = FileContentStore(content_dir)

    def list(self, memory_type: MemoryType | None = None) -> list[MemoryEntry]:
        entries = list(self._index.list())
        if memory_type:
            entries = [e for e in entries if e.memory_type == memory_type]
        return sorted(entries, key=lambda e: e.updated_at, reverse=True)

    def get(self, memory_id: str) -> tuple[MemoryEntry, MemoryContent] | None:
        entry = self._index.get(memory_id)
        if entry is None:
            return None
        content = self._content.get(memory_id) or MemoryContent(id=memory_id)
        return entry, content

    def create(
        self,
        name: str,
        summary: str,
        body: str,
        memory_type: MemoryType = MemoryType.FACT,
        tags: list[str] | None = None,
        confidence: float = 0.5,
        priority: int = 50,
        source: str = "manual",
        ttl_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        memory_id = _slugify(name)
        # Ensure unique ID
        base_id = memory_id
        counter = 1
        while self._index.get(memory_id):
            memory_id = f"{base_id}_{counter}"
            counter += 1

        entry = MemoryEntry(
            id=memory_id,
            name=name,
            memory_type=memory_type,
            summary=summary,
            tags=tags or [],
            confidence=confidence,
            priority=priority,
            source=source,
            ttl_days=ttl_days,
            metadata=metadata or {},
        )
        content = MemoryContent(id=memory_id, body=body)

        self._index.upsert(entry)
        self._content.upsert(content)
        return entry

    def update(
        self,
        memory_id: str,
        name: str | None = None,
        summary: str | None = None,
        body: str | None = None,
        memory_type: MemoryType | None = None,
        tags: list[str] | None = None,
        confidence: float | None = None,
        priority: int | None = None,
        status: RecordStatus | None = None,
        ttl_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        entry = self._index.get(memory_id)
        if entry is None:
            return False

        if name is not None:
            entry.name = name
        if summary is not None:
            entry.summary = summary
        if memory_type is not None:
            entry.memory_type = memory_type
        if tags is not None:
            entry.tags = tags
        if confidence is not None:
            entry.confidence = confidence
        if priority is not None:
            entry.priority = priority
        if status is not None:
            entry.status = status
        if ttl_days is not None:
            entry.ttl_days = ttl_days
        if metadata is not None:
            entry.metadata = metadata

        entry.updated_at = utc_now()
        self._index.upsert(entry)

        if body is not None:
            content = MemoryContent(id=memory_id, body=body)
            self._content.upsert(content)

        return True

    def delete(self, memory_id: str) -> bool:
        if self._index.delete(memory_id):
            self._content.delete(memory_id)
            return True
        return False

    def recall(self, query: MemoryQuery) -> RecallResult:
        """Recall memories using hybrid scoring."""
        scored = self._index.search(query)

        result_entries: list[MemoryEntry] = []
        result_contents: dict[str, MemoryContent] = {}
        used_tokens = 0
        score_breakdown: list[RecallScoreBreakdown] = []
        dropped: list[DroppedCandidate] = []
        seen: set[str] = set()

        for entry, base_score in scored:
            memory_id = entry.id
            content = self._content.get(memory_id)
            token_cost = self._estimate_tokens(content.body if content else entry.summary)

            selected = False

            if len(result_entries) >= query.limit:
                dropped.append(DroppedCandidate(
                    memory_id=memory_id,
                    reason="limit_reached",
                    final_score=base_score,
                    token_cost=token_cost,
                ))
            elif memory_id in seen:
                dropped.append(DroppedCandidate(
                    memory_id=memory_id,
                    reason="duplicate",
                    final_score=base_score,
                    token_cost=token_cost,
                ))
            elif used_tokens + token_cost > query.budget_tokens:
                dropped.append(DroppedCandidate(
                    memory_id=memory_id,
                    reason="budget_exceeded",
                    final_score=base_score,
                    token_cost=token_cost,
                ))
            else:
                result_entries.append(entry)
                if content:
                    result_contents[memory_id] = content
                used_tokens += token_cost
                seen.add(memory_id)
                selected = True

            # Compute score breakdown
            lexical = _lexical_score(_tokenize(query.text), f"{entry.name} {entry.summary}")
            recency = _recency_score(entry, query.now)
            priority = _priority_score(entry)
            graph = _graph_score(entry)

            score_breakdown.append(RecallScoreBreakdown(
                memory_id=memory_id,
                lexical_score=lexical,
                recency_score=recency,
                priority_score=priority,
                graph_score=graph,
                final_score=base_score,
                selected=selected,
            ))

        # Expand relations if needed
        if query.relation_hops > 0:
            used_tokens = self._expand_relations(
                result_entries, result_contents, query, used_tokens, seen, dropped
            )

        return RecallResult(
            entries=result_entries,
            contents=result_contents,
            candidates_scanned=len(scored),
            used_tokens=used_tokens,
            score_breakdown=score_breakdown,
            dropped_candidates=dropped,
        )

    def _expand_relations(
        self,
        entries: list[MemoryEntry],
        contents: dict[str, MemoryContent],
        query: MemoryQuery,
        used_tokens: int,
        seen: set[str],
        dropped: list[DroppedCandidate],
    ) -> int:
        """Expand to related memories (hop expansion)."""
        for entry in list(entries):
            for relation in entry.relations:
                target_id = relation.target_id
                if target_id in seen:
                    continue

                target = self._index.get(target_id)
                if target is None or target.status != RecordStatus.ACTIVE:
                    continue

                target_content = self._content.get(target_id)
                token_cost = self._estimate_tokens(
                    target_content.body if target_content else target.summary
                )

                if used_tokens + token_cost > query.budget_tokens:
                    dropped.append(DroppedCandidate(
                        memory_id=target_id,
                        reason="budget_exceeded",
                        final_score=entry.priority / 100.0 * relation.weight,
                        token_cost=token_cost,
                    ))
                    return used_tokens

                entries.append(target)
                if target_content:
                    contents[target_id] = target_content
                used_tokens += token_cost
                seen.add(target_id)

                if len(entries) >= query.limit:
                    return used_tokens

        return used_tokens

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return max(1, len(text) // 4)
