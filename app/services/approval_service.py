from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta
import json

from app.models import Approval, Allocation
from app.schemas.approval import ApprovalCreate, ApprovalAction
from app.schemas.common import ApprovalStatus, ApprovalActionType
from app.config import get_settings

settings = get_settings()


class ApprovalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_approval(self, approval_in: ApprovalCreate) -> Optional[Approval]:
        alloc_result = await self.db.execute(
            select(Allocation).where(Allocation.id == str(approval_in.allocation_id))
        )
        allocation = alloc_result.scalar_one_or_none()
        if not allocation:
            return None

        timeout_at = datetime.utcnow() + timedelta(hours=approval_in.timeout_hours)

        approval = Approval(
            allocation_id=str(approval_in.allocation_id),
            approval_level=approval_in.approval_level.value,
            approver_id=str(approval_in.approver_id),
            approver_name=approval_in.approver_name,
            approver_role=approval_in.approver_role,
            status="pending",
            timeout_at=timeout_at,
            deadline_at=timeout_at,
        )

        self.db.add(approval)
        await self.db.flush()
        await self.db.refresh(approval)

        if allocation.current_approval_level == "pending":
            allocation.current_approval_level = approval_in.approval_level.value

        await self.db.flush()
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
        approver_id: Optional[str] = None,
        allocation_id: Optional[str] = None,
    ) -> Tuple[List[Approval], int]:
        query = select(Approval)

        if status:
            query = query.where(Approval.status == status)
        if approval_level:
            query = query.where(Approval.approval_level == approval_level)
        if approver_id:
            query = query.where(Approval.approver_id == approver_id)
        if allocation_id:
            query = query.where(Approval.allocation_id == allocation_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Approval.timeout_at.asc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def process_approval_action(
        self,
        action_in: ApprovalAction,
    ) -> Optional[Dict]:
        approval = await self.get_approval(str(action_in.approval_id))
        if not approval:
            return None

        if approval.status != "pending":
            return {
                "success": False,
                "error": f"审批状态为'{approval.status}'，无法执行操作",
                "approval": approval,
            }

        now = datetime.utcnow()
        is_timed_out = now > approval.timeout_at

        approval.comment = action_in.comment

        if action_in.action == ApprovalActionType.approved:
            result = await self._handle_approved(approval)
        elif action_in.action == ApprovalActionType.rejected:
            result = await self._handle_rejected(approval)
        else:
            result = {"success": False, "error": "未知操作类型", "approval": approval}

        if is_timed_out and approval.status == "pending":
            await self._handle_timeout(approval)

        return result

    async def _handle_approved(self, approval: Approval) -> Dict:
        approval.status = "approved"

        allocation_result = await self.db.execute(
            select(Allocation).where(Allocation.id == approval.allocation_id)
        )
        allocation = allocation_result.scalar_one_or_none()

        if not allocation:
            await self.db.flush()
            await self.db.refresh(approval)
            return {"success": False, "error": "Allocation not found", "approval": approval}

        next_level_info = None
        if approval.approval_level == "provincial":
            next_timeout = datetime.utcnow() + timedelta(hours=settings.APPROVAL_TIMEOUT_HOURS)
            national_approval = Approval(
                allocation_id=approval.allocation_id,
                approval_level="national",
                approver_id="national_regulator_auto",
                approver_name="国家级监管部门-待分配",
                approver_role="国家级审批员",
                status="pending",
                timeout_at=next_timeout,
                deadline_at=next_timeout,
            )
            self.db.add(national_approval)

            allocation.current_approval_level = "national"
            allocation.status = "provincial_approved"

            next_level_info = {
                "next_level": "national",
                "timeout_at": next_timeout.isoformat(),
                "new_approval_id": national_approval.id,
            }
        elif approval.approval_level == "national":
            allocation.current_approval_level = "final"
            allocation.status = "national_approved"

        await self.db.flush()
        await self.db.refresh(approval)

        return {
            "success": True,
            "action": "approved",
            "approval": approval,
            "allocation_status": allocation.status if allocation else None,
            "next_level": next_level_info,
        }

    async def _handle_rejected(self, approval: Approval) -> Dict:
        approval.status = "rejected"

        allocation_result = await self.db.execute(
            select(Allocation).where(Allocation.id == approval.allocation_id)
        )
        allocation = allocation_result.scalar_one_or_none()

        if allocation:
            allocation.status = "rejected"

        await self.db.flush()
        await self.db.refresh(approval)

        return {
            "success": True,
            "action": "rejected",
            "approval": approval,
            "allocation_status": allocation.status if allocation else None,
        }

    async def _handle_timeout(self, approval: Approval) -> Optional[Approval]:
        approval.status = "escalated"
        approval.escalated_at = datetime.utcnow()

        allocation_result = await self.db.execute(
            select(Allocation).where(Allocation.id == approval.allocation_id)
        )
        allocation = allocation_result.scalar_one_or_none()

        if approval.approval_level == "provincial":
            next_timeout = datetime.utcnow() + timedelta(hours=settings.APPROVAL_TIMEOUT_HOURS)
            escalated_approval = Approval(
                allocation_id=approval.allocation_id,
                approval_level="national",
                approver_id="national_escalation_auto",
                approver_name="国家级监管部门-超时转交",
                approver_role="国家级审批员",
                status="pending",
                timeout_at=next_timeout,
                deadline_at=next_timeout,
                escalated_to_id="national_supervision",
                comment=f"省级审批超时自动转交, 原审批ID: {approval.id}",
            )
            self.db.add(escalated_approval)
            approval.escalated_to_id = escalated_approval.id

            if allocation:
                allocation.current_approval_level = "national"

        elif approval.approval_level == "national":
            if allocation:
                allocation.status = "rejected"

        await self.db.flush()
        await self.db.refresh(approval)
        return approval

    async def check_and_process_timeouts(self) -> List[Dict]:
        now = datetime.utcnow()

        result = await self.db.execute(
            select(Approval).where(
                Approval.status == "pending",
                Approval.timeout_at < now,
            )
        )
        timed_out_approvals = list(result.scalars().all())

        processed = []
        for approval in timed_out_approvals:
            result_info = await self._handle_timeout(approval)
            processed.append({
                "approval_id": approval.id,
                "allocation_id": approval.allocation_id,
                "approval_level": approval.approval_level,
                "timeout_at": approval.timeout_at.isoformat(),
                "processed_at": now.isoformat(),
                "escalated": approval.status == "escalated",
            })

        return processed

    async def send_reminder(
        self,
        approval_id: str,
        reminder_note: Optional[str] = None,
    ) -> Optional[Dict]:
        approval = await self.get_approval(approval_id)
        if not approval:
            return None

        if approval.status != "pending":
            return {
                "success": False,
                "error": f"审批状态为'{approval.status}'，无需催办",
            }

        now = datetime.utcnow()
        remaining = approval.timeout_at - now
        remaining_hours = remaining.total_seconds() / 3600

        urgency = "normal"
        if remaining_hours < 0.5:
            urgency = "critical"
        elif remaining_hours < 1:
            urgency = "high"
        elif remaining_hours < 2:
            urgency = "medium"

        reminder_info = {
            "approval_id": approval.id,
            "approver_id": approval.approver_id,
            "approver_name": approval.approver_name,
            "approval_level": approval.approval_level,
            "remaining_minutes": round(remaining.total_seconds() / 60, 1),
            "urgency": urgency,
            "note": reminder_note or f"审批即将超时，请尽快处理！剩余{round(remaining_hours, 1)}小时",
            "sent_at": now.isoformat(),
        }

        existing_comment = approval.comment or ""
        reminder_prefix = f"[催办-{now.strftime('%Y-%m-%d %H:%M')}] {reminder_info['note']}"
        approval.comment = reminder_prefix + ("\n" + existing_comment if existing_comment else "")

        await self.db.flush()
        await self.db.refresh(approval)

        return {
            "success": True,
            "reminder": reminder_info,
            "notification_targets": [
                {
                    "recipient_type": "approver",
                    "recipient_id": approval.approver_id,
                    "message": reminder_info["note"],
                },
                {
                    "recipient_type": "regulator",
                    "recipient_id": f"supervision_{approval.approval_level}",
                    "message": f"审批{approval.id}催办通知 - {urgency}级别",
                },
            ],
        }

    async def get_pending_approvals_by_level(
        self,
        approval_level: str,
    ) -> List[Approval]:
        result = await self.db.execute(
            select(Approval).where(
                Approval.approval_level == approval_level,
                Approval.status == "pending",
            ).order_by(Approval.timeout_at.asc())
        )
        return list(result.scalars().all())

    async def list_approvals_by_allocation(
        self,
        allocation_id: str,
    ) -> List[Approval]:
        result = await self.db.execute(
            select(Approval).where(Approval.allocation_id == allocation_id)
            .order_by(Approval.created_at.asc())
        )
        return list(result.scalars().all())

    async def escalate_approval(
        self,
        approval_id: str,
        escalate_reason: str,
    ) -> Optional[Dict]:
        approval = await self.get_approval(approval_id)
        if not approval:
            return None

        if approval.status != "pending":
            return {
                "success": False,
                "error": f"审批状态为'{approval.status}'，无法主动转交",
            }

        approval.status = "escalated"
        approval.escalated_at = datetime.utcnow()

        allocation_result = await self.db.execute(
            select(Allocation).where(Allocation.id == approval.allocation_id)
        )
        allocation = allocation_result.scalar_one_or_none()

        if approval.approval_level == "provincial":
            next_timeout = datetime.utcnow() + timedelta(hours=settings.APPROVAL_TIMEOUT_HOURS)
            escalated_approval = Approval(
                allocation_id=approval.allocation_id,
                approval_level="national",
                approver_id="national_supervision_manual",
                approver_name="国家级监管部门-手动转交",
                approver_role="国家级审批员",
                status="pending",
                timeout_at=next_timeout,
                deadline_at=next_timeout,
                escalated_to_id="national_supervision",
                comment=f"手动转交原因: {escalate_reason}\n原审批ID: {approval.id}",
            )
            self.db.add(escalated_approval)
            approval.escalated_to_id = escalated_approval.id

            if allocation:
                allocation.current_approval_level = "national"

        elif approval.approval_level == "national":
            if allocation:
                allocation.status = "rejected"
                approval.comment = (approval.comment or "") + f"\n[国家级无法处理] {escalate_reason}"

        await self.db.flush()
        await self.db.refresh(approval)

        return {
            "success": True,
            "escalated_from": approval_id,
            "escalated_to": approval.escalated_to_id if approval.approval_level == "provincial" else "rejected",
            "reason": escalate_reason,
        }

    async def get_approval_statistics(self) -> Dict:
        now = datetime.utcnow()
        stats: Dict = {}

        for level in ["provincial", "national"]:
            level_result = await self.db.execute(
                select(
                    func.count(Approval.id).filter(Approval.approval_level == level),
                    func.count(Approval.id).filter(
                        Approval.approval_level == level,
                        Approval.status == "pending",
                    ),
                    func.count(Approval.id).filter(
                        Approval.approval_level == level,
                        Approval.status == "approved",
                    ),
                    func.count(Approval.id).filter(
                        Approval.approval_level == level,
                        Approval.status == "rejected",
                    ),
                    func.count(Approval.id).filter(
                        Approval.approval_level == level,
                        Approval.status == "pending",
                        Approval.timeout_at < now,
                    ),
                )
            )
            row = level_result.first()
            stats[level] = {
                "total": row[0] or 0,
                "pending": row[1] or 0,
                "approved": row[2] or 0,
                "rejected": row[3] or 0,
                "timed_out": row[4] or 0,
            }

        return stats
