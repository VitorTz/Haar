from src.security import get_user_from_token
from src.schemas.pagination import Pagination
from src.schemas.user import User
from src.schemas.urls import (
    UrlTagCreate, 
    UrlTag, 
    UrlTagUpdate, 
    UrlTagDelete, 
    UrlTagRelationCreate, 
    UrlTagRelationDelete, 
    UrlTagId, 
    URLResponse
)
from fastapi import APIRouter, Depends, status, Query, Request, Cookie
from src.services import tag as tag_service
from asyncpg import Connection
from src.db import get_db
from typing import Optional


router = APIRouter()


@router.get("/", status_code=status.HTTP_200_OK, response_model=Pagination[UrlTag])
async def get_user_tags(
    user: User = Depends(get_user_from_token), 
    limit: int = Query(default=64, le=64, ge=0),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_db)
):
    return await tag_service.get_user_tags(user, limit, offset, conn)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag: UrlTagCreate,
    user: User = Depends(get_user_from_token), 
    conn: Connection = Depends(get_db)
):
    return await tag_service.create_tag(user, tag, conn)


@router.put("/", status_code=status.HTTP_201_CREATED, response_model=UrlTag)
async def update_tag(
    tag: UrlTagUpdate,
    user: User = Depends(get_user_from_token), 
    conn: Connection = Depends(get_db)
):
    return await tag_service.update_tag(user, tag, conn)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag: UrlTagDelete,
    user: User = Depends(get_user_from_token), 
    conn: Connection = Depends(get_db)
):
    await tag_service.delete_tag(user, tag, conn)


@router.get("/relations", status_code=status.HTTP_200_OK, response_model=Pagination[URLResponse])
async def get_urls_from_tag(
    tag: UrlTagId,
    request: Request,
    limit: int = Query(default=64, le=64, ge=0),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_user_from_token), 
    conn: Connection = Depends(get_db)
):
    return await tag_service.get_urls_from_tag(request, user, tag, limit, offset, conn)
    

@router.post("/relations", status_code=status.HTTP_201_CREATED)
async def create_url_tag(
    tag: UrlTagRelationCreate,
    user: User = Depends(get_user_from_token), 
    conn: Connection = Depends(get_db)
):
    return await tag_service.create_tag_relation(user, tag, conn)


@router.delete("/relations", status_code=status.HTTP_204_NO_CONTENT)
async def create_url_tag(
    tag: UrlTagRelationDelete,
    user: User = Depends(get_user_from_token), 
    conn: Connection = Depends(get_db)
):
    await tag_service.delete_tag_relation(user, tag, conn)


@router.delete("/relations/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_tag(
    tag: UrlTagId,
    user: User = Depends(get_user_from_token), 
    conn: Connection = Depends(get_db)
):
    await tag_service.clear_tag(user, tag, conn)