import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.routes import router
from .config import get_settings
from .db import get_engine
from .service import Recorder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    get_engine()
    rec = Recorder(settings, asyncio.get_running_loop())
    app.state.recorder = rec
    rec.start()
    try:
        yield
    finally:
        rec.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Piano Companion", version=__version__, lifespan=lifespan)
    # The dev server (vite on the laptop) talks to the Pi across origins.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    static = settings.static_dir
    if static and static.is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = (static / path).resolve()
            if path and f.is_file() and f.is_relative_to(static.resolve()):
                return FileResponse(f)
            return FileResponse(static / "index.html")

    return app


app = create_app()


def run() -> None:
    s = get_settings()
    uvicorn.run("piano_companion.main:app", host=s.host, port=s.port, log_level="info")
