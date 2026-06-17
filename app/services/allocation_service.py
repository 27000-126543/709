from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple, Dict
import json
from datetime import datetime

from app.models import Allocation, Organ, Recipient, Donor
from app.schemas.allocation import AllocationRequest
from app.schemas.common import AllocationStatus
from app.services.matching_utils import calculate_distance_by_province


TRANSPLANT_CENTER_QUALIFICATIONS: Dict[str, List[str]] = {
    "default": ["heart", "liver", "kidney", "lung", "pancreas", "cornea"],
}


class RetrievalTeam:
    def __init__(self, team_id: str, name: str, province: str, latitude: float, longitude: float):
        self.team_id = team_id
        self.name = name
        self.province = province
        self.latitude = latitude
        self.longitude = longitude


MOCK_RETRIEVAL_TEAMS: List[RetrievalTeam] = [
    RetrievalTeam("team_001", "北京协和医院获取团队", "北京市", 39.9042, 116.4074),
    RetrievalTeam("team_002", "上海瑞金医院获取团队", "上海市", 31.2304, 121.4737),
    RetrievalTeam("team_003", "广州中山医院获取团队", "广东省", 23.1291, 113.2644),
    RetrievalTeam("team_004", "成都华西医院获取团队", "四川省", 30.5728, 104.0668),
    RetrievalTeam("team_005", "武汉同济医院获取团队", "湖北省", 30.5928, 114.3055),
    RetrievalTeam("team_006", "西安交大一附院获取团队", "陕西省", 34.3416, 108.9398),
]


class AllocationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_allocation(self, alloc_in: AllocationRequest) -> Optional[Allocation]:
        valid, center_errors = self.validate_transplant_center_qualification(
            transplant_center_id=str(alloc_in.transplant_center_id),
            organ_type="kidney",
        )

        organ_result = await self.db.execute(
            select(Organ).where(Organ.id == str(alloc_in.organ_id))
        )
        organ = organ_result.scalar_one_or_none()
        if organ:
            valid2, _ = self.validate_transplant_center_qualification(
                transplant_center_id=str(alloc_in.transplant_center_id),
                organ_type=organ.organ_type,
            )
            valid = valid and valid2
            if organ.status not in ("available", "locked"):
                return None

        recipient_result = await self.db.execute(
            select(Recipient).where(Recipient.id == str(alloc_in.recipient_id))
        )
        recipient = recipient_result.scalar_one_or_none()
        if not recipient or recipient.status != "waiting":
            return None

        valid_waiting, waiting_errors = await self.validate_waiting_list(
            recipient_id=str(alloc_in.recipient_id)
        )
        if not valid_waiting:
            return None

        if not valid:
            return None

        allocation = Allocation(
            organ_id=str(alloc_in.organ_id),
            recipient_id=str(alloc_in.recipient_id),
            donor_id=str(alloc_in.donor_id),
            matching_score=alloc_in.matching_score,
            matching_detail=json.dumps(alloc_in.matching_detail, ensure_ascii=False) if isinstance(alloc_in.matching_detail, dict) else str(alloc_in.matching_detail),
            transplant_center_id=str(alloc_in.transplant_center_id),
            province=alloc_in.province,
            status="pending",
            current_approval_level="pending",
        )

        self.db.add(allocation)
        await self.db.flush()
        await self.db.refresh(allocation)

        if organ:
            organ.status = "allocated"

        if recipient:
            recipient.status = "matched"
            recipient.matching_score = alloc_in.matching_score

        await self.db.flush()
        return allocation

    def validate_transplant_center_qualification(
        self,
        transplant_center_id: str,
        organ_type: str,
    ) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        allowed_organs = TRANSPLANT_CENTER_QUALIFICATIONS.get(
            transplant_center_id,
            TRANSPLANT_CENTER_QUALIFICATIONS["default"],
        )

        if organ_type not in allowed_organs:
            errors.append(
                f"移植中心(ID:{transplant_center_id})不具备{organ_type}器官移植资质"
            )

        return len(errors) == 0, errors

    async def validate_waiting_list(
        self,
        recipient_id: str,
    ) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        result = await self.db.execute(
            select(Recipient).where(Recipient.id == recipient_id)
        )
        recipient = result.scalar_one_or_none()

        if not recipient:
            errors.append("受者不存在")
            return False, errors

        if recipient.status != "waiting":
            errors.append(f"受者状态为'{recipient.status}'，不在等待列表中")

        if not recipient.waiting_since:
            errors.append("受者未登记等待时间")

        return len(errors) == 0, errors

    async def get_allocation(self, allocation_id: str) -> Optional[Allocation]:
        result = await self.db.execute(
            select(Allocation).where(Allocation.id == allocation_id)
        )
        return result.scalar_one_or_none()

    async def list_allocations(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        province: Optional[str] = None,
        transplant_center_id: Optional[str] = None,
    ) -> Tuple[List[Allocation], int]:
        query = select(Allocation)

        if status:
            query = query.where(Allocation.status == status)
        if province:
            query = query.where(Allocation.province == province)
        if transplant_center_id:
            query = query.where(Allocation.transplant_center_id == transplant_center_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Allocation.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def generate_retrieval_task(
        self,
        allocation_id: str,
    ) -> Optional[Dict]:
        allocation = await self.get_allocation(allocation_id)
        if not allocation:
            return None

        donor_result = await self.db.execute(
            select(Donor).where(Donor.id == allocation.donor_id)
        )
        donor = donor_result.scalar_one_or_none()

        organ_result = await self.db.execute(
            select(Organ).where(Organ.id == allocation.organ_id)
        )
        organ = organ_result.scalar_one_or_none()

        task = {
            "allocation_id": allocation.id,
            "organ_id": allocation.organ_id,
            "donor_id": allocation.donor_id,
            "donor_hospital": donor.hospital if donor else None,
            "donor_province": donor.province if donor else None,
            "organ_type": organ.organ_type if organ else None,
            "task_created_at": datetime.utcnow().isoformat(),
            "status": "pending",
            "requirements": {
                "organ_type": organ.organ_type if organ else None,
                "max_ischemia_hours": organ.max_ischemia_hours if organ else None,
                "temperature_requirement": organ.temperature_requirement if organ else None,
            },
        }

        return task

    async def assign_nearest_retrieval_team(
        self,
        allocation_id: str,
        teams: Optional[List[RetrievalTeam]] = None,
    ) -> Tuple[Optional[RetrievalTeam], List[Dict]]:
        allocation = await self.get_allocation(allocation_id)
        if not allocation:
            return None, []

        donor_result = await self.db.execute(
            select(Donor).where(Donor.id == allocation.donor_id)
        )
        donor = donor_result.scalar_one_or_none()
        if not donor or not donor.province:
            return None, []

        if teams is None:
            teams = MOCK_RETRIEVAL_TEAMS

        from app.services.matching_utils import get_province_coords, haversine_distance

        donor_coords = get_province_coords(donor.province)
        if not donor_coords:
            return teams[0] if teams else None, [{"team_id": t.team_id, "distance_km": 0} for t in teams]

        team_distances = []
        for team in teams:
            dist = haversine_distance(
                donor_coords[0], donor_coords[1],
                team.latitude, team.longitude,
            )
            team_distances.append((team, dist))

        team_distances.sort(key=lambda x: x[1])

        sorted_teams = [
            {"team_id": td[0].team_id, "name": td[0].name, "province": td[0].province, "distance_km": round(td[1], 2)}
            for td in team_distances
        ]

        nearest_team = team_distances[0][0] if team_distances else None
        return nearest_team, sorted_teams

    async def update_allocation_status(
        self,
        allocation_id: str,
        new_status: str,
    ) -> Optional[Allocation]:
        allocation = await self.get_allocation(allocation_id)
        if not allocation:
            return None

        allocation.status = new_status

        if new_status == "completed":
            organ_result = await self.db.execute(
                select(Organ).where(Organ.id == allocation.organ_id)
            )
            organ = organ_result.scalar_one_or_none()
            if organ:
                organ.status = "transplanted"

            recipient_result = await self.db.execute(
                select(Recipient).where(Recipient.id == allocation.recipient_id)
            )
            recipient = recipient_result.scalar_one_or_none()
            if recipient:
                recipient.status = "transplanted"

        elif new_status == "rejected" or new_status == "cancelled":
            organ_result = await self.db.execute(
                select(Organ).where(Organ.id == allocation.organ_id)
            )
            organ = organ_result.scalar_one_or_none()
            if organ and organ.status in ("allocated", "locked"):
                organ.status = "available"

            recipient_result = await self.db.execute(
                select(Recipient).where(Recipient.id == allocation.recipient_id)
            )
            recipient = recipient_result.scalar_one_or_none()
            if recipient and recipient.status == "matched":
                recipient.status = "waiting"

        await self.db.flush()
        await self.db.refresh(allocation)
        return allocation

    async def update_approval_level(
        self,
        allocation_id: str,
        approval_level: str,
    ) -> Optional[Allocation]:
        allocation = await self.get_allocation(allocation_id)
        if not allocation:
            return None

        allocation.current_approval_level = approval_level

        if approval_level == "provincial" and allocation.status == "pending":
            allocation.status = "provincial_approved"
        elif approval_level == "national":
            allocation.status = "national_approved"
        elif approval_level == "final":
            allocation.status = "national_approved"

        await self.db.flush()
        await self.db.refresh(allocation)
        return allocation

    async def list_allocations_by_donor(self, donor_id: str) -> List[Allocation]:
        result = await self.db.execute(
            select(Allocation).where(Allocation.donor_id == donor_id)
            .order_by(Allocation.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_allocations_by_recipient(self, recipient_id: str) -> List[Allocation]:
        result = await self.db.execute(
            select(Allocation).where(Allocation.recipient_id == recipient_id)
            .order_by(Allocation.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_allocations_by_organ(self, organ_id: str) -> List[Allocation]:
        result = await self.db.execute(
            select(Allocation).where(Allocation.organ_id == organ_id)
            .order_by(Allocation.created_at.desc())
        )
        return list(result.scalars().all())

    async def cancel_allocation(self, allocation_id: str, reason: str) -> Optional[Allocation]:
        allocation = await self.update_allocation_status(allocation_id, "cancelled")
        return allocation
