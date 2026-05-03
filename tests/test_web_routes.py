"""Web API 路由集成测试.

使用 Flask test client 测试所有 /api/v1/* 端点。
依赖项通过 patch 隔离，避免依赖本地工作区或外部服务。
"""

import json
import pytest

from unittest.mock import patch, MagicMock

try:
    from flask import Flask
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

pytestmark = pytest.mark.skipif(not HAS_FLASK, reason="Flask 未安装 (需要 uv sync --extra web)")


@pytest.fixture
def app():
    """创建带全部路由的 Flask 测试 app。"""
    app = Flask(__name__)
    app.config["TESTING"] = True

    from nexus.web.routes import register_all_routes

    register_all_routes(app)
    return app


@pytest.fixture
def client(app):
    """Flask 测试客户端。"""
    return app.test_client()


# ══════════════════════════════════════════════════════════════
# Provider & Auth routes
# ══════════════════════════════════════════════════════════════


class TestProviderRoutes:
    """测试 /api/v1/provider/* 和 /api/v1/auth/* 端点。"""

    def test_get_current_provider(self, client):
        """GET /api/v1/provider/current 返回当前 provider 信息。"""
        mock_profile = MagicMock()
        mock_profile.provider = "anthropic"
        mock_profile.last_model = "claude-sonnet-4-6"
        mock_profile.default_model = "claude-sonnet-4-6"
        mock_profile.base_url = "https://api.anthropic.com"
        mock_profile.auth_source = "api_key"

        with patch("nexus.web.routes.providers.load_settings") as mock_load:
            mock_settings = MagicMock()
            mock_settings.resolve_profile.return_value = ("default", mock_profile)
            mock_load.return_value = mock_settings

            resp = client.get("/api/v1/provider/current")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["provider"] == "anthropic"
        assert data["model"] == "claude-sonnet-4-6"

    def test_get_all_profiles(self, client):
        """GET /api/v1/provider/profiles 返回所有 profile。"""
        with patch("nexus.web.routes.providers.AuthManager") as mock_auth:
            mock_mgr = MagicMock()
            mock_mgr.get_profile_statuses.return_value = {
                "default": {"name": "default", "provider": "anthropic", "active": True}
            }
            mock_auth.return_value = mock_mgr

            resp = client.get("/api/v1/provider/profiles")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "profiles" in data

    def test_switch_provider_missing_profile(self, client):
        """POST /api/v1/provider/switch 缺少 profile 时返回 400。"""
        resp = client.post(
            "/api/v1/provider/switch",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_get_auth_status(self, client):
        """GET /api/v1/auth/status 返回认证状态。"""
        with patch("nexus.web.routes.providers.AuthManager") as mock_auth:
            mock_mgr = MagicMock()
            mock_mgr.get_auth_source_statuses.return_value = {
                "api_key": {"state": "active", "source": "env"}
            }
            mock_auth.return_value = mock_mgr

            resp = client.get("/api/v1/auth/status")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "auth_status" in data


# ══════════════════════════════════════════════════════════════
# Model routes
# ══════════════════════════════════════════════════════════════


class TestModelRoutes:
    """测试 /api/v1/models/* 和 /api/v1/model/* 端点。"""

    def test_get_available_models(self, client):
        """GET /api/v1/models 返回可用模型列表。"""
        mock_profile = MagicMock()
        mock_profile.provider = "anthropic"
        mock_profile.allowed_models = ["claude-sonnet-4-6", "claude-opus-4-6"]
        mock_profile.last_model = "claude-sonnet-4-6"
        mock_profile.default_model = "claude-sonnet-4-6"
        mock_profile.base_url = ""
        mock_profile.api_format = ""

        with patch("nexus.web.routes.providers.load_settings") as mock_load:
            mock_settings = MagicMock()
            mock_settings.resolve_profile.return_value = ("default", mock_profile)
            mock_load.return_value = mock_settings

            resp = client.get("/api/v1/models")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "models" in data
        assert "current" in data
        assert len(data["models"]) == 2

    def test_get_current_model(self, client):
        """GET /api/v1/model/current 返回当前模型。"""
        mock_profile = MagicMock()
        mock_profile.last_model = "claude-opus-4-6"
        mock_profile.default_model = "claude-sonnet-4-6"

        with patch("nexus.web.routes.providers.load_settings") as mock_load:
            mock_settings = MagicMock()
            mock_settings.resolve_profile.return_value = ("default", mock_profile)
            mock_load.return_value = mock_settings

            resp = client.get("/api/v1/model/current")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["model"] == "claude-opus-4-6"

    def test_switch_model_missing_field(self, client):
        """POST /api/v1/model/switch 缺少 model 时返回 400。"""
        resp = client.post(
            "/api/v1/model/switch",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400


# ══════════════════════════════════════════════════════════════
# Session routes
# ══════════════════════════════════════════════════════════════


class TestSessionRoutes:
    """测试 /api/v1/sessions/* 端点。"""

    def test_list_sessions(self, client):
        """GET /api/v1/sessions 返回会话列表。"""
        mock_sessions = [
            {
                "session_id": "s1",
                "summary": "Test session",
                "message_count": 5,
                "model": "claude",
                "created_at": 1714400000,
            }
        ]

        with patch(
            "nexus.services.session_backend.DEFAULT_SESSION_BACKEND"
        ) as mock_backend:
            mock_backend.list_snapshots.return_value = mock_sessions

            resp = client.get("/api/v1/sessions")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "sessions" in data
        assert len(data["sessions"]) == 1

    def test_get_session_not_found(self, client):
        """GET /api/v1/sessions/<id> 找不到会话时返回 404。"""
        with patch(
            "nexus.services.session_backend.DEFAULT_SESSION_BACKEND"
        ) as mock_backend:
            mock_backend.load_by_id.return_value = None

            resp = client.get("/api/v1/sessions/nonexistent")

        assert resp.status_code == 404

    def test_clear_session(self, client):
        """DELETE /api/v1/sessions 清除当前会话。"""
        resp = client.delete("/api/v1/sessions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "cleared"

    def test_resume_session_not_found(self, client):
        """POST /api/v1/sessions/<id>/resume 找不到会话时返回 404。"""
        with patch(
            "nexus.services.session_backend.DEFAULT_SESSION_BACKEND"
        ) as mock_backend:
            mock_backend.load_by_id.return_value = None

            resp = client.post("/api/v1/sessions/nonexistent/resume")

        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# Skill routes
# ══════════════════════════════════════════════════════════════


class TestSkillRoutes:
    """测试 /api/v1/skills/* 端点。"""

    def test_list_skills(self, client):
        """GET /api/v1/skills 返回技能列表。"""
        mock_skill = MagicMock()
        mock_skill.name = "test-skill"
        mock_skill.description = "A test skill"
        mock_skill.source = "builtin"

        mock_registry = MagicMock()
        mock_registry.list_skills.return_value = [mock_skill]

        with patch(
            "personal_agent.workspace.get_workspace_root"
        ) as mock_root, patch(
            "nexus.skills.load_skill_registry"
        ) as mock_load:
            mock_root.return_value = "/tmp/ws"
            mock_load.return_value = mock_registry

            resp = client.get("/api/v1/skills")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "skills" in data
        assert len(data["skills"]) == 1

    def test_get_skill_not_found(self, client):
        """GET /api/v1/skills/<name> 找不到时返回 404。"""
        mock_registry = MagicMock()
        mock_registry.get.return_value = None

        with patch(
            "personal_agent.workspace.get_workspace_root"
        ), patch(
            "nexus.skills.load_skill_registry"
        ) as mock_load:
            mock_load.return_value = mock_registry

            resp = client.get("/api/v1/skills/nonexistent")

        assert resp.status_code == 404

    def test_upload_skill_missing_fields(self, client):
        """POST /api/v1/skills 缺少必填字段时返回 400。"""
        resp = client.post(
            "/api/v1/skills",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_upload_skill_invalid_name(self, client):
        """POST /api/v1/skills 名称包含非法字符时返回 400。"""
        resp = client.post(
            "/api/v1/skills",
            data=json.dumps({"name": "bad name!", "content": "test"}),
            content_type="application/json",
        )
        assert resp.status_code == 400


# ══════════════════════════════════════════════════════════════
# Memory routes
# ══════════════════════════════════════════════════════════════


class TestMemoryRoutes:
    """测试 /api/v1/memories/* 端点。"""

    @pytest.fixture
    def mock_store(self):
        """创建 MemoryStore 的 mock。"""
        with patch("nexus.web.routes.memory._get_memory_store") as mock_get:
            store = MagicMock()
            mock_get.return_value = store
            yield store

    def test_list_memories_empty(self, client, mock_store):
        """GET /api/v1/memories 空列表。"""
        mock_store.list.return_value = []

        resp = client.get("/api/v1/memories")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["memories"] == []

    def test_get_memory_not_found(self, client, mock_store):
        """GET /api/v1/memories/<id> 找不到时返回 404。"""
        mock_store.get.return_value = None

        resp = client.get("/api/v1/memories/nonexistent")

        assert resp.status_code == 404

    def test_create_memory(self, client, mock_store):
        """POST /api/v1/memories 创建记忆并返回 201。"""
        from nexus.memory.types import MemoryEntry, MemoryType, RecordStatus, utc_now

        entry = MemoryEntry(
            id="mem_1",
            name="test",
            memory_type=MemoryType.FACT,
            summary="test summary",
            tags=[],
            confidence=0.8,
            priority=50,
            status=RecordStatus.ACTIVE,
            relations=[],
            source="manual",
            event_time=None,
            ttl_days=None,
            metadata={},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        mock_store.create.return_value = entry

        resp = client.post(
            "/api/v1/memories",
            data=json.dumps({"name": "test", "summary": "test summary", "body": "content"}),
            content_type="application/json",
        )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["entry"]["name"] == "test"

    def test_delete_memory_not_found(self, client, mock_store):
        """DELETE /api/v1/memories/<id> 找不到时返回 404。"""
        mock_store.delete.return_value = False

        resp = client.delete("/api/v1/memories/nonexistent")

        assert resp.status_code == 404

    def test_memory_stats(self, client, mock_store):
        """GET /api/v1/memories/stats 返回统计信息。"""
        mock_store._index.list.return_value = []

        resp = client.get("/api/v1/memories/stats")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0
        assert "by_status" in data
        assert "by_type" in data

    def test_feedback_memory_not_found(self, client, mock_store):
        """POST /api/v1/memories/<id>/feedback 找不到时返回 404。"""
        mock_store.get.return_value = None

        resp = client.post(
            "/api/v1/memories/nonexistent/feedback",
            data=json.dumps({"action": "confirm"}),
            content_type="application/json",
        )

        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# Tool routes
# ══════════════════════════════════════════════════════════════


class TestToolRoutes:
    """测试 /api/v1/tools/* 端点。"""

    def test_list_tools(self, client):
        """GET /api/v1/tools 返回工具列表。"""
        mock_tool_schema = {
            "name": "read",
            "description": "Read a file",
            "input_schema": {"type": "object"},
        }

        mock_registry = MagicMock()
        mock_registry.to_api_schema.return_value = [mock_tool_schema]

        with patch(
            "nexus.tools.create_default_tool_registry"
        ) as mock_create:
            mock_create.return_value = mock_registry

            resp = client.get("/api/v1/tools")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "tools" in data

    def test_get_tool_not_found(self, client):
        """GET /api/v1/tools/<name> 找不到工具时返回 404。"""
        mock_registry = MagicMock()
        mock_registry.get.return_value = None

        with patch(
            "nexus.tools.create_default_tool_registry"
        ) as mock_create:
            mock_create.return_value = mock_registry

            resp = client.get("/api/v1/tools/nonexistent")

        assert resp.status_code == 404

    def test_execute_tool_not_found(self, client):
        """POST /api/v1/tools/<name>/execute 找不到时返回 404。"""
        mock_registry = MagicMock()
        mock_registry.get.return_value = None

        with patch(
            "nexus.tools.create_default_tool_registry"
        ) as mock_create:
            mock_create.return_value = mock_registry

            resp = client.post(
                "/api/v1/tools/nonexistent/execute",
                data=json.dumps({}),
                content_type="application/json",
            )

        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# Task routes
# ══════════════════════════════════════════════════════════════


class TestTaskRoutes:
    """测试 /api/v1/tasks/* 端点。"""

    def test_list_tasks(self, client):
        """GET /api/v1/tasks 返回任务列表。"""
        mock_mgr = MagicMock()
        # 使用简单对象避免 JSON 序列化问题
        mock_mgr.list_tasks.return_value = []

        with patch("nexus.tasks.get_task_manager") as mock_get:
            mock_get.return_value = mock_mgr

            resp = client.get("/api/v1/tasks")

        assert resp.status_code == 200
        data = resp.get_json()
        assert "tasks" in data

    def test_get_task_not_found(self, client):
        """GET /api/v1/tasks/<id> 找不到时返回 404。"""
        mock_mgr = MagicMock()
        mock_mgr.get_task.return_value = None

        with patch("nexus.tasks.get_task_manager") as mock_get:
            mock_get.return_value = mock_mgr

            resp = client.get("/api/v1/tasks/nonexistent")

        assert resp.status_code == 404

    def test_stop_task_not_found(self, client):
        """DELETE /api/v1/tasks/<id> 找不到时返回 404。"""
        mock_mgr = MagicMock()
        mock_mgr.get_task.return_value = None

        with patch("nexus.tasks.get_task_manager") as mock_get:
            mock_get.return_value = mock_mgr

            resp = client.delete("/api/v1/tasks/nonexistent")

        assert resp.status_code == 404
