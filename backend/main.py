from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import migrate, models  # noqa: F401  (models đăng ký bảng)
from .config import settings
from .errors import BusinessError
from .routers import ai, applications, auth, candidates, company, jobs, matching, notifications
from .services.llm import LLMError


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate.upgrade()  # tạo/nâng cấp bảng bằng Alembic
    yield


app = FastAPI(title="TalentFit API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(LLMError)
async def llm_error_handler(_: Request, exc: LLMError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(BusinessError)
async def business_error_handler(_: Request, exc: BusinessError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


for r in (auth, company, candidates, jobs, applications, matching, notifications, ai):
    app.include_router(r.router)


@app.get("/health")
def health():
    return {"status": "ok"}
