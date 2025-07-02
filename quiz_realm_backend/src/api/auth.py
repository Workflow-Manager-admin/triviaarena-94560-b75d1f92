from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

# Constants for modularity
SECRET_KEY = "temporary-for-dev-should-be-env"
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# PUBLIC_INTERFACE
def fake_decode_token(token: str):
    """Stub: Replace with JWT logic."""
    return {"username": token}

# PUBLIC_INTERFACE
def get_current_user(token: str = Depends(oauth2_scheme)):
    """Stub: Replace with JWT authentication logic."""
    user = fake_decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return user
