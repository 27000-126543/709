from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple

from app.database import get_db
from app.models import Recipient, WaitingList
from app.schemas import (
    RecipientCreate,
    RecipientUpdate,
    RecipientResponse,
    WaitingListAdd,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/recipients", tags=["recipients"])


class RecipientService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_recipient(self, data: RecipientCreate) -> Recipient:
        recipient = Recipient(**data.model_dump(exclude_none=True))
        recipient.status = "waiting"
        self.db.add(recipient)
        await self.db.flush()
        await self.db.refresh(recipient)
        return recipient

    async def get_recipient(self, recipient_id: str) -> Optional[Recipient]:
        result = await self.db.execute(
            select(Recipient).where(Recipient.id == recipient_id)
        )
        return result.scalar_one_or_none()

    async def list_recipients(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        organ_type_needed: Optional[str] = None,
        urgency_level: Optional[str] = None,
        province: Optional[str] = None,
    ) -> Tuple[List[Recipient], int]:
        query = select(Recipient)
        if status:
            query = query.where(Recipient.status == status)
        if organ_type_needed:
            query = query.where(Recipient.organ_type_needed == organ_type_needed)
        if urgency_level:
            query = query.where(Recipient.urgency_level == urgency_level)
        if province:
            query = query.where(Recipient.province == province)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Recipient.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_recipient(
        self, recipient_id: str, data: RecipientUpdate
    ) -> Optional[Recipient]:
        recipient = await self.get_recipient(recipient_id)
        if not recipient:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(recipient, key, value)
        await self.db.flush()
        await self.db.refresh(recipient)
        return recipient

    async def delete_recipient(self, recipient_id: str) -> bool:
        recipient = await self.get_recipient(recipient_id)
        if not recipient:
            return False
        await self.db.delete(recipient)
        await self.db.flush()
        return True

    async def add_to_waiting_list(self, data: WaitingListAdd) -> WaitingList:
        recipient = await self.get_recipient(data.recipient_id)
        if not recipient:
            raise HTTPException(status_code=404, detail="受赠者不存在")
        existing = await self.db.execute(
            select(WaitingList).where(WaitingList.recipient_id == data.recipient_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="受赠者已在等待名单中")
        wl = WaitingList(**data.model_dump(exclude_none=True))
        self.db.add(wl)
        recipient.status = "waiting"
        await self.db.flush()
        await self.db.refresh(wl)
        return wl

    async def list_waiting_list(
        self,
        skip: int = 0,
        limit: int = 100,
        organ_type_needed: Optional[str] = None,
        urgency_level: Optional[str] = None,
    ) -> Tuple[List[WaitingList], int]:
        query = select(WaitingList)
        if organ_type_needed:
            query = query.where(WaitingList.organ_type_needed == organ_type_needed)
        if urgency_level:
            query = query.where(WaitingList.urgency_level == urgency_level)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(
            WaitingList.urgency_level.desc(), WaitingList.waiting_since.asc()
        ).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def remove_from_waiting_list(self, recipient_id: str) -> bool:
        result = await self.db.execute(
            select(WaitingList).where(WaitingList.recipient_id == recipient_id)
        )
        wl = result.scalar_one_or_none()
        if not wl:
            return False
        recipient = await self.get_recipient(recipient_id)
        if recipient:
            recipient.status = "delisted"
        await self.db.delete(wl)
        await self.db.flush()
        return True


@router.post("", response_model=RecipientResponse)
async def create_recipient(
    data: RecipientCreate,
    db: AsyncSession = Depends(get_db),
):
    service = RecipientService(db)
    return await service.create_recipient(data)


@router.get("/{recipient_id}", response_model=RecipientResponse)
async def get_recipient(
    recipient_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RecipientService(db)
    recipient = await service.get_recipient(recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="受赠者不存在")
    return recipient


@router.get("", response_model=PaginatedResponse[RecipientResponse])
async def list_recipients(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    organ_type_needed: Optional[str] = None,
    urgency_level: Optional[str] = None,
    province: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = RecipientService(db)
    skip = (page - 1) * size
    items, total = await service.list_recipients(
        skip=skip,
        limit=size,
        status=status,
        organ_type_needed=organ_type_needed,
        urgency_level=urgency_level,
        province=province,
    )
    total_pages = (total + size - 1) // size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
    )


@router.put("/{recipient_id}", response_model=RecipientResponse)
async def update_recipient(
    recipient_id: str,
    data: RecipientUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = RecipientService(db)
    recipient = await service.update_recipient(recipient_id, data)
    if not recipient:
        raise HTTPException(status_code=404, detail="受赠者不存在")
    return recipient


@router.delete("/{recipient_id}")
async def delete_recipient(
    recipient_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RecipientService(db)
    success = await service.delete_recipient(recipient_id)
    if not success:
        raise HTTPException(status_code=404, detail="受赠者不存在")
    return {"code": 200, "message": "删除成功"}


@router.post("/waiting-list")
async def add_to_waiting_list(
    data: WaitingListAdd,
    db: AsyncSession = Depends(get_db),
):
    service = RecipientService(db)
    wl = await service.add_to_waiting_list(data)
    return {"code": 200, "message": "已加入等待名单", "data": wl}


@router.get("/waiting-list/list")
async def list_waiting_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    organ_type_needed: Optional[str] = None,
    urgency_level: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = RecipientService(db)
    skip = (page - 1) * size
    items, total = await service.list_waiting_list(
        skip=skip,
        limit=size,
        organ_type_needed=organ_type_needed,
        urgency_level=urgency_level,
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


@router.delete("/waiting-list/{recipient_id}")
async def remove_from_waiting_list(
    recipient_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = RecipientService(db)
    success = await service.remove_from_waiting_list(recipient_id)
    if not success:
        raise HTTPException(status_code=404, detail="等待名单记录不存在")
    return {"code": 200, "message": "已从等待名单移除"}
