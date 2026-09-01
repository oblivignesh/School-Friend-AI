"""MCP server exposing a single `web_search` tool backed by DuckDuckGo.

Runs as a stdio MCP server (spawned as a subprocess by the backend's
MCPToolManager). No API key required.
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("websearch")


@mcp.tool()
def web_search(query: str, max_results: int = 3) -> str:
    """Search the public web for up-to-date factual information (e.g. a
    definition, a historical date, a science fact) and return a short list
    of results with title, URL, and snippet. Use this only to look up facts
    needed to answer a K-12 school question.

    Args:
        query: The search query.
        max_results: Maximum number of results to return (default 3, max 5).
    """
    max_results = max(1, min(max_results, 5))
    try:
        from ddgs import DDGS
    except ImportError:  # pragma: no cover - fallback for older package name
        from duckduckgo_search import DDGS  # type: ignore

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:  # noqa: BLE001
        return f"Error: web search failed ({exc})."

    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, start=1):
        title = r.get("title", "")
        url = r.get("href") or r.get("url", "")
        snippet = r.get("body", "")
        lines.append(f"{i}. {title}\n   URL: {url}\n   {snippet}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
