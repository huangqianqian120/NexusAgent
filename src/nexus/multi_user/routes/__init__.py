"""NexusAgent 多用户系统路由."""

from nexus.multi_user.routes.auth import bp as auth_bp
from nexus.multi_user.routes.admin import bp as admin_bp

__all__ = ["auth_bp", "admin_bp"]
