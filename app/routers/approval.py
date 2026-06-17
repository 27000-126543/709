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

    async def _auto_escalate_if_timeout(self, approval: Approval) -> Optional[dict]:
        now = datetime.utcnow()
        if approval.status == "pending" and approval.timeout_at and approval.timeout_at < now:
            approval.status = "auto_escalated"
            approval.escalated = True
            approval.escalated_at = now
            approval.escalated_reason = f"审批超时(截止时间: {approval.timeout_at.isoformat()})，自动转交上一级"
            approval.decided_at = now
            approval.comment = (approval.comment or "") + " [系统自动转交: 审批超时]"

            escalation_log = ApprovalEscalationLog(
                approval_id=approval.id,
                escalation_type="timeout",
                from_level=approval.approval_level,
                to_level="national" if approval.approval_level == "provincial" else approval.approval_level,
                is_auto=True,
                reason=f"审批超时自动转交，原截止时间: {approval.timeout_at.isoformat()}",
                previous_deadline=approval.timeout_at,
                new_deadline=now + timedelta(hours=2),
                escalated_at=now,
            )
            self.db.add(escalation_log)

            next_approval = None
            if approval.approval_level == "provincial":
                next_timeout = now + timedelta(hours=2)
                next_approval = Approval(
                    allocation_id=approval.allocation_id,
                    approval_level="national",
                    status="pending",
                    timeout_at=next_timeout,
                    deadline_at=next_timeout,
                    timeout_hours=2,
                    sequence=approval.sequence + 1 if approval.sequence else 2,
                    comment="由省级审批超时自动转交",
                    escalated_to_level="national",
                )
                self.db.add(next_approval)

                allocation_result = await self.db.execute(
                    select(Allocation).where(Allocation.id == approval.allocation_id)
                )
                allocation = allocation_result.scalar_one_or_none()
                if allocation:
                    allocation.current_approval_level = "national"

            await self.db.flush()
            await self.db.refresh(approval)
            if next_approval:
                await self.db.refresh(next_approval)

            return {
                "timeout": True,
                "auto_escalated": True,
                "original_approval_id": approval.id,
                "original_level": approval.approval_level,
                "next_approval_id": next_approval.id if next_approval else None,
                "next_level": "national" if next_approval else None,
                "next_timeout": next_approval.timeout_at.isoformat() if next_approval else None,
                "message": "该审批已超时，系统已自动转交上一级审批，请在待办列表中查看新的审批任务",
            }
        return None

    async def process_action(self, data: ApprovalAction) -> Optional[dict]:
        approval = await self.get_approval(data.approval_id)
        if not approval:
            return None

        timeout_result = await self._auto_escalate_if_timeout(approval)
        if timeout_result:
            return {
                "timeout": True,
                "auto_escalated": True,
                "status": "timeout_escalated",
                "message": timeout_result["message"],
                "original_approval_id": timeout_result["original_approval_id"],
                "original_level": timeout_result["original_level"],
                "next_approval_id": timeout_result["next_approval_id"],
                "next_level": timeout_result["next_level"],
                "next_timeout": timeout_result["next_timeout"],
                "allocation_status_unchanged": True,
            }

        if approval.status != "pending":
            raise HTTPException(status_code=400, detail=f"审批状态为 {approval.status}，无法操作")

        if data.action == "approved":
            approval.status = "approved"
            approval.comment = data.comment
            approval.decided_at = datetime.utcnow()
            approval.approver_id = data.approver_id

            allocation_result = await self.db.execute(
                select(Allocation).where(Allocation.id == approval.allocation_id)
            )
            allocation = allocation_result.scalar_one_or_none()
            if allocation:
                if approval.approval_level == "provincial":
                    allocation.status = "provincial_approved"
                    allocation.current_approval_level = "provincial"

                    next_timeout = datetime.utcnow() + timedelta(hours=2)
                    national_approval = Approval(
                        allocation_id=approval.allocation_id,
                        approval_level="national",
                        status="pending",
                        timeout_at=next_timeout,
                        deadline_at=next_timeout,
                        timeout_hours=2,
                        sequence=approval.sequence + 1 if approval.sequence else 2,
                        comment="省级审批通过，自动提交国家级审批",
                    )
                    self.db.add(national_approval)
                elif approval.approval_level == "national":
                    allocation.status = "national_approved"
                    allocation.current_approval_level = "national"

        elif data.action == "rejected":
            approval.status = "rejected"
            approval.comment = data.comment
            approval.decided_at = datetime.utcnow()
            approval.approver_id = data.approver_id

            allocation_result = await self.db.execute(
                select(Allocation).where(Allocation.id == approval.allocation_id)
            )
            allocation = allocation_result.scalar_one_or_none()
            if allocation:
                allocation.status = "rejected"

        elif data.action == "escalated":
            approval.status = "escalated"
            approval.escalated_at = datetime.utcnow()
            approval.comment = data.comment

        else:
            raise HTTPException(status_code=400, detail="无效的操作类型")

        await self.db.flush()
        await self.db.refresh(approval)
        return {
            "timeout": False,
            "auto_escalated": False,
            "status": approval.status,
            "approval": approval,
        }

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
    result = await service.process_action(data)
    if not result:
        raise HTTPException(status_code=404, detail="审批不存在")

    if result.get("timeout"):
        return {
            "code": 409,
            "message": result.get("message", "审批已超时自动转交"),
            "data": {
                "timeout": True,
                "auto_escalated": True,
                "status": "timeout_escalated",
                "original_approval_id": result.get("original_approval_id"),
                "original_level": result.get("original_level"),
                "next_approval_id": result.get("next_approval_id"),
                "next_level": result.get("next_level"),
                "next_timeout": result.get("next_timeout"),
                "allocation_status_unchanged": True,
                "hint": "该分配审批已自动转交国家级，请在待办列表中查找新的国家级审批任务",
            },
        }

    approval = result.get("approval")
    return {
        "code": 200,
        "message": "操作完成",
        "data": {
            "timeout": False,
            "auto_escalated": False,
            "status": approval.status if approval else result.get("status"),
            "approval": ApprovalResponse.model_validate(approval) if approval else None,
        },
    }


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
