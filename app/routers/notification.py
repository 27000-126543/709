from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple
from datetime import datetime
import json

from app.database import get_db
from app.services import NotificationService, WebSocketManager
from app.models import UserNotification
from app.schemas import (
    NotificationCreate,
    NotificationResponse as CenterNotificationResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


ws_manager = WebSocketManager() if "WebSocketManager" in globals() else None


class NotificationRouterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = NotificationService(db) if NotificationService else None

    async def create_notification(self, data: NotificationCreate) -> UserNotification:
        notification = UserNotification(
            recipient_type=data.recipient_type.value if hasattr(data.recipient_type, "value") else str(data.recipient_type),
            recipient_id=data.recipient_id,
            title=data.title,
            content=data.content,
            notification_type=data.notification_type.value if hasattr(data.notification_type, "value") else str(data.notification_type),
            reference_id=data.reference_id,
            reference_type=data.reference_type,
            priority=data.priority or "normal",
            is_read=False,
            sent_at=data.sent_at or datetime.utcnow(),
        )
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)

        if ws_manager:
            try:
                await ws_manager.broadcast(
                    str(notification.recipient_type),
                    str(notification.recipient_id),
                    {
                        "id": str(notification.id),
                        "title": notification.title,
                        "content": notification.content,
                        "type": str(notification.notification_type),
                        "created_at": notification.created_at.isoformat() if hasattr(notification, "created_at") else datetime.utcnow().isoformat(),
                    },
                )
            except Exception:
                pass

        return notification

    async def get_notification(self, notification_id: str) -> Optional[UserNotification]:
        result = await self.db.execute(
            select(UserNotification).where(UserNotification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def list_notifications(
        self,
        skip: int = 0,
        limit: int = 100,
        recipient_type: Optional[str] = None,
        recipient_id: Optional[str] = None,
        is_read: Optional[bool] = None,
        notification_type: Optional[str] = None,
    ) -> Tuple[List[UserNotification], int]:
        query = select(UserNotification)
        if recipient_type:
            query = query.where(UserNotification.recipient_type == recipient_type)
        if recipient_id:
            query = query.where(UserNotification.recipient_id == recipient_id)
        if is_read is not None:
            query = query.where(UserNotification.is_read == is_read)
        if notification_type:
            query = query.where(UserNotification.notification_type == notification_type)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(UserNotification.sent_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def mark_as_read(self, notification_id: str) -> Optional[UserNotification]:
        notification = await self.get_notification(notification_id)
        if not notification:
            return None
        notification.is_read = True
        await self.db.flush()
        await self.db.refresh(notification)
        return notification

    async def mark_all_as_read(
        self,
        recipient_type: Optional[str] = None,
        recipient_id: Optional[str] = None,
    ) -> int:
        query = select(UserNotification).where(UserNotification.is_read == False)
        if recipient_type:
            query = query.where(UserNotification.recipient_type == recipient_type)
        if recipient_id:
            query = query.where(UserNotification.recipient_id == recipient_id)

        result = await self.db.execute(query)
        items = list(result.scalars().all())
        for item in items:
            item.is_read = True
        await self.db.flush()
        return len(items)

    async def get_unread_count(
        self,
        recipient_type: Optional[str] = None,
        recipient_id: Optional[str] = None,
    ) -> int:
        query = select(UserNotification).where(UserNotification.is_read == False)
        if recipient_type:
            query = query.where(UserNotification.recipient_type == recipient_type)
        if recipient_id:
            query = query.where(UserNotification.recipient_id == recipient_id)

        count_query = select(func.count()).select_from(query.subquery())
        return (await self.db.execute(count_query)).scalar() or 0

    async def delete_notification(self, notification_id: str) -> bool:
        notification = await self.get_notification(notification_id)
        if not notification:
            return False
        await self.db.delete(notification)
        await self.db.flush()
        return True


@router.post("")
async def create_notification(
    data: NotificationCreate,
    db: AsyncSession = Depends(get_db),
):
    service = NotificationRouterService(db)
    notification = await service.create_notification(data)
    return {"code": 200, "message": "通知已创建", "data": notification}


@router.get("/{notification_id}")
async def get_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = NotificationRouterService(db)
    notification = await service.get_notification(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"code": 200, "message": "success", "data": notification}


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    recipient_type: Optional[str] = None,
    recipient_id: Optional[str] = None,
    is_read: Optional[bool] = None,
    notification_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = NotificationRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_notifications(
        skip=skip,
        limit=size,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        is_read=is_read,
        notification_type=notification_type,
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


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = NotificationRouterService(db)
    notification = await service.mark_as_read(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"code": 200, "message": "已标记为已读", "data": notification}


@router.post("/read/all")
async def mark_all_as_read(
    recipient_type: Optional[str] = None,
    recipient_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if not recipient_id:
        raise HTTPException(status_code=400, detail="必须指定 recipient_id")
    service = NotificationRouterService(db)
    count = await service.mark_all_as_read(recipient_type, recipient_id)
    return {"code": 200, "message": f"已标记 {count} 条通知为已读"}


@router.get("/unread/count")
async def get_unread_count(
    recipient_type: Optional[str] = None,
    recipient_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if not recipient_id:
        raise HTTPException(status_code=400, detail="必须指定 recipient_id")
    service = NotificationRouterService(db)
    count = await service.get_unread_count(recipient_type, recipient_id)
    return {"code": 200, "message": "success", "data": {"unread_count": count}}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = NotificationRouterService(db)
    success = await service.delete_notification(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"code": 200, "message": "删除成功"}


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str = Query(..., description="用户ID"),
):
    await websocket.accept()

    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": f"WebSocket 连接成功，用户ID: {user_id}",
            "timestamp": datetime.utcnow().isoformat(),
        }))

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    }))
                elif msg_type == "subscribe":
                    topics = msg.get("topics", [])
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "topics": topics,
                        "timestamp": datetime.utcnow().isoformat(),
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "message_received",
                        "data": msg,
                        "timestamp": datetime.utcnow().isoformat(),
                    }))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "无效的 JSON 格式",
                    "timestamp": datetime.utcnow().isoformat(),
                }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }))
        except Exception:
            pass
