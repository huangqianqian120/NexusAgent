"""Flask + Flask-SocketIO server for NexusAgent Web UI."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import queue
import sys
import threading
from pathlib import Path
from typing import Any

# Add project root to sys.path so 'personal_agent' can be imported
_server_file = Path(__file__).resolve()
_project_root = _server_file.parent.parent.parent.parent  # web/server.py -> nexus -> src -> project root (4 parents)
# Insert at position 1 (after current directory) so flask/other deps still resolve first
if str(_project_root) not in sys.path:
    sys.path.insert(1, str(_project_root))

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from nexus.auth.manager import AuthManager
from nexus.config.settings import load_settings
from nexus.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    CompactProgressEvent,
    ErrorEvent,
    StatusEvent,
    StreamEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from nexus.memory.store import MemoryStore
from nexus.memory.types import MemoryType, RecordStatus
from nexus.ui.protocol import BackendEvent, TranscriptItem
from nexus.ui.runtime import build_runtime, close_runtime, handle_line, start_runtime
from nexus.tasks import get_task_manager
from nexus.web.web_backend_host import WebBackendHost, WebBackendHostConfig

log = logging.getLogger(__name__)

# SECURITY: SECRET_KEY and CORS_ORIGINS must be set via environment variables in production
# Generate a warning if using defaults in non-dev environments
_secret_key = os.environ.get("SECRET_KEY")
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")

if not _secret_key:
    import warnings
    warnings.warn(
        "SECRET_KEY not set via environment variable. "
        "Using a predictable default is insecure for production. "
        "Set SECRET_KEY environment variable for production deployments.",
        UserWarning,
    )
    _secret_key = "nexus-web-dev-secret-do-not-use-in-production"

# Create Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = _secret_key
app.config["CORS_ALLOWED_ORIGINS"] = _cors_origins

# Enable CORS only for specified origins
_allowed_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
CORS(app, resources={r"/api/*": {"origins": _allowed_origins}})

# Create SocketIO instance
socketio = SocketIO(
    app,
    cors_allowed_origins=_allowed_origins,
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)

# Store active sessions
active_sessions: dict[str, Any] = {}

PROTOCOL_PREFIX = "OHJSON:"


class SocketIOWebAdapter:
    """Adapter to make WebBackendHost work with Flask-SocketIO."""

    def __init__(self, socket, session_id: str):
        self._socket = socket
        self._session_id = session_id
        self._request_queue: queue.Queue = queue.Queue()
        self._write_lock = threading.Lock()

    async def send_text(self, payload: str) -> None:
        """Send text to the client via SocketIO."""
        with self._write_lock:
            self._socket.emit("message", PROTOCOL_PREFIX + payload)

    async def receive_text(self) -> str:
        """Receive text from the client (converts thread-safe queue to async)."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._request_queue.get
        )

    def queue_request(self, request: dict) -> None:
        """Queue a request from SocketIO event (runs in worker thread)."""
        from nexus.ui.protocol import FrontendRequest
        try:
            req = FrontendRequest.model_validate(request)
            self._request_queue.put_nowait(req)
        except Exception as exc:
            log.warning(f"Failed to queue request: {exc}, request: {request}")

    def close(self) -> None:
        """Close the adapter."""
        from nexus.ui.protocol import FrontendRequest
        self._request_queue.put_nowait(FrontendRequest(type="shutdown"))


