"""工具和任务管理 API 路由."""

from flask import jsonify, request
from pathlib import Path
import asyncio
import threading
import logging

log = logging.getLogger(__name__)

# 持久化事件循环，避免每个请求创建/销毁事件循环
_event_loop: asyncio.AbstractEventLoop | None = None
_event_loop_lock = threading.Lock()


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """获取或创建持久化后台事件循环（线程安全）。"""
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        with _event_loop_lock:
            if _event_loop is None or _event_loop.is_closed():
                _event_loop = asyncio.new_event_loop()
                thread = threading.Thread(target=_event_loop.run_forever, daemon=True)
                thread.start()
    return _event_loop


def _run_async(coro):
    """在持久化事件循环中运行协程并返回结果。"""
    loop = _get_event_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def register_routes(app):
    """在 Flask app 上注册工具和任务管理路由."""

    # ---- Tools Management APIs ----

    @app.route("/api/v1/tools", methods=["GET"])
    def list_tools():
        try:
            from nexus.tools import create_default_tool_registry

            registry = create_default_tool_registry()
            tools = registry.to_api_schema()
            formatted = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("input_schema", {}),
                }
                for t in tools
            ]
            return jsonify({"tools": formatted})
        except Exception as e:
            log.error(f"Error listing tools: {e}")
            return jsonify({"error": str(e), "tools": []}), 500

    @app.route("/api/v1/tools/<tool_name>", methods=["GET"])
    def get_tool(tool_name: str):
        try:
            from nexus.tools import create_default_tool_registry

            registry = create_default_tool_registry()
            tool = registry.get(tool_name)
            if tool is None:
                return jsonify({"error": f"Tool not found: {tool_name}"}), 404
            schema = tool.to_api_schema()
            return jsonify(
                {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": schema.get("input_schema", {}),
                    "is_read_only": tool.is_read_only(tool.input_model()),
                }
            )
        except Exception as e:
            log.error(f"Error getting tool: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/tools/<tool_name>/execute", methods=["POST"])
    def execute_tool(tool_name: str):
        try:
            from nexus.tools import create_default_tool_registry
            from nexus.tools.base import ToolExecutionContext
            import os

            registry = create_default_tool_registry()
            tool = registry.get(tool_name)
            if tool is None:
                return jsonify({"error": f"Tool not found: {tool_name}"}), 404
            data = request.get_json() or {}
            args = tool.input_model.model_validate(data)
            context = ToolExecutionContext(cwd=Path(os.getcwd()))
            result = _run_async(tool.execute(args, context))
            return jsonify(
                {
                    "success": True,
                    "output": result.output,
                    "is_error": result.is_error,
                    "metadata": result.metadata,
                }
            )
        except Exception as e:
            log.error(f"Error executing tool {tool_name}: {e}")
            return jsonify({"error": str(e)}), 500

    # ---- Tasks Management APIs ----

    @app.route("/api/v1/tasks", methods=["GET"])
    def list_tasks():
        try:
            from nexus.tasks import get_task_manager

            manager = get_task_manager()
            tasks = manager.list_tasks()
            formatted = []
            for task in tasks:
                formatted.append(
                    {
                        "id": task.id,
                        "type": task.type,
                        "status": task.status,
                        "description": task.description,
                        "cwd": task.cwd,
                        "command": getattr(task, "command", None),
                        "prompt": getattr(task, "prompt", None),
                        "created_at": task.created_at,
                        "started_at": getattr(task, "started_at", None),
                        "metadata": task.metadata,
                    }
                )
            return jsonify({"tasks": formatted})
        except Exception as e:
            log.error(f"Error listing tasks: {e}")
            return jsonify({"error": str(e), "tasks": []}), 500

    @app.route("/api/v1/tasks/<task_id>", methods=["GET"])
    def get_task(task_id: str):
        try:
            from nexus.tasks import get_task_manager

            manager = get_task_manager()
            task = manager.get_task(task_id)
            if task is None:
                return jsonify({"error": f"Task not found: {task_id}"}), 404
            return jsonify(
                {
                    "id": task.id,
                    "type": task.type,
                    "status": task.status,
                    "description": task.description,
                    "cwd": task.cwd,
                    "command": getattr(task, "command", None),
                    "prompt": getattr(task, "prompt", None),
                    "created_at": task.created_at,
                    "started_at": getattr(task, "started_at", None),
                    "metadata": task.metadata,
                }
            )
        except Exception as e:
            log.error(f"Error getting task: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/tasks/<task_id>/output", methods=["GET"])
    def get_task_output(task_id: str):
        try:
            from nexus.tasks import get_task_manager
            import os

            manager = get_task_manager()
            task = manager.get_task(task_id)
            if task is None:
                return jsonify({"error": f"Task not found: {task_id}"}), 404
            output_path = task.output_file
            if output_path and os.path.exists(output_path):
                content = output_path.read_text(encoding="utf-8", errors="replace")
                if len(content) > 10000:
                    content = "...(truncated)\n" + content[-10000:]
            else:
                content = "(no output)"
            return jsonify({"task_id": task_id, "output": content, "status": task.status})
        except Exception as e:
            log.error(f"Error getting task output: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/tasks/<task_id>", methods=["DELETE"])
    def stop_task(task_id: str):
        try:
            from nexus.tasks import get_task_manager

            manager = get_task_manager()
            task = manager.get_task(task_id)
            if task is None:
                return jsonify({"error": f"Task not found: {task_id}"}), 404
            _run_async(manager.stop_task(task_id))
            return jsonify({"status": "stopped", "task_id": task_id})
        except Exception as e:
            log.error(f"Error stopping task: {e}")
            return jsonify({"error": str(e)}), 500
