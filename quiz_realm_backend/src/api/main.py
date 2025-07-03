from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import quiz_check
from .database import init_db
from . import auth
from .routers import rooms, questions, responses, leaderboard, dashboard
from .routers import websocket as websocket_router

import sys
import traceback

def setup_app() -> FastAPI:
    """
    PUBLIC_INTERFACE
    Initializes the FastAPI app with middleware, database, and routes.
    Prints additional error tracebacks on startup for easier diagnostics if something fails.
    """
    try:
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
        try:
            init_db()
        except Exception as dbinit_ex:
            print("[FATAL] Database initialization error on FastAPI startup:", repr(dbinit_ex), file=sys.stderr)
            traceback.print_exc()
            raise

        # Include routers from modular structure
        app.include_router(quiz_check.router)
        app.include_router(auth.router)
        app.include_router(rooms.router)
        app.include_router(questions.router)
        app.include_router(responses.router)
        app.include_router(leaderboard.router)
        app.include_router(dashboard.router)

        # --- WebSocket endpoint wiring ---
        app.include_router(websocket_router.router)

        return app
    except Exception as ex:
        print("[FATAL] Unhandled exception during FastAPI app initialization:", repr(ex), file=sys.stderr)
        traceback.print_exc()
        raise

app = setup_app()
