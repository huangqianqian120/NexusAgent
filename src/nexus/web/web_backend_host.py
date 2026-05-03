"""WebSocket backend host for the Nexus Web UI."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass
from uuid import uuid4

from nexus.api.client import SupportsStreamingMessages
from nexus.bridge import get_bridge_manager
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
from nexus.tasks import get_task_manager
from nexus.themes import list_themes
from nexus.ui.protocol import BackendEvent, FrontendRequest, TranscriptItem
from nexus.ui.runtime import build_runtime, close_runtime, handle_line, start_runtime
from nexus.services.session_backend import SessionBackend

log = logging.getLogger(__name__)

_PROTOCOL_PREFIX = "OHJSON:"


class WebBackendHost:
    """Drive the Nexus runtime over WebSocket protocol."""

    def __init__(self, websocket, config: "WebBackendHostConfig") -> None:
        self._ws = websocket
        self._config = config
        self._bundle = None
        self._write_lock = asyncio.Lock()
        self._request_queue: asyncio.Queue[FrontendRequest] = asyncio.Queue()
        self._permission_requests: dict[str, asyncio.Future[bool]] = {}
        self._question_requests: dict[str, asyncio.Future[str]] = {}
        self._permission_lock = asyncio.Lock()
        self._busy = False
        self._running = True
        self._last_tool_inputs: dict[str, dict] = {}

    async def run(self) -> None:
        """WebSocket main loop."""
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
                        break
                    continue
                if request.type != "submit_line":
                    await self._emit(BackendEvent(type="error", message=f"Unknown request type: {request.type}"))
                    continue
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
                    break
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader
            if self._bundle is not None:
                await close_runtime(self._bundle)

    async def _read_requests(self) -> None:
        """Read requests from WebSocket."""
        while True:
            try:
                raw = await asyncio.wait_for(self._ws.receive_text(), timeout=60)
            except asyncio.TimeoutError:
                await self._request_queue.put(FrontendRequest(type="shutdown"))
                return
            except Exception:
                await self._request_queue.put(FrontendRequest(type="shutdown"))
                return

            if not raw:
                continue
            try:
                request = FrontendRequest.model_validate_json(raw)
            except Exception as exc:
                await self._emit(BackendEvent(type="error", message=f"Invalid request: {exc}"))
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

    async def _process_line(self, line: str, *, transcript_line: str | None = None) -> bool:
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
                    )
                )
                return
            if isinstance(event, ErrorEvent):
                await self._emit(
                    BackendEvent(
                        type="error",
                        message=event.message,
                    )
                )
                return
            if isinstance(event, StatusEvent):
                if event.state_updates:
                    self._bundle.app_state.set(**event.state_updates)
                return

        async def _clear_output() -> None:
            await self._emit(BackendEvent(type="clear_transcript"))

        should_continue = await handle_line(
            self._bundle,
            line,
            render_event=_render_event,
            print_system=_print_system,
            clear_output=_clear_output,
        )
        return should_continue

    async def _handle_select_command(self, command: str) -> None:
        assert self._bundle is not None
        settings = self._bundle.settings

        if command == "model":
            active_profile = settings.active_profile
            profile_name, profile = settings.resolve_profile(active_profile)
            current_model = profile.last_model or profile.default_model
            options = self._model_select_options(current_model, profile.provider, profile.allowed_models)
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Model", "command": "model"},
                    select_options=options,
                )
            )
            return

        if command == "provider":
            from nexus.auth.manager import AuthManager
            manager = AuthManager(settings)
            profiles = manager.get_profile_statuses()
            active = manager.get_active_profile()
            options = [
                {
                    "value": name,
                    "label": info["label"],
                    "description": f"{info['provider']} - {info['model']}",
                    "active": name == active,
                }
                for name, info in profiles.items()
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Provider", "command": "provider"},
                    select_options=options,
                )
            )
            return

        if command == "permissions":
            from nexus.permissions.modes import PermissionMode
            current = settings.permission.mode.value
            options = [
                {"value": mode.value, "label": _PERMISSION_LABELS.get(mode.value, mode.value), "active": mode.value == current}
                for mode in PermissionMode
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Permissions", "command": "permissions"},
                    select_options=options,
                )
            )
            return

        if command == "theme":
            options = [
                {"value": name, "label": name, "active": name == settings.theme}
                for name in list_themes()
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "Theme", "command": "theme"},
                    select_options=options,
                )
            )
            return

        await self._emit(BackendEvent(type="error", message=f"No selector available for /{command}"))

    def _model_select_options(self, current_model: str, provider: str, allowed_models: list[str] | None = None) -> list[dict[str, object]]:
        from nexus.config.settings import CLAUDE_MODEL_ALIAS_OPTIONS

        if allowed_models:
            return [
                {
                    "value": value,
                    "label": value,
                    "description": "Allowed for this profile",
                    "active": value == current_model,
                }
                for value in allowed_models
            ]
        provider_name = provider.lower()
        if provider_name in {"anthropic", "anthropic_claude"}:
            return [
                {
                    "value": value,
                    "label": label,
                    "description": description,
                    "active": value == current_model,
                }
                for value, label, description in CLAUDE_MODEL_ALIAS_OPTIONS
            ]
        families: list[tuple[str, str]] = []
        if provider_name in {"openai-codex", "openai", "openai-compatible", "openrouter", "github_copilot"}:
            families.extend(
                [
                    ("gpt-5.4", "OpenAI flagship"),
                    ("gpt-5", "General GPT-5"),
                    ("gpt-4.1", "Stable GPT-4.1"),
                    ("o4-mini", "Fast reasoning"),
                ]
            )
        elif provider_name in {"moonshot", "moonshot-compatible"}:
            families.extend(
                [
                    ("kimi-k2.5", "Moonshot K2.5"),
                    ("kimi-k2-turbo-preview", "Faster Moonshot"),
                ]
            )
        elif provider_name == "dashscope":
            families.extend(
                [
                    ("qwen3.5-flash", "Fast Qwen"),
                    ("qwen3-max", "Strong Qwen"),
                    ("deepseek-r1", "Reasoning model"),
                ]
            )
        elif provider_name == "gemini":
            families.extend(
                [
                    ("gemini-2.5-pro", "Gemini Pro"),
                    ("gemini-2.5-flash", "Gemini Flash"),
                ]
            )

        seen: set[str] = set()
        options: list[dict[str, object]] = []
        for value, description in [(current_model, "Current model"), *families]:
            if not value or value in seen:
                continue
            seen.add(value)
            options.append(
                {
                    "value": value,
                    "label": value,
                    "description": description,
                    "active": value == current_model,
                }
            )
        return options

    async def _ask_permission(self, tool_name: str, reason: str) -> bool:
        async with self._permission_lock:
            request_id = uuid4().hex
            future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
            self._permission_requests[request_id] = future
            await self._emit(
                BackendEvent(
                    type="modal_request",
                    modal={
                        "kind": "permission",
                        "request_id": request_id,
                        "tool_name": tool_name,
                        "reason": reason,
                    },
                )
            )
            try:
                return await asyncio.wait_for(future, timeout=300)
            except asyncio.TimeoutError:
                log.warning("Permission request %s timed out after 300s, denying", request_id)
                return False
            finally:
                self._permission_requests.pop(request_id, None)

    async def _ask_question(self, question: str) -> str:
        request_id = uuid4().hex
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._question_requests[request_id] = future
        await self._emit(
            BackendEvent(
                type="modal_request",
                modal={
                    "kind": "question",
                    "request_id": request_id,
                    "question": question,
                },
            )
        )
        try:
            return await asyncio.wait_for(future, timeout=600)
        except asyncio.TimeoutError:
            log.warning("Question request %s timed out after 600s, returning empty answer", request_id)
            return ""
        finally:
            self._question_requests.pop(request_id, None)

    async def _emit(self, event: BackendEvent) -> None:
        """Send event to WebSocket client."""
        async with self._write_lock:
            payload = _PROTOCOL_PREFIX + event.model_dump_json()
            await self._ws.send_text(payload)

    def _status_snapshot(self) -> BackendEvent:
        assert self._bundle is not None
        return BackendEvent.status_snapshot(
            state=self._bundle.app_state.get(),
            mcp_servers=self._bundle.mcp_manager.list_statuses(),
            bridge_sessions=get_bridge_manager().list_sessions(),
        )

    async def _handle_list_sessions(self) -> None:
        import time as _time

        assert self._bundle is not None
        sessions = self._bundle.session_backend.list_snapshots(self._bundle.cwd, limit=10)
        options = []
        for s in sessions:
            ts = _time.strftime("%m/%d %H:%M", _time.localtime(s["created_at"]))
            summary = s.get("summary", "")[:50] or "(no summary)"
            options.append({
                "value": s["session_id"],
                "label": f"{ts}  {s['message_count']}msg  {summary}",
            })
        await self._emit(
            BackendEvent(
                type="select_request",
                modal={"kind": "select", "title": "Resume Session", "command": "resume"},
                select_options=options,
            )
        )

    async def _apply_select_command(self, command_name: str, value: str) -> bool:
        command = command_name.strip().lstrip("/").lower()
        selected = value.strip()
        line = self._build_select_command_line(command, selected)
        if line is None:
            await self._emit(BackendEvent(type="error", message=f"Unknown select command: {command_name}"))
            await self._emit(BackendEvent(type="line_complete"))
            return True
        return await self._process_line(line, transcript_line=f"/{command}")

    def _build_select_command_line(self, command: str, value: str) -> str | None:
        if command == "provider":
            return f"/provider {value}"
        if command == "resume":
            return f"/resume {value}" if value else "/resume"
        if command == "permissions":
            return f"/permissions {value}"
        if command == "theme":
            return f"/theme {value}"
        if command == "output-style":
            return f"/output-style {value}"
        if command == "effort":
            return f"/effort {value}"
        if command == "passes":
            return f"/passes {value}"
        if command == "turns":
            return f"/turns {value}"
        if command == "fast":
            return f"/fast {value}"
        if command == "vim":
            return f"/vim {value}"
        if command == "voice":
            return f"/voice {value}"
        if command == "model":
            return f"/model {value}"
        return None


_PERMISSION_LABELS = {
    "default": "Default (confirm per tool)",
    "plan": "Plan Mode (confirm major changes)",
    "full_auto": "Auto (no confirmations)",
}


@dataclass
class WebBackendHostConfig:
    """Configuration for WebBackendHost session."""

    model: str | None = None
    max_turns: int | None = None
    base_url: str | None = None
    system_prompt: str | None = None
    api_key: str | None = None
    api_format: str | None = None
    active_profile: str | None = None
    api_client: SupportsStreamingMessages | None = None
    cwd: str | None = None
    restore_messages: list[dict] | None = None
    enforce_max_turns: bool = True
    permission_mode: str | None = None
    session_backend: SessionBackend | None = None
    extra_skill_dirs: tuple[str, ...] = ()
    extra_plugin_roots: tuple[str, ...] = ()
