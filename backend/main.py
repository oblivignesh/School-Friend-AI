"""FastAPI app: serves the chat API and the static frontend."""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import anthropic  # noqa: E402

from . import db  # noqa: E402
from . import memory  # noqa: E402
from .agent import run_agent  # noqa: E402
from .auth import (  # noqa: E402
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    AuthError,
    authenticate_user,
    create_session_token,
    create_user,
    get_current_user,
)
from .guard import REFUSAL_MESSAGE, check_banned  # noqa: E402
from .mcp_manager import MCPToolManager, ServerConfig  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
MCP_SERVERS_DIR = Path(__file__).resolve().parent / "mcp_servers"

mcp_manager = MCPToolManager()
# Recency window: how many of the most recent DB messages to always include
# verbatim in the prompt (in addition to the semantically-recalled ones).
RECENCY_WINDOW = 20

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
    db.init_db()
    await mcp_manager.connect(SERVER_CONFIGS)
    yield
    await mcp_manager.close()


app = FastAPI(title="School Friend AI", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class AuthRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    username: str


def _set_session_cookie(response: Response, user_id: int, username: str) -> None:
    token = create_session_token(user_id, username)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )


@app.post("/api/register", response_model=UserResponse)
async def register(req: AuthRequest, response: Response) -> UserResponse:
    conn = db.get_connection()
    try:
        try:
            user_id = create_user(conn, req.username, req.password)
        except AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        username = req.username.strip().lower()
        _set_session_cookie(response, user_id, username)
        return UserResponse(username=username)
    finally:
        conn.close()


@app.post("/api/login", response_model=UserResponse)
async def login(req: AuthRequest, response: Response) -> UserResponse:
    conn = db.get_connection()
    try:
        try:
            user_id = authenticate_user(conn, req.username, req.password)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        username = req.username.strip().lower()
        _set_session_cookie(response, user_id, username)
        return UserResponse(username=username)
    finally:
        conn.close()


@app.post("/api/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "ok"}


@app.get("/api/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse(username=current_user["username"])


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest, current_user: dict = Depends(get_current_user)
) -> ChatResponse:
    user_id = current_user["id"]
    conn = db.get_connection()
    try:
        banned_category = check_banned(req.message)
        if banned_category:
            reply = REFUSAL_MESSAGE
        else:
            history = memory.get_recent_history(conn, user_id, limit=RECENCY_WINDOW)
            recalled = memory.recall_relevant_memories(
                conn, user_id, req.message, exclude_recent=RECENCY_WINDOW
            )
            memory_context = "\n".join(recalled) if recalled else None
            try:
                reply = await run_agent(
                    mcp_manager, history, req.message, memory_context
                )
            except anthropic.AuthenticationError:
                reply = (
                    "I can't reach my AI service right now (invalid API "
                    "key). Please ask the site admin to check the "
                    "ANTHROPIC_API_KEY setting."
                )
            except anthropic.APIError:
                reply = (
                    "I'm having trouble reaching my AI service right now. "
                    "Please try again in a moment."
                )

        memory.add_message(conn, user_id, "user", req.message)
        memory.add_message(conn, user_id, "assistant", reply)

        return ChatResponse(reply=reply)
    finally:
        conn.close()


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "tools": [t["name"] for t in mcp_manager.tool_defs]}


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

