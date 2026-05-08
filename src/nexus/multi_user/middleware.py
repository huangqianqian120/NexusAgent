"""JWT 认证中间件."""

from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import g, jsonify, request

from nexus.multi_user.auth import extract_user_from_header


def require_auth(f: Callable) -> Callable:
    """
    装饰器：要求用户已登录（JWT 有效）.

    成功时将用户信息存入 flask.g.current_user
    失败时返回 401 Unauthorized
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        user = extract_user_from_header(request.headers.get("Authorization"))
        if not user:
            return jsonify({"error": "Unauthorized", "message": "请先登录"}), 401
        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def require_admin(f: Callable) -> Callable:
    """
    装饰器：要求用户已登录且为管理员.

    失败时返回 403 Forbidden
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        user = extract_user_from_header(request.headers.get("Authorization"))
        if not user:
            return jsonify({"error": "Unauthorized", "message": "请先登录"}), 401
        if not user.get("is_admin"):
            return jsonify({"error": "Forbidden", "message": "需要管理员权限"}), 403
        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def optional_auth(f: Callable) -> Callable:
    """
    装饰器：尝试解析 JWT，但不强制要求登录（用于获取当前用户但不阻止访问）.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        user = extract_user_from_header(request.headers.get("Authorization"))
        g.current_user = user  # None 表示未登录
        return f(*args, **kwargs)

    return decorated
