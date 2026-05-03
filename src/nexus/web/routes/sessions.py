"""会话管理 API 路由."""

from flask import jsonify
import logging

log = logging.getLogger(__name__)


def register_routes(app):
    """在 Flask app 上注册会话管理路由."""

    @app.route("/api/v1/sessions", methods=["GET"])
    def list_sessions():
        try:
            from nexus.services.session_backend import DEFAULT_SESSION_BACKEND
            import os
            from datetime import datetime

            cwd = os.getcwd()
            sessions = DEFAULT_SESSION_BACKEND.list_snapshots(cwd, limit=50)
            formatted = []
            for s in sessions:
                ts = s.get("created_at", 0)
                created = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "N/A"
                formatted.append(
                    {
                        "id": s["session_id"],
                        "summary": s.get("summary", "(no summary)"),
                        "message_count": s.get("message_count", 0),
                        "model": s.get("model", ""),
                        "created_at": created,
                        "timestamp": ts,
                    }
                )
            return jsonify({"sessions": formatted})
        except Exception as e:
            log.error(f"Error listing sessions: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/sessions/<session_id>", methods=["GET"])
    def get_session(session_id: str):
        try:
            from nexus.services.session_backend import DEFAULT_SESSION_BACKEND
            import os

            cwd = os.getcwd()
            session = DEFAULT_SESSION_BACKEND.load_by_id(cwd, session_id)
            if session is None:
                return jsonify({"error": "Session not found"}), 404
            return jsonify({"session": session})
        except Exception as e:
            log.error(f"Error getting session: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/sessions", methods=["DELETE"])
    def clear_current_session():
        try:
            return jsonify({"status": "cleared"})
        except Exception as e:
            log.error(f"Error clearing session: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/sessions/<session_id>", methods=["DELETE"])
    def delete_session(session_id: str):
        try:
            from nexus.services.session_backend import DEFAULT_SESSION_BACKEND
            import os

            cwd = os.getcwd()
            session_dir = DEFAULT_SESSION_BACKEND.get_session_dir(cwd)
            session_path = session_dir / f"session-{session_id}.json"
            if session_path.exists():
                session_path.unlink()
            return jsonify({"status": "deleted"})
        except Exception as e:
            log.error(f"Error deleting session: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/sessions/<session_id>/resume", methods=["POST"])
    def resume_session(session_id: str):
        try:
            from nexus.services.session_backend import DEFAULT_SESSION_BACKEND
            import os

            cwd = os.getcwd()
            session = DEFAULT_SESSION_BACKEND.load_by_id(cwd, session_id)
            if session is None:
                return jsonify({"error": "Session not found"}), 404
            return jsonify({"session": session, "ready_to_resume": True})
        except Exception as e:
            log.error(f"Error resuming session: {e}")
            return jsonify({"error": str(e)}), 500
