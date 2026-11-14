"""Tests for OrbitCode tools."""
import pytest
import tempfile
from pathlib import Path

from orbitcode.tools.base import ToolContext
from orbitcode.tools.bash import BashTool
from orbitcode.tools.read import ReadTool
from orbitcode.tools.write import WriteTool
from orbitcode.tools.edit import EditTool
from orbitcode.tools.glob import GlobTool
from orbitcode.tools.grep import GrepTool
from orbitcode.config import Settings


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def tool_context(temp_dir):
    settings = Settings(data_dir=temp_dir, session_dir=temp_dir / "sessions", plugins_dir=temp_dir / "plugins")
    return ToolContext(
        working_dir=temp_dir,
        session_id="test-session",
        settings=settings,
    )


@pytest.mark.asyncio
async def test_bash_tool(tool_context):
    tool = BashTool()
    result = await tool.execute(tool_context, command="echo hello", description="Echo test")
    assert result.success
    assert "hello" in result.output["stdout"]


@pytest.mark.asyncio
async def test_write_read_tool(tool_context):
    write_tool = WriteTool()
    read_tool = ReadTool()

    # Write a file
    result = await write_tool.execute(tool_context, path="test.txt", content="Hello, World!")
    assert result.success

    # Read the file
    result = await read_tool.execute(tool_context, path="test.txt")
    assert result.success
    assert result.output == "Hello, World!"


@pytest.mark.asyncio
async def test_edit_tool(tool_context):
    write_tool = WriteTool()
    edit_tool = EditTool()
    read_tool = ReadTool()

    # Write initial content
    await write_tool.execute(tool_context, path="edit_test.txt", content="Line 1\nLine 2\nLine 3")

    # Edit
    result = await edit_tool.execute(tool_context, path="edit_test.txt", old_string="Line 2", new_string="Modified Line 2")
    assert result.success

    # Verify
    result = await read_tool.execute(tool_context, path="edit_test.txt")
    assert "Modified Line 2" in result.output


@pytest.mark.asyncio
async def test_glob_tool(tool_context):
    write_tool = WriteTool()
    glob_tool = GlobTool()

    # Create test files
    await write_tool.execute(tool_context, path="src/main.py", content="print('hello')")
    await write_tool.execute(tool_context, path="src/utils.py", content="def util(): pass")
    await write_tool.execute(tool_context, path="tests/test_main.py", content="def test(): pass")

    # Glob for Python files
    result = await glob_tool.execute(tool_context, pattern="**/*.py")
    assert result.success
    assert len(result.output) == 3


@pytest.mark.asyncio
async def test_grep_tool(tool_context):
    write_tool = WriteTool()
    grep_tool = GrepTool()

    # Create test file
    await write_tool.execute(tool_context, path="search_test.py", content="def hello():\n    return 'world'\n\ndef foo():\n    return 'bar'")

    # Grep for 'def'
    result = await grep_tool.execute(tool_context, pattern="def ", path=".")
    assert result.success
    assert len(result.output) == 2
    assert all("def " in match["content"] for match in result.output)