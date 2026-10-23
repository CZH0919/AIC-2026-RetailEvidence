"""Account sessions and a fail-closed API ownership boundary.

All API routes inherit authorize_request, including exports and future routes.
Project routes must use the existing project_id path parameter. Child IDs remain
checked by the existing scoped() helpers. No authentication bypass configuration.
"""

import hashlib
import hmac
import os
import re
import secrets
import time
from threading import BoundedSemaphore
from uuid import UUID

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from .models import Account, AccountSession, AuthThrottle, ProjectOwner

PASSWORD_SLOTS = BoundedSemaphore(2)

COOKIE = "retailevidence_session"
SESSION_SECONDS = 12 * 60 * 60
MUTATIONS = {"POST", "PUT", "PATCH", "DELETE"}


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    with PASSWORD_SLOTS:
        value = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64 * 1024 * 1024
        ).hex()
    return f"scrypt$32768$8$3${salt}${value}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        salt = encoded.split("$")[4]
        return hmac.compare_digest(password_hash(password, salt), encoded)
    except (ValueError, IndexError):
        return False


# Unknown usernames still perform the same password derivation as known ones.
DUMMY_HASH = password_hash("unused-constant-never-an-account", "00" * 16)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def project_name_key(user_id: str, normalized_name: str) -> str:
    # Preserve the schema-5 unique index without rewriting historical projects.
    # The human-readable Project.name and its search semantics are unchanged.
    return f"{user_id}:{normalized_name}"


def authorize_request(request: Request):
    if not request.url.path.startswith("/api/"):
        return
    if request.method in MUTATIONS:
        if request.headers.get("x-requested-with") != "RetailEvidence":
            raise HTTPException(403, "请从本站页面提交操作，然后重试。")
    if request.url.path in {"/api/health", "/api/auth/login", "/api/auth/register"}:
        return
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) > 128:
        raise HTTPException(401, "请先登录，或重新登录后继续。")
    with request.app.state.sessions() as session:
        account_session = session.get(AccountSession, token_hash(token))
        if not account_session or account_session.expires_at <= int(time.time()):
            raise HTTPException(401, "登录已过期，请重新登录后继续。")
        account = session.get(Account, account_session.account_id)
        if not account or not account.active:
            raise HTTPException(401, "请重新登录后继续。")
        request.state.user = {"id": account.id, "username": account.username}
        project_id = request.path_params.get("project_id")
        if project_id is not None:
            try:
                project_id = str(UUID(str(project_id)))
            except ValueError:
                raise HTTPException(404, "这个项目不存在或不属于当前账号。") from None
            owner = session.get(ProjectOwner, project_id)
            if not owner or owner.account_id != account.id:
                raise HTTPException(404, "这个项目不存在或不属于当前账号。")


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,31}", value):
            raise ValueError("用户名需为3–32位字母、数字、下划线或短横线")
        return value


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=12, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


def throttle(request: Request, action: str, username: str = ""):
    # Single worker; persisted limits survive application restarts. Do not trust
    # X-Forwarded-For. Only one digest of source address/username is stored.
    now = int(time.time())
    ip = request.client.host if request.client else "unknown"
    limits = [
        (
            f"{action}:ip:{ip}",
            3600 if action == "register" else 900,
            10 if action == "register" else 60,
        )
    ]
    if username:
        limits.append((f"{action}:account:{username}", 900, 15))
    with request.app.state.sessions() as session:
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        session.execute(delete(AuthThrottle).where(AuthThrottle.expires_at <= now))
        for key, window, maximum in limits:
            identity = token_hash(key)
            row = session.get(AuthThrottle, identity)
            if row and row.attempts >= maximum:
                raise HTTPException(429, "尝试次数过多，请稍后再试。")
            if row:
                row.attempts += 1
            else:
                session.add(AuthThrottle(id=identity, attempts=1, expires_at=now + window))
        session.commit()


def issue_session(request: Request, response: Response, session, account):
    now = int(time.time())
    session.execute(delete(AccountSession).where(AccountSession.expires_at <= now))
    old = request.cookies.get(COOKIE)
    if old:
        session.execute(delete(AccountSession).where(AccountSession.id == token_hash(old)))
    token = secrets.token_urlsafe(32)
    session.add(
        AccountSession(
            id=token_hash(token), account_id=account.id, expires_at=now + SESSION_SECONDS
        )
    )
    session.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=os.getenv("AIC_COOKIE_SECURE", "0") == "1",
        samesite="strict",
        path="/",
    )
    return {"user": {"id": account.id, "username": account.username}}


def install_auth_routes(app):
    @app.post("/api/auth/register", status_code=201)
    def register(payload: Credentials, request: Request, response: Response):
        throttle(request, "register")
        encoded = password_hash(payload.password)
        with app.state.sessions() as session:
            account = Account(username=payload.username, password_hash=encoded)
            session.add(account)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                raise HTTPException(409, "这个用户名无法使用，请换一个用户名。") from None
            return issue_session(request, response, session, account)

    @app.post("/api/auth/login")
    def login(payload: Credentials, request: Request, response: Response):
        throttle(request, "login", payload.username)
        with app.state.sessions() as session:
            account = session.scalar(select(Account).where(Account.username == payload.username))
            valid = password_matches(
                payload.password, account.password_hash if account else DUMMY_HASH
            )
            if not valid or not account or not account.active:
                raise HTTPException(401, "用户名或密码不正确。")
            return issue_session(request, response, session, account)

    @app.get("/api/auth/me")
    def me(request: Request):
        return {"user": request.state.user}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        with app.state.sessions() as session:
            session.execute(
                delete(AccountSession).where(
                    AccountSession.id == token_hash(request.cookies[COOKIE])
                )
            )
            session.commit()
        response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
        return {"ok": True}

    @app.post("/api/auth/password")
    def change_password(payload: PasswordChange, request: Request, response: Response):
        throttle(request, "password", request.state.user["username"])
        with app.state.sessions() as session:
            account = session.get(Account, request.state.user["id"])
            if not password_matches(payload.current_password, account.password_hash):
                raise HTTPException(400, "当前密码不正确。")
            account.password_hash = password_hash(payload.new_password)
            session.execute(delete(AccountSession).where(AccountSession.account_id == account.id))
            return issue_session(request, response, session, account)
