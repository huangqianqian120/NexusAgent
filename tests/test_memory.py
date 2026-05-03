"""Tests for memory system."""

from nexus.memory.types import MemoryEntry, MemoryType


class TestMemoryTypes:
    """Test memory type definitions."""

    def test_memory_entry_creation(self):
        """Test creating a basic memory entry."""
        entry = MemoryEntry(
            id="test-001",
            name="Test Memory",
            memory_type=MemoryType.FACT,
            summary="This is a test memory",
        )
        assert entry.id == "test-001"
        assert entry.name == "Test Memory"
        assert entry.memory_type == MemoryType.FACT

    def test_memory_types_enum(self):
        """Test MemoryType enum values."""
        assert MemoryType.FACT.value == "fact"
        assert MemoryType.EPISODE.value == "episode"
        assert MemoryType.PREFERENCE.value == "preference"
        assert MemoryType.PROCEDURE.value == "procedure"


class TestMemoryRecall:
    """Test memory recall functionality."""

    def test_recall_result_structure(self):
        """Test RecallScoreBreakdown has required fields."""
        from nexus.memory.types import RecallScoreBreakdown

        breakdown = RecallScoreBreakdown(
            memory_id="test-001",
            lexical_score=0.5,
            recency_score=0.3,
            priority_score=0.2,
        )
        assert breakdown.memory_id == "test-001"
        assert breakdown.lexical_score == 0.5
