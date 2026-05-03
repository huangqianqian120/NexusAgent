"""记忆类型和数据模型测试."""

from datetime import datetime, timezone
from nexus.memory.types import (
    MemoryType,
    RecordStatus,
    MemoryEntry,
    MemoryContent,
    MemoryQuery,
    MemoryRelation,
    RecallScoreBreakdown,
    DroppedCandidate,
    RecallResult,
    utc_now,
)


class TestMemoryType:
    """MemoryType 枚举测试."""

    def test_fact_value(self):
        assert MemoryType.FACT.value == "fact"

    def test_episode_value(self):
        assert MemoryType.EPISODE.value == "episode"

    def test_preference_value(self):
        assert MemoryType.PREFERENCE.value == "preference"

    def test_procedure_value(self):
        assert MemoryType.PROCEDURE.value == "procedure"

    def test_from_value(self):
        assert MemoryType("fact") == MemoryType.FACT
        assert MemoryType("episode") == MemoryType.EPISODE


class TestRecordStatus:
    """RecordStatus 枚举测试."""

    def test_active_value(self):
        assert RecordStatus.ACTIVE.value == "active"

    def test_superseded_value(self):
        assert RecordStatus.SUPERSEDED.value == "superseded"

    def test_archived_value(self):
        assert RecordStatus.ARCHIVED.value == "archived"


class TestMemoryEntry:
    """MemoryEntry 数据模型测试."""

    def test_create_minimal(self):
        entry = MemoryEntry(
            id="test-001",
            name="测试记忆",
            memory_type=MemoryType.FACT,
            summary="这是一条测试记忆",
        )
        assert entry.id == "test-001"
        assert entry.name == "测试记忆"
        assert entry.memory_type == MemoryType.FACT
        assert entry.summary == "这是一条测试记忆"

    def test_default_values(self):
        entry = MemoryEntry(id="test-002", name="默认值测试")
        assert entry.memory_type == MemoryType.FACT
        assert entry.summary == ""
        assert entry.tags == []
        assert entry.confidence == 0.5
        assert entry.priority == 50
        assert entry.status == RecordStatus.ACTIVE
        assert entry.relations == []
        assert entry.source == "manual"
        assert entry.event_time is None
        assert entry.ttl_days is None
        assert entry.metadata == {}
        assert entry.created_at is not None
        assert entry.updated_at is not None

    def test_created_at_utc(self):
        entry = MemoryEntry(id="test-003", name="UTC 时间测试")
        assert entry.created_at.tzinfo == timezone.utc

    def test_normalized_text(self):
        entry = MemoryEntry(
            id="test-004",
            name="Python开发",
            summary="Python异步编程最佳实践",
            tags=["python", "async", "best_practices"],
        )
        text = entry.normalized_text()
        assert "python开发" in text
        assert "python异步编程最佳实践" in text
        assert "async" in text

    def test_with_tags(self):
        entry = MemoryEntry(
            id="test-005",
            name="带标签的记忆",
            tags=["重要", "紧急", "python"],
        )
        assert len(entry.tags) == 3
        assert "重要" in entry.tags

    def test_with_relations(self):
        entry = MemoryEntry(
            id="test-006",
            name="有关联的记忆",
            relations=[
                MemoryRelation(target_id="other-001", relation="related_to", weight=0.8),
                MemoryRelation(target_id="other-002", relation="parent_of"),
            ],
        )
        assert len(entry.relations) == 2
        assert entry.relations[0].target_id == "other-001"
        assert entry.relations[0].relation == "related_to"
        assert entry.relations[0].weight == 0.8
        assert entry.relations[1].weight == 1.0  # 默认权重

    def test_memory_header_fields(self):
        """验证 MemoryHeader 是独立的 dataclass，拥有扫描所需字段."""
        from nexus.memory.types import MemoryHeader
        from pathlib import Path

        header = MemoryHeader(
            path=Path("/tmp/test.md"),
            title="测试记忆",
            description="一段描述",
            modified_at=1234567890.0,
            memory_type="fact",
            body_preview="正文预览...",
        )
        assert header.path == Path("/tmp/test.md")
        assert header.title == "测试记忆"
        assert header.description == "一段描述"
        assert header.modified_at == 1234567890.0
        assert header.memory_type == "fact"
        assert header.body_preview == "正文预览..."


class TestMemoryContent:
    """MemoryContent 数据模型测试."""

    def test_create_content(self):
        content = MemoryContent(
            id="test-001",
            body="这是记忆的完整正文内容",
            metadata={"source": "manual", "version": 1},
        )
        assert content.id == "test-001"
        assert content.body == "这是记忆的完整正文内容"
        assert content.metadata["source"] == "manual"

    def test_empty_body(self):
        content = MemoryContent(id="test-002")
        assert content.body == ""
        assert content.metadata == {}


class TestMemoryQuery:
    """MemoryQuery 数据模型测试."""

    def test_default_query(self):
        query = MemoryQuery()
        assert query.text == ""
        assert query.limit == 8
        assert query.budget_tokens == 2000
        assert query.relation_hops == 1

    def test_query_with_text(self):
        query = MemoryQuery(text="Python 异步编程")
        assert query.text == "Python 异步编程"

    def test_query_with_limit(self):
        query = MemoryQuery(limit=3)
        assert query.limit == 3

    def test_query_required_tags(self):
        query = MemoryQuery(required_tags={"python", "async"})
        assert query.required_tags == {"python", "async"}

    def test_query_memory_types_filter(self):
        query = MemoryQuery(memory_types={"fact", "procedure"})
        assert query.memory_types == {"fact", "procedure"}


class TestRecallResult:
    """RecallResult 和相关类型测试."""

    def test_score_breakdown(self):
        breakdown = RecallScoreBreakdown(
            memory_id="test-001",
            lexical_score=0.8,
            recency_score=0.5,
            priority_score=0.7,
            graph_score=0.3,
            final_score=0.6,
            selected=True,
        )
        assert breakdown.memory_id == "test-001"
        assert breakdown.lexical_score == 0.8
        assert breakdown.selected is True

    def test_dropped_candidate(self):
        dropped = DroppedCandidate(
            memory_id="test-002",
            reason="budget_exceeded",
            final_score=0.4,
            token_cost=500,
        )
        assert dropped.memory_id == "test-002"
        assert dropped.reason == "budget_exceeded"
        assert dropped.token_cost == 500

    def test_recall_result(self):
        entry = MemoryEntry(id="recall-001", name="召回测试")
        content = MemoryContent(id="recall-001", body="测试内容")
        breakdown = RecallScoreBreakdown(memory_id="recall-001", final_score=0.9)
        dropped = DroppedCandidate(memory_id="recall-002", reason="limit_reached")

        result = RecallResult(
            entries=[entry],
            contents={"recall-001": content},
            candidates_scanned=10,
            used_tokens=150,
            score_breakdown=[breakdown],
            dropped_candidates=[dropped],
        )
        assert len(result.entries) == 1
        assert result.candidates_scanned == 10
        assert result.used_tokens == 150
        assert len(result.score_breakdown) == 1
        assert len(result.dropped_candidates) == 1


class TestUtcNow:
    """utc_now 工具函数测试."""

    def test_returns_datetime_with_utc_tz(self):
        result = utc_now()
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_is_close_to_now(self):
        result = utc_now()
        now = datetime.now(timezone.utc)
        diff = abs((now - result).total_seconds())
        # 应该在 1 秒以内
        assert diff < 1.0
