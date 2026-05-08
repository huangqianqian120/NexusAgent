"""多用户 API 服务入口（独立运行，与原有单用户 server.py 共存）."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS

from nexus.multi_user.db import create_all_tables
from nexus.multi_user.middleware import optional_auth

log = logging.getLogger(__name__)

# ---- Flask App ----

_server_file = Path(__file__).resolve()
_project_root = _server_file.parent.parent.parent.parent
if str(_project_root) not in os.sys.path:
    os.sys.path.insert(1, str(_project_root))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("MULTI_USER_SECRET_KEY") or os.environ.get("SECRET_KEY") or "nexus-multi-user-dev"

# CORS（同源部署）
CORS(app, resources={r"/api/*": {"origins": "*"}})


# ---- 健康检查 ----


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "nexus-multi-user"})


# ---- 用户信息 API（需登录） ----


@app.route("/api/user/credits", methods=["GET"])
@optional_auth
def my_credits():
    from flask import g
    from nexus.multi_user.db import get_session
    from nexus.multi_user.models import User

    if not getattr(g, "current_user", None):
        return jsonify({"error": "Unauthorized"}), 401

    user_id = g.current_user["user_id"]
    session = get_session()
    user = session.get(User, user_id)
    session.close()

    if not user:
        return jsonify({"error": "用户不存在"}), 404

    return jsonify({
        "credits_balance": str(user.credits_balance),
        "email": user.email,
        "username": user.username,
    })


@app.route("/api/user/credits/history", methods=["GET"])
@optional_auth
def my_credits_history():
    from flask import g, request
    from sqlmodel import select
    from nexus.multi_user.db import get_session
    from nexus.multi_user.models import CreditTransaction

    if not getattr(g, "current_user", None):
        return jsonify({"error": "Unauthorized"}), 401

    user_id = g.current_user["user_id"]
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    offset = (page - 1) * page_size

    session = get_session()
    query = select(CreditTransaction).where(
        CreditTransaction.user_id == user_id
    ).order_by(CreditTransaction.created_at.desc())

    txs = session.exec(query.offset(offset).limit(page_size)).all()
    session.close()

    return jsonify({
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
        ]
    })


# ---- 注册多用户路由 ----


def register_multi_user_routes(app: Flask) -> None:
    """将多用户相关路由注册到 Flask app."""
    from nexus.multi_user.routes.auth import bp as auth_bp
    from nexus.multi_user.routes.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)


register_multi_user_routes(app)


# ---- 服务器入口 ----


def run_server(host: str = "0.0.0.0", port: int = 8766, debug: bool = False):
    """启动多用户 API 服务器."""
    # 初始化数据库表
    create_all_tables()

    # 初始化默认模型定价
    from nexus.multi_user.credits import init_default_pricing
    init_default_pricing()

    log.info("启动 NexusAgent 多用户服务 → http://%s:%s", host, port)
    log.info("API 端点:")
    log.info("  POST /api/auth/register  - 注册")
    log.info("  POST /api/auth/login     - 登录")
    log.info("  GET  /api/auth/me       - 当前用户信息")
    log.info("  GET  /api/admin/users   - 用户列表（管理员）")
    log.info("  POST /api/admin/credits/allocate - 分配 Credits（管理员）")

    from flask_socketio import SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", logger=False)
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


def create_app() -> Flask:
    """创建并配置 Flask app（用于 gunicorn 等生产服务器）."""
    create_all_tables()
    from nexus.multi_user.credits import init_default_pricing
    init_default_pricing()
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server(debug=False)