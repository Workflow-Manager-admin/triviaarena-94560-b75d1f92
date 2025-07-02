from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

# PUBLIC_INTERFACE
class User(SQLModel, table=True):
    """
    User model for authentication and participation.
    Fields:
        - id: Primary key.
        - username: Unique username.
        - email: Unique email.
        - hashed_password: Hashed password string.
        - created_at: Timestamp for when the user was created.
    Relationships:
        - responses: One-to-many for user quiz responses.
        - scores: One-to-many for user scores per room.
        - match_history: One-to-many for user's match/game history.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    responses: List["Response"] = Relationship(back_populates="user")
    scores: List["Score"] = Relationship(back_populates="user")
    match_history: List["MatchHistory"] = Relationship(back_populates="user")


# PUBLIC_INTERFACE
class Room(SQLModel, table=True):
    """
    Represents a quiz room/lobby.
    Fields:
        - id: Primary key.
        - name: Room name.
        - is_active: If the room is currently live.
        - created_at: Timestamp for room creation.
        - owner_id: The user id who created/owns the room.
    Relationships:
        - questions: Questions assigned to this room.
        - responses: Responses made in this room.
        - scores: Scores for users in this room.
        - match_history: Past matches associated with this room.
        - owner: User who created the room.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")

    questions: List["Question"] = Relationship(back_populates="room")
    responses: List["Response"] = Relationship(back_populates="room")
    scores: List["Score"] = Relationship(back_populates="room")
    match_history: List["MatchHistory"] = Relationship(back_populates="room")
    owner: Optional[User] = Relationship()


# PUBLIC_INTERFACE
class Question(SQLModel, table=True):
    """
    Represents a quiz question.
    Fields:
        - id: Primary key.
        - content: The question text.
        - option_a/b/c/d: Multiple choice options.
        - correct_option: String matching one option key.
        - room_id: The quiz room this question is part of.
    Relationships:
        - room: Parent quiz room.
        - responses: User answers for this question.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    room_id: int = Field(foreign_key="room.id")

    room: Optional[Room] = Relationship(back_populates="questions")
    responses: List["Response"] = Relationship(back_populates="question")


# PUBLIC_INTERFACE
class Response(SQLModel, table=True):
    """
    Represents a single user's answer to a question in a room.
    Fields:
        - id: Primary key.
        - user_id: FK to User.
        - room_id: FK to Room.
        - question_id: FK to Question.
        - selected_option: The answer chosen by user.
        - is_correct: If answer is correct.
        - answered_at: Timestamp when answered.
    Relationships:
        - user: The user giving this response.
        - question: The question being answered.
        - room: The room context.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    room_id: int = Field(foreign_key="room.id")
    question_id: int = Field(foreign_key="question.id")
    selected_option: str
    is_correct: bool
    answered_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="responses")
    question: Optional[Question] = Relationship(back_populates="responses")
    room: Optional[Room] = Relationship(back_populates="responses")


# PUBLIC_INTERFACE
class Score(SQLModel, table=True):
    """
    Score for a user in a specific room/quiz.
    Fields:
        - id: Primary key.
        - user_id: FK to User.
        - room_id: FK to Room.
        - total_score: Numeric score.
        - rank: Position/standing in leaderboard.
        - updated_at: Last updated timestamp.
    Relationships:
        - user: The user earning this score.
        - room: The related room/quiz.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    room_id: int = Field(foreign_key="room.id")
    total_score: int = 0
    rank: Optional[int] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="scores")
    room: Optional[Room] = Relationship(back_populates="scores")


# PUBLIC_INTERFACE
class MatchHistory(SQLModel, table=True):
    """
    Represents the results of completed matches (for user dashboard/history).
    Fields:
        - id: Primary key.
        - user_id: FK to User
        - room_id: FK to Room
        - final_score: User's score in match
        - position: Final ranking/standing of the user.
        - played_at: Completion timestamp for match.
    Relationships:
        - user: The participant.
        - room: Room where match happened.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    room_id: int = Field(foreign_key="room.id")
    final_score: int
    position: int
    played_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="match_history")
    room: Optional[Room] = Relationship(back_populates="match_history")
