"""Memory consolidation policies and algorithms."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from nexus.memory.types import MemoryEntry, RecordStatus, utc_now


@dataclass
class ConsolidationPolicy:
    """Policy for memory consolidation."""
    decay_per_day: int = 1  # Priority decay per day
    min_priority: int = 5    # Minimum priority after decay
    dedupe_enabled: bool = True  # Enable deduplication
    archive_expired: bool = True  # Archive TTL-expired memories
    dedupe_similarity_threshold: float = 0.85  # Similarity threshold for dedupe


def consolidate_entries(
    entries: list[MemoryEntry],
    now: datetime | None = None,
    policy: ConsolidationPolicy | None = None,
) -> list[MemoryEntry]:
    """Consolidate memories: decay priorities, archive expired, dedupe similar.

    Returns list of entries that were modified.
    """
    if now is None:
        now = utc_now()
    if policy is None:
        policy = ConsolidationPolicy()

    touched: dict[str, MemoryEntry] = {}

    # 1. Archive expired and apply decay
    for entry in entries:
        if entry.status != RecordStatus.ACTIVE:
            continue

        changed = False

        # Archive TTL-expired entries
        if policy.archive_expired and entry.ttl_days is not None:
            base_time = entry.event_time or entry.created_at
            age_days = max(0, (now - base_time).days)
            if age_days > entry.ttl_days:
                entry.status = RecordStatus.ARCHIVED
                entry.metadata["archived_reason"] = "ttl_expired"
                entry.metadata["archived_at"] = now.isoformat()
                touched[entry.id] = entry
                changed = True

        # Apply priority decay for active entries
        if entry.status == RecordStatus.ACTIVE and policy.decay_per_day > 0:
            base_time = entry.event_time or entry.created_at
            age_days = max(0, (now - base_time).days)
            if age_days > 0:
                new_priority = max(policy.min_priority, entry.priority - age_days * policy.decay_per_day)
                if new_priority != entry.priority:
                    entry.priority = new_priority
                    entry.metadata["decayed_at"] = now.isoformat()
                    entry.metadata["decay_age_days"] = age_days
                    touched[entry.id] = entry
                    changed = True

    # 2. Deduplicate similar entries
    if policy.dedupe_enabled:
        groups: dict[str, list[MemoryEntry]] = defaultdict(list)
        for entry in entries:
            if entry.status != RecordStatus.ACTIVE:
                continue
            fp = _fingerprint(entry)
            groups[fp].append(entry)

        for fp, group in groups.items():
            if len(group) <= 1:
                continue

            # Sort by confidence, priority, then creation time
            winner = max(group, key=_dedupe_rank)
            for entry in group:
                if entry.id == winner.id:
                    continue

                if (
                    entry.status != RecordStatus.SUPERSEDED
                    or entry.metadata.get("superseded_by") != winner.id
                ):
                    entry.status = RecordStatus.SUPERSEDED
                    entry.metadata["superseded_by"] = winner.id
                    entry.metadata["superseded_at"] = now.isoformat()
                    entry.metadata["superseded_reason"] = "dedupe"
                    touched[entry.id] = entry

    return list(touched.values())


def _dedupe_rank(entry: MemoryEntry) -> tuple[float, int, datetime]:
    """Ranking key for deduplication: higher confidence, priority, newer first."""
    return (entry.confidence, entry.priority, entry.created_at)


def _fingerprint(entry: MemoryEntry) -> str:
    """Generate a fingerprint for deduplication grouping.

    Entries with the same fingerprint are considered duplicates.
    Uses normalized summary + memory_type + overlapping tags.
    """
    # Normalize summary: lowercase, strip, collapse whitespace
    summary_words = " ".join(entry.summary.lower().split()) if entry.summary else ""

    # Sort and join tags for consistent fingerprinting
    tags_key = ",".join(sorted(set(entry.tags))) if entry.tags else ""

    # Memory type is part of fingerprint
    type_key = entry.memory_type.value

    return f"{type_key}|{summary_words[:100]}|{tags_key}"


def suggest_archives(
    entries: list[MemoryEntry],
    max_age_days: int = 90,
    max_entries: int = 100,
) -> list[str]:
    """Suggest memory IDs that should be archived based on age and count.

    Returns list of memory IDs to archive.
    """
    now = utc_now()
    candidates: list[tuple[int, str]] = []  # (score, id)

    # Score each entry for archival priority (higher = more likely to archive)
    for entry in entries:
        if entry.status != RecordStatus.ACTIVE:
            continue

        base_time = entry.event_time or entry.created_at
        age_days = (now - base_time).days

        score = age_days  # Base score on age

        # Boost score for lower confidence/priority
        score += (1.0 - entry.confidence) * 30
        score += (100 - entry.priority) * 0.5

        # Boost if has been superseded
        if entry.metadata.get("superseded_by"):
            score += 50

        candidates.append((score, entry.id))

    # Sort by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)

    # Take top candidates, but respect max_age_days for very old entries
    result: list[str] = []
    for score, entry_id in candidates:
        if len(result) >= max_entries:
            break
        # Find the entry to check age
        for e in entries:
            if e.id == entry_id:
                base_time = e.event_time or e.created_at
                age_days = (now - base_time).days
                if age_days < max_age_days and len(result) >= max_entries // 2:
                    continue
                result.append(entry_id)
                break

    return result
