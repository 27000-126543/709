from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple
from datetime import datetime

from app.database import get_db
from app.models import TransplantCenter, Coordinator, Regulator, TransportTeam
from app.schemas import (
    TransplantCenterCreate,
    TransplantCenterUpdate,
    TransplantCenterResponse,
    CoordinatorCreate,
    CoordinatorUpdate,
    CoordinatorResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/centers", tags=["centers"])


class CenterRouterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_center(self, data: TransplantCenterCreate) -> TransplantCenter:
        existing = await self.db.execute(
            select(TransplantCenter).where(
                (TransplantCenter.code == data.code) | (TransplantCenter.name == data.name)
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="移植中心名称或编码已存在")
        center = TransplantCenter(**data.model_dump(exclude_none=True))
        self.db.add(center)
        await self.db.flush()
        await self.db.refresh(center)
        return center

    async def get_center(self, center_id: str) -> Optional[TransplantCenter]:
        result = await self.db.execute(
            select(TransplantCenter).where(TransplantCenter.id == center_id)
        )
        return result.scalar_one_or_none()

    async def list_centers(
        self,
        skip: int = 0,
        limit: int = 100,
        province: Optional[str] = None,
        city: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[TransplantCenter], int]:
        query = select(TransplantCenter)
        if province:
            query = query.where(TransplantCenter.province == province)
        if city:
            query = query.where(TransplantCenter.city == city)
        if status:
            query = query.where(TransplantCenter.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(TransplantCenter.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_center(
        self, center_id: str, data: TransplantCenterUpdate
    ) -> Optional[TransplantCenter]:
        center = await self.get_center(center_id)
        if not center:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(center, key, value)
        await self.db.flush()
        await self.db.refresh(center)
        return center

    async def delete_center(self, center_id: str) -> bool:
        center = await self.get_center(center_id)
        if not center:
            return False
        await self.db.delete(center)
        await self.db.flush()
        return True

    async def create_coordinator(self, data: CoordinatorCreate) -> Coordinator:
        existing = await self.db.execute(
            select(Coordinator).where(Coordinator.id_number == data.id_number)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="协调员身份证号已存在")
        coordinator = Coordinator(**data.model_dump(exclude_none=True))
        self.db.add(coordinator)
        await self.db.flush()
        await self.db.refresh(coordinator)
        return coordinator

    async def get_coordinator(self, coordinator_id: str) -> Optional[Coordinator]:
        result = await self.db.execute(
            select(Coordinator).where(Coordinator.id == coordinator_id)
        )
        return result.scalar_one_or_none()

    async def list_coordinators(
        self,
        skip: int = 0,
        limit: int = 100,
        transplant_center_id: Optional[str] = None,
        province: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Coordinator], int]:
        query = select(Coordinator)
        if transplant_center_id:
            query = query.where(Coordinator.transplant_center_id == transplant_center_id)
        if province:
            query = query.where(Coordinator.province == province)
        if status:
            query = query.where(Coordinator.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Coordinator.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_coordinator(
        self, coordinator_id: str, data: CoordinatorUpdate
    ) -> Optional[Coordinator]:
        coordinator = await self.get_coordinator(coordinator_id)
        if not coordinator:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(coordinator, key, value)
        await self.db.flush()
        await self.db.refresh(coordinator)
        return coordinator

    async def delete_coordinator(self, coordinator_id: str) -> bool:
        coordinator = await self.get_coordinator(coordinator_id)
        if not coordinator:
            return False
        await self.db.delete(coordinator)
        await self.db.flush()
        return True

    async def list_regulators(
        self,
        skip: int = 0,
        limit: int = 100,
        level: Optional[str] = None,
        province: Optional[str] = None,
    ) -> Tuple[List[Regulator], int]:
        query = select(Regulator)
        if level:
            query = query.where(Regulator.level == level)
        if province:
            query = query.where(Regulator.province == province)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Regulator.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def list_transport_teams(
        self,
        skip: int = 0,
        limit: int = 100,
        province: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[TransportTeam], int]:
        query = select(TransportTeam)
        if province:
            query = query.where(TransportTeam.province == province)
        if status:
            query = query.where(TransportTeam.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(TransportTeam.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total


@router.post("", response_model=TransplantCenterResponse)
async def create_center(
    data: TransplantCenterCreate,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    return await service.create_center(data)


@router.get("/{center_id}", response_model=TransplantCenterResponse)
async def get_center(
    center_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    center = await service.get_center(center_id)
    if not center:
        raise HTTPException(status_code=404, detail="移植中心不存在")
    return center


@router.get("", response_model=PaginatedResponse[TransplantCenterResponse])
async def list_centers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    province: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_centers(
        skip=skip,
        limit=size,
        province=province,
        city=city,
        status=status,
    )
    total_pages = (total + size - 1) // size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
    )


@router.put("/{center_id}", response_model=TransplantCenterResponse)
async def update_center(
    center_id: str,
    data: TransplantCenterUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    center = await service.update_center(center_id, data)
    if not center:
        raise HTTPException(status_code=404, detail="移植中心不存在")
    return center


@router.delete("/{center_id}")
async def delete_center(
    center_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    success = await service.delete_center(center_id)
    if not success:
        raise HTTPException(status_code=404, detail="移植中心不存在")
    return {"code": 200, "message": "删除成功"}


@router.post("/coordinators", response_model=CoordinatorResponse)
async def create_coordinator(
    data: CoordinatorCreate,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    return await service.create_coordinator(data)


@router.get("/coordinators/{coordinator_id}", response_model=CoordinatorResponse)
async def get_coordinator(
    coordinator_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    coordinator = await service.get_coordinator(coordinator_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="协调员不存在")
    return coordinator


@router.get("/coordinators/list/all")
async def list_coordinators(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    transplant_center_id: Optional[str] = None,
    province: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_coordinators(
        skip=skip,
        limit=size,
        transplant_center_id=transplant_center_id,
        province=province,
        status=status,
    )
    total_pages = (total + size - 1) // size
    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": size,
            "total_pages": total_pages,
        },
    }


@router.put("/coordinators/{coordinator_id}", response_model=CoordinatorResponse)
async def update_coordinator(
    coordinator_id: str,
    data: CoordinatorUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    coordinator = await service.update_coordinator(coordinator_id, data)
    if not coordinator:
        raise HTTPException(status_code=404, detail="协调员不存在")
    return coordinator


@router.delete("/coordinators/{coordinator_id}")
async def delete_coordinator(
    coordinator_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    success = await service.delete_coordinator(coordinator_id)
    if not success:
        raise HTTPException(status_code=404, detail="协调员不存在")
    return {"code": 200, "message": "删除成功"}


@router.get("/regulators/list")
async def list_regulators(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    level: Optional[str] = None,
    province: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_regulators(
        skip=skip,
        limit=size,
        level=level,
        province=province,
    )
    total_pages = (total + size - 1) // size
    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": size,
            "total_pages": total_pages,
        },
    }


@router.get("/transport-teams/list")
async def list_transport_teams(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    province: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = CenterRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_transport_teams(
        skip=skip,
        limit=size,
        province=province,
        status=status,
    )
    total_pages = (total + size - 1) // size
    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": size,
            "total_pages": total_pages,
        },
    }