class SocketIOBackendHost(WebBackendHost):
    """WebBackendHost variant that uses SocketIO adapter."""

    def __init__(self, adapter: SocketIOWebAdapter, config: WebBackendHostConfig) -> None:
        self._adapter = adapter
        # Don't call parent __init__, we'll use parent's methods
        self._config = config
        self._bundle = None
        self._write_lock = asyncio.Lock()
        self._request_queue: asyncio.Queue = asyncio.Queue()
        self._permission_requests: dict[str, asyncio.Future[bool]] = {}
        self._question_requests: dict[str, asyncio.Future[str]] = {}
        self._permission_lock = asyncio.Lock()
        self._busy = False
        self._running = True
        self._last_tool_inputs: dict[str, dict] = {}

    async def run(self) -> None:
        """WebSocket main loop with session restore support."""
        from nexus.engine.messages import ConversationMessage

        self._bundle = await build_runtime(
            model=self._config.model,
            max_turns=self._config.max_turns,
            base_url=self._config.base_url,
            system_prompt=self._config.system_prompt,
            api_key=self._config.api_key,
            api_format=self._config.api_format,
            active_profile=self._config.active_profile,
            api_client=self._config.api_client,
            cwd=self._config.cwd,
            restore_messages=self._config.restore_messages,
            permission_prompt=self._ask_permission,
            ask_user_prompt=self._ask_question,
            enforce_max_turns=self._config.enforce_max_turns,
            permission_mode=self._config.permission_mode,
            session_backend=self._config.session_backend,
            extra_skill_dirs=self._config.extra_skill_dirs,
            extra_plugin_roots=self._config.extra_plugin_roots,
        )
        await start_runtime(self._bundle)

        await self._emit(
            BackendEvent.ready(
                self._bundle.app_state.get(),
                get_task_manager().list_tasks(),
                [f"/{command.name}" for command in self._bundle.commands.list_commands()],
            )
        )

        # Send restored messages to frontend if this is a resumed session
        if self._config.restore_messages:
            for msg in self._config.restore_messages:
                try:
                    if isinstance(msg, dict):
                        role = msg.get("role", "assistant")
                        text = ""
                        if isinstance(msg.get("content"), list):
                            for block in msg["content"]:
                                if block.get("type") == "text":
                                    text = block.get("text", "")
                                    break
                        elif isinstance(msg.get("text"), str):
                            text = msg["text"]
                    else:
                        role = getattr(msg, "role", "assistant")
                        text = getattr(msg, "text", "")

                    item = TranscriptItem(
                        role=role,
                        text=text or "",
                    )
                    await self._emit(BackendEvent(type="transcript_item", item=item))
                except Exception as e:
                    log.warning(f"Failed to emit restored message: {e}")

        await self._emit(self._status_snapshot())

        reader = asyncio.create_task(self._read_requests())
        try:
            while self._running:
                request = await self._request_queue.get()
                if request.type == "shutdown":
                    await self._emit(BackendEvent(type="shutdown"))
                    break
                if request.type in ("permission_response", "question_response"):
                    continue
                if request.type == "list_sessions":
                    await self._handle_list_sessions()
                    continue
                if request.type == "select_command":
                    await self._handle_select_command(request.command or "")
                    continue
                if request.type == "apply_select_command":
                    if self._busy:
                        await self._emit(BackendEvent(type="error", message="Session is busy"))
                        continue
                    self._busy = True
                    try:
                        should_continue = await self._apply_select_command(
                            request.command or "",
                            request.value or "",
                        )
                    finally:
                        self._busy = False
                    if not should_continue:
                        await self._emit(BackendEvent(type="shutdown"))
                        self._running = False
                    continue
                if request.type == "submit_line":
                    if self._busy:
                        await self._emit(BackendEvent(type="error", message="Session is busy"))
                        continue
                    line = (request.line or "").strip()
                    if not line:
                        continue
                    self._busy = True
                    try:
                        should_continue = await self._process_line(line)
                    finally:
                        self._busy = False
                    if not should_continue:
                        await self._emit(BackendEvent(type="shutdown"))
                        self._running = False
                    continue
                log.warning("Unexpected request type: %s", request.type)
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader

    async def _process_line(self, line: str, *, transcript_line: str | None = None) -> bool:
        """Process a line of input with proper render callbacks."""
        assert self._bundle is not None
        await self._emit(
            BackendEvent(type="transcript_item", item=TranscriptItem(role="user", text=transcript_line or line))
        )

        async def _print_system(message: str) -> None:
            await self._emit(
                BackendEvent(type="transcript_item", item=TranscriptItem(role="system", text=message))
            )

        async def _render_event(event: StreamEvent) -> None:
            if isinstance(event, AssistantTextDelta):
                await self._emit(BackendEvent(type="assistant_delta", message=event.text))
                return
            if isinstance(event, CompactProgressEvent):
                await self._emit(
                    BackendEvent(
                        type="compact_progress",
                        compact_phase=event.phase,
                        compact_trigger=event.trigger,
                        attempt=event.attempt,
                        compact_checkpoint=event.checkpoint,
                        compact_metadata=event.metadata,
                        message=event.message,
                    )
                )
                return
            if isinstance(event, AssistantTurnComplete):
                await self._emit(
                    BackendEvent(
                        type="assistant_complete",
                        message=event.message.text.strip(),
                        item=TranscriptItem(role="assistant", text=event.message.text.strip()),
                    )
                )
                await self._emit(BackendEvent.tasks_snapshot(get_task_manager().list_tasks()))
                return
            if isinstance(event, ToolExecutionStarted):
                self._last_tool_inputs[event.tool_name] = event.tool_input or {}
                await self._emit(
                    BackendEvent(
                        type="tool_started",
                        tool_name=event.tool_name,
                        tool_input=event.tool_input,
                        item=TranscriptItem(
                            role="tool",
                            text=f"{event.tool_name} {json.dumps(event.tool_input, ensure_ascii=True)}",
                            tool_name=event.tool_name,
                            tool_input=event.tool_input,
                        ),
                    )
                )
                return
            if isinstance(event, ToolExecutionCompleted):
                await self._emit(
                    BackendEvent(
                        type="tool_completed",
                        tool_name=event.tool_name,
                        output=event.output,
                        is_error=event.is_error,
                        item=TranscriptItem(
                            role="tool_result",
                            text=event.output,
                            tool_name=event.tool_name,
                            is_error=event.is_error,
                        ),
                    )
                )
                await self._emit(BackendEvent.tasks_snapshot(get_task_manager().list_tasks()))
                await self._emit(self._status_snapshot())
                # Emit todo_update when TodoWrite tool runs
                if event.tool_name in ("TodoWrite", "todo_write"):
                    tool_input = self._last_tool_inputs.get(event.tool_name, {})
                    todos = tool_input.get("todos") or tool_input.get("content") or []
                    if isinstance(todos, list) and todos:
                        lines = []
                        for item in todos:
                            if isinstance(item, dict):
                                checked = item.get("status", "") in ("done", "completed", "x", True)
                                text = item.get("content") or item.get("text") or str(item)
                                lines.append(f"- [{'x' if checked else ' '}] {text}")
                        if lines:
                            await self._emit(BackendEvent(type="todo_update", todo_markdown="\n".join(lines)))
                # Emit plan_mode_change when plan-related tools complete
                if event.tool_name in ("set_permission_mode", "plan_mode"):
                    assert self._bundle is not None
                    new_mode = self._bundle.app_state.get().permission_mode
                    await self._emit(BackendEvent(type="plan_mode_change", plan_mode=new_mode))
                return
            if isinstance(event, ErrorEvent):
                await self._emit(BackendEvent(type="error", message=event.message))
                await self._emit(
                    BackendEvent(type="transcript_item", item=TranscriptItem(role="system", text=event.message))
                )
                return
            if isinstance(event, StatusEvent):
                await self._emit(
                    BackendEvent(type="transcript_item", item=TranscriptItem(role="system", text=event.message))
                )
                return

        async def _clear_output() -> None:
            await self._emit(BackendEvent(type="clear_transcript"))

        should_continue = await handle_line(
            self._bundle,
            line,
            print_system=_print_system,
            render_event=_render_event,
            clear_output=_clear_output,
        )
        await self._emit(self._status_snapshot())
        await self._emit(BackendEvent.tasks_snapshot(get_task_manager().list_tasks()))
        await self._emit(BackendEvent(type="line_complete"))
        return should_continue

    async def _read_requests(self) -> None:
        """Read requests from SocketIO adapter."""
        from nexus.ui.protocol import FrontendRequest
        log.info("_read_requests: started")
        while True:
            try:
                log.info("_read_requests: waiting for message...")
                raw = await asyncio.wait_for(self._adapter.receive_text(), timeout=60)
                preview = raw[:100] if isinstance(raw, str) else repr(raw)
                log.info(f"_read_requests: got raw: {preview if raw else 'empty'}")
            except asyncio.TimeoutError:
                log.info("_read_requests: timeout")
                await self._request_queue.put(FrontendRequest(type="shutdown"))
                return
            except Exception as e:
                log.info(f"_read_requests: exception: {e}")
                await self._request_queue.put(FrontendRequest(type="shutdown"))
                return

            if not raw:
                log.info("_read_requests: empty raw")
                continue

            try:
                if isinstance(raw, FrontendRequest):
                    request = raw
                elif isinstance(raw, str):
                    request = FrontendRequest.model_validate_json(raw)
                else:
                    request = FrontendRequest.model_validate(raw)
                log.info(f"_read_requests: validated: {request.type}")
            except Exception as exc:
                log.info(f"_read_requests: validation error: {exc}")
                await self._emit_error(f"Invalid request: {exc}")
                continue

            if request.type == "permission_response" and request.request_id in self._permission_requests:
                future = self._permission_requests[request.request_id]
                if not future.done():
                    future.set_result(bool(request.allowed))
                continue
            if request.type == "question_response" and request.request_id in self._question_requests:
                future = self._question_requests[request.request_id]
                if not future.done():
                    future.set_result(request.answer or "")
                continue
            await self._request_queue.put(request)

    async def _emit(self, event) -> None:
        """Send event to SocketIO client."""
        from nexus.ui.protocol import BackendEvent
        async with self._write_lock:
            # send_text already adds PROTOCOL_PREFIX, so just send the JSON
            await self._adapter.send_text(event.model_dump_json())

    async def _emit_error(self, message: str) -> None:
        """Emit error event."""
        from nexus.ui.protocol import BackendEvent
        await self._emit(BackendEvent(type="error", message=message))


