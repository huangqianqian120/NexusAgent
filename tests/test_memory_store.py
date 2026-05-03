"""FileIndexStore 和 FileContentStore 单元测试."""

import pytest

from nexus.memory.store import (
    FileIndexStore,
    FileContentStore,
    _tokenize,
    _slugify,
    _graph_score,
    _recency_score,
    _priority_score,
    _lexical_score,
)
from nexus.memory.types import (
    MemoryEntry,
    MemoryContent,
    MemoryQuery,
    MemoryType,
    RecordStatus,
    utc_now,
)


class TestTokenizer:
    """_tokenize 函数测试."""

    def test_ascii_words(self):
        tokens = _tokenize("hello world python async programming")
        assert "hello" in tokens
        assert "world" in tokens
        assert "python" in tokens
        assert "async" in tokens
        assert "programming" in tokens

    def test_short_words_filtered(self):
        """短于 2 个字符的英文单词应被过滤."""
        tokens = _tokenize("a b c d ef gh i jk")
        for t in tokens:
            assert len(t) >= 2

    def test_chinese_characters(self):
        """中文每个字作为独立 token."""
        tokens = _tokenize("你好世界 Python 编程")
        assert "你" in tokens
        assert "好" in tokens
        assert "世" in tokens
        assert "界" in tokens
        assert "python" in tokens

    def test_empty_string(self):
        tokens = _tokenize("")
        assert tokens == set()


class TestSlugify:
    """_slugify 函数测试."""

    def test_basic(self):
        assert _slugify("Hello World") == "hello_world"

    def test_chinese(self):
        """slugify 对中文会生成空字符串或只保留 ASCII 部分."""
        result = _slugify("你好世界")
        # 中文没有 ASCII 匹配 → 返回 "memory"
        assert result == "memory"

    def test_mixed(self):
        result = _slugify("Test 测试 Memory 记忆")
        assert "test" in result
        assert "memory" in result

    def test_special_chars(self):
        result = _slugify("hello@#$world!!!test")
        assert result == "hello_world_test"


class TestScoringFunctions:
    """评分函数单元测试."""

    def test_graph_score_no_relations(self):
        entry = MemoryEntry(id="test", name="test")
        assert _graph_score(entry) == 0.0

    def test_graph_score_with_relations(self):
        from nexus.memory.types import MemoryRelation

        entry = MemoryEntry(
            id="test",
            name="test",
            relations=[
                MemoryRelation(target_id="a", relation="ref"),
                MemoryRelation(target_id="b", relation="ref"),
            ],
        )
        score = _graph_score(entry)
        assert 0 < score <= 1.0

    def test_recency_score_recent(self):
        entry = MemoryEntry(id="test", name="test")
        now = utc_now()
        score = _recency_score(entry, now)
        assert 0.95 <= score <= 1.0  # 刚刚创建的应接近 1.0

    def test_priority_score(self):
        entry = MemoryEntry(id="test", name="test", priority=80)
        assert _priority_score(entry) == 0.8

    def test_priority_score_max(self):
        entry = MemoryEntry(id="test", name="test", priority=100)
        assert _priority_score(entry) == 1.0

    def test_lexical_score_perfect_match(self):
        tokens = {"python", "async", "programming"}
        text = "python async programming guide"
        assert _lexical_score(tokens, text) == 1.0

    def test_lexical_score_partial_match(self):
        tokens = {"python", "async", "rust"}
        text = "python async programming"
        assert _lexical_score(tokens, text) == 2.0 / 3.0

    def test_lexical_score_no_match(self):
        tokens = {"rust", "golang"}
        text = "python async programming"
        assert _lexical_score(tokens, text) == 0.0


