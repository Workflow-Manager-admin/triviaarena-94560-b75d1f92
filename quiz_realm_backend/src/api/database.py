import os
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager
import sys

# Load DATABASE_URL from environment or default to SQLite file
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quizrealm.db")

# Ensure correct working directory for relative SQLite path if running via preview
if DATABASE_URL.startswith("sqlite:///./"):
    abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../", DATABASE_URL.replace("sqlite:///./", "")))
    DATABASE_URL = f"sqlite:///{abs_path}"

# Diagnostic print for startup
print(f"[INFO] Using DATABASE_URL: {DATABASE_URL}", file=sys.stderr)
if not DATABASE_URL.startswith("sqlite"):
    print("[WARNING] Currently only SQLite is fully supported and tested. Your DATABASE_URL is set to:", DATABASE_URL, file=sys.stderr)

# Use check_same_thread=False for SQLite if multi-threaded app (e.g., FastAPI with uvicorn)
try:
    engine = create_engine(
        DATABASE_URL,
        echo=True,
        connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    )
except Exception:
    print("[FATAL] Error creating SQLModel engine with DATABASE_URL:", DATABASE_URL, file=sys.stderr)
    import traceback
    traceback.print_exc()
    raise

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
