from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import sqlite3
import uuid
import os

# App-level metadata and OpenAPI tags for documentation
app = FastAPI(
    title="QuizRealm Backend API",
    description=(
        "Backend API for QuizRealm: Multiplayer quiz rooms, realtime updates, live leaderboards, "
        "JWT authentication."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "User Signup/Login"},
        {"name": "rooms", "description": "Quiz Room Browsing/Creation/Joining"},
        {"name": "questions", "description": "Question APIs"},
        {"name": "responses", "description": "User Response APIs"},
        {"name": "leaderboard", "description": "Leaderboard/Dashboard APIs"},
        {"name": "match", "description": "Match History APIs"},
        {"name": "health", "description": "Health/quiz-check Endpoint"},
        {"name": "realtime", "description": "Real-time WebSocket Endpoints"},
    ]
)

# == CORS ==
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
SECRET_KEY = os.environ.get("SECRET_KEY", "devsecret123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

DB_PATH = os.environ.get("QUIZ_DB_PATH", "quizrealm.sqlite3")

# --- DATABASE ---
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # Create tables if not exist
    c.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS room (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            host_user_id TEXT NOT NULL,
            status TEXT DEFAULT 'waiting',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS question (
            id TEXT PRIMARY KEY,
            room_id TEXT,
            text TEXT NOT NULL,
            options TEXT NOT NULL, -- serialized as JSON
            correct_answer TEXT NOT NULL
        );
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS response (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            room_id TEXT,
            question_id TEXT,
            selected_option TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            answered_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS score (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            room_id TEXT NOT NULL,
            total_score INTEGER NOT NULL,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS match_history (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            room_id TEXT NOT NULL,
            final_score INTEGER NOT NULL,
            finished_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


init_db()


# --- UTILITY FUNCTIONS (JWT/Password) ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_username(username: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM user WHERE username = ?", (username,))
        return cur.fetchone()


def get_user_by_id(user_id: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM user WHERE id = ?", (user_id,))
        return cur.fetchone()


# --- SCHEMA/MODELS ---
# User Models
class UserOut(BaseModel):
    id: str
    username: str
    email: EmailStr
    created_at: Optional[str]


class UserIn(BaseModel):
    username: str = Field(..., description="Unique username for the user")
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=5, description="Password")


class Token(BaseModel):
    access_token: str
    token_type: str


class RoomOut(BaseModel):
    id: str
    name: str
    host_user_id: str
    status: str
    created_at: Optional[str]


class RoomCreate(BaseModel):
    name: str
    host_user_id: str


class RoomJoin(BaseModel):
    room_id: str


class QuestionOut(BaseModel):
    id: str
    room_id: Optional[str]
    text: str
    options: List[str]
    # No correct_answer field (hidden for clients)


class ResponseIn(BaseModel):
    room_id: str
    question_id: str
    selected_option: str


class ResponseOut(BaseModel):
    id: str
    user_id: str
    room_id: str
    question_id: str
    selected_option: str
    is_correct: bool
    answered_at: Optional[str]


class ScoreOut(BaseModel):
    user_id: str
    username: str
    total_score: int


class MatchHistoryOut(BaseModel):
    room_id: str
    final_score: int
    finished_at: Optional[str]
    room_name: Optional[str]


# --- DEPENDENCIES ---
# PUBLIC_INTERFACE
def get_current_user(token: str = Depends(oauth2_scheme)):
    """Extract and return the current user based on the provided JWT access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user


# --- AUTH ROUTES ---
@app.post(
    '/signup',
    response_model=UserOut,
    tags=["auth"],
    summary="Signup",
    description="Register a new user account"
)
# PUBLIC_INTERFACE
def signup(user: UserIn):
    """Register a new user and return user info. Throws error if username/email is taken."""
    if get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    with get_db() as conn:
        cur = conn.cursor()
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(user.password)
        try:
            cur.execute(
                "INSERT INTO user (id, username, email, hashed_password) VALUES (?, ?, ?, ?)",
                (user_id, user.username, user.email, hashed_password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Email already registered")
        return UserOut(
            id=user_id,
            username=user.username,
            email=user.email,
            created_at=datetime.utcnow().isoformat()
        )


@app.post(
    '/login',
    response_model=Token,
    tags=["auth"],
    summary="Login",
    description="Authenticate and receive a JWT token"
)
# PUBLIC_INTERFACE
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return JWT access token."""
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user['hashed_password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user["id"]})
    return Token(access_token=access_token, token_type="bearer")


# --- ROOM BROWSING & MANAGEMENT ---
@app.get(
    '/rooms',
    response_model=List[RoomOut],
    tags=["rooms"],
    summary="Browse Rooms",
    description="List all active rooms"
)
# PUBLIC_INTERFACE
def get_rooms(current_user=Depends(get_current_user)):
    """Return a list of all rooms."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM room")
        rooms = cur.fetchall()
        return [RoomOut(**dict(room)) for room in rooms]


@app.post(
    '/rooms/create',
    response_model=RoomOut,
    tags=["rooms"],
    summary="Create Room",
    description="Create a new quiz room"
)
# PUBLIC_INTERFACE
def create_room(room: RoomCreate, current_user=Depends(get_current_user)):
    """Create a new quiz room. Only available to authenticated users."""
    with get_db() as conn:
        cur = conn.cursor()
        room_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO room (id, name, host_user_id) VALUES (?, ?, ?)",
            (room_id, room.name, room.host_user_id)
        )
        conn.commit()
        return RoomOut(
            id=room_id,
            name=room.name,
            host_user_id=room.host_user_id,
            status="waiting",
            created_at=datetime.utcnow().isoformat()
        )


@app.post(
    '/rooms/join',
    tags=["rooms"],
    summary="Join Room",
    description="Join an existing quiz room"
)
# PUBLIC_INTERFACE
def join_room(data: RoomJoin, current_user=Depends(get_current_user)):
    """Stub logic for joining a room. Updates can be made to handle participant tracking."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM room WHERE id = ?", (data.room_id,))
        room = cur.fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        # TODO: Implement participant-tracking table for join/leave
        return {"message": f"Joined {room['name']}", "room_id": room['id']}


# --- QUESTIONS ---
@app.get(
    '/questions/{room_id}',
    response_model=List[QuestionOut],
    tags=["questions"],
    summary="Get Questions",
    description="Get questions for a room"
)
# PUBLIC_INTERFACE
def get_questions(room_id: str, current_user=Depends(get_current_user)):
    """Return all questions for the given room (answers hidden from client)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM question WHERE room_id = ?", (room_id,))
        questions = cur.fetchall()
        result = []
        for q in questions:
            result.append(
                QuestionOut(
                    id=q["id"],
                    room_id=q["room_id"],
                    text=q["text"],
                    options=eval(q["options"]),  # Not safe for prod, for PoC
                )
            )
        return result


# --- RESPONSE & ANSWERING ---
@app.post(
    '/responses',
    response_model=ResponseOut,
    tags=["responses"],
    summary="Submit Response",
    description="Submit an answer to a quiz question"
)
# PUBLIC_INTERFACE
def submit_response(data: ResponseIn, current_user=Depends(get_current_user)):
    """Submit a response and calculate correctness, update score."""
    user_id = current_user['id']
    with get_db() as conn:
        cur = conn.cursor()
        # Fetch the question
        cur.execute("SELECT * FROM question WHERE id = ?", (data.question_id,))
        q = cur.fetchone()
        if not q:
            raise HTTPException(status_code=404, detail="Question not found")
        is_correct = int(data.selected_option == q['correct_answer'])

        # Store response
        resp_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO response (id, user_id, room_id, question_id, selected_option, is_correct) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (resp_id, user_id, data.room_id, data.question_id, data.selected_option, is_correct)
        )

        # Update or Insert score
        cur.execute("SELECT * FROM score WHERE user_id=? AND room_id=?", (user_id, data.room_id))
        score = cur.fetchone()
        if not score:
            cur.execute(
                "INSERT INTO score (id, user_id, room_id, total_score) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, data.room_id, is_correct)
            )
        else:
            new_score = score['total_score'] + is_correct
            cur.execute(
                "UPDATE score SET total_score=?, last_updated=CURRENT_TIMESTAMP WHERE id=?",
                (new_score, score["id"])
            )
        conn.commit()
        return ResponseOut(
            id=resp_id,
            user_id=user_id,
            room_id=data.room_id,
            question_id=data.question_id,
            selected_option=data.selected_option,
            is_correct=bool(is_correct),
            answered_at=datetime.utcnow().isoformat()
        )


# --- LEADERBOARD ---
@app.get(
    '/leaderboard/{room_id}',
    response_model=List[ScoreOut],
    tags=["leaderboard"],
    summary="Room Leaderboard",
    description="Show leaderboard for a room"
)
# PUBLIC_INTERFACE
def get_leaderboard(room_id: str, current_user=Depends(get_current_user)):
    """Return leaderboard for the specified quiz room, ordered by highest score."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.user_id, u.username, s.total_score
            FROM score s
            JOIN user u ON u.id = s.user_id
            WHERE s.room_id = ?
            ORDER BY s.total_score DESC
            """,
            (room_id,)
        )
        return [
            ScoreOut(
                user_id=r['user_id'],
                username=r['username'],
                total_score=r['total_score']
            )
            for r in cur.fetchall()
        ]


# --- DASHBOARD ---
@app.get(
    '/dashboard',
    response_model=List[MatchHistoryOut],
    tags=["leaderboard"],
    summary="User Dashboard",
    description="View your past quiz matches and final scores"
)
# PUBLIC_INTERFACE
def get_dashboard(current_user=Depends(get_current_user)):
    """Return the match history for the currently authenticated user."""
    uid = current_user['id']
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT mh.room_id, mh.final_score, mh.finished_at, r.name as room_name
            FROM match_history mh
            LEFT JOIN room r ON r.id = mh.room_id
            WHERE mh.user_id = ?
            ORDER BY mh.finished_at DESC
            LIMIT 50
            """,
            (uid,)
        )
        return [
            MatchHistoryOut(
                room_id=h['room_id'],
                final_score=h['final_score'],
                finished_at=h['finished_at'],
                room_name=h['room_name']
            )
            for h in cur.fetchall()
        ]


# --- HEALTH CHECK ---
@app.get(
    '/quiz-check',
    tags=["health"],
    summary="Quiz Backend Health Check",
    description="Returns OK if backend running"
)
# PUBLIC_INTERFACE
def quiz_check():
    """Health check endpoint, returns status:OK if server is reachable."""
    return {"status": "OK"}


# --- WEBSOCKET (STUBS/INITIAL) ---
@app.websocket("/ws/room/{room_id}")
# PUBLIC_INTERFACE
async def websocket_quiz_room(ws: WebSocket, room_id: str):
    """
    WebSocket stub for realtime quiz room events. See /docs for implementation/usage.
    OperationId: wsRoomUpdates
    Tags: ["realtime"]

    Project-level usage note: This is a stub implementation. Handles WebSocket connections, but
    does not broadcast updates yet.
    """
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            # Handle quiz/room commands here in future (stub)
            await ws.send_json({"message": f"Received: {str(data)}"})
    except WebSocketDisconnect:
        # Cleanup if needed
        pass


@app.websocket("/ws/leaderboard/{room_id}")
# PUBLIC_INTERFACE
async def websocket_leaderboard(ws: WebSocket, room_id: str):
    """
    WebSocket stub for realtime leaderboard events. See /docs for implementation/usage.
    OperationId: wsLeaderboardUpdates
    Tags: ["realtime"]

    Project-level usage note: This is a stub implementation. Handles WebSocket connections, but
    does not broadcast updates yet.
    """
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            # Handle leaderboard commands here in future (stub)
            await ws.send_json({"message": f"Leaderboard event: {str(data)}"})
    except WebSocketDisconnect:
        pass


# --- OPENAPI HELP FOR WEBSOCKETS (EXTRA) ---
@app.get(
    "/realtime-help",
    tags=["realtime"],
    summary="WebSocket Usage Help",
    description="API docs: How to use WebSocket endpoints for real-time updates"
)
# PUBLIC_INTERFACE
def ws_usage_help():
    """
    Returns a note on how to use WebSocket endpoints. This appears in the API docs & /openapi.json
    for easy frontend discovery.
    """
    return {
        "websockets": [
            {
                "endpoint": "/ws/room/{room_id}",
                "purpose": "Quiz room real-time events",
                "usage": "Connect and receive/send messages"
            },
            {
                "endpoint": "/ws/leaderboard/{room_id}",
                "purpose": "Real-time leaderboard updates",
                "usage": "Connect and receive/send leaderboard messages"
            }
        ]
    }


# --- ROOT ENDPOINT OVERRIDE (also for CI check) ---
@app.get("/", tags=["health"])
def health_check():
    """Root health check endpoint."""
    return {"message": "Healthy"}
