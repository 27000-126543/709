from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple

from app.database import get_db
from app.models import Organ, Donor
from app.schemas import (
    OrganCreate,
    OrganUpdate,
    OrganResponse,
    OrganLockRequest,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/organs", tags=["organs"])


class OrganService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_organ(self, data: OrganCreate) -> Organ:
        donor_result = await self.db.execute(
            select(Donor).where(Donor.id == data.donor_id)
        )
        if not donor_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="捐赠者不存在")
        organ = Organ(**data.model_dump(exclude_none=True))
        organ.status = "available"
        self.db.add(organ)
        await self.db.flush()
        await self.db.refresh(organ)
        return organ

    async def get_organ(self, organ_id: str) -> Optional[Organ]:
        result = await self.db.execute(
            select(Organ).where(Organ.id == organ_id)
        )
        return result.scalar_one_or_none()

    async def list_organs(
        self,
        skip: int = 0,
        limit: int = 100,
        organ_type: Optional[str] = None,
        status: Optional[str] = None,
        donor_id: Optional[str] = None,
    ) -> Tuple[List[Organ], int]:
        query = select(Organ)
        if organ_type:
            query = query.where(Organ.organ_type == organ_type)
        if status:
            query = query.where(Organ.status == status)
        if donor_id:
            query = query.where(Organ.donor_id == donor_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Organ.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_organ(self, organ_id: str, data: OrganUpdate) -> Optional[Organ]:
        organ = await self.get_organ(organ_id)
        if not organ:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(organ, key, value)
        await self.db.flush()
        await self.db.refresh(organ)
        return organ

    async def delete_organ(self, organ_id: str) -> bool:
        organ = await self.get_organ(organ_id)
        if not organ:
            return False
        await self.db.delete(organ)
        await self.db.flush()
        return True

    async def lock_organ(self, data: OrganLockRequest) -> Optional[Organ]:
        organ = await self.get_organ(data.organ_id)
        if not organ:
            return None
        if organ.status != "available":
            raise HTTPException(status_code=400, detail=f"器官当前状态为 {organ.status}，无法锁定")
        organ.status = "locked"
        await self.db.flush()
        await self.db.refresh(organ)
        return organ

    async def unlock_organ(self, organ_id: str) -> Optional[Organ]:
        organ = await self.get_organ(organ_id)
        if not organ:
            return None
        if organ.status != "locked":
            raise HTTPException(status_code=400, detail=f"器官当前状态为 {organ.status}，无法解锁")
        organ.status = "available"
        await self.db.flush()
        await self.db.refresh(organ)
        return organ


@router.post("", response_model=OrganResponse)
async def create_organ(
    data: OrganCreate,
    db: AsyncSession = Depends(get_db),
):
    service = OrganService(db)
    return await service.create_organ(data)


@router.get("/{organ_id}", response_model=OrganResponse)
async def get_organ(
    organ_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = OrganService(db)
    organ = await service.get_organ(organ_id)
    if not organ:
        raise HTTPException(status_code=404, detail="器官不存在")
    return organ


@router.get("", response_model=PaginatedResponse[OrganResponse])
async def list_organs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    organ_type: Optional[str] = None,
    status: Optional[str] = None,
    donor_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = OrganService(db)
    skip = (page - 1) * size
    items, total = await service.list_organs(
        skip=skip,
        limit=size,
        organ_type=organ_type,
        status=status,
        donor_id=donor_id,
    )
    total_pages = (total + size - 1) // size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
    )


@router.put("/{organ_id}", response_model=OrganResponse)
async def update_organ(
    organ_id: str,
    data: OrganUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = OrganService(db)
    organ = await service.update_organ(organ_id, data)
    if not organ:
        raise HTTPException(status_code=404, detail="器官不存在")
    return organ


@router.delete("/{organ_id}")
async def delete_organ(
    organ_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = OrganService(db)
    success = await service.delete_organ(organ_id)
    if not success:
        raise HTTPException(status_code=404, detail="器官不存在")
    return {"code": 200, "message": "删除成功"}


@router.post("/lock")
async def lock_organ(
    data: OrganLockRequest,
    db: AsyncSession = Depends(get_db),
):
    service = OrganService(db)
    organ = await service.lock_organ(data)
    if not organ:
        raise HTTPException(status_code=404, detail="器官不存在")
    return {"code": 200, "message": "器官已锁定", "data": OrganResponse.model_validate(organ)}


@router.post("/{organ_id}/unlock")
async def unlock_organ(
    organ_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = OrganService(db)
    organ = await service.unlock_organ(organ_id)
    if not organ:
        raise HTTPException(status_code=404, detail="器官不存在")
    return {"code": 200, "message": "器官已解锁", "data": OrganResponse.model_validate(organ)}
