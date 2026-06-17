from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple, Any
from datetime import datetime, date, timedelta

from app.database import get_db
from app.services import SurgeryService
from app.models import (
    Surgery,
    PreOpCheck,
    ImmunosuppressantPlan,
    DrugMonitoring,
    RejectionAlert,
)
from app.schemas import (
    SurgeryCreate,
    SurgeryUpdate,
    SurgeryResponse,
    PreOpCheckCreate,
    PreOpCheckResponse,
    ImmunosuppressantPlanCreate,
    DrugMonitoringCreate,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/surgery", tags=["surgery"])


class SurgeryRouterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = SurgeryService(db) if SurgeryService else None

    async def create_surgery(self, data: SurgeryCreate) -> Surgery:
        surgery = Surgery(**data.model_dump(exclude_none=True))
        surgery.surgery_status = "scheduled"
        surgery.preop_check_status = "pending"
        self.db.add(surgery)
        await self.db.flush()
        await self.db.refresh(surgery)
        return surgery

    async def get_surgery(self, surgery_id: str) -> Optional[Surgery]:
        result = await self.db.execute(
            select(Surgery).where(Surgery.id == surgery_id)
        )
        return result.scalar_one_or_none()

    async def list_surgeries(
        self,
        skip: int = 0,
        limit: int = 100,
        surgery_status: Optional[str] = None,
        allocation_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
        transplant_center_id: Optional[str] = None,
    ) -> Tuple[List[Surgery], int]:
        query = select(Surgery)
        if surgery_status:
            query = query.where(Surgery.surgery_status == surgery_status)
        if allocation_id:
            query = query.where(Surgery.allocation_id == allocation_id)
        if recipient_id:
            query = query.where(Surgery.recipient_id == recipient_id)
        if transplant_center_id:
            query = query.where(Surgery.transplant_center_id == transplant_center_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Surgery.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_surgery(
        self, surgery_id: str, data: SurgeryUpdate
    ) -> Optional[Surgery]:
        surgery = await self.get_surgery(surgery_id)
        if not surgery:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(surgery, key, value)
        await self.db.flush()
        await self.db.refresh(surgery)
        return surgery

    async def delete_surgery(self, surgery_id: str) -> bool:
        surgery = await self.get_surgery(surgery_id)
        if not surgery:
            return False
        await self.db.delete(surgery)
        await self.db.flush()
        return True

    async def upload_preop_check(
        self, data: PreOpCheckCreate
    ) -> PreOpCheck:
        surgery = await self.get_surgery(data.surgery_id)
        if not surgery:
            raise HTTPException(status_code=404, detail="手术记录不存在")

        check_items = data.check_items or {}
        failed_count = 0
        warning_count = 0
        for item_name, item_value in check_items.items():
            if isinstance(item_value, dict):
                status = item_value.get("status", "")
                if status == "failed":
                    failed_count += 1
                elif status == "warning":
                    warning_count += 1

        if failed_count > 0:
            preop_status = "failed"
        elif warning_count > 0:
            preop_status = "recheck_recommended"
        else:
            preop_status = "passed"

        preop = PreOpCheck(
            surgery_id=data.surgery_id,
            preop_data=data.preop_data,
            preop_check_status=preop_status,
            checked_at=datetime.utcnow(),
        )
        self.db.add(preop)

        surgery.preop_check_status = preop_status
        surgery.preop_data = data.preop_data

        await self.db.flush()
        await self.db.refresh(preop)
        return preop

    async def list_preop_checks(
        self, surgery_id: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[PreOpCheck], int]:
        query = select(PreOpCheck).where(PreOpCheck.surgery_id == surgery_id)
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.order_by(PreOpCheck.checked_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def create_immunosuppressant_plan(
        self, data: ImmunosuppressantPlanCreate
    ) -> ImmunosuppressantPlan:
        surgery = await self.get_surgery(data.surgery_id)
        if not surgery:
            raise HTTPException(status_code=404, detail="手术记录不存在")
        plan = ImmunosuppressantPlan(**data.model_dump(exclude_none=True))
        self.db.add(plan)
        await self.db.flush()
        await self.db.refresh(plan)
        return plan

    async def list_immunosuppressant_plans(
        self, surgery_id: str
    ) -> List[ImmunosuppressantPlan]:
        result = await self.db.execute(
            select(ImmunosuppressantPlan).where(
                ImmunosuppressantPlan.surgery_id == surgery_id
            )
        )
        return list(result.scalars().all())

    async def create_drug_monitoring(
        self, data: DrugMonitoringCreate
    ) -> DrugMonitoring:
        surgery = await self.get_surgery(data.surgery_id)
        if not surgery:
            raise HTTPException(status_code=404, detail="手术记录不存在")

        monitoring = DrugMonitoring(**data.model_dump(exclude_none=True))

        is_abnormal = False
        alert_detail = ""
        if data.target_concentration_min is not None and data.blood_concentration < data.target_concentration_min:
            is_abnormal = True
            alert_detail = f"{data.drug_name} 血药浓度低于下限"
        if data.target_concentration_max is not None and data.blood_concentration > data.target_concentration_max:
            is_abnormal = True
            alert_detail = f"{data.drug_name} 血药浓度高于上限"

        if is_abnormal:
            alert = RejectionAlert(
                surgery_id=data.surgery_id,
                alert_type="drug_concentration",
                alert_detail=alert_detail,
                alert_time=datetime.utcnow(),
                severity="warning",
                resolved=False,
            )
            self.db.add(alert)

        self.db.add(monitoring)
        await self.db.flush()
        await self.db.refresh(monitoring)
        return monitoring

    async def list_drug_monitorings(
        self, surgery_id: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[DrugMonitoring], int]:
        query = select(DrugMonitoring).where(DrugMonitoring.surgery_id == surgery_id)
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.order_by(DrugMonitoring.measurement_date.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def list_rejection_alerts(
        self,
        skip: int = 0,
        limit: int = 100,
        surgery_id: Optional[str] = None,
        resolved: Optional[bool] = None,
    ) -> Tuple[List[RejectionAlert], int]:
        query = select(RejectionAlert)
        if surgery_id:
            query = query.where(RejectionAlert.surgery_id == surgery_id)
        if resolved is not None:
            query = query.where(RejectionAlert.resolved == resolved)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(RejectionAlert.alert_time.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total


@router.post("", response_model=SurgeryResponse)
async def create_surgery(
    data: SurgeryCreate,
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    return await service.create_surgery(data)


@router.get("/{surgery_id}", response_model=SurgeryResponse)
async def get_surgery(
    surgery_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    surgery = await service.get_surgery(surgery_id)
    if not surgery:
        raise HTTPException(status_code=404, detail="手术记录不存在")
    return surgery


@router.get("", response_model=PaginatedResponse[SurgeryResponse])
async def list_surgeries(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    surgery_status: Optional[str] = None,
    allocation_id: Optional[str] = None,
    recipient_id: Optional[str] = None,
    transplant_center_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_surgeries(
        skip=skip,
        limit=size,
        surgery_status=surgery_status,
        allocation_id=allocation_id,
        recipient_id=recipient_id,
        transplant_center_id=transplant_center_id,
    )
    total_pages = (total + size - 1) // size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
    )


@router.put("/{surgery_id}", response_model=SurgeryResponse)
async def update_surgery(
    surgery_id: str,
    data: SurgeryUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    surgery = await service.update_surgery(surgery_id, data)
    if not surgery:
        raise HTTPException(status_code=404, detail="手术记录不存在")
    return surgery


@router.delete("/{surgery_id}")
async def delete_surgery(
    surgery_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    success = await service.delete_surgery(surgery_id)
    if not success:
        raise HTTPException(status_code=404, detail="手术记录不存在")
    return {"code": 200, "message": "删除成功"}


@router.post("/preop-check")
async def upload_preop_check(
    data: PreOpCheckCreate,
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    preop = await service.upload_preop_check(data)
    return {"code": 200, "message": "术前检查已上传", "data": preop}


@router.get("/{surgery_id}/preop-checks")
async def list_preop_checks(
    surgery_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_preop_checks(surgery_id, skip, size)
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


@router.post("/immunosuppressant-plan")
async def create_immunosuppressant_plan(
    data: ImmunosuppressantPlanCreate,
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    plan = await service.create_immunosuppressant_plan(data)
    return {"code": 200, "message": "免疫抑制剂计划已创建", "data": plan}


@router.get("/{surgery_id}/immunosuppressant-plans")
async def list_immunosuppressant_plans(
    surgery_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    items = await service.list_immunosuppressant_plans(surgery_id)
    return {"code": 200, "message": "success", "data": items}


@router.post("/drug-monitoring")
async def submit_drug_monitoring(
    data: DrugMonitoringCreate,
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    monitoring = await service.create_drug_monitoring(data)
    return {"code": 200, "message": "血药浓度监测已提交", "data": monitoring}


@router.get("/{surgery_id}/drug-monitorings")
async def list_drug_monitorings(
    surgery_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_drug_monitorings(surgery_id, skip, size)
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


@router.get("/alerts/rejection-list")
async def list_rejection_alerts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    surgery_id: Optional[str] = None,
    resolved: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    service = SurgeryRouterService(db)
    skip = (page - 1) * size
    items, total = await service.list_rejection_alerts(
        skip=skip,
        limit=size,
        surgery_id=surgery_id,
        resolved=resolved,
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
