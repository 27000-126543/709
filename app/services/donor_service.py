from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple
import json

from app.models import Donor
from app.schemas.donor import DonorCreate, DonorUpdate
from app.schemas.common import HealthStatus


HEALTH_CHECK_RANGES = {
    "infectious_diseases": {
        "hbsag": {"name": "乙肝表面抗原", "type": "boolean", "normal": False, "critical": True},
        "hcv": {"name": "丙肝抗体", "type": "boolean", "normal": False, "critical": True},
        "hiv": {"name": "艾滋病抗体", "type": "boolean", "normal": False, "critical": True},
        "syphilis": {"name": "梅毒抗体", "type": "boolean", "normal": False, "critical": True},
        "tuberculosis": {"name": "结核杆菌", "type": "boolean", "normal": False, "critical": True},
    },
    "liver_function": {
        "alt": {"name": "谷丙转氨酶(ALT)", "min": 0, "max": 40, "unit": "U/L"},
        "ast": {"name": "谷草转氨酶(AST)", "min": 0, "max": 40, "unit": "U/L"},
        "total_bilirubin": {"name": "总胆红素", "min": 3.4, "max": 17.1, "unit": "μmol/L"},
        "direct_bilirubin": {"name": "直接胆红素", "min": 0, "max": 6.8, "unit": "μmol/L"},
        "albumin": {"name": "白蛋白", "min": 35, "max": 55, "unit": "g/L"},
    },
    "kidney_function": {
        "creatinine": {"name": "肌酐", "min": 44, "max": 133, "unit": "μmol/L"},
        "urea": {"name": "尿素氮", "min": 2.5, "max": 7.5, "unit": "mmol/L"},
        "uric_acid": {"name": "尿酸", "min": 150, "max": 420, "unit": "μmol/L"},
        "egfr": {"name": "肾小球滤过率", "min": 90, "max": None, "unit": "mL/min/1.73m²"},
    },
    "cardiac_function": {
        "troponin": {"name": "肌钙蛋白", "min": 0, "max": 0.04, "unit": "ng/mL"},
        "bnp": {"name": "脑钠肽", "min": 0, "max": 100, "unit": "pg/mL"},
        "lvef": {"name": "左室射血分数", "min": 55, "max": None, "unit": "%"},
        "ck_mb": {"name": "肌酸激酶同工酶", "min": 0, "max": 25, "unit": "U/L"},
    },
    "general": {
        "blood_pressure_systolic": {"name": "收缩压", "min": 90, "max": 140, "unit": "mmHg"},
        "blood_pressure_diastolic": {"name": "舒张压", "min": 60, "max": 90, "unit": "mmHg"},
        "heart_rate": {"name": "心率", "min": 60, "max": 100, "unit": "bpm"},
        "temperature": {"name": "体温", "min": 36.0, "max": 37.5, "unit": "°C"},
    },
}


class DonorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_donor(self, donor_in: DonorCreate) -> Donor:
        donor = Donor(**donor_in.model_dump(exclude_none=True))
        donor.status = "registered"
        self.db.add(donor)
        await self.db.flush()
        await self.db.refresh(donor)
        return donor

    async def get_donor(self, donor_id: str) -> Optional[Donor]:
        result = await self.db.execute(select(Donor).where(Donor.id == donor_id))
        return result.scalar_one_or_none()

    async def list_donors(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        province: Optional[str] = None,
    ) -> Tuple[List[Donor], int]:
        query = select(Donor)
        if status:
            query = query.where(Donor.status == status)
        if province:
            query = query.where(Donor.province == province)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Donor.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_donor(self, donor_id: str, donor_in: DonorUpdate) -> Optional[Donor]:
        donor = await self.get_donor(donor_id)
        if not donor:
            return None

        update_data = donor_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(donor, key, value)

        await self.db.flush()
        await self.db.refresh(donor)
        return donor

    async def delete_donor(self, donor_id: str) -> bool:
        donor = await self.get_donor(donor_id)
        if not donor:
            return False
        await self.db.delete(donor)
        await self.db.flush()
        return True

    def _parse_health_detail(self, health_check_detail: Optional[str]) -> dict:
        if not health_check_detail:
            return {}
        try:
            if isinstance(health_check_detail, str):
                return json.loads(health_check_detail)
            return health_check_detail if isinstance(health_check_detail, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def validate_health_status(
        self,
        health_check_detail: Optional[str],
    ) -> Tuple[bool, List[str], List[str]]:
        data = self._parse_health_detail(health_check_detail)
        errors: List[str] = []
        warnings: List[str] = []

        for category_name, category_checks in HEALTH_CHECK_RANGES.items():
            category_data = data.get(category_name, {})
            if category_name == "infectious_diseases":
                for key, check in category_checks.items():
                    value = category_data.get(key)
                    if value is None:
                        warnings.append(f"{check['name']}: 未检测")
                        continue
                    if check.get("type") == "boolean":
                        if value != check["normal"]:
                            if check.get("critical"):
                                errors.append(f"{check['name']}: 阳性 - 不合格")
                            else:
                                warnings.append(f"{check['name']}: 异常")
            else:
                for key, check in category_checks.items():
                    value = category_data.get(key)
                    if value is None:
                        warnings.append(f"{check['name']}: 未检测")
                        continue
                    try:
                        num_value = float(value)
                    except (TypeError, ValueError):
                        warnings.append(f"{check['name']}: 数据格式错误")
                        continue

                    min_val = check.get("min")
                    max_val = check.get("max")
                    unit = check.get("unit", "")
                    out_of_range = False

                    if min_val is not None and num_value < min_val:
                        out_of_range = True
                        errors.append(
                            f"{check['name']}: {num_value}{unit} 低于下限 {min_val}{unit}"
                        )
                    if max_val is not None and num_value > max_val:
                        out_of_range = True
                        errors.append(
                            f"{check['name']}: {num_value}{unit} 高于上限 {max_val}{unit}"
                        )

                    if not out_of_range:
                        margin_factor = 0.1
                        if min_val is not None:
                            margin = (max_val - min_val) * margin_factor if max_val else min_val * margin_factor
                            if num_value < min_val + margin:
                                warnings.append(f"{check['name']}: {num_value}{unit} 接近正常下限")
                        if max_val is not None:
                            margin = (max_val - min_val) * margin_factor if min_val else max_val * margin_factor
                            if num_value > max_val - margin:
                                warnings.append(f"{check['name']}: {num_value}{unit} 接近正常上限")

        is_qualified = len(errors) == 0
        return is_qualified, errors, warnings

    def validate_family_consent(self, donor: Donor) -> Tuple[bool, List[str]]:
        issues: List[str] = []

        if not donor.family_consent:
            issues.append("未获得家属同意签字")
        if not donor.consent_document_url:
            issues.append("缺少同意书文件")
        if not donor.consent_verified:
            issues.append("同意书未完成核验")

        is_complete = len(issues) == 0
        return is_complete, issues

    async def review_donor_health(self, donor_id: str) -> Optional[dict]:
        donor = await self.get_donor(donor_id)
        if not donor:
            return None

        is_qualified, health_errors, health_warnings = self.validate_health_status(
            donor.health_check_detail
        )
        consent_complete, consent_issues = self.validate_family_consent(donor)

        all_issues = health_errors + consent_issues
        all_warnings = health_warnings

        if all_issues:
            donor.status = "rejected"
            donor.health_status = "disqualified"
            donor.rejection_reason = json.dumps(
                {
                    "health_errors": health_errors,
                    "consent_issues": consent_issues,
                    "warnings": all_warnings,
                },
                ensure_ascii=False,
            )
        elif all_warnings:
            donor.health_status = "conditional"
            donor.status = "verified"
            donor.rejection_reason = None
        else:
            donor.health_status = "qualified"
            donor.status = "verified"
            donor.rejection_reason = None

        await self.db.flush()
        await self.db.refresh(donor)

        return {
            "donor_id": donor.id,
            "status": donor.status,
            "health_status": donor.health_status,
            "is_qualified": is_qualified,
            "consent_complete": consent_complete,
            "health_errors": health_errors,
            "health_warnings": health_warnings,
            "consent_issues": consent_issues,
            "rejection_reason": donor.rejection_reason,
        }

    async def reject_donor(self, donor_id: str, reason: str) -> Optional[Donor]:
        donor = await self.get_donor(donor_id)
        if not donor:
            return None

        donor.status = "rejected"
        donor.health_status = "disqualified"
        donor.rejection_reason = reason

        await self.db.flush()
        await self.db.refresh(donor)
        return donor

    async def mark_organ_retrieved(self, donor_id: str) -> Optional[Donor]:
        donor = await self.get_donor(donor_id)
        if not donor:
            return None

        donor.status = "organ_retrieved"
        await self.db.flush()
        await self.db.refresh(donor)
        return donor

    async def close_donor(self, donor_id: str) -> Optional[Donor]:
        donor = await self.get_donor(donor_id)
        if not donor:
            return None

        donor.status = "closed"
        await self.db.flush()
        await self.db.refresh(donor)
        return donor
