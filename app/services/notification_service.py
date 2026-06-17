from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timedelta
import json
import uuid
import asyncio
from collections import defaultdict

from app.models import Notification
from app.schemas.notification import (
    RecipientType,
    NotificationType,
    ReferenceType,
)


class WebSocketManager:
    def __init__(self):
        self._connections: Dict[str, List[Any]] = defaultdict(list)
        self._user_channels: Dict[str, Dict[str, Any]] = {}

    async def connect(self, recipient_type: str, recipient_id: str, websocket: Any) -> None:
        channel_key = f"{recipient_type}:{recipient_id}"
        if websocket not in self._connections[channel_key]:
            self._connections[channel_key].append(websocket)
        self._user_channels[channel_key] = {
            "recipient_type": recipient_type,
            "recipient_id": recipient_id,
            "connected_at": datetime.utcnow().isoformat(),
        }

    async def disconnect(self, recipient_type: str, recipient_id: str, websocket: Any) -> None:
        channel_key = f"{recipient_type}:{recipient_id}"
        if websocket in self._connections[channel_key]:
            self._connections[channel_key].remove(websocket)
        if not self._connections[channel_key]:
            self._user_channels.pop(channel_key, None)

    async def broadcast(
        self,
        recipient_type: str,
        recipient_id: str,
        message: Dict[str, Any],
    ) -> int:
        channel_key = f"{recipient_type}:{recipient_id}"
        connections = self._connections.get(channel_key, [])
        sent_count = 0

        for ws in connections:
            try:
                if hasattr(ws, "send_text"):
                    await ws.send_text(json.dumps(message, ensure_ascii=False))
                    sent_count += 1
            except Exception:
                try:
                    connections.remove(ws)
                except ValueError:
                    pass

        return sent_count

    async def broadcast_to_role(
        self,
        recipient_type: str,
        message: Dict[str, Any],
    ) -> int:
        sent_count = 0
        for channel_key, connections in self._connections.items():
            if channel_key.startswith(f"{recipient_type}:"):
                for ws in connections:
                    try:
                        if hasattr(ws, "send_text"):
                            await ws.send_text(json.dumps(message, ensure_ascii=False))
                            sent_count += 1
                    except Exception:
                        pass
        return sent_count

    def get_connected_users(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = defaultdict(list)
        for channel_key in self._connections:
            if self._connections[channel_key]:
                parts = channel_key.split(":", 1)
                if len(parts) == 2:
                    rtype, rid = parts
                    result[rtype].append(rid)
        return dict(result)

    def get_connection_count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


_global_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    global _global_ws_manager
    if _global_ws_manager is None:
        _global_ws_manager = WebSocketManager()
    return _global_ws_manager


NOTIFICATION_TITLE_TEMPLATES: Dict[str, str] = {
    "donor_registered": "新捐献者登记通知",
    "allocation_request": "器官分配申请通知",
    "transport_alert": "运输状态告警",
    "approval_progress": "审批进度更新",
    "followup_alert": "随访异常预警",
    "inventory_alert": "库存告警通知",
    "report_ready": "运营报表已生成",
}


class NotificationService:
    def __init__(self, db: AsyncSession, ws_manager: Optional[WebSocketManager] = None):
        self.db = db
        self.ws_manager = ws_manager or get_ws_manager()

    async def send_notification(
        self,
        recipient_type: str,
        recipient_id: str,
        title: str,
        content: str,
        notification_type: str,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        extra_data: Optional[Dict] = None,
    ) -> Notification:
        notification = Notification(
            recipient_type=recipient_type,
            recipient_id=str(recipient_id),
            title=title,
            content=content,
            notification_type=notification_type,
            reference_id=str(reference_id) if reference_id else None,
            reference_type=reference_type,
            is_read=False,
            sent_at=datetime.utcnow(),
        )

        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)

        ws_message = {
            "notification_id": notification.id,
            "recipient_type": recipient_type,
            "recipient_id": str(recipient_id),
            "title": title,
            "content": content,
            "notification_type": notification_type,
            "reference_id": reference_id,
            "reference_type": reference_type,
            "extra_data": extra_data or {},
            "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
        }

        await self.ws_manager.broadcast(recipient_type, str(recipient_id), ws_message)

        return notification

    async def notify_donor_registered(
        self,
        donor_id: str,
        donor_name: str,
        province: str,
        coordinator_id: str,
    ) -> List[Notification]:
        notifications: List[Notification] = []

        n1 = await self.send_notification(
            recipient_type=RecipientType.coordinator.value,
            recipient_id=coordinator_id,
            title=NOTIFICATION_TITLE_TEMPLATES["donor_registered"],
            content=(
                f"捐献者 {donor_name} 已在 {province} 完成登记，"
                f"请尽快完成健康核验和家属同意书确认。捐献者ID: {donor_id}"
            ),
            notification_type=NotificationType.donor_registered.value,
            reference_id=donor_id,
            reference_type=ReferenceType.allocation.value,
            extra_data={"donor_name": donor_name, "province": province, "action_needed": "health_verification"},
        )
        notifications.append(n1)

        return notifications

    async def notify_allocation_request(
        self,
        allocation_id: str,
        organ_type: str,
        recipient_name: str,
        matching_score: float,
        transplant_center_id: str,
        provincial_approver_ids: Optional[List[str]] = None,
    ) -> List[Notification]:
        notifications: List[Notification] = []

        n1 = await self.send_notification(
            recipient_type=RecipientType.transplant_center.value,
            recipient_id=transplant_center_id,
            title=NOTIFICATION_TITLE_TEMPLATES["allocation_request"],
            content=(
                f"受者 {recipient_name} 获得 {organ_type} 器官分配机会，"
                f"匹配得分 {round(matching_score, 2)} 分。请确认手术方案。分配ID: {allocation_id}"
            ),
            notification_type=NotificationType.allocation_request.value,
            reference_id=allocation_id,
            reference_type=ReferenceType.allocation.value,
            extra_data={
                "organ_type": organ_type,
                "recipient_name": recipient_name,
                "matching_score": matching_score,
                "action_needed": "confirm_surgery",
            },
        )
        notifications.append(n1)

        approver_ids = provincial_approver_ids or ["provincial_approver_default"]
        for approver_id in approver_ids:
            n2 = await self.send_notification(
                recipient_type="regulator",
                recipient_id=approver_id,
                title="省级审批待处理",
                content=(
                    f"新的 {organ_type} 分配申请等待您的审批："
                    f"受者 {recipient_name}, 匹配分 {round(matching_score, 2)}。"
                    f"请在2小时内完成审批。分配ID: {allocation_id}"
                ),
                notification_type="approval_progress",
                reference_id=allocation_id,
                reference_type="approval",
                extra_data={
                    "approval_level": "provincial",
                    "deadline_hours": 2,
                },
            )
            notifications.append(n2)

        return notifications

    async def notify_transport_alert(
        self,
        transport_id: str,
        alert_type: str,
        alert_detail: str,
        severity: str,
        retrieval_team_id: str,
        transplant_center_id: Optional[str] = None,
    ) -> List[Notification]:
        notifications: List[Notification] = []

        n1 = await self.send_notification(
            recipient_type=RecipientType.transport_team.value,
            recipient_id=retrieval_team_id,
            title=f"[{severity.upper()}] {NOTIFICATION_TITLE_TEMPLATES['transport_alert']}",
            content=(
                f"运输任务告警({alert_type}): {alert_detail}\n"
                f"请立即检查并采取相应措施。运输ID: {transport_id}"
            ),
            notification_type=NotificationType.transport_alert.value,
            reference_id=transport_id,
            reference_type=ReferenceType.transport.value,
            extra_data={
                "alert_type": alert_type,
                "severity": severity,
                "action_needed": "alert_response",
            },
        )
        notifications.append(n1)

        n2 = await self.send_notification(
            recipient_type=RecipientType.coordinator.value,
            recipient_id="dispatch_coordinator",
            title=f"运输调度告警 - {severity}",
            content=(
                f"运输ID {transport_id} 触发 {alert_type} 告警: {alert_detail}\n"
                f"严重级别: {severity}。请协调应急方案。"
            ),
            notification_type=NotificationType.transport_alert.value,
            reference_id=transport_id,
            reference_type=ReferenceType.transport.value,
            extra_data={
                "alert_type": alert_type,
                "severity": severity,
                "action_needed": "emergency_coordination",
            },
        )
        notifications.append(n2)

        if transplant_center_id:
            n3 = await self.send_notification(
                recipient_type=RecipientType.transplant_center.value,
                recipient_id=transplant_center_id,
                title="器官运输状态更新",
                content=(
                    f"运输中器官出现 {alert_type} 告警: {alert_detail}\n"
                    f"请做好手术时间调整准备。运输ID: {transport_id}"
                ),
                notification_type=NotificationType.transport_alert.value,
                reference_id=transport_id,
                reference_type=ReferenceType.transport.value,
                extra_data={
                    "alert_type": alert_type,
                    "severity": severity,
                },
            )
            notifications.append(n3)

        return notifications

    async def notify_approval_progress(
        self,
        allocation_id: str,
        approval_id: str,
        approval_level: str,
        approval_status: str,
        approver_name: str,
        approver_role: str,
        comment: Optional[str] = None,
        next_approver_id: Optional[str] = None,
    ) -> List[Notification]:
        notifications: List[Notification] = []

        status_text = {
            "approved": "已通过",
            "rejected": "已拒绝",
            "escalated": "已转交上级",
            "pending": "待审批",
        }.get(approval_status, approval_status)

        alloc_result = await self.db.execute(
            select("*").select_from(
                __import__("sqlalchemy", fromlist=["text"]).text(
                    f"SELECT recipient_id, transplant_center_id FROM allocations WHERE id = '{allocation_id}'"
                )
            )
        )
        alloc_row = alloc_result.first()
        transplant_center_id = None
        recipient_id = None
        if alloc_row:
            try:
                transplant_center_id = alloc_row.transplant_center_id
                recipient_id = alloc_row.recipient_id
            except Exception:
                pass

        if transplant_center_id:
            n1 = await self.send_notification(
                recipient_type=RecipientType.transplant_center.value,
                recipient_id=transplant_center_id,
                title=NOTIFICATION_TITLE_TEMPLATES["approval_progress"],
                content=(
                    f"分配申请 {allocation_id} 的{approval_level}级审批{status_text}。\n"
                    f"审批人: {approver_name}({approver_role})\n"
                    f"意见: {comment or '无'}"
                ),
                notification_type=NotificationType.approval_progress.value,
                reference_id=allocation_id,
                reference_type=ReferenceType.approval.value,
                extra_data={
                    "approval_level": approval_level,
                    "approval_status": approval_status,
                    "approver_name": approver_name,
                },
            )
            notifications.append(n1)

        if next_approver_id:
            next_level = "国家级" if approval_level == "provincial" else "更高层级"
            n2 = await self.send_notification(
                recipient_type="regulator",
                recipient_id=next_approver_id,
                title=f"{next_level}审批待处理",
                content=(
                    f"分配申请 {allocation_id} 已通过{approval_level}级审批，"
                    f"请您尽快完成{next_level}审批（2小时内）。\n"
                    f"上一级审批人: {approver_name}"
                ),
                notification_type=NotificationType.approval_progress.value,
                reference_id=allocation_id,
                reference_type=ReferenceType.approval.value,
                extra_data={
                    "approval_level": next_level,
                    "deadline_hours": 2,
                    "previous_approver": approver_name,
                },
            )
            notifications.append(n2)

        return notifications

    async def notify_followup_alert(
        self,
        followup_id: str,
        recipient_id: str,
        recipient_name: str,
        abnormal_flags: List[str],
        alert_detail: List[str],
        doctor_id: Optional[str] = None,
    ) -> List[Notification]:
        notifications: List[Notification] = []

        notify_doctor_id = doctor_id or f"doctor_{recipient_id}"

        alert_summary = "; ".join(alert_detail[:3])
        if len(alert_detail) > 3:
            alert_summary += f" 等共{len(alert_detail)}项异常"

        n1 = await self.send_notification(
            recipient_type="coordinator",
            recipient_id=notify_doctor_id,
            title=NOTIFICATION_TITLE_TEMPLATES["followup_alert"],
            content=(
                f"患者 {recipient_name} 随访数据出现异常：\n{alert_summary}\n"
                f"异常项数: {len(abnormal_flags)}。请尽快评估并调整治疗方案。随访ID: {followup_id}"
            ),
            notification_type=NotificationType.followup_alert.value,
            reference_id=followup_id,
            reference_type=ReferenceType.followup.value,
            extra_data={
                "recipient_name": recipient_name,
                "abnormal_count": len(abnormal_flags),
                "abnormal_flags": abnormal_flags[:10],
                "action_needed": "clinical_assessment",
            },
        )
        notifications.append(n1)

        return notifications

    async def notify_inventory_alert(
        self,
        consumable_id: str,
        consumable_name: str,
        current_stock: int,
        safety_level: int,
        severity: str,
        category: str,
    ) -> List[Notification]:
        notifications: List[Notification] = []

        recipients = [
            ("coordinator", "inventory_manager_001"),
            ("regulator", "procurement_dept"),
        ]

        for rtype, rid in recipients:
            n = await self.send_notification(
                recipient_type=rtype,
                recipient_id=rid,
                title=f"[{severity.upper()}] {NOTIFICATION_TITLE_TEMPLATES['inventory_alert']}",
                content=(
                    f"耗材 [{consumable_name}] 库存告警\n"
                    f"当前库存: {current_stock}, 安全水位: {safety_level}\n"
                    f"严重级别: {severity}, 类别: {category}\n"
                    f"请及时处理补货申请。耗材ID: {consumable_id}"
                ),
                notification_type=NotificationType.inventory_alert.value,
                reference_id=consumable_id,
                reference_type=ReferenceType.consumable.value,
                extra_data={
                    "consumable_name": consumable_name,
                    "current_stock": current_stock,
                    "safety_level": safety_level,
                    "severity": severity,
                    "action_needed": "replenishment",
                },
            )
            notifications.append(n)

        return notifications

    async def notify_report_ready(
        self,
        report_date: str,
        report_type: str,
        generated_by: str,
        recipient_ids: Optional[List[str]] = None,
    ) -> List[Notification]:
        notifications: List[Notification] = []

        targets = recipient_ids or [
            ("regulator", "national_admin_001"),
            ("regulator", "provincial_admin_all"),
        ]

        for rtype, rid in targets:
            if rid == "provincial_admin_all":
                for province_idx in range(1, 35):
                    n = await self.send_notification(
                        recipient_type=rtype,
                        recipient_id=f"provincial_admin_{province_idx:03d}",
                        title=NOTIFICATION_TITLE_TEMPLATES["report_ready"],
                        content=(
                            f"{report_date} 的{report_type}运营报表已生成。\n"
                            f"生成时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}\n"
                            f"请登录系统查看详细数据。"
                        ),
                        notification_type=NotificationType.report_ready.value,
                        reference_id=f"report_{report_date}_{report_type}",
                        reference_type="report",
                        extra_data={
                            "report_date": report_date,
                            "report_type": report_type,
                            "generated_by": generated_by,
                        },
                    )
                    notifications.append(n)
            else:
                n = await self.send_notification(
                    recipient_type=rtype,
                    recipient_id=rid,
                    title=NOTIFICATION_TITLE_TEMPLATES["report_ready"],
                    content=(
                        f"{report_date} 的{report_type}运营报表已生成。\n"
                        f"生成时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}\n"
                        f"请登录系统查看详细数据。"
                    ),
                    notification_type=NotificationType.report_ready.value,
                    reference_id=f"report_{report_date}_{report_type}",
                    reference_type="report",
                    extra_data={
                        "report_date": report_date,
                        "report_type": report_type,
                        "generated_by": generated_by,
                    },
                )
                notifications.append(n)

        return notifications

    async def list_notifications(
        self,
        recipient_type: Optional[str] = None,
        recipient_id: Optional[str] = None,
        is_read: Optional[bool] = None,
        notification_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Notification], int]:
        query = select(Notification)

        if recipient_type:
            query = query.where(Notification.recipient_type == recipient_type)
        if recipient_id:
            query = query.where(Notification.recipient_id == str(recipient_id))
        if is_read is not None:
            query = query.where(Notification.is_read == is_read)
        if notification_type:
            query = query.where(Notification.notification_type == notification_type)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def mark_as_read(
        self,
        notification_id: str,
        recipient_id: Optional[str] = None,
    ) -> Optional[Notification]:
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if not notification:
            return None

        if recipient_id and str(notification.recipient_id) != str(recipient_id):
            return None

        notification.is_read = True
        await self.db.flush()
        await self.db.refresh(notification)
        return notification

    async def mark_all_as_read(
        self,
        recipient_type: str,
        recipient_id: str,
    ) -> int:
        result = await self.db.execute(
            select(Notification).where(
                Notification.recipient_type == recipient_type,
                Notification.recipient_id == str(recipient_id),
                Notification.is_read == False,
            )
        )
        notifications = list(result.scalars().all())

        for n in notifications:
            n.is_read = True

        await self.db.flush()
        return len(notifications)

    async def get_unread_count(
        self,
        recipient_type: str,
        recipient_id: str,
    ) -> Dict[str, int]:
        base_query = select(Notification).where(
            Notification.recipient_type == recipient_type,
            Notification.recipient_id == str(recipient_id),
            Notification.is_read == False,
        )

        total_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = total_result.scalar() or 0

        by_type: Dict[str, int] = {}
        for ntype in [
            "donor_registered", "allocation_request", "transport_alert",
            "approval_progress", "followup_alert", "inventory_alert", "report_ready",
        ]:
            type_result = await self.db.execute(
                select(func.count()).select_from(
                    base_query.where(Notification.notification_type == ntype).subquery()
                )
            )
            count = type_result.scalar() or 0
            if count > 0:
                by_type[ntype] = count

        return {
            "total": total,
            "by_type": by_type,
        }

    async def get_ws_connection_status(self) -> Dict:
        return {
            "total_connections": self.ws_manager.get_connection_count(),
            "connected_users": self.ws_manager.get_connected_users(),
        }

    async def push_realtime_update(
        self,
        recipient_type: str,
        recipient_id: str,
        event_type: str,
        payload: Dict,
    ) -> int:
        message = {
            "event": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return await self.ws_manager.broadcast(recipient_type, str(recipient_id), message)

    async def push_role_broadcast(
        self,
        recipient_type: str,
        event_type: str,
        payload: Dict,
    ) -> int:
        message = {
            "event": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
            "broadcast": True,
        }
        return await self.ws_manager.broadcast_to_role(recipient_type, message)

    async def delete_old_notifications(
        self,
        days_old: int = 90,
        only_read: bool = True,
    ) -> int:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        query = select(Notification).where(Notification.created_at < cutoff_date)
        if only_read:
            query = query.where(Notification.is_read == True)

        result = await self.db.execute(query)
        old_notifications = list(result.scalars().all())

        for n in old_notifications:
            await self.db.delete(n)

        await self.db.flush()
        return len(old_notifications)
