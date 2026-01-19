from src.schemas.user import User, UserLogin, UserSession, UserCreate
from src.schemas.pagination import Pagination
from fastapi import APIRouter, Depends, Request, Query, Cookie, status, Response
from fastapi.responses import JSONResponse
from src.security import get_user_from_token
from src.services import auth as auth_service
from src.db import get_db
from asyncpg import Connection
from typing import Optional


router = APIRouter()


@router.get("/me", response_model=User)
async def get_manager(
    user: User = Depends(get_user_from_token),
    conn: Connection = Depends(get_db)
) -> JSONResponse:
    return await auth_service.get_user(user.id, conn)


@router.post("/login", response_model=User)
async def login(
    response: Response,
    user_login: UserLogin,
    request: Request,
    conn: Connection = Depends(get_db)
) -> User:
    return await auth_service.login(response, user_login, request, conn)


@router.get("/sessions", response_model=Pagination[UserSession])
async def get_manager_active_sessions(
    limit: int = Query(default=64, le=64, ge=1),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_user_from_token),
    conn: Connection = Depends(get_db)
):
    return await auth_service.get_user_sessions(user, limit, offset, conn)


@router.post("/refresh", response_model=User)
async def refresh_token_manager(refresh_token: Optional[str] = Cookie(default=None), conn: Connection = Depends(get_db)):
    return await auth_service.refresh_access_token(refresh_token, conn)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(new_user: UserCreate, conn: Connection = Depends(get_db)):
    return await auth_service.signup(new_user, conn)


@router.post("/logout")
async def logout(refresh_token: str | None = Cookie(default=None), conn: Connection = Depends(get_db)):
    return await auth_service.logout(refresh_token, conn)


@router.post("/logout/all")
async def logout(user: User = Depends(get_user_from_token), conn: Connection = Depends(get_db)):
    return await auth_service.logout_all(user, conn)