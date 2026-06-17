from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from app.database import get_db
from app.services import AllocationService
from app.models import Allocation, RetrievalTask, Organ, Donor, Recipient
from app.schemas import (
    AllocationRequest,
    AllocationUpdate,
    AllocationResponse,
    RetrievalTaskResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/allocation", tags=["allocation"])


class AllocationRouterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = AllocationService(db) if AllocationService else None

    async def create_allocation(self, data: AllocationRequest) -> Allocation:
        organ_result = await self.db.execute(
            select(Organ).where(Organ.id == data.organ_id)
        )
        organ = organ_result.scalar_one_or_none()
        if not organ:
            raise HTTPException(status_code=404, detail="器官不存在")
        if organ.status not in ("locked", "available"):
            raise HTTPException(status_code=400, detail=f"器官状态为 {organ.status}，无法申请分配")

        recipient_result = await self.db.execute(
            select(Recipient).where(Recipient.id == data.recipient_id)
        )
        if not recipient_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="受赠者不存在")

        existing = await self.db.execute(
            select(Allocation).where(
                Allocation.organ_id == data.organ_id,
                Allocation.status.in_(["pending", "provincial_approved", "national_approved"]),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该器官已有进行中的分配申请")

        allocation = Allocation(**data.model_dump(exclude_none=True))
        allocation.status = "pending"
        allocation.current_approval_level = "pending"
        self.db.add(allocation)

        organ.status = "allocated"

        await self.db.flush()
        await self.db.refresh(allocation)
        return allocation

    async def get_allocation(self, allocation_id: str) -> Optional[Allocation]:
        result = await self.db.execute(
            select(Allocation).where(Allocation.id == allocation_id)
        )
        return result.scalar_one_or_none()

    async def list_allocations(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        organ_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
        transplant_center_id: Optional[str] = None,
        current_approval_level: Optional[str] = None,
    ) -> Tuple[List[Allocation], int]:
        query = select(Allocation)
        if status:
            query = query.where(Allocation.status == status)
        if organ_id:
            query = query.where(Allocation.organ_id == organ_id)
        if recipient_id:
            query = query.where(Allocation.recipient_id == recipient_id)
        if transplant_center_id:
            query = query.where(Allocation.transplant_center_id == transplant_center_id)
        if current_approval_level:
            query = query.where(Allocation.current_approval_level == current_approval_level)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Allocation.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_allocation(
        self, allocation_id: str, data: AllocationUpdate
    ) -> Optional[Allocation]:
        allocation = await self.get_allocation(allocation_id)
        if not allocation:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(allocation, key, value)
        await self.db.flush()
        await self.db.refresh(allocation)
        return allocation

    async def approve_allocation(
        self,
        allocation_id: str,
        level: str,
        approver_id: str,
        comment: Optional[str] = None,
    ) -> Optional[Allocation]:
        allocation = await self.get_allocation(allocation_id)
        if not allocation:
            return None

        if level == "provincial":
            if allocation.status != "pending":
                raise HTTPException(status_code=400, detail="当前状态不允许省级审批")
            allocation.status = "provincial_approved"
            allocation.current_approval_level = "provincial"
        elif level == "national":
            if allocation.status != "provincial_approved":
                raise HTTPException(status_code=400, detail="当前状态不允许国家级审批")
            allocation.status = "national_approved"
            allocation.current_approval_level = "national"
        else:
            raise HTTPException(status_code=400, detail="无效的审批级别")

        await self.db.flush()
        await self.db.refresh(allocation)
        return allocation

    async def reject_allocation(
        self,
        allocation_id: str,
        reason: str,
        approver_id: str,
    ) -> Optional[Allocation]:
        allocation = await self.get_allocation(allocation_id)
        if not allocation:
            return None
        allocation.status = "rejected"
        organ_result = await self.db.execute(
            select(Organ).where(Organ.id == allocation.organ_id)
        )
        organ = organ_result.scalar_one_or_none()
        if organ:
            organ.status = "available"
        await self.db.flush()
        await self.db.refresh(allocation)
        return allocation

    async def list_retrieval_tasks(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        retrieval_team_id: Optional[str] = None,
    ) -> Tuple[List[dict], int]:
        query = select(Allocation).where(
            Allocation.status == "national_approved"
        )
        if status:
            pass

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Allocation.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        allocations = list(result.scalars().all())

        tasks = []
        for alloc in allocations:
            organ_result = await self.db.execute(
                select(Organ, Donor)
                .join(Donor, Organ.donor_id == Donor.id)
                .where(Organ.id == alloc.organ_id)
            )
            organ_row = organ_result.first()
            organ = organ_row[0] if organ_row else None
            donor = organ_row[1] if organ_row else None

            recipient_result = await self.db.execute(
                select(Recipient).where(Recipient.id == alloc.recipient_id)
            )
            recipient = recipient_result.scalar_one_or_none()

            deadline = alloc.created_at + timedelta(hours=6)

            tasks.append({
                "allocation_id": str(alloc.id),
                "organ_id": alloc.organ_id,
                "organ_type": organ.organ_type if organ else alloc.organ_id,
                "donor_id": alloc.donor_id,
                "donor_name": donor.name if donor else "",
                "recipient_id": alloc.recipient_id,
                "recipient_name": recipient.name if recipient else "",
                "origin_hospital": donor.hospital if donor else "",
                "destination_hospital": recipient.hospital if recipient else "",
                "retrieval_team_id": None,
                "retrieval_deadline": deadline,
                "status": "pending",
                "created_at": alloc.created_at,
            })

        return tasks, total


@router.post("", response_model=AllocationResponse)
async def submit_allocation_request(
    data: AllocationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AllocationRouterService(db)
    return await service.create_allocation(data)


@router.get("/{allocation_id}", response_model=AllocationResponse)
async def get_allocation(
    allocation_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AllocationRouterService(db)
    allocation = await service.get_allocation(allocation_id)
    if not allocation:
        raise HTTPException(status_code=404, detail="分配申请不存在")
    return allocation


@router.get("", response_model=PaginatedResponse[AllocationResponse])
async def list_allocations(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    organ_id: Optional[str] = None,
    recipient_id: Optional[str] = None,
    transplant_center_id: Optional[str] = None,
    current_approval_level: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = AllocationRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_allocations(
        skip=skip,
        limit=size,
        status=status,
        organ_id=organ_id,
        recipient_id=recipient_id,
        transplant_center_id=transplant_center_id,
        current_approval_level=current_approval_level,
    )
    total_pages = (total + size - 1) // size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
    )


@router.put("/{allocation_id}", response_model=AllocationResponse)
async def update_allocation(
    allocation_id: str,
    data: AllocationUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = AllocationRouterService(db)
    allocation = await service.update_allocation(allocation_id, data)
    if not allocation:
        raise HTTPException(status_code=404, detail="分配申请不存在")
    return allocation


@router.post("/{allocation_id}/approve")
async def approve_allocation(
    allocation_id: str,
    level: str = Query(..., description="审批级别: provincial/national"),
    approver_id: str = Query(..., description="审批人ID"),
    comment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = AllocationRouterService(db)
    allocation = await service.approve_allocation(allocation_id, level, approver_id, comment)
    if not allocation:
        raise HTTPException(status_code=404, detail="分配申请不存在")
    return {"code": 200, "message": "审批完成", "data": AllocationResponse.model_validate(allocation)}


@router.post("/{allocation_id}/reject")
async def reject_allocation(
    allocation_id: str,
    reason: str,
    approver_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = AllocationRouterService(db)
    allocation = await service.reject_allocation(allocation_id, reason, approver_id)
    if not allocation:
        raise HTTPException(status_code=404, detail="分配申请不存在")
    return {"code": 200, "message": "申请已拒绝", "data": AllocationResponse.model_validate(allocation)}


@router.get("/tasks/list")
async def list_retrieval_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    retrieval_team_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = AllocationRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_retrieval_tasks(
        skip=skip,
        limit=size,
        status=status,
        retrieval_team_id=retrieval_team_id,
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
