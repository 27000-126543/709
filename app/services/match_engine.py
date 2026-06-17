from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Optional, Tuple
import json

from app.models import Organ, Recipient, Donor
from app.schemas.match import MatchingResult
from app.config import get_settings
from app.services.matching_utils import (
    blood_type_score,
    is_blood_compatible,
    hla_score_normalized,
    hla_match_score,
    pra_score,
    calculate_geography_score_by_province,
    calculate_distance_by_province,
    urgency_score,
)

settings = get_settings()


class MatchEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _calculate_matching_score(
        self,
        donor: Donor,
        organ: Organ,
        recipient: Recipient,
    ) -> Tuple[float, Dict]:
        detail: Dict = {}

        blood_score = blood_type_score(organ.blood_type, recipient.blood_type)
        detail["blood_type"] = {
            "donor": organ.blood_type,
            "recipient": recipient.blood_type,
            "compatible": is_blood_compatible(organ.blood_type, recipient.blood_type),
            "score": round(blood_score, 4),
            "weight": settings.MATCH_BLOOD_TYPE_WEIGHT,
        }

        hla_norm = hla_score_normalized(organ.hla_typing, recipient.hla_typing)
        hla_matched, hla_total = hla_match_score(organ.hla_typing, recipient.hla_typing)
        detail["hla"] = {
            "matched_loci": hla_matched,
            "total_loci": hla_total,
            "score": round(hla_norm, 4),
            "weight": settings.MATCH_HLA_WEIGHT,
        }

        pra_norm = pra_score(recipient.pra_level)
        detail["pra"] = {
            "recipient_pra": recipient.pra_level or 0,
            "score": round(pra_norm, 4),
            "weight": settings.MATCH_PRA_WEIGHT,
        }

        geo_score = calculate_geography_score_by_province(donor.province, recipient.province)
        distance_km = calculate_distance_by_province(donor.province, recipient.province)
        detail["geography"] = {
            "donor_province": donor.province,
            "recipient_province": recipient.province,
            "distance_km": round(distance_km, 2),
            "score": round(geo_score, 4),
            "weight": settings.MATCH_GEOGRAPHY_WEIGHT,
        }

        urg_score = urgency_score(recipient.urgency_level)
        detail["urgency"] = {
            "level": recipient.urgency_level,
            "score": round(urg_score, 4),
            "weight": settings.MATCH_URGENCY_WEIGHT,
        }

        total_score = (
            blood_score * settings.MATCH_BLOOD_TYPE_WEIGHT
            + hla_norm * settings.MATCH_HLA_WEIGHT
            + pra_norm * settings.MATCH_PRA_WEIGHT
            + geo_score * settings.MATCH_GEOGRAPHY_WEIGHT
            + urg_score * settings.MATCH_URGENCY_WEIGHT
        ) * 100

        detail["total_score"] = round(total_score, 2)

        return total_score, detail

    async def find_matches(
        self,
        organ_id: str,
        top_n: Optional[int] = None,
        min_score: float = 0.0,
    ) -> List[Dict]:
        result = await self.db.execute(
            select(Organ, Donor)
            .join(Donor, Organ.donor_id == Donor.id)
            .where(Organ.id == organ_id)
        )
        row = result.first()
        if not row:
            return []
        organ, donor = row

        if organ.status not in ("available",):
            return []

        recipients_result = await self.db.execute(
            select(Recipient).where(
                Recipient.organ_type_needed == organ.organ_type,
                Recipient.status == "waiting",
            )
        )
        recipients = list(recipients_result.scalars().all())

        matches: List[Dict] = []
        for recipient in recipients:
            if not is_blood_compatible(organ.blood_type, recipient.blood_type):
                continue

            score, detail = self._calculate_matching_score(donor, organ, recipient)

            if score < min_score:
                continue

            matches.append(
                {
                    "recipient_id": recipient.id,
                    "recipient_name": recipient.name,
                    "organ_type": organ.organ_type,
                    "matching_score": round(score, 2),
                    "matching_detail": detail,
                    "urgency_level": recipient.urgency_level,
                    "province": recipient.province,
                    "transplant_center_id": recipient.transplant_center_id,
                    "waiting_since": recipient.waiting_since.isoformat() if recipient.waiting_since else None,
                }
            )

        matches.sort(key=lambda x: (-x["matching_score"], x.get("waiting_since") or ""))

        for i, m in enumerate(matches):
            m["rank"] = i + 1

        if top_n is not None:
            matches = matches[:top_n]

        return matches

    async def get_match_for_recipient(
        self,
        recipient_id: str,
    ) -> List[Dict]:
        recipient_result = await self.db.execute(
            select(Recipient).where(Recipient.id == recipient_id)
        )
        recipient = recipient_result.scalar_one_or_none()
        if not recipient:
            return []

        organs_result = await self.db.execute(
            select(Organ, Donor)
            .join(Donor, Organ.donor_id == Donor.id)
            .where(
                Organ.organ_type == recipient.organ_type_needed,
                Organ.status == "available",
            )
        )
        organ_rows = organs_result.all()

        matches: List[Dict] = []
        for organ, donor in organ_rows:
            if not is_blood_compatible(organ.blood_type, recipient.blood_type):
                continue

            score, detail = self._calculate_matching_score(donor, organ, recipient)
            matches.append(
                {
                    "organ_id": organ.id,
                    "donor_id": donor.id,
                    "donor_name": donor.name,
                    "organ_type": organ.organ_type,
                    "matching_score": round(score, 2),
                    "matching_detail": detail,
                    "province": donor.province,
                    "hospital": donor.hospital,
                }
            )

        matches.sort(key=lambda x: -x["matching_score"])

        for i, m in enumerate(matches):
            m["rank"] = i + 1

        return matches

    async def lock_organ(self, organ_id: str, recipient_id: str) -> Optional[Organ]:
        result = await self.db.execute(select(Organ).where(Organ.id == organ_id))
        organ = result.scalar_one_or_none()
        if not organ:
            return None

        if organ.status != "available":
            return None

        organ.status = "locked"
        await self.db.flush()
        await self.db.refresh(organ)
        return organ

    async def unlock_organ(self, organ_id: str) -> Optional[Organ]:
        result = await self.db.execute(select(Organ).where(Organ.id == organ_id))
        organ = result.scalar_one_or_none()
        if not organ:
            return None

        if organ.status != "locked":
            return None

        organ.status = "available"
        await self.db.flush()
        await self.db.refresh(organ)
        return organ

    def build_matching_result(self, match_dict: Dict) -> MatchingResult:
        return MatchingResult(
            recipient_id=int(match_dict["recipient_id"]) if match_dict["recipient_id"].isdigit() else match_dict["recipient_id"],
            matching_score=match_dict["matching_score"],
            matching_detail=match_dict["matching_detail"],
            rank=match_dict["rank"],
        )

    async def find_all_available_organs(self) -> List[Organ]:
        result = await self.db.execute(
            select(Organ).where(Organ.status == "available")
        )
        return list(result.scalars().all())

    async def get_matching_candidates(
        self,
        organ_id: str,
        limit: int = 50,
    ) -> Tuple[List[MatchingResult], Dict]:
        matches = await self.find_matches(organ_id=organ_id, top_n=limit)

        results = [
            MatchingResult(
                recipient_id=int(m["recipient_id"]) if str(m["recipient_id"]).isdigit() else m["recipient_id"],
                matching_score=m["matching_score"],
                matching_detail=m["matching_detail"],
                rank=m["rank"],
            )
            for m in matches
        ]

        summary = {
            "organ_id": organ_id,
            "total_candidates": len(matches),
            "average_score": round(sum(m["matching_score"] for m in matches) / len(matches), 2) if matches else 0,
            "urgency_breakdown": {},
        }
        for m in matches:
            lvl = m.get("urgency_level", "unknown")
            summary["urgency_breakdown"][lvl] = summary["urgency_breakdown"].get(lvl, 0) + 1

        return results, summary
