"""MemoryStore (index + content) 集成测试."""


import pytest

from nexus.memory.store import MemoryStore, FileIndexStore, FileContentStore
from nexus.memory.types import (
    MemoryQuery,
    MemoryType,
)


class TestMemoryStore:
    """MemoryStore 完整功能测试."""

    @pytest.fixture
    def store(self, monkeypatch, tmp_path):
        """创建一个使用临时目录的 MemoryStore."""
        memory_dir = tmp_path / "memory"
        index_path = memory_dir / "index" / "root.yaml"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        content_dir = memory_dir / "content"
        content_dir.mkdir(parents=True, exist_ok=True)

        store = MemoryStore.__new__(MemoryStore)
        store._index = FileIndexStore(index_path)
        store._content = FileContentStore(content_dir)
        return store

    def test_create_and_get(self, store):
        entry = store.create(
            name="Python 最佳实践",
            summary="Python 编程的最佳实践指南",
            body="这是一份详细的 Python 最佳实践文档...",
            memory_type=MemoryType.PROCEDURE,
            tags=["python", "best_practices"],
            confidence=0.8,
            priority=70,
        )
        assert entry.id is not None
        assert entry.name == "Python 最佳实践"

        result = store.get(entry.id)
        assert result is not None
        retrieved_entry, retrieved_content = result
        assert retrieved_entry.name == "Python 最佳实践"
        assert "Python 最佳实践" in retrieved_content.body

    def test_get_missing(self, store):
        assert store.get("nonexistent") is None

    def test_list_all(self, store):
        store.create(name="记忆1", summary="摘要1", body="正文1")
        store.create(name="记忆2", summary="摘要2", body="正文2")
        store.create(name="记忆3", summary="摘要3", body="正文3")

        entries = store.list()
        assert len(entries) == 3

    def test_list_filter_by_type(self, store):
        store.create(
            name="事实记忆", summary="摘要", body="正文",
            memory_type=MemoryType.FACT,
        )
        store.create(
            name="过程记忆", summary="摘要", body="正文",
            memory_type=MemoryType.PROCEDURE,
        )

        facts = store.list(memory_type=MemoryType.FACT)
        assert len(facts) == 1
        assert facts[0].name == "事实记忆"

        procedures = store.list(memory_type=MemoryType.PROCEDURE)
        assert len(procedures) == 1
        assert procedures[0].name == "过程记忆"

    def test_list_sorted_by_updated_at(self, store):
        import time
        store.create(name="旧记忆", summary="旧", body="旧")
        time.sleep(0.01)
        store.create(name="新记忆", summary="新", body="新")

        entries = store.list()
        assert entries[0].name == "新记忆"  # 最新的排前面

    def test_update(self, store):
        entry = store.create(name="原始名称", summary="原始摘要", body="原始正文")

        success = store.update(
            entry.id,
            name="更新名称",
            summary="更新摘要",
            body="更新正文",
        )
        assert success is True

        _, content = store.get(entry.id)
        assert content.body == "更新正文"

        entry = store._index.get(entry.id)
        assert entry.name == "更新名称"
        assert entry.summary == "更新摘要"

    def test_update_missing(self, store):
        assert store.update("nonexistent", name="x") is False

    def test_delete(self, store):
        entry = store.create(name="待删除", summary="待删除", body="待删除")
        assert store.delete(entry.id) is True
        assert store.get(entry.id) is None

    def test_delete_nonexistent(self, store):
        assert store.delete("nonexistent") is False

    def test_recall_basic(self, store):
        """测试基本召回功能."""
        store.create(
            name="Python 异步编程",
            summary="asyncio 和 async/await 的使用",
            body="Python 3.5+ 引入了 async/await 语法...",
            tags=["python", "async"],
        )
        store.create(
            name="Rust 所有权",
            summary="Rust 的所有权系统",
            body="Rust 的所有权模型确保内存安全...",
            tags=["rust"],
        )
        store.create(
            name="Git 工作流",
            summary="Git 分支管理策略",
            body="Git Flow 和 Trunk Based Development...",
            tags=["git", "workflow"],
        )

        query = MemoryQuery(text="Python 异步编程", limit=3)
        result = store.recall(query)

        assert len(result.entries) >= 1
        # Python 相关的应该排第一
        assert "python" in result.entries[0].id

    def test_recall_respects_limit(self, store):
        for i in range(10):
            store.create(name=f"记忆{i}", summary=f"摘要{i}", body=f"正文{i}")

        query = MemoryQuery(limit=3)
        result = store.recall(query)
        assert len(result.entries) <= 3

    def test_recall_token_budget(self, store):
        """测试 token 预算限制."""
        # 创建一个很大的记忆
        big_body = "测试内容 " * 1000  # 约 5000 chars → ~1250 tokens
        store.create(name="大记忆", summary="大记忆摘要", body=big_body)

        query = MemoryQuery(text="测试", limit=10, budget_tokens=200)
        result = store.recall(query)
        # 理论上大记忆会因为超预算被丢弃
        assert result.used_tokens <= 200 or len(result.dropped_candidates) > 0

    def test_recall_dup_id(self, store):
        """测试不会因为重复 ID 崩溃."""
        store.create(name="测试", summary="测试摘要", body="测试正文")
        # 第二次创建同一名称应该生成不同的 ID
        store.create(name="测试", summary="测试摘要", body="测试正文")

        entries = store.list()
        ids = {e.id for e in entries}
        # 应该是两个不同的 ID
        assert len(ids) == 2
