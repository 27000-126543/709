from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from app.database import get_db
from app.services import ApprovalService
from app.models import Approval, ApprovalEscalationLog, Allocation
from app.schemas import (
    ApprovalCreate,
    ApprovalAction,
    ApprovalResponse,
    ApprovalEscalation,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/approval", tags=["approval"])


class ApprovalRouterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = ApprovalService(db) if ApprovalService else None

    async def create_approval(self, data: ApprovalCreate) -> Approval:
        allocation_result = await self.db.execute(
            select(Allocation).where(Allocation.id == data.allocation_id)
        )
        if not allocation_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="分配申请不存在")

        existing = await self.db.execute(
            select(Approval).where(
                Approval.allocation_id == data.allocation_id,
                Approval.approval_level == data.approval_level,
                Approval.status == "pending",
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该级别已有待审批记录")

        approval = Approval(**data.model_dump(exclude_none=True))
        approval.status = "pending"
        approval.timeout_at = datetime.utcnow() + timedelta(hours=data.timeout_hours)
        self.db.add(approval)
        await self.db.flush()
        await self.db.refresh(approval)
        return approval

    async def get_approval(self, approval_id: str) -> Optional[Approval]:
        result = await self.db.execute(
            select(Approval).where(Approval.id == approval_id)
        )
        return result.scalar_one_or_none()

    async def list_approvals(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        approval_level: Optional[str] = None,
        allocation_id: Optional[str] = None,
        approver_id: Optional[str] = None,
    ) -> Tuple[List[Approval], int]:
        query = select(Approval)
        if status:
            query = query.where(Approval.status == status)
        if approval_level:
            query = query.where(Approval.approval_level == approval_level)
        if allocation_id:
            query = query.where(Approval.allocation_id == allocation_id)
        if approver_id:
            query = query.where(Approval.approver_id == approver_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Approval.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def process_action(self, data: ApprovalAction) -> Optional[Approval]:
        approval = await self.get_approval(data.approval_id)
        if not approval:
            return None
        if approval.status != "pending":
            raise HTTPException(status_code=400, detail=f"审批状态为 {approval.status}，无法操作")

        if data.action == "approve":
            approval.status = "approved"
            approval.comment = data.comment

            allocation_result = await self.db.execute(
                select(Allocation).where(Allocation.id == approval.allocation_id)
            )
            allocation = allocation_result.scalar_one_or_none()
            if allocation:
                if approval.approval_level == "provincial":
                    allocation.status = "provincial_approved"
                    allocation.current_approval_level = "provincial"
                elif approval.approval_level == "national":
                    allocation.status = "national_approved"
                    allocation.current_approval_level = "national"

        elif data.action == "reject":
            approval.status = "rejected"
            approval.comment = data.comment

            allocation_result = await self.db.execute(
                select(Allocation).where(Allocation.id == approval.allocation_id)
            )
            allocation = allocation_result.scalar_one_or_none()
            if allocation:
                allocation.status = "rejected"

        elif data.action == "escalate":
            approval.status = "escalated"
            approval.escalated_at = datetime.utcnow()
            approval.comment = data.comment

        else:
            raise HTTPException(status_code=400, detail="无效的操作类型")

        await self.db.flush()
        await self.db.refresh(approval)
        return approval

    async def escalate(self, data: ApprovalEscalation) -> Approval:
        approval = await self.get_approval(data.approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="审批不存在")

        log = ApprovalEscalationLog(
            approval_id=data.approval_id,
            escalated_to_id=data.escalated_to_id,
            escalated_to_name=data.escalated_to_name,
            escalated_to_role=data.escalated_to_role,
            reason=data.reason,
            escalated_at=datetime.utcnow(),
        )
        self.db.add(log)

        approval.status = "escalated"
        approval.escalated_at = datetime.utcnow()
        approval.escalated_to_id = data.escalated_to_id
        if data.additional_timeout_hours:
            approval.timeout_at = approval.timeout_at + timedelta(hours=data.additional_timeout_hours)

        await self.db.flush()
        await self.db.refresh(approval)
        return approval

    async def list_timeout_approvals(self) -> List[Approval]:
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Approval).where(
                Approval.status == "pending",
                Approval.timeout_at < now,
            )
        )
        return list(result.scalars().all())

    async def send_reminder(self, approval_id: str, message: str) -> Optional[Approval]:
        approval = await self.get_approval(approval_id)
        if not approval:
            return None
        return approval


@router.post("", response_model=ApprovalResponse)
async def submit_approval(
    data: ApprovalCreate,
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRouterService(db)
    return await service.create_approval(data)


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRouterService(db)
    approval = await service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="审批不存在")
    return approval


@router.get("", response_model=PaginatedResponse[ApprovalResponse])
async def list_approvals(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    approval_level: Optional[str] = None,
    allocation_id: Optional[str] = None,
    approver_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_approvals(
        skip=skip,
        limit=size,
        status=status,
        approval_level=approval_level,
        allocation_id=allocation_id,
        approver_id=approver_id,
    )
    total_pages = (total + size - 1) // size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
    )


@router.post("/action")
async def process_approval_action(
    data: ApprovalAction,
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRouterService(db)
    approval = await service.process_action(data)
    if not approval:
        raise HTTPException(status_code=404, detail="审批不存在")
    return {"code": 200, "message": "操作完成", "data": ApprovalResponse.model_validate(approval)}


@router.post("/escalate")
async def escalate_approval(
    data: ApprovalEscalation,
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRouterService(db)
    approval = await service.escalate(data)
    return {"code": 200, "message": "已提交升级", "data": ApprovalResponse.model_validate(approval)}


@router.get("/timeout/list")
async def list_timeout_approvals(
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRouterService(db)
    items = await service.list_timeout_approvals()
    return {"code": 200, "message": "success", "data": items}


@router.post("/{approval_id}/remind")
async def send_timeout_reminder(
    approval_id: str,
    message: str = Query(..., description="催办消息"),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRouterService(db)
    approval = await service.send_reminder(approval_id, message)
    if not approval:
        raise HTTPException(status_code=404, detail="审批不存在")
    return {"code": 200, "message": "催办通知已发送", "data": ApprovalResponse.model_validate(approval)}
