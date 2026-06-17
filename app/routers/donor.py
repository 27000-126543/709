from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.services import DonorService, MatchEngine
from app.schemas import (
    DonorCreate,
    DonorUpdate,
    DonorResponse,
    DonorHealthCheckCreate,
    DonorConsentVerify,
    DonorRejectRequest,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/donors", tags=["donors"])


@router.post("", response_model=DonorResponse)
async def create_donor(
    donor_in: DonorCreate,
    db: AsyncSession = Depends(get_db),
):
    service = DonorService(db)
    donor = await service.create_donor(donor_in)
    return donor


@router.get("/{donor_id}", response_model=DonorResponse)
async def get_donor(
    donor_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = DonorService(db)
    donor = await service.get_donor(donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="捐赠者不存在")
    return donor


@router.get("", response_model=PaginatedResponse[DonorResponse])
async def list_donors(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    province: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = DonorService(db)
    skip = (page - 1) * size
    items, total = await service.list_donors(
        skip=skip, limit=size, status=status, province=province
    )
    total_pages = (total + size - 1) // size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
    )


@router.put("/{donor_id}", response_model=DonorResponse)
async def update_donor(
    donor_id: str,
    donor_in: DonorUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = DonorService(db)
    donor = await service.update_donor(donor_id, donor_in)
    if not donor:
        raise HTTPException(status_code=404, detail="捐赠者不存在")
    return donor


@router.delete("/{donor_id}")
async def delete_donor(
    donor_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = DonorService(db)
    success = await service.delete_donor(donor_id)
    if not success:
        raise HTTPException(status_code=404, detail="捐赠者不存在")
    return {"code": 200, "message": "删除成功"}


@router.post("/health-check")
async def submit_health_check(
    data: DonorHealthCheckCreate,
    db: AsyncSession = Depends(get_db),
):
    service = DonorService(db)
    donor = await service.get_donor(data.donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="捐赠者不存在")
    donor.health_status = data.health_status
    donor.health_check_detail = data.health_check_detail
    if data.hla_typing is not None:
        donor.hla_typing = data.hla_typing
    if data.pra_level is not None:
        donor.pra_level = data.pra_level
    await db.flush()
    await db.refresh(donor)
    result = await service.review_donor_health(data.donor_id)
    return {"code": 200, "message": "健康检查提交成功", "data": result}


@router.post("/verify-consent")
async def verify_consent(
    data: DonorConsentVerify,
    db: AsyncSession = Depends(get_db),
):
    service = DonorService(db)
    donor = await service.get_donor(data.donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="捐赠者不存在")
    donor.consent_verified = data.consent_verified
    donor.family_consent = data.family_consent
    if data.consent_notes:
        donor.consent_notes = data.consent_notes
    if data.consent_document_url:
        donor.consent_document_url = data.consent_document_url
    await db.flush()
    await db.refresh(donor)
    return {"code": 200, "message": "同意书验证完成", "data": DonorResponse.model_validate(donor)}


@router.post("/reject")
async def reject_donor(
    data: DonorRejectRequest,
    db: AsyncSession = Depends(get_db),
):
    service = DonorService(db)
    donor = await service.reject_donor(data.donor_id, data.rejection_reason)
    if not donor:
        raise HTTPException(status_code=404, detail="捐赠者不存在")
    return {"code": 200, "message": "捐赠者已拒绝", "data": DonorResponse.model_validate(donor)}


@router.get("/{donor_id}/auto-verify")
async def auto_verify_and_match(
    donor_id: str,
    max_results: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = DonorService(db)
    donor = await service.get_donor(donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="捐赠者不存在")

    verify_result = await service.review_donor_health(donor_id)

    if verify_result and verify_result.get("status") != "rejected":
        from app.models import Organ
        from sqlalchemy.future import select
        organ_result = await db.execute(
            select(Organ).where(Organ.donor_id == donor_id, Organ.status == "available")
        )
        organs = list(organ_result.scalars().all())

        match_engine = MatchEngine(db)
        all_matches = []
        for organ in organs:
            matches = await match_engine.find_matches(organ.id, top_n=max_results)
            all_matches.append({
                "organ_id": organ.id,
                "organ_type": organ.organ_type,
                "matches": matches,
            })

        return {
            "code": 200,
            "message": "自动校验完成",
            "data": {
                "verification": verify_result,
                "matches": all_matches,
            },
        }

    return {
        "code": 200,
        "message": "自动校验完成，捐赠者未通过校验",
        "data": {
            "verification": verify_result,
            "matches": [],
        },
    }
