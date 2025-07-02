from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketState
from sqlmodel import Session, select
from typing import Dict, Set, Optional, Any
from datetime import datetime
import asyncio

from ..database import get_session
from ..models import Room, User, Question, Response, Score

router = APIRouter(
    tags=["websocket"],
    prefix="/ws"
)

# PUBLIC_INTERFACE
class ConnectionManager:
    """Manager to track active connections and per-room membership."""
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}  # room_id to set of WebSockets
        self.user_map: Dict[WebSocket, int] = {}                # ws -> user_id
        self.room_state: Dict[int, Dict[str, Any]] = {}         # room_id: state dict (current q, timers, etc.)

    # PUBLIC_INTERFACE
    async def connect(self, websocket: WebSocket, room_id: int, user_id: int):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
            self.room_state[room_id] = {
                "current_question": None,
                "countdown_task": None
            }
        self.active_connections[room_id].add(websocket)
        self.user_map[websocket] = user_id

    # PUBLIC_INTERFACE
    def disconnect(self, websocket: WebSocket, room_id: int):
        self.active_connections.get(room_id, set()).discard(websocket)
        self.user_map.pop(websocket, None)
        # clean up if room is empty
        if not self.active_connections.get(room_id):
            self.active_connections.pop(room_id, None)
            state = self.room_state.pop(room_id, None)
            # cancel timer if present
            if state and state.get("countdown_task"):
                state["countdown_task"].cancel()

    # PUBLIC_INTERFACE
    async def broadcast_room(self, room_id: int, message: dict):
        for ws in list(self.active_connections.get(room_id, [])):
            if ws.client_state == WebSocketState.CONNECTED:
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect(ws, room_id)

    # PUBLIC_INTERFACE
    def room_connections(self, room_id: int):
        return self.active_connections.get(room_id, set())

    # PUBLIC_INTERFACE
    def get_state(self, room_id: int) -> dict:
        return self.room_state.setdefault(room_id, {})

    # PUBLIC_INTERFACE
    def set_countdown_task(self, room_id: int, task: Optional[asyncio.Task]):
        state = self.room_state.setdefault(room_id, {})
        old_task = state.get('countdown_task')
        if old_task and not old_task.done():
            old_task.cancel()
        state['countdown_task'] = task


conn_manager = ConnectionManager()

### WebSocket utility (authentication)
async def get_user_token(websocket: WebSocket, session: Session) -> Optional[User]:
    """Extract JWT from query params or headers and get User; returns None if unauthenticated."""
    token: Optional[str] = websocket.query_params.get('token')
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:]
    if not token:
        return None
    from jose import JWTError, jwt
    from ..auth import SECRET_KEY, ALGORITHM
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
        user = session.exec(select(User).where(User.username == username)).first()
        return user
    except JWTError:
        return None

# PUBLIC_INTERFACE
@router.websocket(
    "/room/{room_id}",
    name="WebSocket: Join quiz room",
)
async def ws_room_join(websocket: WebSocket, room_id: int):
    """
    WebSocket endpoint for joining a quiz room in real-time.
    - Requires JWT token provided as a query param `token` or header `Authorization: Bearer`
    - Allows bi-directional real-time communication for:
        * Room membership (join/leave notice)
        * Question countdown ticks
        * Live leaderboard updates
        * Question/answer events
    - All broadcasts are to participants in the same room only.
    """
    async with asyncio.Lock():
        async with get_session() as session:
            user = await get_user_token(websocket, session)
            if not user:
                await websocket.close(code=4401)
                return
            room = session.get(Room, room_id)
            if not room or not room.is_active:
                await websocket.close(code=4004)
                return
            await conn_manager.connect(websocket, room_id, user.id)
            await conn_manager.broadcast_room(room_id, {
                "event": "user_joined",
                "user_id": user.id,
                "username": user.username,
                "members": [u for u in [conn_manager.user_map.get(ws) for ws in conn_manager.room_connections(room_id)] if u]
            })            
            try:
                while True:
                    data = await websocket.receive_json()
                    # Supported messages: {action, ...payload}
                    action = data.get('action')
                    if action == "start_question":
                        # Only room owner can trigger
                        if room.owner_id != user.id:
                            await websocket.send_json({"error": "Only owner can start question"})
                            continue
                        question_id = data.get("question_id")
                        q = session.get(Question, question_id)
                        if not q or q.room_id != room_id:
                            await websocket.send_json({"error": "Invalid question for room"})
                            continue
                        await start_question(room_id, q, session)
                    elif action == "answer":
                        # User submits answer -- notifies others, can be used for rapid display
                        await handle_answer(room_id, user.id, data, session)
                    elif action == "request_leaderboard":
                        # Fetch and broadcast updated leaderboard
                        await broadcast_leaderboard(room_id, session)
                    # ignore unsupported actions
            except WebSocketDisconnect:
                pass
            finally:
                conn_manager.disconnect(websocket, room_id)
                # Notify remaining users
                await conn_manager.broadcast_room(room_id, {
                    "event": "user_left",
                    "user_id": user.id,
                    "username": user.username,
                    "members": [u for u in [conn_manager.user_map.get(ws) for ws in conn_manager.room_connections(room_id)] if u]
                })

