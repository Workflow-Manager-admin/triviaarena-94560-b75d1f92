from sqlmodel import SQLModel, create_engine, Session
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quizrealm.db")
engine = create_engine(DATABASE_URL, echo=True)

# PUBLIC_INTERFACE
def init_db():
    """Initializes database and creates tables."""
    SQLModel.metadata.create_all(engine)

# PUBLIC_INTERFACE
def get_session():
    """Yields new DB session (for use with FastAPI dependency injection)."""
    with Session(engine) as session:
        yield session
