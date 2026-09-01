"""FastAPI app: serves the chat API and the static frontend."""
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import anthropic  # noqa: E402

from .agent import run_agent  # noqa: E402
from .guard import REFUSAL_MESSAGE, check_banned  # noqa: E402
from .mcp_manager import MCPToolManager, ServerConfig  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
MCP_SERVERS_DIR = Path(__file__).resolve().parent / "mcp_servers"

mcp_manager = MCPToolManager()
# In-memory per-session conversation history. Fine for a single-process demo;
# swap for a real store (Redis/DB) for production/multi-worker deployments.
_sessions: dict[str, list[dict]] = {}

SERVER_CONFIGS = [
    ServerConfig(
        name="calculator",
        command=sys.executable,
        args=[str(MCP_SERVERS_DIR / "calculator_server.py")],
    ),
    ServerConfig(
        name="websearch",
        command=sys.executable,
        args=[str(MCP_SERVERS_DIR / "websearch_server.py")],
    ),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_manager.connect(SERVER_CONFIGS)
    yield
    await mcp_manager.close()


app = FastAPI(title="School Friend AI", lifespan=lifespan)


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    session_id = req.session_id or str(uuid.uuid4())
    history = _sessions.setdefault(session_id, [])

    banned_category = check_banned(req.message)
    if banned_category:
        reply = REFUSAL_MESSAGE
    else:
        try:
            reply = await run_agent(mcp_manager, history, req.message)
        except anthropic.AuthenticationError:
            reply = (
                "I can't reach my AI service right now (invalid API key). "
                "Please ask the site admin to check the ANTHROPIC_API_KEY "
                "setting."
            )
        except anthropic.APIError:
            reply = (
                "I'm having trouble reaching my AI service right now. "
                "Please try again in a moment."
            )

    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": reply})
    # Cap history length to keep token usage bounded.
    if len(history) > 20:
        del history[: len(history) - 20]

    return ChatResponse(session_id=session_id, reply=reply)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "tools": [t["name"] for t in mcp_manager.tool_defs]}


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
