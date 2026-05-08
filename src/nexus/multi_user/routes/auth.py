"""用户认证 API 路由."""

from flask import Blueprint, g, jsonify, request
from sqlmodel import select

from nexus.multi_user.auth import create_jwt, hash_password, verify_password
from nexus.multi_user.db import get_session
from nexus.multi_user.middleware import require_auth
from nexus.multi_user.models import User

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/register", methods=["POST"])
def register():
    """用户注册."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    username = (data.get("username") or "").strip()

    # 基础验证
    if not email or "@" not in email:
        return jsonify({"error": "无效的邮箱地址"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码长度至少 6 位"}), 400
    if not username:
        username = email.split("@")[0]

    session = get_session()
    # 检查邮箱是否已注册
    existing = session.exec(
        select(User).where(User.email == email)
    ).first()
    if existing:
        session.close()
        return jsonify({"error": "该邮箱已被注册"}), 409

    # 创建用户（默认非管理员）
    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
        is_admin=False,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    user_id = user.id
    user_email = user.email
    user_is_admin = user.is_admin
    user_credits = user.credits_balance
    session.close()

    token = create_jwt(user_id, user_email, user_is_admin)
    return jsonify({
        "message": "注册成功",
        "user": {
            "id": user_id,
            "email": user_email,
            "username": username,
            "is_admin": user_is_admin,
            "credits_balance": str(user_credits),
        },
        "token": token,
    }), 201


@bp.route("/login", methods=["POST"])
def login():
    """用户登录."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "邮箱和密码不能为空"}), 400

    session = get_session()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        session.close()
        return jsonify({"error": "邮箱或密码错误"}), 401

    if not verify_password(password, user.password_hash):
        session.close()
        return jsonify({"error": "邮箱或密码错误"}), 401

    if not user.is_active:
        session.close()
        return jsonify({"error": "账号已被禁用"}), 403

    # 更新最后登录时间并提取用户信息（在 session 关闭前提取）
    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    session.commit()
    user_id = user.id
    user_email = user.email
    user_is_admin = user.is_admin
    user_credits = user.credits_balance
    session.close()

    token = create_jwt(user_id, user_email, user_is_admin)
    return jsonify({
        "user": {
            "id": user_id,
            "email": user_email,
            "username": user.username,
            "is_admin": user_is_admin,
            "credits_balance": str(user_credits),
        },
        "token": token,
    })


@bp.route("/me", methods=["GET"])
@require_auth
def me():
    """获取当前登录用户信息."""
    if not getattr(g, "current_user", None):
        return jsonify({"error": "Unauthorized"}), 401

    user_id = g.current_user.get("user_id")
    session = get_session()
    user = session.get(User, user_id)
    session.close()

    if not user or not user.is_active:
        return jsonify({"error": "用户不存在或已禁用"}), 404

    return jsonify({
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "credits_balance": str(user.credits_balance),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    })


@bp.route("/logout", methods=["POST"])
def logout():
    """登出（客户端删除 Token 即可，服务端无状态）."""
    return jsonify({"message": "已登出"})


@bp.route("/change-password", methods=["POST"])
@require_auth
def change_password():
    """修改密码."""
    if not getattr(g, "current_user", None):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    old_password = data.get("old_password") or ""
    new_password = data.get("new_password") or ""

    if len(new_password) < 6:
        return jsonify({"error": "新密码长度至少 6 位"}), 400

    user_id = g.current_user.get("user_id")
    session = get_session()
    user = session.get(User, user_id)

    if not verify_password(old_password, user.password_hash):
        session.close()
        return jsonify({"error": "原密码错误"}), 400

    user.password_hash = hash_password(new_password)
    session.commit()
    session.close()

    return jsonify({"message": "密码修改成功"})