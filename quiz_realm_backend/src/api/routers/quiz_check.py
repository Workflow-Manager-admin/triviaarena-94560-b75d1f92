from fastapi import APIRouter

router = APIRouter()

# PUBLIC_INTERFACE
@router.get("/quiz_check", tags=["diagnostics"])
def quiz_check():
    """Health-check endpoint for QuizRealm backend wiring."""
    return {"status": "QuizRealm backend is running"}
