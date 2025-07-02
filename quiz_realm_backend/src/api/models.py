from typing import Optional
from sqlmodel import Field, SQLModel

# PUBLIC_INTERFACE
class User(SQLModel, table=True):
    """User model for authentication and participation."""
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str

# PUBLIC_INTERFACE
class Room(SQLModel, table=True):
    """Quiz room model (simplified)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    is_active: bool = True

# Additional models (Question, Response, Score, etc) can be added here.