def get_config() -> WebBackendHostConfig:
    """Build WebBackendHostConfig from current settings."""
    import sys
    from pathlib import Path
    # Add project root / nexus to path for personal-agent imports
    project_root = Path(__file__).parent.parent.parent.parent  # src/nexus/web/server.py -> project root
    nexus_path = project_root / "nexus"
    if nexus_path.exists():
        # Remove any existing nexus entries from sys.path to avoid conflict with src/nexus
        sys.path = [p for p in sys.path if not p.endswith('/src/nexus') and p != 'src/nexus']
        # Insert project root at the beginning so nexus/ takes precedence
        sys.path.insert(0, str(project_root))

    from nexus.auth.manager import AuthManager
    settings = load_settings()
    profile_name, profile = settings.resolve_profile()

    # Load API key from auth manager
    manager = AuthManager(settings)
    auth_source = profile.auth_source
    storage_provider = auth_source.replace("_api_key", "") if auth_source.endswith("_api_key") else auth_source
    api_key = None

    # Try to load credential
    from nexus.auth.storage import load_credential
    cred = load_credential(storage_provider, "api_key")
    if cred:
        api_key = cred
    # Fallback to settings api_key
    if not api_key and getattr(settings, "api_key", ""):
        api_key = settings.api_key

    # Initialize nexus workspace and build the nexus system prompt
    # so that SOUL.md, IDENTITY.md, USER.md, BOOTSTRAP.md are respected
    import importlib
    workspace_module = importlib.import_module("personal_agent.workspace")
    prompts_module = importlib.import_module("personal_agent.prompts")
    get_workspace_root = workspace_module.get_workspace_root
    initialize_workspace = workspace_module.initialize_workspace
    get_skills_dir = workspace_module.get_skills_dir
    get_plugins_dir = workspace_module.get_plugins_dir
    build_nexus_system_prompt = prompts_module.build_nexus_system_prompt
    workspace = initialize_workspace()
    workspace_root = get_workspace_root()
    cwd = os.getcwd()
    system_prompt = build_nexus_system_prompt(
        cwd,
        workspace=workspace_root,
        extra_prompt=None,
        include_project_memory=True,
    )
    extra_skill_dirs = (str(get_skills_dir(workspace_root)),)
    extra_plugin_roots = (str(get_plugins_dir(workspace_root)),)

    return WebBackendHostConfig(
        model=profile.last_model or profile.default_model,
        base_url=profile.base_url,
        api_format=profile.api_format,
        active_profile=profile_name,
        api_key=api_key,
        cwd=cwd,
        session_backend=None,
        system_prompt=system_prompt,
        extra_skill_dirs=extra_skill_dirs,
        extra_plugin_roots=extra_plugin_roots,
    )


