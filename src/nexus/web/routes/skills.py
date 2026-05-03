"""技能管理 API 路由."""

from flask import jsonify, request
import logging
import re

log = logging.getLogger(__name__)


def register_routes(app):
    """在 Flask app 上注册技能管理路由."""

    @app.route("/api/v1/skills", methods=["GET"])
    def list_skills():
        try:
            from nexus.skills import load_skill_registry
            from personal_agent.workspace import get_workspace_root
            workspace_root = get_workspace_root()
            skill_registry = load_skill_registry(workspace_root)
            skills = skill_registry.list_skills()
            formatted = [{"name": s.name, "description": s.description, "source": s.source} for s in skills]
            return jsonify({"skills": formatted})
        except Exception as e:
            log.error(f"Error listing skills: {e}")
            return jsonify({"error": str(e), "skills": []}), 500

    @app.route("/api/v1/skills/<skill_name>", methods=["GET"])
    def get_skill(skill_name: str):
        try:
            from nexus.skills import load_skill_registry
            from personal_agent.workspace import get_workspace_root
            workspace_root = get_workspace_root()
            skill_registry = load_skill_registry(workspace_root)
            skill = skill_registry.get(skill_name)
            if skill is None:
                return jsonify({"error": f"Skill not found: {skill_name}"}), 404
            return jsonify({
                "name": skill.name, "description": skill.description,
                "content": skill.content, "source": skill.source,
            })
        except Exception as e:
            log.error(f"Error getting skill: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/skills", methods=["POST"])
    def upload_skill():
        try:
            from personal_agent.workspace import get_skills_dir
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400
            name = data.get("name", "").strip()
            description = data.get("description", "").strip()
            content = data.get("content", "").strip()
            if not name:
                return jsonify({"error": "Skill name is required"}), 400
            if not content:
                return jsonify({"error": "Skill content is required"}), 400
            if not re.match(r"^[a-zA-Z0-9_-]+$", name):
                return jsonify({"error": "Skill name can only contain letters, numbers, underscores and hyphens"}), 400
            skills_dir = get_skills_dir()
            skill_path = skills_dir / f"{name}.md"
            file_content = f"# Skill: {name}\n\n## Description\n{description}\n\n## Content\n{content}"
            skill_path.write_text(file_content, encoding="utf-8")
            return jsonify({"status": "uploaded", "name": name, "path": str(skill_path)})
        except Exception as e:
            log.error(f"Error uploading skill: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/skills/<skill_name>", methods=["DELETE"])
    def delete_skill(skill_name: str):
        try:
            from personal_agent.workspace import get_skills_dir
            skills_dir = get_skills_dir()
            skill_path = skills_dir / f"{skill_name}.md"
            if not skill_path.exists():
                return jsonify({"error": f"Skill not found: {skill_name}"}), 404
            skill_path.unlink()
            return jsonify({"status": "deleted", "name": skill_name})
        except Exception as e:
            log.error(f"Error deleting skill: {e}")
            return jsonify({"error": str(e)}), 500
