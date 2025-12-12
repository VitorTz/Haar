from datetime import datetime, timezone, timedelta
from fastapi.exceptions import HTTPException
from fastapi.responses import Response
from fastapi import Depends, Cookie
from passlib.context import CryptContext
from src.constants import Constants
from src.db import get_db
from src.schemas.user import User, UserLoginAttempt
from src.schemas.token import SessionToken, Token
from src.tables import users as users_table
from src.globals import Globals
from fastapi import status
from jose import jwt, JWTError
from asyncpg import Connection
from src.constants import Constants
from typing import Optional
from dataclasses import dataclass
from src import util
import uuid


@dataclass
class UrlMetadata:

    final_url: str
    status: int
    content_type: str
    content_length: str | None


pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

INVALID_PASSWORD_EXCEPTION = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Password must be at least 8 characters long"
)


def check_admin_token(token: Optional[str]):
    if not token: return False
    try:
        payload = jwt.decode(token, Constants.SECRET_KEY, algorithms=[Constants.ALGORITHM])
        admin_password: str = payload.get("sub")
        if admin_password != Constants.ADMIN_PASSWORD:
            return False
    except Exception:        
        return False
    return True


def require_admin(token: str = Depends(Globals.oauth2_admin_scheme)):
    if not check_admin_token(token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required"
        )
    return True


def hash_password(password: str) -> bytes:
    if not password or len(password) < 8:
        raise INVALID_PASSWORD_EXCEPTION
    return pwd_context.hash(password).encode()


def verify_password(plain_password: str, hashed_password: bytes) -> bool:
    try:      
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_new_refresh_token_expires_time() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=Constants.REFRESH_TOKEN_EXPIRE_DAYS)


def create_new_access_token_expires_time() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=Constants.ACCESS_TOKEN_EXPIRE_HOURS)


def create_refresh_token() -> Token:
    return Token(
        token=str(uuid.uuid4()), 
        expires_at=create_new_refresh_token_expires_time()
    )


def create_access_token(manager_id: uuid.UUID) -> Token:
    expires_at: str = datetime.now(timezone.utc) + (timedelta(hours=Constants.ACCESS_TOKEN_EXPIRE_HOURS))
    token: str = jwt.encode(
        {"sub": str(manager_id), "exp": expires_at}, 
        Constants.SECRET_KEY,
        algorithm=Constants.ALGORITHM
    )
    return Token(token=token, expires_at=expires_at)


def create_session_token(manager_id: uuid.UUID) -> SessionToken:
    return SessionToken(
        access_token=create_access_token(manager_id), 
        refresh_token=create_refresh_token()
    )


def check_user_login_attempts(lock: UserLoginAttempt):
    now = datetime.now(timezone.utc)
    if lock.locked_until and lock.locked_until > now:
        raise HTTPException(status_code=403, detail=f"Account locked until {lock.locked_until}")
    

async def get_user_from_token(
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )    
    if access_token is None: 
        raise credentials_exception
    
    try:
        payload = jwt.decode(
            access_token,
            Constants.SECRET_KEY,
            algorithms=[Constants.ALGORITHM]
        )
        
        user_id: str = payload.get("sub")
        if user_id is None: 
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    manager: Optional[User] = await users_table.get_user(user_id, conn)
    
    if manager is None:
        raise credentials_exception
    
    return manager


async def get_user_from_token_if_exists(
    access_token: Optional[str] = Cookie(default=None),
    conn: Connection = Depends(get_db)
) -> Optional[User]:
    if access_token is None: return None

    try:
        payload = jwt.decode(
            access_token,
            Constants.SECRET_KEY,
            algorithms=[Constants.ALGORITHM]
        )
        user_id: str | None = payload.get("sub")
        if user_id: return await users_table.get_user(user_id, conn)
    except JWTError:
        return None


def set_session_token_cookie(response: Response, session_token: SessionToken):
    print(Constants.IS_PRODUCTION)
    if Constants.IS_PRODUCTION:
        samesite_policy = "none"
        secure_policy = True
    else:
        samesite_policy = "lax"
        secure_policy = False
    
    response.set_cookie(
        key="refresh_token",
        value=session_token.refresh_token.token,
        httponly=True,
        secure=secure_policy,
        samesite=samesite_policy,
        path="/",
        max_age=util.seconds_until(session_token.refresh_token.expires_at)
    )

    response.set_cookie(
        key="access_token",
        value=session_token.access_token.token,
        httponly=True,
        secure=secure_policy,
        samesite=samesite_policy,
        path="/",
        max_age=util.seconds_until(session_token.access_token.expires_at)
    )


def unset_session_token_cookie(response: Response):
    if Constants.IS_PRODUCTION:
        samesite_policy = "none"
        secure_policy = True 
    else:
        samesite_policy = "lax"
        secure_policy = False

    response.delete_cookie(
        key="access_token", 
        httponly=True, 
        path='/', 
        samesite=samesite_policy, 
        secure=secure_policy
    )

    response.delete_cookie(
        key="refresh_token", 
        httponly=True, 
        path='/', 
        samesite=samesite_policy, 
        secure=secure_policy
    )