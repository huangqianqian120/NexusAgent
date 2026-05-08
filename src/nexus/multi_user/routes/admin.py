"""管理员 API 路由（用户管理 + Credits 分配）."""

from flask import Blueprint, jsonify, request
from sqlmodel import select

from nexus.multi_user.db import get_session
from nexus.multi_user.middleware import require_admin
from nexus.multi_user.models import User, CreditTransaction

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# ---- 用户管理 ----


@bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    """列出所有用户（分页）."""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    offset = (page - 1) * page_size

    session = get_session()
    total = session.exec(select(User)).all()
    users = session.exec(select(User).offset(offset).limit(page_size)).all()
    session.close()

    return jsonify(
        {
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "username": u.username,
                    "is_admin": u.is_admin,
                    "is_active": u.is_active,
                    "credits_balance": str(u.credits_balance),
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                }
                for u in users
            ],
            "total": len(total),
            "page": page,
            "page_size": page_size,
        }
    )


@bp.route("/users", methods=["POST"])
@require_admin
def create_user():
    """管理员手动创建用户."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    username = (data.get("username") or "").strip() or email.split("@")[0]

    if not email or "@" not in email:
        return jsonify({"error": "无效的邮箱地址"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码长度至少 6 位"}), 400

    from nexus.multi_user.auth import hash_password

    session = get_session()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        session.close()
        return jsonify({"error": "该邮箱已被注册"}), 409

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
        is_admin=data.get("is_admin", False),
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()

    return jsonify(
        {
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "is_admin": user.is_admin,
                "credits_balance": str(user.credits_balance),
            }
        }
    ), 201


@bp.route("/users/<int:user_id>", methods=["GET"])
@require_admin
def get_user(user_id: int):
    """获取单个用户详情."""
    session = get_session()
    user = session.get(User, user_id)
    session.close()

    if not user:
        return jsonify({"error": "用户不存在"}), 404

    return jsonify(
        {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "credits_balance": str(user.credits_balance),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        }
    )


@bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@require_admin
def toggle_user_active(user_id: int):
    """启用/禁用用户."""
    session = get_session()
    user = session.get(User, user_id)
    if not user:
        session.close()
        return jsonify({"error": "用户不存在"}), 404

    user.is_active = not user.is_active
    session.commit()
    session.close()

    return jsonify({"id": user.id, "is_active": user.is_active})


# ---- Credits 分配 ----


@bp.route("/credits/allocate", methods=["POST"])
@require_admin
def allocate_credits():
    """分配 Credits 给用户."""
    data = request.get_json() or {}
    user_id = data.get("user_id")
    amount = data.get("amount")
    description = data.get("description", "").strip()

    if not user_id:
        return jsonify({"error": "缺少 user_id"}), 400
    if amount is None:
        return jsonify({"error": "缺少 amount"}), 400

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({"error": "无效的金额格式"}), 400

    if amount <= 0:
        return jsonify({"error": "金额必须为正数"}), 400

    session = get_session()
    user = session.get(User, user_id)
    if not user:
        session.close()
        return jsonify({"error": "用户不存在"}), 404

    # 更新用户余额
    session = get_session()
    user = session.get(User, user_id)
    new_balance = float(user.credits_balance) + float(amount)
    user.credits_balance = float(new_balance)

    # 记录交易
    tx = CreditTransaction(
        user_id=user_id,
        amount=float(amount),
        balance_after=float(new_balance),
        transaction_type="admin_allocation",
        description=description or f"管理员分配 {amount} Credits",
    )
    session.add(tx)
    session.commit()
    tx_id = tx.id
    session.close()

    return jsonify(
        {
            "user_id": user_id,
            "amount": str(amount),
            "balance_after": str(new_balance),
            "transaction_id": tx_id,
        }
    )


@bp.route("/credits/transactions", methods=["GET"])
@require_admin
def list_transactions():
    """列出所有 Credits 交易记录."""
    user_id = request.args.get("user_id", type=int)
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    offset = (page - 1) * page_size

    session = get_session()
    query = select(CreditTransaction).order_by(CreditTransaction.created_at.desc())
    if user_id:
        query = query.where(CreditTransaction.user_id == user_id)

    txs = session.exec(query.offset(offset).limit(page_size)).all()
    total = len(session.exec(query).all())
    session.close()

    return jsonify(
        {
            "transactions": [
                {
                    "id": t.id,
                    "user_id": t.user_id,
                    "amount": str(t.amount),
                    "balance_after": str(t.balance_after),
                    "transaction_type": t.transaction_type,
                    "description": t.description,
                    "model": t.model,
                    "input_tokens": t.input_tokens,
                    "output_tokens": t.output_tokens,
                    "cost_usd": t.cost_usd,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in txs
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@bp.route("/users/<int:user_id>/credits/transactions", methods=["GET"])
@require_admin
def get_user_transactions(user_id: int):
    """获取指定用户的 Credits 交易记录."""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    offset = (page - 1) * page_size

    session = get_session()
    query = (
        select(CreditTransaction)
        .where(CreditTransaction.user_id == user_id)
        .order_by(CreditTransaction.created_at.desc())
    )

    txs = session.exec(query.offset(offset).limit(page_size)).all()
    total = len(session.exec(query).all())
    session.close()

    return jsonify(
        {
            "user_id": user_id,
            "transactions": [
                {
                    "id": t.id,
                    "amount": str(t.amount),
                    "balance_after": str(t.balance_after),
                    "transaction_type": t.transaction_type,
                    "description": t.description,
                    "model": t.model,
                    "cost_usd": t.cost_usd,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in txs
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@require_admin
def reset_user_password(user_id: int):
    """重置用户密码（管理员操作）."""
    data = request.get_json() or {}
    new_password = data.get("new_password", "")
    if len(new_password) < 6:
        return jsonify({"error": "新密码长度至少 6 位"}), 400

    from nexus.multi_user.auth import hash_password

    session = get_session()
    user = session.get(User, user_id)
    if not user:
        session.close()
        return jsonify({"error": "用户不存在"}), 404

    user.password_hash = hash_password(new_password)
    session.commit()
    session.close()

    return jsonify({"message": "密码已重置"})
