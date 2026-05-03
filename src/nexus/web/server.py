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
_project_root = _server_file.parent.parent.parent.parent
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
from nexus.ui.protocol import BackendEvent, TranscriptItem
from nexus.ui.runtime import build_runtime, handle_line, start_runtime
from nexus.tasks import get_task_manager
from nexus.web.web_backend_host import WebBackendHost, WebBackendHostConfig

log = logging.getLogger(__name__)

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
CORS(
    app,
    resources={
        r"/api/*": {"origins": _allowed_origins},
        r"/socket.io/*": {"origins": _allowed_origins},
    },
)

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
        with self._write_lock:
            self._socket.emit("message", PROTOCOL_PREFIX + payload)

    async def receive_text(self) -> str:
        return await asyncio.get_event_loop().run_in_executor(None, self._request_queue.get)

    def queue_request(self, request: dict) -> None:
        from nexus.ui.protocol import FrontendRequest

        try:
            req = FrontendRequest.model_validate(request)
            self._request_queue.put_nowait(req)
        except Exception as exc:
            log.warning(f"Failed to queue request: {exc}, request: {request}")

    def close(self) -> None:
        from nexus.ui.protocol import FrontendRequest

        self._request_queue.put_nowait(FrontendRequest(type="shutdown"))


class SocketIOBackendHost(WebBackendHost):
    """WebBackendHost variant that uses SocketIO adapter."""

    def __init__(self, adapter: SocketIOWebAdapter, config: WebBackendHostConfig) -> None:
        self._adapter = adapter
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
                    item = TranscriptItem(role=role, text=text or "")
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
                            request.command or "", request.value or ""
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
        assert self._bundle is not None
        await self._emit(
            BackendEvent(
                type="transcript_item",
                item=TranscriptItem(role="user", text=transcript_line or line),
            )
        )

        async def _print_system(message: str) -> None:
            await self._emit(
                BackendEvent(
                    type="transcript_item", item=TranscriptItem(role="system", text=message)
                )
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
                            await self._emit(
                                BackendEvent(type="todo_update", todo_markdown="\n".join(lines))
                            )
                if event.tool_name in ("set_permission_mode", "plan_mode"):
                    assert self._bundle is not None
                    new_mode = self._bundle.app_state.get().permission_mode
                    await self._emit(BackendEvent(type="plan_mode_change", plan_mode=new_mode))
                return
            if isinstance(event, ErrorEvent):
                await self._emit(BackendEvent(type="error", message=event.message))
                await self._emit(
                    BackendEvent(
                        type="transcript_item",
                        item=TranscriptItem(role="system", text=event.message),
                    )
                )
                return
            if isinstance(event, StatusEvent):
                await self._emit(
                    BackendEvent(
                        type="transcript_item",
                        item=TranscriptItem(role="system", text=event.message),
                    )
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

            if (
                request.type == "permission_response"
                and request.request_id in self._permission_requests
            ):
                future = self._permission_requests[request.request_id]
                if not future.done():
                    future.set_result(bool(request.allowed))
                continue
            if (
                request.type == "question_response"
                and request.request_id in self._question_requests
            ):
                future = self._question_requests[request.request_id]
                if not future.done():
                    future.set_result(request.answer or "")
                continue
            await self._request_queue.put(request)

    async def _emit(self, event) -> None:
        async with self._write_lock:
            await self._adapter.send_text(event.model_dump_json())

    async def _emit_error(self, message: str) -> None:
        from nexus.ui.protocol import BackendEvent

        await self._emit(BackendEvent(type="error", message=message))


def get_config() -> WebBackendHostConfig:
    """Build WebBackendHostConfig from current settings."""
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent.parent
    nexus_path = project_root / "nexus"
    if nexus_path.exists():
        sys.path = [p for p in sys.path if not p.endswith("/src/nexus") and p != "src/nexus"]
        sys.path.insert(0, str(project_root))

    settings = load_settings()
    profile_name, profile = settings.resolve_profile()

    auth_source = profile.auth_source
    storage_provider = (
        auth_source.replace("_api_key", "") if auth_source.endswith("_api_key") else auth_source
    )
    api_key = None

    from nexus.auth.storage import load_credential

    cred = load_credential(storage_provider, "api_key")
    if cred:
        api_key = cred
    if not api_key and getattr(settings, "api_key", ""):
        api_key = settings.api_key

    import importlib

    workspace_module = importlib.import_module("personal_agent.workspace")
    prompts_module = importlib.import_module("personal_agent.prompts")
    get_workspace_root = workspace_module.get_workspace_root
    initialize_workspace = workspace_module.initialize_workspace
    get_skills_dir = workspace_module.get_skills_dir
    get_plugins_dir = workspace_module.get_plugins_dir
    build_nexus_system_prompt = prompts_module.build_nexus_system_prompt
    _workspace = initialize_workspace()
    workspace_root = get_workspace_root()
    system_prompt = build_nexus_system_prompt(
        os.getcwd(),
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
        cwd=os.getcwd(),
        session_backend=None,
        system_prompt=system_prompt,
        extra_skill_dirs=extra_skill_dirs,
        extra_plugin_roots=extra_plugin_roots,
    )


# ---- Misc Routes (status, settings, commands, health) ----


@app.route("/api/v1/status", methods=["GET"])
def get_status():
    try:
        settings = load_settings()
        profile_name, profile = settings.resolve_profile()
        manager = AuthManager(settings)
        return jsonify(
            {
                "model": profile.last_model or profile.default_model,
                "provider": profile.provider,
                "profile": profile_name,
                "auth_status": manager.get_auth_status().get(profile.provider, {}),
            }
        )
    except Exception as e:
        log.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/settings", methods=["GET"])
def get_settings():
    try:
        settings = load_settings()
        return jsonify(settings.model_dump())
    except Exception as e:
        log.error(f"Error getting settings: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/settings", methods=["PUT"])
def update_settings():
    try:
        data = request.get_json()
        settings = load_settings()
        allowed_fields = [
            "theme",
            "vim_mode",
            "voice_mode",
            "fast_mode",
            "effort",
            "passes",
            "verbose",
        ]
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
    try:
        manager = AuthManager()
        profiles = manager.get_profile_statuses()
        return jsonify({"profiles": profiles})
    except Exception as e:
        log.error(f"Error getting providers: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


# ---- Socket.IO Event Handlers ----


@socketio.on("connect")
def handle_connect():
    log.info("Client connected")
    emit("connected", {"status": "ok"})


@socketio.on("disconnect")
def handle_disconnect():
    session_id = request.sid
    if session_id in active_sessions:
        del active_sessions[session_id]
    log.info("Client disconnected")


@socketio.on("message")
def handle_message(data):
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
    session_id = request.sid
    log.info(f"Starting session: {session_id}")
    adapter = SocketIOWebAdapter(socketio, session_id)
    active_sessions[session_id] = adapter
    config = get_config()
    host = SocketIOBackendHost(adapter, config)
    asyncio.run(host.run())


@socketio.on("session_resume")
def handle_session_resume(data):
    session_id = request.sid
    session_to_resume = data.get("session_id")
    log.info(f"Resuming session: {session_to_resume} for socket {session_id}")
    adapter = SocketIOWebAdapter(socketio, session_id)
    active_sessions[session_id] = adapter
    config = get_config()
    from nexus.services.session_backend import DEFAULT_SESSION_BACKEND
    import os

    session_data = DEFAULT_SESSION_BACKEND.load_by_id(os.getcwd(), session_to_resume)
    if session_data:
        config.restore_messages = session_data.get("messages", [])
        config.model = session_data.get("model", config.model)
    host = SocketIOBackendHost(adapter, config)
    asyncio.run(host.run())


# ---- Register all route modules ----


from nexus.web.routes import register_all_routes

register_all_routes(app)


# ---- Server entry points ----


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