class TestFileIndexStore:
    """FileIndexStore YAML 索引存储测试."""

    @pytest.fixture
    def index_path(self, tmp_path):
        return tmp_path / "index" / "root.yaml"

    @pytest.fixture
    def store(self, index_path):
        return FileIndexStore(index_path)

    def test_upsert_and_get(self, store):
        entry = MemoryEntry(
            id="mem-001",
            name="测试记忆",
            memory_type=MemoryType.FACT,
            summary="这是一条测试",
        )
        store.upsert(entry)
        retrieved = store.get("mem-001")
        assert retrieved is not None
        assert retrieved.name == "测试记忆"
        assert retrieved.memory_type == MemoryType.FACT

    def test_get_missing(self, store):
        assert store.get("nonexistent") is None

    def test_list_empty(self, store):
        assert list(store.list()) == []

    def test_list_with_entries(self, store):
        store.upsert(MemoryEntry(id="a", name="A"))
        store.upsert(MemoryEntry(id="b", name="B"))
        entries = list(store.list())
        assert len(entries) == 2
        ids = {e.id for e in entries}
        assert ids == {"a", "b"}

    def test_delete(self, store):
        store.upsert(MemoryEntry(id="to-delete", name="待删除"))
        assert store.delete("to-delete") is True
        assert store.get("to-delete") is None

    def test_delete_nonexistent(self, store):
        assert store.delete("nonexistent") is False

    def test_search_by_text(self, store):
        store.upsert(
            MemoryEntry(
                id="py", name="Python指南", summary="Python 编程语言的最佳实践", tags=["python"]
            )
        )
        store.upsert(
            MemoryEntry(id="rust", name="Rust指南", summary="Rust 系统编程语言", tags=["rust"])
        )
        store.upsert(
            MemoryEntry(id="js", name="JavaScript指南", summary="JavaScript 前端开发", tags=["js"])
        )

        query = MemoryQuery(text="Python 编程", limit=5)
        results = store.search(query)
        assert len(results) >= 1
        # Python 相关的应该排在前面
        assert results[0][0].id == "py"

    def test_search_archived_excluded(self, store):
        store.upsert(MemoryEntry(id="archived", name="已归档", status=RecordStatus.ARCHIVED))
        query = MemoryQuery(text="已归档", limit=5)
        results = store.search(query)
        # 已归档的不应出现在搜索结果中
        assert all(r[0].id != "archived" for r in results)

    def test_persistence(self, index_path):
        """测试索引能正确持久化并重新加载."""
        store1 = FileIndexStore(index_path)
        store1.upsert(MemoryEntry(id="persist", name="持久化测试", summary="测试"))
        assert store1.get("persist") is not None

        # 重新创建 store，从文件加载
        store2 = FileIndexStore(index_path)
        retrieved = store2.get("persist")
        assert retrieved is not None
        assert retrieved.name == "持久化测试"
        assert retrieved.summary == "测试"

    def test_persistence_preserves_fields(self, index_path):
        """测试持久化保留所有字段."""
        from nexus.memory.types import MemoryRelation

        entry = MemoryEntry(
            id="full",
            name="完整字段",
            memory_type=MemoryType.PROCEDURE,
            summary="完整字段测试",
            tags=["test", "full"],
            confidence=0.8,
            priority=75,
            status=RecordStatus.ACTIVE,
            relations=[MemoryRelation(target_id="other", relation="depends_on")],
            source="import",
            ttl_days=30,
            metadata={"key": "value"},
        )
        store1 = FileIndexStore(index_path)
        store1.upsert(entry)

        store2 = FileIndexStore(index_path)
        retrieved = store2.get("full")
        assert retrieved is not None
        assert retrieved.memory_type == MemoryType.PROCEDURE
        assert retrieved.tags == ["test", "full"]
        assert retrieved.confidence == 0.8
        assert retrieved.priority == 75
        assert retrieved.source == "import"
        assert retrieved.ttl_days == 30
        assert len(retrieved.relations) == 1
        assert retrieved.relations[0].target_id == "other"


class TestFileContentStore:
    """FileContentStore Markdown 内容存储测试."""

    @pytest.fixture
    def content_dir(self, tmp_path):
        return tmp_path / "content"

    @pytest.fixture
    def store(self, content_dir):
        return FileContentStore(content_dir)

    def test_upsert_and_get(self, store):
        content = MemoryContent(id="test", body="# 记忆内容\n\n正文内容")
        store.upsert(content)
        retrieved = store.get("test")
        assert retrieved is not None
        assert retrieved.body == "# 记忆内容\n\n正文内容"
        assert retrieved.id == "test"

    def test_get_missing(self, store):
        assert store.get("missing") is None

    def test_upsert_with_metadata(self, store):
        content = MemoryContent(
            id="meta-test",
            body="正文",
            metadata={"author": "nexus", "version": 2},
        )
        store.upsert(content)
        retrieved = store.get("meta-test")
        assert retrieved is not None
        assert retrieved.metadata == {"author": "nexus", "version": 2}

    def test_delete(self, store):
        store.upsert(MemoryContent(id="del", body="待删除"))
        assert store.delete("del") is True
        assert store.get("del") is None

    def test_delete_nonexistent(self, store):
        assert store.delete("nonexistent") is False

    def test_update_content(self, store):
        store.upsert(MemoryContent(id="update", body="原始内容"))
        store.upsert(MemoryContent(id="update", body="更新后内容"))
        retrieved = store.get("update")
        assert retrieved.body == "更新后内容"
