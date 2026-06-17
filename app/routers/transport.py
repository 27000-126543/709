from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple
from datetime import datetime

from app.database import get_db
from app.services import TransportService
from app.models import Transport, TransportLog, TransportAlert
from app.schemas import (
    TransportCreate,
    TransportUpdate,
    TransportResponse,
    TransportLogCreate,
    TransportAlertResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/transport", tags=["transport"])


class TransportRouterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = TransportService(db) if TransportService else None

    async def create_transport(self, data: TransportCreate) -> Transport:
        transport = Transport(**data.model_dump(exclude_none=True))
        transport.status = "pending"
        transport.alert_triggered = False
        transport.emergency_plan_activated = False
        transport.route_deviation_km = 0.0
        self.db.add(transport)
        await self.db.flush()
        await self.db.refresh(transport)
        return transport

    async def get_transport(self, transport_id: str) -> Optional[Transport]:
        result = await self.db.execute(
            select(Transport).where(Transport.id == transport_id)
        )
        return result.scalar_one_or_none()

    async def list_transports(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        allocation_id: Optional[str] = None,
        retrieval_team_id: Optional[str] = None,
    ) -> Tuple[List[Transport], int]:
        query = select(Transport)
        if status:
            query = query.where(Transport.status == status)
        if allocation_id:
            query = query.where(Transport.allocation_id == allocation_id)
        if retrieval_team_id:
            query = query.where(Transport.retrieval_team_id == retrieval_team_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Transport.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_transport(
        self, transport_id: str, data: TransportUpdate
    ) -> Optional[Transport]:
        transport = await self.get_transport(transport_id)
        if not transport:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(transport, key, value)

        should_alert = False
        alert_type = None
        alert_detail = ""

        if data.current_temperature is not None:
            if data.current_temperature < 0 or data.current_temperature > 10:
                should_alert = True
                alert_type = "temperature"
                alert_detail = f"温度异常: {data.current_temperature}°C"

        if data.route_deviation_km is not None and data.route_deviation_km > 50:
            should_alert = True
            alert_type = "route_deviation"
            alert_detail = f"路线偏离: {data.route_deviation_km}km"

        if data.status == "emergency":
            should_alert = True
            alert_type = "other"
            alert_detail = "紧急状态已激活"

        if should_alert:
            transport.alert_triggered = True
            transport.alert_type = alert_type
            transport.alert_detail = alert_detail
            alert = TransportAlert(
                transport_id=transport_id,
                alert_type=alert_type or "other",
                alert_detail=alert_detail,
                alert_time=datetime.utcnow(),
                current_temperature=data.current_temperature,
                route_deviation_km=data.route_deviation_km,
                resolved=False,
            )
            self.db.add(alert)

        await self.db.flush()
        await self.db.refresh(transport)
        return transport

    async def delete_transport(self, transport_id: str) -> bool:
        transport = await self.get_transport(transport_id)
        if not transport:
            return False
        await self.db.delete(transport)
        await self.db.flush()
        return True

    async def submit_log(self, data: TransportLogCreate) -> TransportLog:
        transport = await self.get_transport(data.transport_id)
        if not transport:
            raise HTTPException(status_code=404, detail="运输任务不存在")

        log = TransportLog(**data.model_dump(exclude_none=True))
        self.db.add(log)

        if data.status:
            transport.status = data.status
        if data.current_temperature is not None:
            transport.current_temperature = data.current_temperature
        if data.current_latitude is not None:
            transport.current_latitude = data.current_latitude
        if data.current_longitude is not None:
            transport.current_longitude = data.current_longitude

        await self.db.flush()
        await self.db.refresh(log)
        return log

    async def get_transport_logs(
        self, transport_id: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[TransportLog], int]:
        query = select(TransportLog).where(TransportLog.transport_id == transport_id)
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.order_by(TransportLog.log_time.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def list_alerts(
        self,
        skip: int = 0,
        limit: int = 100,
        alert_type: Optional[str] = None,
        resolved: Optional[bool] = None,
        transport_id: Optional[str] = None,
    ) -> Tuple[List[TransportAlert], int]:
        query = select(TransportAlert)
        if alert_type:
            query = query.where(TransportAlert.alert_type == alert_type)
        if resolved is not None:
            query = query.where(TransportAlert.resolved == resolved)
        if transport_id:
            query = query.where(TransportAlert.transport_id == transport_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(TransportAlert.alert_time.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def resolve_alert(self, alert_id: str) -> Optional[TransportAlert]:
        result = await self.db.execute(
            select(TransportAlert).where(TransportAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(alert)
        return alert


@router.post("", response_model=TransportResponse)
async def create_transport(
    data: TransportCreate,
    db: AsyncSession = Depends(get_db),
):
    service = TransportRouterService(db)
    return await service.create_transport(data)


@router.get("/{transport_id}", response_model=TransportResponse)
async def get_transport(
    transport_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = TransportRouterService(db)
    transport = await service.get_transport(transport_id)
    if not transport:
        raise HTTPException(status_code=404, detail="运输任务不存在")
    return transport


@router.get("", response_model=PaginatedResponse[TransportResponse])
async def list_transports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    allocation_id: Optional[str] = None,
    retrieval_team_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = TransportRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_transports(
        skip=skip,
        limit=size,
        status=status,
        allocation_id=allocation_id,
        retrieval_team_id=retrieval_team_id,
    )
    total_pages = (total + size - 1) // size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
    )


@router.put("/{transport_id}", response_model=TransportResponse)
async def update_transport(
    transport_id: str,
    data: TransportUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = TransportRouterService(db)
    transport = await service.update_transport(transport_id, data)
    if not transport:
        raise HTTPException(status_code=404, detail="运输任务不存在")
    return transport


@router.delete("/{transport_id}")
async def delete_transport(
    transport_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = TransportRouterService(db)
    success = await service.delete_transport(transport_id)
    if not success:
        raise HTTPException(status_code=404, detail="运输任务不存在")
    return {"code": 200, "message": "删除成功"}


@router.post("/logs")
async def submit_transport_log(
    data: TransportLogCreate,
    db: AsyncSession = Depends(get_db),
):
    service = TransportRouterService(db)
    log = await service.submit_log(data)
    return {"code": 200, "message": "日志提交成功", "data": log}


@router.get("/{transport_id}/logs")
async def get_transport_logs(
    transport_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = TransportRouterService(db)
    skip = (page - 1) * size
    items, total = await service.get_transport_logs(transport_id, skip, size)
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


@router.get("/alerts/list")
async def list_transport_alerts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    alert_type: Optional[str] = None,
    resolved: Optional[bool] = None,
    transport_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = TransportRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_alerts(
        skip=skip,
        limit=size,
        alert_type=alert_type,
        resolved=resolved,
        transport_id=transport_id,
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


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = TransportRouterService(db)
    alert = await service.resolve_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    return {"code": 200, "message": "告警已处理", "data": alert}
