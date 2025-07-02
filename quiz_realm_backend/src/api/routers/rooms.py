from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from ..models import Room, User
from ..database import get_session
from ..auth import get_current_user

router = APIRouter(
    prefix="/rooms",
    tags=["rooms"]
)

# PUBLIC_INTERFACE
@router.get("/", response_model=List[Room], summary="List all available quiz rooms")
def list_rooms(session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """Get a list of all active quiz rooms."""
    rooms = session.exec(select(Room).where(Room.is_active)).all()
    return rooms

# PUBLIC_INTERFACE
@router.post("/create", response_model=Room, summary="Create a new quiz room")
def create_room(name: str, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """Create a new quiz room with the current user as owner."""
    room = Room(name=name, owner_id=user.id)
    session.add(room)
    session.commit()
    session.refresh(room)
    return room

# PUBLIC_INTERFACE
@router.post("/join", response_model=Room, summary="Join an existing quiz room")
def join_room(room_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    """
    Join an existing room if it is active. (Could track participants in Room-user table if desired.)
    """
    room = session.get(Room, room_id)
    if not room or not room.is_active:
        raise HTTPException(status_code=404, detail="Room does not exist or is inactive")
    # Participation logic can be added here as needed.
    return room
