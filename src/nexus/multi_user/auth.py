"""多用户系统认证工具."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt

_secret_key = os.environ.get("MULTI_USER_SECRET_KEY") or os.environ.get("SECRET_KEY")
if not _secret_key:
    import logging
    logging.warning("未设置 MULTI_USER_SECRET_KEY，系统自动生成随机密钥（重启后会失效，请设置环境变量）")
    _secret_key = secrets.token_hex(32)
_jwt_expiry_hours = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))


def hash_password(password: str) -> str:
    """密码哈希（bcrypt）."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """验证密码."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_jwt(user_id: int, email: str, is_admin: bool) -> str:
    """创建 JWT Token."""
    payload = {
        "user_id": user_id,
        "email": email,
        "is_admin": is_admin,
        "exp": datetime.utcnow() + timedelta(hours=_jwt_expiry_hours),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, _secret_key, algorithm="HS256")


def decode_jwt(token: str) -> Optional[dict]:
    """解码 JWT Token，返回 payload 或 None（过期/无效）."""
    try:
        return jwt.decode(token, _secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def extract_user_from_header(auth_header: str | None) -> Optional[dict]:
    """
    从 Authorization header 中提取用户信息.

    格式: Bearer <token>

    返回: {"user_id": int, "email": str, "is_admin": bool} 或 None
    """
    if not auth_header:
        return None
    parts = auth_header.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    return decode_jwt(token)


def generate_session_id() -> str:
    """生成随机会话 ID."""
    return secrets.token_urlsafe(32)