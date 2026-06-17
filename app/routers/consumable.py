from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple
from datetime import datetime

from app.database import get_db
from app.services import ConsumableService
from app.models import Consumable, ConsumableTransaction, ReplenishmentRequest, OutboundQuota
from app.schemas import (
    ConsumableCreate,
    ConsumableUpdate,
    ConsumableResponse,
    ReplenishmentRequestCreate,
    ReplenishmentRequestUpdate,
    OutboundQuotaCreate,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/consumables", tags=["consumables"])


class ConsumableRouterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = ConsumableService(db) if ConsumableService else None

    async def create_consumable(self, data: ConsumableCreate) -> Consumable:
        consumable = Consumable(**data.model_dump(exclude_none=True))
        consumable.status = "normal"
        consumable.replenishment_status = "none"
        consumable.outbound_quota_locked = 0
        self.db.add(consumable)
        await self.db.flush()
        await self.db.refresh(consumable)
        return consumable

    async def get_consumable(self, consumable_id: str) -> Optional[Consumable]:
        result = await self.db.execute(
            select(Consumable).where(Consumable.id == consumable_id)
        )
        return result.scalar_one_or_none()

    async def list_consumables(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        status: Optional[str] = None,
        supplier: Optional[str] = None,
    ) -> Tuple[List[Consumable], int]:
        query = select(Consumable)
        if category:
            query = query.where(Consumable.category == category)
        if status:
            query = query.where(Consumable.status == status)
        if supplier:
            query = query.where(Consumable.supplier.like(f"%{supplier}%"))

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Consumable.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_consumable(
        self, consumable_id: str, data: ConsumableUpdate
    ) -> Optional[Consumable]:
        consumable = await self.get_consumable(consumable_id)
        if not consumable:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(consumable, key, value)

        if data.stock_quantity is not None and data.stock_quantity <= consumable.safety_stock_level:
            if data.stock_quantity == 0:
                consumable.status = "critical"
            elif data.stock_quantity <= consumable.safety_stock_level * 0.5:
                consumable.status = "critical"
            else:
                consumable.status = "low"
        elif data.stock_quantity is not None:
            consumable.status = "normal"

        await self.db.flush()
        await self.db.refresh(consumable)
        return consumable

    async def delete_consumable(self, consumable_id: str) -> bool:
        consumable = await self.get_consumable(consumable_id)
        if not consumable:
            return False
        await self.db.delete(consumable)
        await self.db.flush()
        return True

    async def create_replenishment_request(
        self, data: ReplenishmentRequestCreate
    ) -> ReplenishmentRequest:
        consumable = await self.get_consumable(data.consumable_id)
        if not consumable:
            raise HTTPException(status_code=404, detail="耗材不存在")

        existing = await self.db.execute(
            select(ReplenishmentRequest).where(
                ReplenishmentRequest.consumable_id == data.consumable_id,
                ReplenishmentRequest.status.in_(["submitted", "under_review", "approved", "ordered", "shipped"]),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该耗材已有进行中的补货申请")

        request = ReplenishmentRequest(**data.model_dump(exclude_none=True))
        request.status = "submitted"
        self.db.add(request)

        consumable.replenishment_status = "replenishing"
        consumable.status = "replenishing"

        await self.db.flush()
        await self.db.refresh(request)
        return request

    async def list_replenishment_requests(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        consumable_id: Optional[str] = None,
        requested_by: Optional[str] = None,
    ) -> Tuple[List[ReplenishmentRequest], int]:
        query = select(ReplenishmentRequest)
        if status:
            query = query.where(ReplenishmentRequest.status == status)
        if consumable_id:
            query = query.where(ReplenishmentRequest.consumable_id == consumable_id)
        if requested_by:
            query = query.where(ReplenishmentRequest.requested_by == requested_by)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(ReplenishmentRequest.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_replenishment_request(
        self, request_id: str, data: ReplenishmentRequestUpdate
    ) -> Optional[ReplenishmentRequest]:
        result = await self.db.execute(
            select(ReplenishmentRequest).where(ReplenishmentRequest.id == request_id)
        )
        request = result.scalar_one_or_none()
        if not request:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(request, key, value)

        if data.status == "received" and data.received_quantity:
            consumable = await self.get_consumable(request.consumable_id)
            if consumable:
                consumable.stock_quantity += data.received_quantity
                consumable.replenishment_status = "completed"
                if consumable.stock_quantity >= consumable.safety_stock_level:
                    consumable.status = "normal"
                else:
                    consumable.status = "low"
                transaction = ConsumableTransaction(
                    consumable_id=request.consumable_id,
                    transaction_type="replenishment",
                    quantity=data.received_quantity,
                    reference_id=str(request.id),
                    notes=f"补货入库, 申请单ID: {request.id}",
                )
                self.db.add(transaction)

        await self.db.flush()
        await self.db.refresh(request)
        return request

    async def lock_outbound_quota(
        self, data: OutboundQuotaCreate
    ) -> OutboundQuota:
        consumable = await self.get_consumable(data.consumable_id)
        if not consumable:
            raise HTTPException(status_code=404, detail="耗材不存在")

        available = consumable.stock_quantity - consumable.outbound_quota_locked
        if data.requested_quantity > available:
            raise HTTPException(
                status_code=400,
                detail=f"库存不足，可用数量: {available}",
            )

        quota = OutboundQuota(**data.model_dump(exclude_none=True))
        quota.locked_quantity = data.requested_quantity
        quota.status = "locked"
        self.db.add(quota)

        consumable.outbound_quota_locked += data.requested_quantity

        await self.db.flush()
        await self.db.refresh(quota)
        return quota

    async def list_outbound_quotas(
        self,
        skip: int = 0,
        limit: int = 100,
        consumable_id: Optional[str] = None,
        status: Optional[str] = None,
        allocation_id: Optional[str] = None,
        surgery_id: Optional[str] = None,
    ) -> Tuple[List[OutboundQuota], int]:
        query = select(OutboundQuota)
        if consumable_id:
            query = query.where(OutboundQuota.consumable_id == consumable_id)
        if status:
            query = query.where(OutboundQuota.status == status)
        if allocation_id:
            query = query.where(OutboundQuota.allocation_id == allocation_id)
        if surgery_id:
            query = query.where(OutboundQuota.surgery_id == surgery_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(OutboundQuota.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total


@router.post("", response_model=ConsumableResponse)
async def create_consumable(
    data: ConsumableCreate,
    db: AsyncSession = Depends(get_db),
):
    service = ConsumableRouterService(db)
    return await service.create_consumable(data)


@router.get("/{consumable_id}", response_model=ConsumableResponse)
async def get_consumable(
    consumable_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = ConsumableRouterService(db)
    consumable = await service.get_consumable(consumable_id)
    if not consumable:
        raise HTTPException(status_code=404, detail="耗材不存在")
    return consumable


@router.get("", response_model=PaginatedResponse[ConsumableResponse])
async def list_consumables(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    status: Optional[str] = None,
    supplier: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = ConsumableRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_consumables(
        skip=skip,
        limit=size,
        category=category,
        status=status,
        supplier=supplier,
    )
    total_pages = (total + size - 1) // size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
    )


@router.put("/{consumable_id}", response_model=ConsumableResponse)
async def update_consumable(
    consumable_id: str,
    data: ConsumableUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = ConsumableRouterService(db)
    consumable = await service.update_consumable(consumable_id, data)
    if not consumable:
        raise HTTPException(status_code=404, detail="耗材不存在")
    return consumable


@router.delete("/{consumable_id}")
async def delete_consumable(
    consumable_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = ConsumableRouterService(db)
    success = await service.delete_consumable(consumable_id)
    if not success:
        raise HTTPException(status_code=404, detail="耗材不存在")
    return {"code": 200, "message": "删除成功"}


@router.post("/replenishment")
async def create_replenishment_request(
    data: ReplenishmentRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    service = ConsumableRouterService(db)
    request = await service.create_replenishment_request(data)
    return {"code": 200, "message": "补货申请已提交", "data": request}


@router.get("/replenishment/list")
async def list_replenishment_requests(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    consumable_id: Optional[str] = None,
    requested_by: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = ConsumableRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_replenishment_requests(
        skip=skip,
        limit=size,
        status=status,
        consumable_id=consumable_id,
        requested_by=requested_by,
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


@router.put("/replenishment/{request_id}")
async def update_replenishment_request(
    request_id: str,
    data: ReplenishmentRequestUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = ConsumableRouterService(db)
    request = await service.update_replenishment_request(request_id, data)
    if not request:
        raise HTTPException(status_code=404, detail="补货申请不存在")
    return {"code": 200, "message": "更新成功", "data": request}


@router.post("/outbound-quota")
async def lock_outbound_quota(
    data: OutboundQuotaCreate,
    db: AsyncSession = Depends(get_db),
):
    service = ConsumableRouterService(db)
    quota = await service.lock_outbound_quota(data)
    return {"code": 200, "message": "出库配额已锁定", "data": quota}


@router.get("/outbound-quota/list")
async def list_outbound_quotas(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    consumable_id: Optional[str] = None,
    status: Optional[str] = None,
    allocation_id: Optional[str] = None,
    surgery_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = ConsumableRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_outbound_quotas(
        skip=skip,
        limit=size,
        consumable_id=consumable_id,
        status=status,
        allocation_id=allocation_id,
        surgery_id=surgery_id,
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
