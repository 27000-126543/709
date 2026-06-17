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
        consumable.outbound_quota_locked = consumable.outbound_quota_locked or 0
        consumable.replenishment_status = consumable.replenishment_status or "none"
        if not consumable.status:
            consumable.status = "normal"
        self.db.add(consumable)
        await self.db.flush()
        await self.db.refresh(consumable)

        try:
            available = (consumable.stock_quantity or 0) - (consumable.outbound_quota_locked or 0)
            safety_level = consumable.safety_stock_level or 0

            if available < safety_level and safety_level > 0:
                if available <= safety_level * 0.3:
                    consumable.status = "critical"
                else:
                    consumable.status = "low"

                existing = await self.db.execute(
                    select(ReplenishmentRequest).where(
                        ReplenishmentRequest.consumable_id == consumable.id,
                        ReplenishmentRequest.status.in_(["submitted", "under_review", "approved", "ordered", "shipped", "partially_received"]),
                    )
                )
                if not existing.scalar_one_or_none():
                    replenish_qty = int(max(safety_level * 3 - available, safety_level))
                    urgency = "routine"
                    if available <= safety_level * 0.3:
                        urgency = "emergency"
                    elif available <= safety_level * 0.6:
                        urgency = "urgent"

                    request = ReplenishmentRequest(
                        consumable_id=consumable.id,
                        request_code=f"AUTO-{datetime.utcnow().strftime('%Y%m%d')}-{__import__('uuid').uuid4().hex[:8].upper()}",
                        requested_quantity=replenish_qty,
                        current_stock=consumable.stock_quantity,
                        safety_stock=consumable.safety_stock_level,
                        urgency_level=urgency,
                        supplier=consumable.supplier,
                        estimated_cost=float(replenish_qty) * float(consumable.unit_price or 0),
                        status="submitted",
                        requested_by="auto_system",
                        requested_by_id="system_auto",
                        notes=f"安全库存自动补货: 现有{consumable.stock_quantity}{consumable.unit or ''}, 安全水位{safety_level}{consumable.unit or ''}, 可用{available}{consumable.unit or ''}",
                    )
                    self.db.add(request)
                    consumable.replenishment_request_id = request.id
                    consumable.replenishment_status = "replenishing"
                    await self.db.flush()
                    await self.db.refresh(consumable)
        except Exception:
            pass

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

        received_qty = data.received_quantity or data.actual_quantity

        if data.status == "received" and received_qty:
            if request.status not in ("ordered", "shipped", "approved", "partially_received"):
                raise HTTPException(
                    status_code=400,
                    detail=f"当前申请状态为 '{request.status}'，无法确认到货",
                )

            consumable = await self.get_consumable(request.consumable_id)
            if not consumable:
                raise HTTPException(status_code=404, detail="耗材不存在")

            request.status = "received"
            request.received_quantity = (request.received_quantity or 0) + received_qty
            request.received_date = data.received_date or data.actual_arrival_date or datetime.utcnow()
            request.received_by = data.received_by or request.received_by
            if data.arrival_notes:
                request.notes = (request.notes or "") + f"\n到货备注: {data.arrival_notes}"
            if data.batch_number:
                request.notes = (request.notes or "") + f"\n批次号: {data.batch_number}"

            consumable.stock_quantity = (consumable.stock_quantity or 0) + received_qty

            available = consumable.stock_quantity - (consumable.outbound_quota_locked or 0)
            safety_level = consumable.safety_stock_level or 0

            if available >= safety_level:
                consumable.status = "normal"
                consumable.replenishment_status = "completed"
                consumable.replenishment_request_id = None
            else:
                consumable.status = "low"
                consumable.replenishment_status = "partially"

            transaction = ConsumableTransaction(
                consumable_id=request.consumable_id,
                transaction_type="replenishment",
                quantity=received_qty,
                reference_id=str(request.id),
                notes=f"补货入库, 申请单: {request.request_code or request.id}, 批次: {data.batch_number or '-'}",
            )
            self.db.add(transaction)
        else:
            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if key in ("received_quantity", "actual_quantity", "received_date", "actual_arrival_date",
                           "received_by", "batch_number", "arrival_notes"):
                    continue
                setattr(request, key, value)

            if data.status == "approved" and request.status in ("submitted", "under_review"):
                request.approved_by = data.approver_name or request.approved_by
                request.approved_at = datetime.utcnow()
                if data.approval_notes:
                    request.notes = (request.notes or "") + f"\n审批备注: {data.approval_notes}"

                consumable = await self.get_consumable(request.consumable_id)
                if consumable:
                    consumable.replenishment_status = "approved"

            if data.status == "rejected" and request.status in ("submitted", "under_review"):
                request.rejected_at = datetime.utcnow()
                if data.approval_notes:
                    request.rejection_reason = data.approval_notes

                consumable = await self.get_consumable(request.consumable_id)
                if consumable:
                    consumable.replenishment_status = "none"
                    consumable.replenishment_request_id = None
                    available = (consumable.stock_quantity or 0) - (consumable.outbound_quota_locked or 0)
                    safety_level = consumable.safety_stock_level or 0
                    if available < safety_level * 0.3:
                        consumable.status = "critical"
                    elif available < safety_level:
                        consumable.status = "low"
                    else:
                        consumable.status = "normal"

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