@app.route("/api/v1/status", methods=["GET"])
def get_status():
    """Get current status."""
    try:
        settings = load_settings()
        profile_name, profile = settings.resolve_profile()
        manager = AuthManager(settings)

        return jsonify({
            "model": profile.last_model or profile.default_model,
            "provider": profile.provider,
            "profile": profile_name,
            "auth_status": manager.get_auth_status().get(profile.provider, {}),
        })
    except Exception as e:
        log.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/settings", methods=["GET"])
def get_settings():
    """Get current settings."""
    try:
        settings = load_settings()
        return jsonify(settings.model_dump())
    except Exception as e:
        log.error(f"Error getting settings: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/settings", methods=["PUT"])
def update_settings():
    """Update settings."""
    try:
        data = request.get_json()
        settings = load_settings()

        allowed_fields = ["theme", "vim_mode", "voice_mode", "fast_mode", "effort", "passes", "verbose"]
        for field in allowed_fields:
            if field in data:
                setattr(settings, field, data[field])

        from nexus.config.settings import save_settings
        save_settings(settings)

        return jsonify({"status": "ok"})
    except Exception as e:
        log.error(f"Error updating settings: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/commands", methods=["GET"])
def get_commands():
    """Get available commands."""
    try:
        from nexus.commands.registry import create_default_command_registry
        registry = create_default_command_registry()
        commands = [f"/{cmd.name}" for cmd in registry.list_commands()]
        return jsonify({"commands": commands})
    except Exception as e:
        log.error(f"Error getting commands: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/providers", methods=["GET"])
def get_providers():
    """Get available provider profiles."""
    try:
        manager = AuthManager()
        profiles = manager.get_profile_statuses()
        return jsonify({"profiles": profiles})
    except Exception as e:
        log.error(f"Error getting providers: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


# ---- Session Management APIs ----

@app.route("/api/v1/sessions", methods=["GET"])
def list_sessions():
    """List all saved sessions."""
    try:
        from nexus.services.session_backend import DEFAULT_SESSION_BACKEND
        import os

        cwd = os.getcwd()
        sessions = DEFAULT_SESSION_BACKEND.list_snapshots(cwd, limit=50)
        # Format for frontend
        formatted = []
        for s in sessions:
            from datetime import datetime
            ts = s.get("created_at", 0)
            created = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "N/A"
            formatted.append({
                "id": s["session_id"],
                "summary": s.get("summary", "(no summary)"),
                "message_count": s.get("message_count", 0),
                "model": s.get("model", ""),
                "created_at": created,
                "timestamp": ts,
            })
        return jsonify({"sessions": formatted})
    except Exception as e:
        log.error(f"Error listing sessions: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/sessions/<session_id>", methods=["GET"])
def get_session(session_id: str):
    """Get a specific session by ID."""
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
    """Clear the current session (equivalent to /clear command)."""
    try:
        # The actual clear is done via WebSocket protocol
        # This just marks the session as ended
        return jsonify({"status": "cleared"})
    except Exception as e:
        log.error(f"Error clearing session: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id: str):
    """Delete a specific session."""
    try:
        from nexus.services.session_backend import DEFAULT_SESSION_BACKEND
        import os

        cwd = os.getcwd()
        session_dir = DEFAULT_SESSION_BACKEND.get_session_dir(cwd)

        # Try to delete session file
        session_path = session_dir / f"session-{session_id}.json"
        if session_path.exists():
            session_path.unlink()

        return jsonify({"status": "deleted"})
    except Exception as e:
        log.error(f"Error deleting session: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/sessions/<session_id>/resume", methods=["POST"])
def resume_session(session_id: str):
    """Resume a specific session via WebSocket."""
    try:
        # Session resume is handled via WebSocket protocol
        # This endpoint returns the session data for the frontend to trigger resume
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


# ---- Skills Management APIs ----

@app.route("/api/v1/skills", methods=["GET"])
def list_skills():
    """List all available skills."""
    try:
        from nexus.skills import load_skill_registry
        from personal_agent.workspace import get_workspace_root

        workspace_root = get_workspace_root()
        skill_registry = load_skill_registry(workspace_root)
        skills = skill_registry.list_skills()

        formatted = []
        for skill in skills:
            formatted.append({
                "name": skill.name,
                "description": skill.description,
                "source": skill.source,
            })

        return jsonify({"skills": formatted})
    except Exception as e:
        log.error(f"Error listing skills: {e}")
        return jsonify({"error": str(e), "skills": []}), 500


@app.route("/api/v1/skills/<skill_name>", methods=["GET"])
def get_skill(skill_name: str):
    """Get a specific skill content."""
    try:
        from nexus.skills import load_skill_registry
        from personal_agent.workspace import get_workspace_root

        workspace_root = get_workspace_root()
        skill_registry = load_skill_registry(workspace_root)
        skill = skill_registry.get(skill_name)

        if skill is None:
            return jsonify({"error": f"Skill not found: {skill_name}"}), 404

        return jsonify({
            "name": skill.name,
            "description": skill.description,
            "content": skill.content,
            "source": skill.source,
        })
    except Exception as e:
        log.error(f"Error getting skill: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/skills", methods=["POST"])
def upload_skill():
    """Upload a new skill."""
    try:
        from personal_agent.workspace import get_skills_dir
        import re

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

        # Validate name format
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            return jsonify({"error": "Skill name can only contain letters, numbers, underscores and hyphens"}), 400

        # Save skill file
        skills_dir = get_skills_dir()
        skill_path = skills_dir / f"{name}.md"

        # Format: # Skill: {name}\n\n## Description\n{description}\n\n## Content\n{content}
        file_content = f"# Skill: {name}\n\n## Description\n{description}\n\n## Content\n{content}"

        skill_path.write_text(file_content, encoding="utf-8")

        return jsonify({
            "status": "uploaded",
            "name": name,
            "path": str(skill_path),
        })
    except Exception as e:
        log.error(f"Error uploading skill: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/skills/<skill_name>", methods=["DELETE"])
def delete_skill(skill_name: str):
    """Delete a skill."""
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


# ---- Tools Management APIs ----

@app.route("/api/v1/tools", methods=["GET"])
def list_tools():
    """List all available built-in tools."""
    try:
        from nexus.tools import create_default_tool_registry

        registry = create_default_tool_registry()
        tools = registry.to_api_schema()

        formatted = []
        for tool in tools:
            formatted.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("input_schema", {}),
            })

        return jsonify({"tools": formatted})
    except Exception as e:
        log.error(f"Error listing tools: {e}")
        return jsonify({"error": str(e), "tools": []}), 500


