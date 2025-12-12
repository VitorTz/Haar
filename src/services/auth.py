from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import HTTPException
from fastapi import status, Request
from asyncpg import Connection, UniqueViolationError
from src.schemas.user import User, UserLogin, UserLoginData, UserCreate, UserSession
from src.schemas.pagination import Pagination
from src.schemas.token import SessionToken
from src.tables import users as users_table
from datetime import datetime, timezone, timedelta
from src.constants import Constants
from src import security
from uuid import UUID
from typing import Optional
from src import util
from src.security import hash_password


async def get_user(user_id: str | UUID, conn: Connection) -> User:
    try:
        user: Optional[User] = await users_table.get_user(user_id, conn)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}")
    if user is None: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return user


async def login(login: UserLogin, request: Request, conn: Connection):
    user_login_data: Optional[UserLoginData] = await users_table.get_user_login_data_from_email(login.email, conn)
    if user_login_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
    if user_login_data.locked_until and user_login_data.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Account locked until {user_login_data.locked_until}")
    
    if not security.verify_password(login.password, user_login_data.p_hash):
        user_login_data = await users_table.register_failed_login_attempt(user_login_data, conn)
        if user_login_data.login_attempts >= Constants.MAX_FAILED_ATTEMPTS:
            user_login_data.locked_until = datetime.now(timezone.utc) + timedelta(minutes=Constants.LOCK_TIME_MINUTES)
            await users_table.lock_user_login(user_login_data, conn)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Account locked until {user_login_data.locked_until}")
                
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    await users_table.reset_user_login_attempts(user_login_data, conn)
    
    # Create unique access token
    session_token: SessionToken = security.create_session_token(user_login_data.id)
    await users_table.create_user_session_token(
        user_login_data.id,
        session_token.refresh_token,
        util.get_client_info(request),
        conn        
    )

    await users_table.update_user_last_login_at(user_login_data.id, conn)
    
    user = User(
        id=user_login_data.id,
        email=user_login_data.email,
        last_login_at=user_login_data.last_login_at,
        created_at=user_login_data.created_at
    )
    response = JSONResponse(content=user.model_dump(mode='json'))
    security.set_session_token_cookie(response, session_token)
    
    return response


async def get_user_sessions(user: User, limit: int, offset: int, conn: Connection) -> Pagination[UserSession]:
    return await users_table.get_user_sessions(user.id, limit, offset, conn)


async def refresh_access_token(refresh_token: Optional[str], conn: Connection) -> User:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    
    user: Optional[User] = await users_table.get_user_by_refresh_token(refresh_token, conn)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    
    session_token: SessionToken = security.create_session_token(user.id)
    session_token.refresh_token.token = refresh_token

    await users_table.update_user_session_token(
        user.id,
        session_token.refresh_token,
        conn 
    )

    user: User = await users_table.get_user(user.id, conn)
    response = JSONResponse(user.model_dump(mode='json'))
    security.set_session_token_cookie(response, session_token)

    return response


async def signup(new_user: UserCreate, conn: Connection):
    try:
        await users_table.create_user(new_user, hash_password, conn)
        return Response(status_code=status.HTTP_201_CREATED)
    except UniqueViolationError:
        raise HTTPException(status_code=409, detail="Email already registered")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}")


async def logout(refresh_token: Optional[str], conn: Connection):
    if refresh_token is not None:
        await users_table.delete_user_session_token(refresh_token, conn)
    
    response = Response()
    security.unset_session_token_cookie(response)
    return response


async def logout_all(user: User, conn: Connection):
    await users_table.delete_all_user_session_tokens(user.id, conn)
    response = Response()
    security.unset_session_token_cookie(response)
    return response