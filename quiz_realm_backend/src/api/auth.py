from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from sqlmodel import Session, select
from .models import User
from .database import get_session
from pydantic import BaseModel, Field, EmailStr

# PUBLIC_INTERFACE
# Constants for JWT
SECRET_KEY = "temporary-for-dev-should-be-env"  # TODO: replace with os.getenv
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours (tweak as needed)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

router = APIRouter(tags=["auth"])

####### Utility Functions #######

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against hash using passlib."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password for storing."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Creates and returns a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token

def get_user_by_username_or_email(session: Session, username_or_email: str):
    """Fetch a user from DB by username or email (for login)."""
    user = session.exec(
        select(User).where(
            (User.username == username_or_email) | (User.email == username_or_email)
        )
    ).first()
    return user

####### SCHEMAS #######

class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, description="User's unique username")
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128, description="Raw password")

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    created_at: datetime

####### ENDPOINTS #######

# PUBLIC_INTERFACE
@router.post("/signup", response_model=UserOut, summary="User registration/signup")
def signup(payload: SignupRequest, session: Session = Depends(get_session)):
    """
    Register a new user. Username and email must be unique. Password is securely hashed.
    """
    # Check for username or email collision
    if session.exec(select(User).where(User.username == payload.username)).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if session.exec(select(User).where(User.email == payload.email)).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    # Hash and create user
    hashed_pw = get_password_hash(payload.password)
    user = User(username=payload.username, email=payload.email, hashed_password=hashed_pw)
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserOut.model_validate(user)

# PUBLIC_INTERFACE
@router.post("/login", response_model=Token, summary="User login and JWT token issuing")
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    """
    Authenticate user with username/email and password.
    Returns a JWT access token on successful login.
    """
    user = get_user_by_username_or_email(session, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username/email or password")
    token_data = {"sub": user.username, "uid": user.id}
    access_token = create_access_token(token_data)
    return Token(access_token=access_token)

####### JWT Authentication Dependency #######

# PUBLIC_INTERFACE
def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    """
    Dependency that extracts user from JWT token.
    Throws error if auth fails. Returns User model.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise credentials_exception
    return user