@app.route("/api/v1/tools/<tool_name>", methods=["GET"])
def get_tool(tool_name: str):
    """Get a specific tool schema."""
    try:
        from nexus.tools import create_default_tool_registry

        registry = create_default_tool_registry()
        tool = registry.get(tool_name)

        if tool is None:
            return jsonify({"error": f"Tool not found: {tool_name}"}), 404

        schema = tool.to_api_schema()
        return jsonify({
            "name": schema["name"],
            "description": schema["description"],
            "parameters": schema.get("input_schema", {}),
            "is_read_only": tool.is_read_only(tool.input_model()),
        })
    except Exception as e:
        log.error(f"Error getting tool: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/tools/<tool_name>/execute", methods=["POST"])
def execute_tool(tool_name: str):
    """Execute a tool with given arguments."""
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
        result = asyncio.run(tool.execute(args, context))

        return jsonify({
            "success": True,
            "output": result.output,
            "is_error": result.is_error,
            "metadata": result.metadata,
        })
    except Exception as e:
        log.error(f"Error executing tool {tool_name}: {e}")
        return jsonify({"error": str(e)}), 500


# ---- Provider Management APIs ----

@app.route("/api/v1/provider/current", methods=["GET"])
def get_current_provider():
    """Get current active provider profile."""
    try:
        settings = load_settings()
        profile_name, profile = settings.resolve_profile()
        return jsonify({
            "profile": profile_name,
            "provider": profile.provider,
            "model": profile.last_model or profile.default_model,
            "base_url": profile.base_url,
            "auth_source": profile.auth_source,
        })
    except Exception as e:
        log.error(f"Error getting provider: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/provider/profiles", methods=["GET"])
def get_all_profiles():
    """Get all provider profiles."""
    try:
        manager = AuthManager()
        profiles = manager.get_profile_statuses()
        return jsonify({"profiles": profiles})
    except Exception as e:
        log.error(f"Error getting profiles: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/provider/switch", methods=["POST"])
def switch_provider():
    """Switch to a different provider profile."""
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


# ---- Tasks Management APIs ----

@app.route("/api/v1/tasks", methods=["GET"])
def list_tasks():
    """List all background tasks."""
    try:
        from nexus.tasks import get_task_manager

        manager = get_task_manager()
        tasks = manager.list_tasks()

        formatted = []
        for task in tasks:
            formatted.append({
                "id": task.id,
                "type": task.type,
                "status": task.status,
                "description": task.description,
                "cwd": task.cwd,
                "command": getattr(task, 'command', None),
                "prompt": getattr(task, 'prompt', None),
                "created_at": task.created_at,
                "started_at": getattr(task, 'started_at', None),
                "metadata": task.metadata,
            })

        return jsonify({"tasks": formatted})
    except Exception as e:
        log.error(f"Error listing tasks: {e}")
        return jsonify({"error": str(e), "tasks": []}), 500