# PUBLIC_INTERFACE
async def start_question(room_id: int, question: Question, session: Session):
    """Broadcast question w/ countdown and handle ticks and expiration."""
    # Announce new question start immediately to room
    data = {
        "event": "question_start",
        "question": {
            "id": question.id,
            "content": question.content,
            "option_a": question.option_a,
            "option_b": question.option_b,
            "option_c": question.option_c,
            "option_d": question.option_d,
        },
        "countdown": 10  # you can make this adjustable
    }
    await conn_manager.broadcast_room(room_id, data)
    # Start countdown for question in background
    async def countdown():
        for i in range(10, 0, -1):
            await asyncio.sleep(1)
            await conn_manager.broadcast_room(room_id, {"event": "countdown", "seconds_left": i - 1})
        # After countdown, broadcast that question is closed
        await conn_manager.broadcast_room(room_id, {"event": "question_closed", "question_id": question.id})
        # Can trigger leaderboard update here
        await broadcast_leaderboard(room_id, session)
    task = asyncio.create_task(countdown())
    conn_manager.set_countdown_task(room_id, task)


# PUBLIC_INTERFACE
async def handle_answer(room_id: int, user_id: int, data: dict, session: Session):
    """Process an answer, persist, broadcast to room, update leaderboard."""
    question_id = data.get("question_id")
    selected_option = data.get("selected_option")
    # Check question
    question = session.get(Question, question_id)
    if not question or question.room_id != room_id:
        return
    # Avoid duplicate answers for same question-user
    resp_exists = session.exec(
        select(Response).where(
            (Response.user_id == user_id) & (Response.question_id == question_id) & (Response.room_id == room_id)
        )
    ).first()
    is_correct = (selected_option == question.correct_option)
    if not resp_exists:
        # Save response in DB
        resp = Response(
            user_id=user_id,
            room_id=room_id,
            question_id=question_id,
            selected_option=selected_option,
            is_correct=is_correct,
            answered_at=datetime.utcnow()
        )
        session.add(resp)
        # Update score for leaderboard
        score_obj = session.exec(
            select(Score).where((Score.user_id == user_id) & (Score.room_id == room_id))
        ).first()
        if not score_obj:
            score_obj = Score(user_id=user_id, room_id=room_id, total_score=0)
            session.add(score_obj)
        if is_correct:
            score_obj.total_score += 10  # award points
            score_obj.updated_at = datetime.utcnow()
        session.commit()
    # Notify all clients about the answer submission result (for live effect)
    await conn_manager.broadcast_room(room_id, {
        "event": "answer_submitted",
        "user_id": user_id,
        "username": session.get(User, user_id).username,
        "question_id": question_id,
        "selected_option": selected_option,
        "is_correct": is_correct
    })


# PUBLIC_INTERFACE
async def broadcast_leaderboard(room_id: int, session: Session):
    """Broadcast current leaderboard for the given room."""
    scores = session.exec(select(Score).where(Score.room_id == room_id)).all()
    ranking = sorted(scores, key=lambda x: x.total_score, reverse=True)
    # Assign and save new ranks
    for idx, s in enumerate(ranking):
        s.rank = idx + 1
        s.updated_at = datetime.utcnow()
    session.commit()
    leaderboard = [
        {
            "user_id": s.user_id,
            "username": session.get(User, s.user_id).username,
            "total_score": s.total_score,
            "rank": s.rank
        }
        for s in ranking
    ]
    await conn_manager.broadcast_room(room_id, {
        "event": "leaderboard_update",
        "leaderboard": leaderboard
    })

# PUBLIC_INTERFACE
@router.get("/websocket-info", response_class=HTMLResponse, tags=["websocket"], summary="WebSocket API documentation", description="Instructions for WebSocket usage in QuizRealm. Token authentication required.")
def websocket_instructions():
    """
    HTML help for using WebSockets in the QuizRealm backend. Details required actions and payloads.
    """
    return """
    <h2>WebSocket Usage (QuizRealm Realtime API)</h2>
    <b>Base endpoint (per room):</b><br>
    <code>ws://&lt;server&gt;/ws/room/{room_id}?token=&lt;JWT&gt;</code>
    <br><br>
    <b>Available actions to send/receive:</b>
    <ul>
      <li><b>Join/Leave</b>: real-time notification when participant joins or leaves.</li>
      <li><b>Start question</b> (only owner):<br>
        { "action": "start_question", "question_id": 42 }
      </li>
      <li><b>Answer question</b>:<br>
        { "action": "answer", "question_id": 42, "selected_option": "A" }
      </li>
      <li><b>Request leaderboard</b>:<br>
        { "action": "request_leaderboard" }
      </li>
    </ul>
    <b>Events broadcast to all:</b>
    <ul>
      <li>user_joined, user_left, question_start, countdown, question_closed, leaderboard_update, answer_submitted</li>
    </ul>
    """
