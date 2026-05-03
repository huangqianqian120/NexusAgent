"""工具系统测试 — 通过 importlib 直接加载 base 模块，避开 __init__.py 的 MCP 依赖链."""

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

# 直接加载 nexus.tools.base 模块，不经过 __init__.py（避免触发 MCP 导入错误）
_base_path = Path(__file__).parent.parent / "src" / "nexus" / "tools" / "base.py"
_spec = importlib.util.spec_from_file_location(
    "nexus.tools.base_direct",
    str(_base_path),
    submodule_search_locations=[],
)
_base_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _base_mod
_spec.loader.exec_module(_base_mod)

BaseTool = _base_mod.BaseTool
ToolExecutionContext = _base_mod.ToolExecutionContext
ToolRegistry = _base_mod.ToolRegistry
ToolResult = _base_mod.ToolResult

# 加载 path_utils 以支持 ToolExecutionContext(cwd=Path(...))
# 如果 ToolExecutionContext 不需要额外依赖就可以直接使用


# ---------------------------------------------------------------------------
# 测试用简单工具
# ---------------------------------------------------------------------------


class EchoInput(BaseModel):
    message: str = Field(description="要回显的消息")


class EchoTool(BaseTool):
    name = "echo"
    description = "回显输入的消息"

    def __init__(self):
        self.input_model = EchoInput

    async def execute(self, arguments: EchoInput, context: ToolExecutionContext) -> ToolResult:
        return ToolResult(output=arguments.message)

    def is_read_only(self, arguments: EchoInput) -> bool:
        return True


class FailingTool(BaseTool):
    name = "failing"
    description = "总是返回错误的工具"

    def __init__(self):
        self.input_model = EchoInput

    async def execute(self, arguments: EchoInput, context: ToolExecutionContext) -> ToolResult:
        return ToolResult(output="错误!", is_error=True)


# ---------------------------------------------------------------------------


class TestToolExecutionContext:
    """ToolExecutionContext 测试."""

    def test_create_with_cwd(self):
        ctx = ToolExecutionContext(cwd=Path("/tmp/test"))
        assert ctx.cwd == Path("/tmp/test")

    def test_default_metadata_empty(self):
        ctx = ToolExecutionContext(cwd=Path.cwd())
        assert ctx.metadata == {}

    def test_custom_metadata(self):
        ctx = ToolExecutionContext(
            cwd=Path.cwd(),
            metadata={"session_id": "sesh-001", "user": "test"},
        )
        assert ctx.metadata["session_id"] == "sesh-001"
        assert ctx.metadata["user"] == "test"


class TestToolResult:
    """ToolResult 测试."""

    def test_success_result(self):
        result = ToolResult(output="执行成功")
        assert result.output == "执行成功"
        assert result.is_error is False
        assert result.metadata == {}

    def test_error_result(self):
        result = ToolResult(output="执行失败", is_error=True)
        assert result.is_error is True

    def test_result_with_metadata(self):
        result = ToolResult(
            output="完成",
            metadata={"duration_ms": 150, "tokens": 42},
        )
        assert result.metadata["duration_ms"] == 150


class TestEchoTool:
    """EchoTool 单元测试."""

    @pytest.fixture
    def tool(self):
        return EchoTool()

    @pytest.fixture
    def ctx(self):
        return ToolExecutionContext(cwd=Path("/tmp/test"))

    @pytest.mark.asyncio
    async def test_echo(self, tool, ctx):
        inp = EchoInput(message="你好世界")
        result = await tool.execute(inp, ctx)
        assert result.output == "你好世界"
        assert result.is_error is False

    def test_read_only(self, tool):
        inp = EchoInput(message="test")
        assert tool.is_read_only(inp) is True

    def test_api_schema(self, tool):
        schema = tool.to_api_schema()
        assert schema["name"] == "echo"
        assert schema["description"] == "回显输入的消息"
        assert "input_schema" in schema
        assert schema["input_schema"]["type"] == "object"


class TestFailingTool:
    """FailingTool 单元测试."""

    @pytest.fixture
    def tool(self):
        return FailingTool()

    @pytest.fixture
    def ctx(self):
        return ToolExecutionContext(cwd=Path.cwd())

    @pytest.mark.asyncio
    async def test_returns_error(self, tool, ctx):
        inp = EchoInput(message="test")
        result = await tool.execute(inp, ctx)
        assert result.is_error is True
        assert result.output == "错误!"


class TestToolRegistry:
    """ToolRegistry 测试."""

    @pytest.fixture
    def registry(self):
        reg = ToolRegistry()
        reg.register(EchoTool())
        reg.register(FailingTool())
        return reg

    def test_register_and_list(self, registry):
        tools = registry.list_tools()
        names = {t.name for t in tools}
        assert "echo" in names
        assert "failing" in names
        assert len(tools) == 2

    def test_get_existing(self, registry):
        tool = registry.get("echo")
        assert tool is not None
        assert tool.name == "echo"

    def test_get_missing(self, registry):
        assert registry.get("nonexistent") is None

    def test_register_duplicate(self, registry):
        """重复注册应该覆盖旧的."""
        registry.register(EchoTool())
        # 不应该报错，长度不变
        assert len(registry.list_tools()) == 2

    def test_api_schemas(self, registry):
        schemas = registry.to_api_schema()
        assert len(schemas) == 2
        names = {s["name"] for s in schemas}
        assert names == {"echo", "failing"}
