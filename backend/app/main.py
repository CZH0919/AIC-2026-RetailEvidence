import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .database import create_database
from .models import Project, timestamp
from .schemas import ProjectInput, ProjectList, ProjectRead, ProjectUpdate, name_key

ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


def error(status: int, code: str, message: str, fields=None):
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "fields": fields or {}}},
    )


def create_app(database_path: Path | None = None, static_dir: Path | None = None) -> FastAPI:
    state_dir = Path(os.environ.get("AIC_STATE_DIR", ROOT / "storage" / "state"))
    db_path = database_path or state_dir / "retailevidence.sqlite3"
    frontend = static_dir or ROOT / "frontend" / "dist"

    @asynccontextmanager
    async def lifespan(app):
        engine, sessions = create_database(db_path)
        app.state.sessions = sessions
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="RetailEvidence Studio", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def protect_browser_requests(request: Request, call_next):
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site" or (
                origin and urlsplit(origin).netloc != request.headers.get("host")
            ):
                return error(403, "origin_rejected", "请求来源不匹配，请从当前页面重新操作。")
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, exc):
        fields = {}
        for issue in exc.errors():
            field = str(issue["loc"][-1])
            messages = {
                "name": "请填写 1–64 个字符的项目名称。",
                "description": "项目说明最多 500 个字符。",
                "color": "请选择有效的项目标记。",
                "revision": "项目信息已变化，请刷新后重试。",
            }
            fields[field] = messages.get(field, "请检查输入内容。")
        return error(422, "validation_error", "请检查填写的信息。", fields)

    @app.exception_handler(HTTPException)
    async def http_error(_, exc):
        code = "not_found" if exc.status_code == 404 else "request_error"
        return error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_, exc):
        logger.error("Database operation failed", exc_info=exc)
        return error(503, "storage_unavailable", "暂时无法保存或读取项目，请稍后重试。")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/projects", response_model=ProjectList)
    def list_projects(
        q: str = Query(default="", max_length=100),
        limit: int = Query(default=30, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        condition = or_(
            Project.name_key.contains(name_key(q.strip()), autoescape=True),
            Project.description.contains(q.strip(), autoescape=True),
        )
        with app.state.sessions() as session:
            total = session.scalar(select(func.count()).select_from(Project).where(condition))
            items = session.scalars(
                select(Project).where(condition)
                .order_by(Project.updated_at.desc(), Project.id).offset(offset).limit(limit)
            ).all()
            return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.post("/api/projects", response_model=ProjectRead, status_code=201)
    def create_project(payload: ProjectInput):
        project = Project(**payload.model_dump(), name_key=name_key(payload.name))
        with app.state.sessions() as session:
            session.add(project)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return error(
                    409, "name_exists", "已存在同名项目，请使用一个不同的名称。",
                    {"name": "项目名称已被使用。"},
                )
            return project

    @app.get("/api/projects/{project_id}", response_model=ProjectRead)
    def get_project(project_id: UUID):
        with app.state.sessions() as session:
            project = session.get(Project, str(project_id))
            if project is None:
                raise HTTPException(404, "这个项目不存在，请返回项目库重新选择。")
            return project

    @app.patch("/api/projects/{project_id}", response_model=ProjectRead)
    def update_project(project_id: UUID, payload: ProjectUpdate):
        values = payload.model_dump(exclude={"revision"})
        values.update(
            name_key=name_key(payload.name), updated_at=timestamp(), revision=payload.revision + 1
        )
        with app.state.sessions() as session:
            try:
                changed = session.execute(
                    update(Project)
                    .where(Project.id == str(project_id), Project.revision == payload.revision)
                    .values(**values)
                )
                if changed.rowcount == 0:
                    session.rollback()
                    if session.get(Project, str(project_id)) is None:
                        raise HTTPException(404, "这个项目不存在，请返回项目库重新选择。")
                    return error(409, "revision_conflict", "其他成员已更新此项目，请刷新后再编辑。")
                session.commit()
            except IntegrityError:
                session.rollback()
                return error(
                    409, "name_exists", "已存在同名项目，请使用一个不同的名称。",
                    {"name": "项目名称已被使用。"},
                )
            return session.get(Project, str(project_id))

    if (frontend / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/{client_path:path}", include_in_schema=False)
    def client_page(client_path: str):
        if client_path == "favicon.svg" and (frontend / "favicon.svg").is_file():
            return FileResponse(frontend / "favicon.svg")
        if client_path.startswith(("api/", "assets/")):
            raise HTTPException(404, "请求的内容不存在。")
        if not (frontend / "index.html").is_file():
            return error(503, "ui_unavailable", "页面暂不可用，请稍后重试。")
        return FileResponse(frontend / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
