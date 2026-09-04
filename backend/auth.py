"""User auth: registration/login with bcrypt-hashed passwords, and a JWT
stored in an httponly cookie to identify the logged-in user on later
requests (including after logout/login again on a new browser session).
"""
import os
import sqlite3
import time
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request

SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-insecure-secret-change-me")
SESSION_COOKIE = "session_token"
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


class AuthError(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_user(conn: sqlite3.Connection, username: str, password: str) -> int:
    username = username.strip().lower()
    if not username or not password:
        raise AuthError("Username and password are required.")
    if len(password) < 6:
        raise AuthError("Password must be at least 6 characters.")
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        raise AuthError("That username is already taken.")
    cur = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, hash_password(password)),
    )
    conn.commit()
    return cur.lastrowid


def authenticate_user(conn: sqlite3.Connection, username: str, password: str) -> int:
    username = username.strip().lower()
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise AuthError("Invalid username or password.")
    return row["id"]


def create_session_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    return jwt.encode(payload, SESSION_SECRET, algorithm="HS256")


def decode_session_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: resolve the logged-in user from the session
    cookie, or raise 401 if missing/invalid/expired.
    """
    token = request.cookies.get(SESSION_COOKIE)
    payload = decode_session_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return {"id": int(payload["sub"]), "username": payload["username"]}
