from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from ..models import MatchHistory, User, Room
from ..database import get_session
from ..auth import get_current_user

router = APIRouter(
    tags=["dashboard"],
    prefix="/dashboard"
)

# PUBLIC_INTERFACE
@router.get("/", summary="Get user dashboard (match history and stats)")
def get_dashboard(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """
    Returns dashboard data for the logged-in user: recent matches, rooms, and performance.
    """
    match_history = session.exec(select(MatchHistory).where(MatchHistory.user_id == user.id)).all()
    data = []
    for match in match_history:
        room = session.get(Room, match.room_id)
        data.append({
            "room_id": match.room_id,
            "room_name": room.name if room else "",
            "final_score": match.final_score,
            "position": match.position,
            "played_at": match.played_at,
        })
    # Optionally add stats aggregations here.
    return {"user": user.username, "history": data}
