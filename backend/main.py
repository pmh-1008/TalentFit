from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import inspect, text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import models  # noqa: F401  (đăng ký bảng)
from .database import Base, engine
from .routers import ai, applications, auth, candidates, company, jobs, matching, notifications
from .services.llm import LLMError


def _migrate():
    """create_all không thêm cột vào bảng đã có, nên tự bổ sung cột mới cho CSDL cũ."""
    cols = {c["name"] for c in inspect(engine).get_columns("jobs")}
    application_cols = {c["name"] for c in inspect(engine).get_columns("applications")}
    with engine.begin() as conn:
        if "deadline" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN deadline DATE NULL"))
        if "open_date" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN open_date DATE NULL"))
        conn.execute(text("UPDATE jobs SET open_date = DATE(opened_at) WHERE open_date IS NULL"))
        if "benefits" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN benefits TEXT NULL"))
        if "decisions_finalized" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN decisions_finalized BOOLEAN NOT NULL DEFAULT 0"))
        if "draft_decision" not in application_cols:
            conn.execute(text("ALTER TABLE applications ADD COLUMN draft_decision VARCHAR(10) NULL"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    _migrate()
    yield


app = FastAPI(title="TalentFit API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(LLMError)
async def llm_error_handler(_: Request, exc: LLMError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


for r in (auth, company, candidates, jobs, applications, matching, notifications, ai):
    app.include_router(r.router)


@app.get("/health")
def health():
    return {"status": "ok"}
