import os
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager

# Load DATABASE_URL from environment or default to SQLite file
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quizrealm.db")

# Use check_same_thread=False for SQLite if multi-threaded app (e.g., FastAPI with uvicorn)
engine = create_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

# PUBLIC_INTERFACE
def init_db():
    """
    Initializes database and creates all tables on startup.

    This will ensure tables for User, Room, Question, Response, Score, and MatchHistory are created.
    """
    from . import models  # noqa: F401  # Ensure models are imported for SQLModel table registration
    SQLModel.metadata.create_all(engine)

# PUBLIC_INTERFACE
def get_session() -> Generator[Session, None, None]:
    """
    Dependency function for FastAPI to yield a database session.

    Usage:
        async def endpoint(..., session: Session = Depends(get_session)):
            ...
    Ensures proper closing of resources.
    Prints all exceptions and tracebacks if session fails to open or context errors occur.
    """
    import sys
    import traceback
    try:
        with Session(engine) as session:
            try:
                yield session
            except Exception as in_session_ex:
                print("[Exception inside DB session generator context]:", repr(in_session_ex), file=sys.stderr)
                traceback.print_exc()
                raise
    except Exception as sess_ex:
        print("[Exception opening DB session]:", repr(sess_ex), file=sys.stderr)
        traceback.print_exc()
        raise

# PUBLIC_INTERFACE
@contextmanager
def session_context() -> Generator[Session, None, None]:
    """
    Alternative context manager for DB session outside of FastAPI DI.

    Usage:
        with session_context() as session:
            # use session
    Prints all exceptions and tracebacks if DB session fails to open or exits with errors.
    """
    import sys
    import traceback
    try:
        with Session(engine) as session:
            try:
                yield session
            except Exception as in_ctx_ex:
                print("[Exception inside session_context()]:", repr(in_ctx_ex), file=sys.stderr)
                traceback.print_exc()
                raise
    except Exception as ctx_ex:
        print("[Exception opening session_context()]:", repr(ctx_ex), file=sys.stderr)
        traceback.print_exc()
        raise
