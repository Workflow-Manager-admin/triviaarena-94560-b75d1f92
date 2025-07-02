from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import quiz_check
from .database import init_db

def setup_app() -> FastAPI:
    """
    PUBLIC_INTERFACE
    Initializes the FastAPI app with middleware, database, and routes.
    """
    app = FastAPI(
        title="QuizRealm Backend",
        description="API and WebSocket backend for multiplayer QuizRealm app",
        version="0.1.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Setup database connection, could be expanded for events
    init_db()

    # Include routers from modular structure
    app.include_router(quiz_check.router, prefix="")

    return app

app = setup_app()
