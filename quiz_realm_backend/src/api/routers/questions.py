from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from ..models import Question
from ..database import get_session
from ..auth import get_current_user

router = APIRouter(
    prefix="/questions",
    tags=["questions"]
)

# PUBLIC_INTERFACE
@router.get("/{room_id}", response_model=List[Question], summary="Get all questions for a room")
def get_questions_for_room(room_id: int, session: Session = Depends(get_session), user=Depends(get_current_user)):
    """Get all questions assigned to a quiz room by room_id."""
    questions = session.exec(select(Question).where(Question.room_id == room_id)).all()
    if not questions:
        raise HTTPException(status_code=404, detail="No questions found for this room")
    return questions
