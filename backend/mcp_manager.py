"""MCP client manager: connects to local stdio MCP servers (calculator,
websearch), lists their tools in Anthropic tool-schema format, and routes
tool_use calls to the right server.
"""
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass
class ServerConfig:
    name: str
    command: str
    args: list[str]


class MCPToolManager:
    def __init__(self) -> None:
        self._exit_stack = AsyncExitStack()
        self._sessions_by_tool: dict[str, ClientSession] = {}
        self.tool_defs: list[dict[str, Any]] = []

    async def connect(self, configs: list[ServerConfig]) -> None:
        for cfg in configs:
            params = StdioServerParameters(command=cfg.command, args=cfg.args)
            read, write = await self._exit_stack.enter_async_context(stdio_client(params))
            session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                self._sessions_by_tool[tool.name] = session
                self.tool_defs.append(
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema,
                    }
                )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        session = self._sessions_by_tool.get(name)
        if session is None:
            return f"Error: tool '{name}' is not available."

        result = await session.call_tool(name, arguments)
        parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
        output = "\n".join(parts) if parts else str(result)
        if getattr(result, "isError", False):
            return f"Error: {output}"
        return output

    async def close(self) -> None:
        await self._exit_stack.aclose()
