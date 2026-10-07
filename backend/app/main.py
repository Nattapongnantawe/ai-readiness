import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import scheduler
from app.config import settings
from app.db import init_db
from app.embedding import warm_up
from app.routers import analytics, auth, crawler, curriculum, gap, jobs, search

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    warm_up()  # load the embedding model once at startup (NFR-02)
    scheduler.bootstrap()
    yield
    scheduler.shutdown()


app = FastAPI(title="AI Readiness — Module 4 API", version="1.0.0", lifespan=lifespan,
              description="Dashboard, semantic search, curriculum gap analysis and crawler control.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()]
    message = errors[0]["msg"] if errors else "Invalid input"
    return JSONResponse(status_code=422, content={"error": {"code": "INVALID_INPUT", "message": message, "details": errors}})


for r in (auth.router, crawler.router, analytics.router, search.router, jobs.router, curriculum.router, gap.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/api/v1/health", tags=["health"])
def health():
    return {"status": "ok"}


# ----------------------------------------------------------------------------- website (production)
# `npm run build` puts the React app in frontend/dist. If it is there, serve it from this same server:
# /assets/* = built JS/CSS, any other non-API path = index.html (React Router handles the URL).
# Development still uses `npm run dev` on :5173, which proxies /api to this server.
DIST = Path(settings.frontend_dist or Path(__file__).resolve().parents[2] / "frontend" / "dist").resolve()

if (DIST / "index.html").is_file():
    if (DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def website(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, detail={"code": "NOT_FOUND", "message": f"No API at /{full_path}"})
        file = (DIST / full_path).resolve()
        if full_path and file.is_file() and DIST in file.parents:
            return FileResponse(file)          # logo.svg, favicon, ...
        return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})

    logging.getLogger("web").info("serving website from %s", DIST)
else:
    logging.getLogger("web").info("no built website at %s (use npm run dev, or build-frontend.bat)", DIST)