@app.route("/api/v1/tasks/<task_id>", methods=["GET"])
def get_task(task_id: str):
    """Get a specific task details."""
    try:
        from nexus.tasks import get_task_manager

        manager = get_task_manager()
        task = manager.get_task(task_id)

        if task is None:
            return jsonify({"error": f"Task not found: {task_id}"}), 404

        return jsonify({
            "id": task.id,
            "type": task.type,
            "status": task.status,
            "description": task.description,
            "cwd": task.cwd,
            "command": getattr(task, 'command', None),
            "prompt": getattr(task, 'prompt', None),
            "created_at": task.created_at,
            "started_at": getattr(task, 'started_at', None),
            "metadata": task.metadata,
        })
    except Exception as e:
        log.error(f"Error getting task: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/tasks/<task_id>/output", methods=["GET"])
def get_task_output(task_id: str):
    """Get task output log."""
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
            # Limit to last 10000 chars
            if len(content) > 10000:
                content = "...(truncated)\n" + content[-10000:]
        else:
            content = "(no output)"

        return jsonify({
            "task_id": task_id,
            "output": content,
            "status": task.status,
        })
    except Exception as e:
        log.error(f"Error getting task output: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/tasks/<task_id>", methods=["DELETE"])
def stop_task(task_id: str):
    """Stop a running task."""
    try:
        from nexus.tasks import get_task_manager

        manager = get_task_manager()
        task = manager.get_task(task_id)

        if task is None:
            return jsonify({"error": f"Task not found: {task_id}"}), 404

        # Stop the task if running
        asyncio.run(manager.stop_task(task_id))

        return jsonify({"status": "stopped", "task_id": task_id})
    except Exception as e:
        log.error(f"Error stopping task: {e}")
        return jsonify({"error": str(e)}), 500


# ---- Model Management APIs ----

@app.route("/api/v1/models", methods=["GET"])
def get_available_models():
    """Get available models for current provider."""
    try:
        settings = load_settings()
        profile_name, profile = settings.resolve_profile()

        models = []
        # If profile has allowed_models, use those
        if profile.allowed_models:
            for m in profile.allowed_models:
                models.append({"id": m, "name": m, "description": "Allowed model"})
        else:
            # Use default model list based on provider
            from nexus.config.settings import CLAUDE_MODEL_ALIAS_OPTIONS

            if profile.provider in {"anthropic", "anthropic_claude"}:
                for value, label, desc in CLAUDE_MODEL_ALIAS_OPTIONS:
                    models.append({"id": value, "name": label, "description": desc})
            elif profile.base_url and "bigmodel.cn" in profile.base_url:
                # Zhipu AI models
                for m in ["glm-4", "glm-4-plus", "glm-4-air", "glm-4-flash", "glm-4v", "glm-4-long"]:
                    models.append({"id": m, "name": m, "description": "Zhipu AI"})
            elif profile.provider == "openai" or profile.api_format == "openai":
                # OpenAI compatible models
                for m in ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]:
                    models.append({"id": m, "name": m, "description": "OpenAI compatible"})

        return jsonify({
            "models": models,
            "current": profile.last_model or profile.default_model,
        })
    except Exception as e:
        log.error(f"Error getting models: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/model/current", methods=["GET"])
def get_current_model():
    """Get current active model."""
    try:
        settings = load_settings()
        profile_name, profile = settings.resolve_profile()
        return jsonify({
            "model": profile.last_model or profile.default_model,
            "profile": profile_name,
        })
    except Exception as e:
        log.error(f"Error getting model: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/model/switch", methods=["POST"])
def switch_model():
    """Switch to a different model."""
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
    """Get authentication status for all providers."""
    try:
        manager = AuthManager()
        auth_status = manager.get_auth_source_statuses()
        return jsonify({"auth_status": auth_status})
    except Exception as e:
        log.error(f"Error getting auth status: {e}")
        return jsonify({"error": str(e)}), 500


# ---- Memory Management APIs ----

def _get_memory_store():
    """Get MemoryStore instance for current workspace."""
    from personal_agent.workspace import get_workspace_root
    workspace = get_workspace_root()
    return MemoryStore(workspace)


def _entry_to_dict(entry) -> dict:
    """Convert MemoryEntry to dict for JSON serialization."""
    from nexus.memory.types import utc_now
    return {
        "id": entry.id,
        "name": entry.name,
        "memory_type": entry.memory_type.value,
        "summary": entry.summary,
        "tags": entry.tags,
        "confidence": entry.confidence,
        "priority": entry.priority,
        "status": entry.status.value,
        "relations": [
            {"target_id": r.target_id, "relation": r.relation, "weight": r.weight}
            for r in entry.relations
        ],
        "source": entry.source,
        "event_time": entry.event_time.isoformat() if entry.event_time else None,
        "ttl_days": entry.ttl_days,
        "metadata": entry.metadata,
        "created_at": entry.created_at.isoformat() if entry.created_at else utc_now().isoformat(),
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else utc_now().isoformat(),
    }


def _content_to_dict(content) -> dict:
    """Convert MemoryContent to dict for JSON serialization."""
    return {
        "id": content.id,
        "body": content.body,
        "metadata": content.metadata,
    }


@app.route("/api/v1/memories", methods=["GET"])
def list_memories():
    """List all memory entries, optionally filtered by type."""
    try:
        store = _get_memory_store()
        memory_type = request.args.get("type")
        entries = store.list()
        if memory_type:
            entries = [e for e in entries if e.memory_type.value == memory_type]
        return jsonify({
            "memories": [_entry_to_dict(e) for e in entries],
        })
    except Exception as e:
        log.error(f"Error listing memories: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/memories/<memory_id>", methods=["GET"])
