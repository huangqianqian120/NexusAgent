"""NexusAgent Web UI 路由模块."""

from nexus.web.routes.memory import register_routes as register_memory_routes
from nexus.web.routes.sessions import register_routes as register_session_routes
from nexus.web.routes.skills import register_routes as register_skill_routes
from nexus.web.routes.tools import register_routes as register_tool_routes
from nexus.web.routes.providers import register_routes as register_provider_routes


def register_all_routes(app):
    """在 Flask app 上注册所有 API 路由."""
    register_memory_routes(app)
    register_session_routes(app)
    register_skill_routes(app)
    register_tool_routes(app)
    register_provider_routes(app)
