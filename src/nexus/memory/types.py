"""Memory data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryType(str, Enum):
    """Type of memory entry."""
    FACT = "fact"
    EPISODE = "episode"
    PREFERENCE = "preference"
    PROCEDURE = "procedure"


class RecordStatus(str, Enum):
    """Lifecycle status of a memory entry."""
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


@dataclass(slots=True)
class MemoryRelation:
    """Relation to another memory entry."""
    target_id: str
    relation: str
    weight: float = 1.0


@dataclass(slots=True)
class MemoryEntry:
    """Lightweight memory header for fast recall."""
    id: str
    name: str
    memory_type: MemoryType = MemoryType.FACT
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.5
    priority: int = 50
    status: RecordStatus = RecordStatus.ACTIVE
    relations: list[MemoryRelation] = field(default_factory=list)
    source: str = "manual"
    event_time: datetime | None = None
    ttl_days: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def normalized_text(self) -> str:
        parts = [self.name, self.summary, " ".join(self.tags)]
        return " ".join(part for part in parts if part).lower()


# Backward compatibility alias
MemoryHeader = MemoryEntry


@dataclass(slots=True)
class MemoryContent:
    """Full memory content body."""
    id: str
    body: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MemoryQuery:
    """Query parameters for memory recall."""
    text: str = ""
    limit: int = 8
    budget_tokens: int = 2000
    relation_hops: int = 1
    required_tags: set[str] = field(default_factory=set)
    context_layers: set[str] = field(default_factory=lambda: {"l0", "l1", "l2"})
    memory_types: set[str] = field(default_factory=set)
    now: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class RecallScoreBreakdown:
    """Score breakdown for a recalled memory."""
    memory_id: str
    lexical_score: float = 0.0
    recency_score: float = 0.0
    priority_score: float = 0.0
    graph_score: float = 0.0
    final_score: float = 0.0
    selected: bool = False


@dataclass(slots=True)
class DroppedCandidate:
    """Memory that was not selected during recall."""
    memory_id: str
    reason: str
    final_score: float = 0.0
    token_cost: int = 0


@dataclass(slots=True)
class RecallResult:
    """Result of a memory recall operation."""
    entries: list[MemoryEntry]
    contents: dict[str, MemoryContent]
    candidates_scanned: int = 0
    used_tokens: int = 0
    score_breakdown: list[RecallScoreBreakdown] = field(default_factory=list)
    dropped_candidates: list[DroppedCandidate] = field(default_factory=list)
