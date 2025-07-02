from fastapi import APIRouter
from sqlmodel import Session, select
from starlette.responses import JSONResponse
from ..models import User

# Register with explicit response_class and response_model
router = APIRouter()

# PUBLIC_INTERFACE
@router.get(
    "/quiz_check",
    response_class=JSONResponse,
    tags=["diagnostics"],
    summary="Health check and DB connectivity",
    response_description="Status of server and DB"
)
def quiz_check():
    """
    Health-check endpoint for QuizRealm backend.
    Attempts a simple database operation to confirm DB connection in addition to signaling server is running.

    Returns:
        JSON object: {"status": "ok", "database": "connected"} if all is well,
        {"status": "error", "database": "unreachable"} if DB fails.
    """
    try:
        # Try DB connectivity: select 1 user (or just count in pure SQL)
        from ..database import engine
        with Session(engine) as session:
            session.exec(select(User).limit(1))
        db_status = "connected"
        status = "ok"
    except Exception:
        db_status = "unreachable"
        status = "error"
    # Always ensure JSON object is returned w/ proper CORS
    return JSONResponse(content={"status": status, "database": db_status})
