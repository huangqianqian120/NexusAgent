"""Provider、模型和认证管理 API 路由."""

from flask import jsonify, request
import logging

from nexus.auth.manager import AuthManager
from nexus.config.settings import load_settings

log = logging.getLogger(__name__)


def register_routes(app):
    """在 Flask app 上注册 Provider/Model/Auth 管理路由."""

    # ---- Provider Management APIs ----

    @app.route("/api/v1/provider/current", methods=["GET"])
    def get_current_provider():
        try:
            settings = load_settings()
            profile_name, profile = settings.resolve_profile()
            return jsonify(
                {
                    "profile": profile_name,
                    "provider": profile.provider,
                    "model": profile.last_model or profile.default_model,
                    "base_url": profile.base_url,
                    "auth_source": profile.auth_source,
                }
            )
        except Exception as e:
            log.error(f"Error getting provider: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/provider/profiles", methods=["GET"])
    def get_all_profiles():
        try:
            manager = AuthManager()
            profiles = manager.get_profile_statuses()
            return jsonify({"profiles": profiles})
        except Exception as e:
            log.error(f"Error getting profiles: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/provider/switch", methods=["POST"])
    def switch_provider():
        try:
            data = request.get_json()
            profile_name = data.get("profile")
            if not profile_name:
                return jsonify({"error": "profile is required"}), 400
            manager = AuthManager()
            manager.use_profile(profile_name)
            return jsonify({"status": "switched", "profile": profile_name})
        except Exception as e:
            log.error(f"Error switching provider: {e}")
            return jsonify({"error": str(e)}), 500

    # ---- Model Management APIs ----

    @app.route("/api/v1/models", methods=["GET"])
    def get_available_models():
        try:
            settings = load_settings()
            profile_name, profile = settings.resolve_profile()
            models = []
            if profile.allowed_models:
                for m in profile.allowed_models:
                    models.append({"id": m, "name": m, "description": "Allowed model"})
            else:
                from nexus.config.settings import CLAUDE_MODEL_ALIAS_OPTIONS

                if profile.provider in {"anthropic", "anthropic_claude"}:
                    for value, label, desc in CLAUDE_MODEL_ALIAS_OPTIONS:
                        models.append({"id": value, "name": label, "description": desc})
                elif profile.base_url and "bigmodel.cn" in profile.base_url:
                    for m in [
                        "glm-4",
                        "glm-4-plus",
                        "glm-4-air",
                        "glm-4-flash",
                        "glm-4v",
                        "glm-4-long",
                    ]:
                        models.append({"id": m, "name": m, "description": "Zhipu AI"})
                elif profile.provider == "openai" or profile.api_format == "openai":
                    for m in ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]:
                        models.append({"id": m, "name": m, "description": "OpenAI compatible"})
            return jsonify(
                {"models": models, "current": profile.last_model or profile.default_model}
            )
        except Exception as e:
            log.error(f"Error getting models: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/model/current", methods=["GET"])
    def get_current_model():
        try:
            settings = load_settings()
            profile_name, profile = settings.resolve_profile()
            return jsonify(
                {"model": profile.last_model or profile.default_model, "profile": profile_name}
            )
        except Exception as e:
            log.error(f"Error getting model: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/model/switch", methods=["POST"])
    def switch_model():
        try:
            data = request.get_json()
            model_name = data.get("model")
            if not model_name:
                return jsonify({"error": "model is required"}), 400
            manager = AuthManager()
            settings = load_settings()
            profile_name, _ = settings.resolve_profile()
            if model_name.lower() == "default":
                manager.update_profile(profile_name, last_model="")
            else:
                manager.update_profile(profile_name, last_model=model_name)
            return jsonify({"status": "switched", "model": model_name})
        except Exception as e:
            log.error(f"Error switching model: {e}")
            return jsonify({"error": str(e)}), 500

    # ---- Auth Management APIs ----

    @app.route("/api/v1/auth/status", methods=["GET"])
    def get_auth_status():
        try:
            manager = AuthManager()
            auth_status = manager.get_auth_source_statuses()
            return jsonify({"auth_status": auth_status})
        except Exception as e:
            log.error(f"Error getting auth status: {e}")
            return jsonify({"error": str(e)}), 500
