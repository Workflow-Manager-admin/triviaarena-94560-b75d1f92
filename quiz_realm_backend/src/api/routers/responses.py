from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session
from datetime import datetime
from ..models import Response, Question, Room, User
from ..database import get_session
from ..auth import get_current_user

router = APIRouter(
    prefix="/responses",
    tags=["responses"]
)

class AnswerRequest(BaseModel):
    room_id: int
    question_id: int
    selected_option: str

# PUBLIC_INTERFACE
@router.post("/", response_model=Response, summary="Submit an answer to a quiz question")
def submit_response(payload: AnswerRequest, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """Submit an answer to a quiz question, create a Response object, and mark correctness."""
    question = session.get(Question, payload.question_id)
    room = session.get(Room, payload.room_id)
    if not question or not room:
        raise HTTPException(status_code=404, detail="Room or Question not found")
    is_correct = (payload.selected_option == question.correct_option)
    response = Response(
        user_id=user.id,
        room_id=payload.room_id,
        question_id=payload.question_id,
        selected_option=payload.selected_option,
        is_correct=is_correct,
        answered_at=datetime.utcnow()
    )
    session.add(response)
    session.commit()
    session.refresh(response)
    return response