def get_memory(memory_id):
    """Get a single memory entry with its content."""
    try:
        store = _get_memory_store()
        result = store.get(memory_id)
        if result is None:
            return jsonify({"error": "Memory not found"}), 404
        entry, content = result
        return jsonify({
            "entry": _entry_to_dict(entry),
            "content": _content_to_dict(content),
        })
    except Exception as e:
        log.error(f"Error getting memory: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/memories", methods=["POST"])
def create_memory():
    """Create a new memory entry."""
    try:
        store = _get_memory_store()
        data = request.get_json() or {}

        entry = store.create(
            name=data.get("name", "Untitled"),
            summary=data.get("summary", ""),
            body=data.get("body", ""),
            memory_type=MemoryType(data.get("memory_type", "fact")),
            tags=data.get("tags", []),
            confidence=float(data.get("confidence", 0.5)),
            priority=int(data.get("priority", 50)),
            source=data.get("source", "manual"),
            ttl_days=data.get("ttl_days"),
            metadata=data.get("metadata", {}),
        )
        return jsonify({"entry": _entry_to_dict(entry)}), 201
    except Exception as e:
        log.error(f"Error creating memory: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/memories/<memory_id>", methods=["PUT"])
def update_memory(memory_id):
    """Update an existing memory entry."""
    try:
        store = _get_memory_store()
        data = request.get_json() or {}

        # Parse enum values
        memory_type = None
        if data.get("memory_type"):
            memory_type = MemoryType(data.get("memory_type"))

        status = None
        if data.get("status"):
            status = RecordStatus(data.get("status"))

        success = store.update(
            memory_id,
            name=data.get("name"),
            summary=data.get("summary"),
            body=data.get("body"),
            memory_type=memory_type,
            tags=data.get("tags"),
            confidence=data.get("confidence"),
            priority=data.get("priority"),
            status=status,
            ttl_days=data.get("ttl_days"),
            metadata=data.get("metadata"),
        )
        if not success:
            return jsonify({"error": "Memory not found"}), 404

        entry, content = store.get(memory_id)
        return jsonify({
            "entry": _entry_to_dict(entry),
            "content": _content_to_dict(content),
        })
    except Exception as e:
        log.error(f"Error updating memory: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/memories/<memory_id>", methods=["DELETE"])
def delete_memory(memory_id):
    """Delete a memory entry."""
    try:
        store = _get_memory_store()
        if store.delete(memory_id):
            return jsonify({"status": "deleted"})
        return jsonify({"error": "Memory not found"}), 404
    except Exception as e:
        log.error(f"Error deleting memory: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/memories/query", methods=["POST"])
def query_memories():
    """Query memories with hybrid recall."""
    try:
        store = _get_memory_store()
        data = request.get_json() or {}

        from nexus.memory.types import MemoryQuery
        query = MemoryQuery(
            text=data.get("text", ""),
            limit=int(data.get("limit", 8)),
            budget_tokens=int(data.get("budget_tokens", 2000)),
            relation_hops=int(data.get("relation_hops", 1)),
            required_tags=set(data.get("required_tags", [])),
            context_layers=set(data.get("context_layers", ["l0", "l1", "l2"])),
            memory_types=set(data.get("memory_types", [])),
        )

        result = store.recall(query)
        return jsonify({
            "entries": [_entry_to_dict(e) for e in result.entries],
            "contents": {k: _content_to_dict(c) for k, c in result.contents.items()},
            "candidates_scanned": result.candidates_scanned,
            "used_tokens": result.used_tokens,
            "score_breakdown": [
                {
                    "memory_id": sb.memory_id,
                    "lexical_score": sb.lexical_score,
                    "recency_score": sb.recency_score,
                    "priority_score": sb.priority_score,
                    "graph_score": sb.graph_score,
                    "final_score": sb.final_score,
                    "selected": sb.selected,
                }
                for sb in result.score_breakdown
            ],
            "dropped_candidates": [
                {
                    "memory_id": d.memory_id,
                    "reason": d.reason,
                    "final_score": d.final_score,
                    "token_cost": d.token_cost,
                }
                for d in result.dropped_candidates
            ],
        })
    except Exception as e:
        log.error(f"Error querying memories: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/memories/<memory_id>/feedback", methods=["POST"])
def memory_feedback(memory_id):
    """Provide feedback on a memory (confirm/reject)."""
    try:
        store = _get_memory_store()
        data = request.get_json() or {}
        action = data.get("action", "confirm")
        reason = data.get("reason", "")

        entry = store.get(memory_id)
        if entry is None:
            return jsonify({"error": "Memory not found"}), 404

        if action == "delete":
            store.delete(memory_id)
            return jsonify({"status": "deleted"})
        elif action == "reject":
            store.update(memory_id, metadata={"feedback_rejected": True, "feedback_reason": reason})
        elif action == "confirm":
            store.update(memory_id, metadata={"feedback_confirmed": True, "feedback_reason": reason})

        entry, _ = store.get(memory_id)
        return jsonify({"entry": _entry_to_dict(entry)})
    except Exception as e:
        log.error(f"Error providing memory feedback: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/memories/consolidate", methods=["POST"])
