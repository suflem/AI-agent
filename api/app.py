from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    academic,
    chat,
    daily,
    feed,
    grad,
    kb,
    notify,
    scheduler,
    study,
    system,
    tools,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Agent Modular API",
        version="0.1.0",
        description="API gateway for frontend/UI integration over the local skill system.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return {
            "name": "ai-agent-api",
            "version": "0.1.0",
            "docs": "/docs",
            "prefix": "/api",
        }

    app.include_router(system.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(tools.router, prefix="/api")
    app.include_router(kb.router, prefix="/api")
    app.include_router(study.router, prefix="/api")
    app.include_router(academic.router, prefix="/api")
    app.include_router(grad.router, prefix="/api")
    app.include_router(feed.router, prefix="/api")
    app.include_router(daily.router, prefix="/api")
    app.include_router(notify.router, prefix="/api")
    app.include_router(scheduler.router, prefix="/api")
    return app


app = create_app()

