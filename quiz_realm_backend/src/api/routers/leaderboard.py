from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..models import Score, User
from ..database import get_session
from ..auth import get_current_user

router = APIRouter(
    prefix="/leaderboard",
    tags=["leaderboard"]
)

# PUBLIC_INTERFACE
@router.get("/{room_id}", summary="Get leaderboard for a quiz room")
def get_leaderboard(room_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """
    Returns a leaderboard for the specified quiz room, sorted by score (descending).
    """
    scores = session.exec(select(Score).where(Score.room_id == room_id)).all()
    if not scores:
        raise HTTPException(status_code=404, detail="Leaderboard for room not found")
    # Attach user info
    result = []
    for s in sorted(scores, key=lambda x: x.total_score, reverse=True):
        user_obj = session.get(User, s.user_id)
        result.append({
            "user_id": s.user_id,
            "username": user_obj.username if user_obj else "",
            "total_score": s.total_score,
            "rank": s.rank,
        })
    return result