def consolidate_memories():
    """Run memory consolidation: decay priorities, archive expired, dedupe similar."""
    try:
        from nexus.memory.lifecycle import consolidate_entries, ConsolidationPolicy

        store = _get_memory_store()
        data = request.get_json() or {}

        policy = ConsolidationPolicy(
            decay_per_day=int(data.get("decay_per_day", 1)),
            min_priority=int(data.get("min_priority", 5)),
            dedupe_enabled=bool(data.get("dedupe_enabled", True)),
            archive_expired=bool(data.get("archive_expired", True)),
        )

        entries = list(store._index.list())  # Access internal index
        touched = consolidate_entries(entries, policy=policy)

        # Persist touched entries
        for entry in touched:
            store._index.upsert(entry)

        return jsonify({
            "status": "consolidated",
            "touched_count": len(touched),
            "entries": [_entry_to_dict(e) for e in touched],
        })
    except Exception as e:
        log.error(f"Error consolidating memories: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/memories/suggest-archives", methods=["GET"])
def suggest_memory_archives():
    """Get suggested memory IDs to archive."""
    try:
        from nexus.memory.lifecycle import suggest_archives

        store = _get_memory_store()
        max_age_days = int(request.args.get("max_age_days", 90))
        max_entries = int(request.args.get("max_entries", 100))

        entries = list(store._index.list())
        suggested = suggest_archives(entries, max_age_days=max_age_days, max_entries=max_entries)

        return jsonify({
            "suggested_ids": suggested,
            "count": len(suggested),
        })
    except Exception as e:
        log.error(f"Error suggesting archives: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/memories/stats", methods=["GET"])
def memory_stats():
    """Get memory statistics."""
    try:
        store = _get_memory_store()
        entries = list(store._index.list())

        stats = {
            "total": len(entries),
            "by_status": {
                "active": 0,
                "superseded": 0,
                "archived": 0,
            },
            "by_type": {
                "fact": 0,
                "episode": 0,
                "preference": 0,
                "procedure": 0,
            },
            "avg_confidence": 0.0,
            "avg_priority": 0.0,
        }

        total_confidence = 0.0
        total_priority = 0.0

        for entry in entries:
            stats["by_status"][entry.status.value] = stats["by_status"].get(entry.status.value, 0) + 1
            stats["by_type"][entry.memory_type.value] = stats["by_type"].get(entry.memory_type.value, 0) + 1
            total_confidence += entry.confidence
            total_priority += entry.priority

        if entries:
            stats["avg_confidence"] = total_confidence / len(entries)
            stats["avg_priority"] = total_priority / len(entries)

        return jsonify(stats)
    except Exception as e:
        log.error(f"Error getting memory stats: {e}")
        return jsonify({"error": str(e)}), 500


@socketio.on("connect")
def handle_connect():
    """Handle WebSocket connection."""
    log.info("Client connected")
    emit("connected", {"status": "ok"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle WebSocket disconnection."""
    session_id = request.sid
    if session_id in active_sessions:
        del active_sessions[session_id]
    log.info("Client disconnected")


@socketio.on("message")
def handle_message(data):
    """Handle incoming SocketIO messages."""
    session_id = request.sid
    log.info(f"Received message from {session_id}: {type(data).__name__}")
    if session_id in active_sessions:
        adapter = active_sessions[session_id]
        if isinstance(data, dict):
            log.info(f"Queuing dict request: {data.get('type', 'unknown')}")
            adapter.queue_request(data)
        elif isinstance(data, str):
            log.info(f"Received string: {data[:100]}")
            try:
                adapter.queue_request(json.loads(data))
            except json.JSONDecodeError:
                log.warning(f"Failed to decode JSON: {data[:100]}")
                pass


@socketio.on("session_start")
def handle_session_start(data):
    """Start a new agent session."""
    session_id = request.sid
    log.info(f"Starting session: {session_id}")

    # Create adapter
    adapter = SocketIOWebAdapter(socketio, session_id)
    active_sessions[session_id] = adapter

    # Create host
    config = get_config()
    host = SocketIOBackendHost(adapter, config)

    # Run session
    asyncio.run(host.run())


@socketio.on("session_resume")
def handle_session_resume(data):
    """Resume an existing agent session."""
    session_id = request.sid
    session_to_resume = data.get("session_id")
    log.info(f"Resuming session: {session_to_resume} for socket {session_id}")

    # Create adapter
    adapter = SocketIOWebAdapter(socketio, session_id)
    active_sessions[session_id] = adapter

    # Create config and load session data
    config = get_config()

    # Load session from backend
    from nexus.services.session_backend import DEFAULT_SESSION_BACKEND
    import os
    session_data = DEFAULT_SESSION_BACKEND.load_by_id(os.getcwd(), session_to_resume)

    if session_data:
        # Pass restore_messages to restore the conversation
        config.restore_messages = session_data.get("messages", [])
        config.model = session_data.get("model", config.model)

    host = SocketIOBackendHost(adapter, config)

    # Run session
    asyncio.run(host.run())


def run_server(host: str = "0.0.0.0", port: int = 8765, debug: bool = False):
    """Run the Flask-SocketIO server."""
    log.info(f"Starting NexusAgent Web UI server on {host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


def create_app() -> Flask:
    """Create and configure the Flask app."""
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server(debug=False)
