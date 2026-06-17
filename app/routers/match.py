from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple
from datetime import datetime

from app.database import get_db
from app.services import MatchEngine
from app.models import MatchResult, MatchDetail, Organ, Donor
from app.schemas import (
    MatchRequest,
    MatchResultItem,
    MatchResultResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/match", tags=["match"])


class MatchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = MatchEngine(db)

    async def trigger_matching(self, data: MatchRequest) -> dict:
        organ_result = await self.db.execute(
            select(Organ).where(Organ.id == data.organ_id)
        )
        organ = organ_result.scalar_one_or_none()
        if not organ:
            raise HTTPException(status_code=404, detail="器官不存在")

        if organ.status not in ("available",):
            raise HTTPException(status_code=400, detail=f"器官状态为 {organ.status}，无法进行匹配")

        matches = await self.engine.find_matches(
            organ_id=data.organ_id,
            top_n=data.max_results,
        )

        result_items = []
        for i, m in enumerate(matches):
            result_items.append(
                MatchResultItem(
                    recipient_id=m["recipient_id"],
                    recipient_name=m["recipient_name"],
                    matching_score=m["matching_score"],
                    blood_type_match=m.get("matching_detail", {}).get("blood_type", {}).get("compatible", False),
                    hla_match_count=m.get("matching_detail", {}).get("hla", {}).get("matched_loci", 0),
                    pra_compatible=(m.get("matching_detail", {}).get("pra", {}).get("recipient_pra", 0) < 80),
                    urgency_level=m["urgency_level"],
                    waiting_days=0,
                    rank=i + 1,
                    matching_detail=str(m.get("matching_detail", "")),
                )
            )

        match_record = MatchResult(
            organ_id=data.organ_id,
            donor_id=data.donor_id,
            organ_type=data.organ_type,
            total_candidates=len(matches),
            matched_at=datetime.utcnow(),
        )
        self.db.add(match_record)
        await self.db.flush()
        await self.db.refresh(match_record)

        return {
            "organ_id": data.organ_id,
            "donor_id": data.donor_id,
            "organ_type": data.organ_type,
            "total_candidates": len(matches),
            "matched_at": match_record.matched_at,
            "results": result_items,
            "match_id": str(match_record.id),
        }

    async def list_match_results(
        self,
        skip: int = 0,
        limit: int = 100,
        organ_id: Optional[str] = None,
        donor_id: Optional[str] = None,
        organ_type: Optional[str] = None,
    ) -> Tuple[List[MatchResult], int]:
        query = select(MatchResult)
        if organ_id:
            query = query.where(MatchResult.organ_id == organ_id)
        if donor_id:
            query = query.where(MatchResult.donor_id == donor_id)
        if organ_type:
            query = query.where(MatchResult.organ_type == organ_type)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(MatchResult.matched_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_match_detail(self, match_id: str) -> Optional[MatchResult]:
        result = await self.db.execute(
            select(MatchResult).where(MatchResult.id == match_id)
        )
        return result.scalar_one_or_none()

    async def lock_best_match(
        self,
        match_id: str,
        recipient_id: str,
    ) -> dict:
        match_record = await self.get_match_detail(match_id)
        if not match_record:
            raise HTTPException(status_code=404, detail="匹配记录不存在")

        organ = await self.engine.lock_organ(match_record.organ_id, recipient_id)
        if not organ:
            raise HTTPException(status_code=400, detail="锁定失败：器官不可用或已被锁定")

        detail = MatchDetail(
            match_id=match_id,
            recipient_id=recipient_id,
            is_locked=True,
            locked_at=datetime.utcnow(),
        )
        self.db.add(detail)
        await self.db.flush()

        return {
            "match_id": match_id,
            "organ_id": match_record.organ_id,
            "recipient_id": recipient_id,
            "status": "locked",
            "locked_at": detail.locked_at,
        }

    async def get_matches_for_recipient(self, recipient_id: str) -> list[dict]:
        return await self.engine.get_match_for_recipient(recipient_id)


@router.post("/trigger")
async def trigger_matching(
    data: MatchRequest,
    db: AsyncSession = Depends(get_db),
):
    service = MatchService(db)
    result = await service.trigger_matching(data)
    return {"code": 200, "message": "匹配完成", "data": result}


@router.get("/results")
async def list_match_results(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    organ_id: Optional[str] = None,
    donor_id: Optional[str] = None,
    organ_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    service = MatchService(db)
    skip = (page - 1) * size
    items, total = await service.list_match_results(
        skip=skip,
        limit=size,
        organ_id=organ_id,
        donor_id=donor_id,
        organ_type=organ_type,
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


@router.get("/results/{match_id}")
async def get_match_detail(
    match_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = MatchService(db)
    match_record = await service.get_match_detail(match_id)
    if not match_record:
        raise HTTPException(status_code=404, detail="匹配记录不存在")
    return {"code": 200, "message": "success", "data": match_record}


@router.post("/lock-best")
async def lock_best_match(
    match_id: str = Query(..., description="匹配记录ID"),
    recipient_id: str = Query(..., description="受赠者ID"),
    db: AsyncSession = Depends(get_db),
):
    service = MatchService(db)
    result = await service.lock_best_match(match_id, recipient_id)
    return {"code": 200, "message": "最佳匹配已锁定", "data": result}


@router.get("/recipient/{recipient_id}")
async def get_recipient_matches(
    recipient_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = MatchService(db)
    matches = await service.get_matches_for_recipient(recipient_id)
    return {"code": 200, "message": "success", "data": matches}
