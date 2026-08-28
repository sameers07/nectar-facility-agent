"""Synchronous wrapper around the MCP SDK's async client. The SDK is
async-first; the rest of this codebase (Investigator's loop) is
synchronous, so a background thread owns the event loop and every public
method blocks on `run_coroutine_threadsafe` -- callers never need to know
this is async underneath.

The stdio_client/ClientSession context managers are opened and closed
within a single long-lived coroutine (`_lifecycle`) because anyio's cancel
scopes require entering and exiting a task group in the same task --
`call_tool`/`list_tools` run as separate tasks against the already-open
session, which is fine; only the session's own enter/exit boundary is
task-bound.
"""
import asyncio
import json
import sys
import threading

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPError(Exception):
    """The MCP server is unreachable, failed to start, or a call to it
    failed at the transport/protocol level (not a tool-level business
    error, which comes back as a normal {"error": ...} result)."""


class MCPClient:
    def __init__(self, command: str = None, args: list = None, connect_timeout: float = 15.0):
        self.command = command or sys.executable
        self.args = args if args is not None else ["-m", "mcp_server.server"]
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._session = None
        self._shutdown_event = None
        self._closed_event = threading.Event()
        self._connect_error = None
        ready = threading.Event()

        async def _lifecycle():
            self._shutdown_event = asyncio.Event()
            try:
                server_params = StdioServerParameters(command=self.command, args=self.args)
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self._session = session
                        ready.set()
                        await self._shutdown_event.wait()
            except Exception as e:
                self._connect_error = e
                ready.set()
            finally:
                self._closed_event.set()

        asyncio.run_coroutine_threadsafe(_lifecycle(), self._loop)
        if not ready.wait(timeout=connect_timeout):
            raise MCPError("Timed out connecting to MCP server")
        if self._connect_error:
            raise MCPError(str(self._connect_error)) from self._connect_error

    def _run(self, coro, timeout: float = 15.0):
        try:
            return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)
        except Exception as e:
            raise MCPError(str(e)) from e

    def list_tools(self) -> list:
        async def _list():
            result = await self._session.list_tools()
            return [t.name for t in result.tools]

        return self._run(_list())

    def call_tool(self, name: str, arguments: dict) -> dict:
        async def _call():
            return await self._session.call_tool(name, arguments)

        result = self._run(_call())
        text = result.content[0].text if result.content else "{}"
        if result.is_error:
            return {"error": text}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": text}

    def close(self):
        if self._shutdown_event is not None:
            self._loop.call_soon_threadsafe(self._shutdown_event.set)
        self._closed_event.wait(timeout=5)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)
