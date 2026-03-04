import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.admin import (
    AdminStatsResponse,
    AdminUserDetailResponse,
    AdminUserUpdateRequest,
    PaginatedResponse,
)
from src.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await admin_service.get_stats(db)


@router.get("/users", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_users(db, page=page, page_size=page_size, search=search)


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    user = await admin_service.get_user_detail(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=AdminUserDetailResponse)
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await admin_service.update_user(db, user_id, name=body.name, is_active=body.is_active)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Return full detail
    return await admin_service.get_user_detail(db, user_id)


@router.get("/workspaces", response_model=PaginatedResponse)
async def list_workspaces(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_workspaces(db, page=page, page_size=page_size, search=search)
