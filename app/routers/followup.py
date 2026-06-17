from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple, Any
from datetime import datetime

from app.database import get_db
from app.services import FollowUpService
from app.models import FollowUpRecord, FollowUpAlert, Recipient
from app.schemas import (
    FollowUpCreate,
    FollowUpUpdate,
    FollowUpResponse,
    FollowUpRecordCreate,
    FollowUpAlertResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/followup", tags=["followup"])


class FollowUpRouterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = FollowUpService(db) if FollowUpService else None

    async def create_followup(self, data: FollowUpCreate) -> dict:
        result = await self.service.create_followup(data)
        if not result:
            raise HTTPException(status_code=404, detail="受赠者不存在")
        return result

    async def get_followup(self, followup_id: str) -> Optional[FollowUpRecord]:
        result = await self.db.execute(
            select(FollowUpRecord).where(FollowUpRecord.id == followup_id)
        )
        return result.scalar_one_or_none()

    async def list_followups(
        self,
        skip: int = 0,
        limit: int = 100,
        recipient_id: Optional[str] = None,
        surgery_id: Optional[str] = None,
        followup_type: Optional[str] = None,
        doctor_id: Optional[str] = None,
    ) -> Tuple[List[FollowUpRecord], int]:
        query = select(FollowUpRecord)
        if recipient_id:
            query = query.where(FollowUpRecord.recipient_id == recipient_id)
        if surgery_id:
            query = query.where(FollowUpRecord.surgery_id == surgery_id)
        if followup_type:
            query = query.where(FollowUpRecord.followup_type == followup_type)
        if doctor_id:
            query = query.where(FollowUpRecord.doctor_id == doctor_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(FollowUpRecord.followup_date.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_followup(
        self, followup_id: str, data: FollowUpUpdate
    ) -> Optional[FollowUpRecord]:
        followup = await self.get_followup(followup_id)
        if not followup:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(followup, key, value)
        await self.db.flush()
        await self.db.refresh(followup)
        return followup

    async def delete_followup(self, followup_id: str) -> bool:
        followup = await self.get_followup(followup_id)
        if not followup:
            return False
        await self.db.delete(followup)
        await self.db.flush()
        return True

    async def create_detailed_record(
        self, data: FollowUpRecordCreate
    ) -> dict:
        try:
            import json
            data_dict = {
                "visit_type": data.visit_type,
                "vital_signs": data.vital_signs,
                "lab_results": data.lab_results,
                "imaging_results": data.imaging_results,
                "biopsy_results": data.biopsy_results,
                "medication_adherence": data.medication_adherence,
                "adverse_events": data.adverse_events,
                "doctor_assessment": data.doctor_assessment,
            }
            if data.next_followup_date:
                data_dict["next_followup_date"] = data.next_followup_date.isoformat()

            from app.schemas.followup import FollowUpCreate as FC
            from app.schemas.common import FollowUpType as FUT
            followup_create = FC(
                recipient_id=data.recipient_id,
                surgery_id=data.surgery_id,
                followup_date=data.followup_date,
                followup_type=data.followup_type,
                data=data_dict,
                doctor_id=data.doctor_id,
                notes=data.notes,
            )
            return await self.service.create_followup(followup_create)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"创建随访记录失败: {str(e)}")

    async def list_alerts(
        self,
        skip: int = 0,
        limit: int = 100,
        recipient_id: Optional[str] = None,
        resolved: Optional[bool] = None,
        severity: Optional[str] = None,
    ) -> Tuple[List[FollowUpAlert], int]:
        query = select(FollowUpAlert)
        if recipient_id:
            query = query.where(FollowUpAlert.recipient_id == recipient_id)
        if resolved is not None:
            query = query.where(FollowUpAlert.resolved == resolved)
        if severity:
            query = query.where(FollowUpAlert.severity == severity)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(FollowUpAlert.alert_time.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def resolve_alert(self, alert_id: str, resolved_by: str) -> Optional[FollowUpAlert]:
        result = await self.db.execute(
            select(FollowUpAlert).where(FollowUpAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return None
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = resolved_by
        await self.db.flush()
        await self.db.refresh(alert)
        return alert


@router.post("")
async def create_followup(
    data: FollowUpCreate,
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpRouterService(db)
    result = await service.create_followup(data)
    followup = result["followup"]
    return {
        "code": 200,
        "message": "success",
        "data": {
            "followup": FollowUpResponse.model_validate(followup),
            "abnormal_flags": result["abnormal_flags"],
            "alert_details": result["alert_details"],
            "alert_triggered": result["alert_triggered"],
            "alerts_count": result["alerts_count"],
        },
    }


@router.get("/{followup_id}", response_model=FollowUpResponse)
async def get_followup(
    followup_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpRouterService(db)
    followup = await service.get_followup(followup_id)
    if not followup:
        raise HTTPException(status_code=404, detail="随访记录不存在")
    return followup


@router.get("", response_model=PaginatedResponse[FollowUpResponse])
async def list_followups(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    recipient_id: Optional[str] = None,
    surgery_id: Optional[str] = None,
    followup_type: Optional[str] = None,
    doctor_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_followups(
        skip=skip,
        limit=size,
        recipient_id=recipient_id,
        surgery_id=surgery_id,
        followup_type=followup_type,
        doctor_id=doctor_id,
    )
    total_pages = (total + size - 1) // size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
    )


@router.put("/{followup_id}", response_model=FollowUpResponse)
async def update_followup(
    followup_id: str,
    data: FollowUpUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpRouterService(db)
    followup = await service.update_followup(followup_id, data)
    if not followup:
        raise HTTPException(status_code=404, detail="随访记录不存在")
    return followup


@router.delete("/{followup_id}")
async def delete_followup(
    followup_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpRouterService(db)
    success = await service.delete_followup(followup_id)
    if not success:
        raise HTTPException(status_code=404, detail="随访记录不存在")
    return {"code": 200, "message": "删除成功"}


@router.post("/detailed")
async def create_detailed_followup(
    data: FollowUpRecordCreate,
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpRouterService(db)
    result = await service.create_detailed_record(data)
    if not result:
        raise HTTPException(status_code=404, detail="受赠者不存在")
    followup = result["followup"]
    return {
        "code": 200,
        "message": "随访记录已创建",
        "data": {
            "followup": FollowUpResponse.model_validate(followup),
            "abnormal_flags": result["abnormal_flags"],
            "alert_details": result["alert_details"],
            "alert_triggered": result["alert_triggered"],
            "alerts_count": result["alerts_count"],
        },
    }


@router.get("/alerts/list")
async def list_followup_alerts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    recipient_id: Optional[str] = None,
    resolved: Optional[bool] = None,
    severity: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_alerts(
        skip=skip,
        limit=size,
        recipient_id=recipient_id,
        resolved=resolved,
        severity=severity,
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
async def resolve_followup_alert(
    alert_id: str,
    resolved_by: str = Query(..., description="处理人ID"),
    db: AsyncSession = Depends(get_db),
):
    service = FollowUpRouterService(db)
    alert = await service.resolve_alert(alert_id, resolved_by)
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    return {"code": 200, "message": "预警已处理", "data": alert}
