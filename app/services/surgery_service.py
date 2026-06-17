from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta, date
import json

from app.models import Surgery, Allocation, Recipient, Organ
from app.schemas.surgery import (
    SurgeryCreate,
    SurgeryUpdate,
    PreOpCheckCreate,
    ImmunosuppressantPlanCreate,
    DrugMonitoringCreate,
)
from app.schemas.common import PreopCheckStatus


PREOP_REFERENCE_RANGES: Dict[str, Dict] = {
    "blood_routine": {
        "wbc": {"name": "白细胞计数", "min": 4.0, "max": 10.0, "unit": "×10⁹/L"},
        "rbc": {"name": "红细胞计数", "min": 4.0, "max": 5.5, "unit": "×10¹²/L"},
        "hgb": {"name": "血红蛋白", "min": 120, "max": 160, "unit": "g/L"},
        "plt": {"name": "血小板计数", "min": 100, "max": 300, "unit": "×10⁹/L"},
    },
    "blood_biochemistry": {
        "alt": {"name": "谷丙转氨酶", "min": 0, "max": 40, "unit": "U/L"},
        "ast": {"name": "谷草转氨酶", "min": 0, "max": 40, "unit": "U/L"},
        "creatinine": {"name": "肌酐", "min": 44, "max": 133, "unit": "μmol/L"},
        "urea": {"name": "尿素氮", "min": 2.5, "max": 7.5, "unit": "mmol/L"},
        "glucose": {"name": "空腹血糖", "min": 3.9, "max": 6.1, "unit": "mmol/L"},
        "albumin": {"name": "白蛋白", "min": 35, "max": 55, "unit": "g/L"},
    },
    "coagulation": {
        "pt": {"name": "凝血酶原时间", "min": 11, "max": 14, "unit": "s"},
        "aptt": {"name": "活化部分凝血活酶时间", "min": 25, "max": 35, "unit": "s"},
        "inr": {"name": "国际标准化比值", "min": 0.8, "max": 1.2, "unit": ""},
        "fibrinogen": {"name": "纤维蛋白原", "min": 2, "max": 4, "unit": "g/L"},
    },
    "infectious_markers": {
        "hbsag": {"name": "乙肝表面抗原", "type": "negative"},
        "anti_hcv": {"name": "丙肝抗体", "type": "negative"},
        "anti_hiv": {"name": "艾滋病毒抗体", "type": "negative"},
        "rpr": {"name": "梅毒抗体", "type": "negative"},
    },
    "cardiac": {
        "lvef": {"name": "左室射血分数", "min": 55, "max": None, "unit": "%"},
        "troponin_i": {"name": "肌钙蛋白I", "min": 0, "max": 0.04, "unit": "ng/mL"},
        "bnp": {"name": "脑钠肽", "min": 0, "max": 100, "unit": "pg/mL"},
    },
    "crossmatch": {
        "t_cell_crossmatch": {"name": "T细胞交叉配型", "type": "negative"},
        "b_cell_crossmatch": {"name": "B细胞交叉配型", "type": "negative"},
        "flow_cytometry": {"name": "流式细胞仪交叉配型", "type": "negative"},
    },
}


IMMUNOSUPPRESSANT_PROTOCOLS: Dict[str, List[Dict]] = {
    "induction": [
        {
            "drug": "巴利昔单抗 (Basiliximab)",
            "dose": "20mg",
            "frequency": "术前2小时及第4天各1次",
            "duration": "2剂",
            "monitoring": "监测白细胞计数",
        },
        {
            "drug": "抗胸腺细胞球蛋白 (ATG)",
            "dose": "1.5mg/kg/天",
            "frequency": "每日1次，静脉输注",
            "duration": "3-5天",
            "monitoring": "监测CD3+细胞计数、过敏反应",
        },
    ],
    "maintenance_kidney": [
        {
            "drug": "他克莫司 (Tacrolimus)",
            "dose": "0.15-0.3mg/kg/天，分2次",
            "frequency": "每12小时1次",
            "duration": "长期",
            "target_level": "术后1个月: 10-15ng/mL, 3-6个月: 8-12ng/mL, 长期: 5-10ng/mL",
            "monitoring": "每周2次谷浓度监测",
        },
        {
            "drug": "霉酚酸酯 (MMF)",
            "dose": "500-1000mg",
            "frequency": "每12小时1次",
            "duration": "长期",
            "target_level": "MPA-AUC 30-60mg·h/L",
            "monitoring": "监测白细胞、肝功能",
        },
        {
            "drug": "泼尼松 (Prednisone)",
            "dose": "术后第1天500mg，逐渐减量至5-10mg/天",
            "frequency": "每日1次(晨起)",
            "duration": "长期维持",
            "monitoring": "监测血糖、血压、骨密度",
        },
    ],
    "maintenance_liver": [
        {
            "drug": "他克莫司 (Tacrolimus)",
            "dose": "0.1-0.2mg/kg/天，分2次",
            "frequency": "每12小时1次",
            "duration": "长期",
            "target_level": "术后1-3个月: 8-12ng/mL, 长期: 5-8ng/mL",
            "monitoring": "每周2次谷浓度监测",
        },
        {
            "drug": "霉酚酸酯 (MMF)",
            "dose": "500-1000mg",
            "frequency": "每12小时1次",
            "duration": "长期",
            "monitoring": "监测全血细胞计数",
        },
        {
            "drug": "泼尼松 (Prednisone)",
            "dose": "术后起始20mg/天，逐渐减量",
            "frequency": "每日1次(晨起)",
            "duration": "根据情况逐渐停用",
            "monitoring": "监测代谢指标",
        },
    ],
}


REJECTION_MONITORING_SCHEDULE = [
    {"period": "术后1周内", "type": "daily_lab", "frequency": "每日", "tests": ["血常规", "肝肾功能", "血药浓度", "凝血功能"]},
    {"period": "术后1-4周", "type": "biopsy_surveillance", "frequency": "每周1次", "tests": ["移植器官穿刺活检(必要时)", "超声检查", "免疫学监测"]},
    {"period": "术后1-3个月", "type": "acute_rejection_risk", "frequency": "每2周1次", "tests": ["器官功能评估", "血药浓度", "供体特异性抗体(DSA)"]},
    {"period": "术后3-6个月", "type": "stabilization", "frequency": "每月1次", "tests": ["完整器官功能评估", "血药浓度", "DSA监测", "感染筛查"]},
    {"period": "术后6-12个月", "type": "routine_followup", "frequency": "每2-3个月1次", "tests": ["年度综合评估", "活检(必要时)", "影像学检查"]},
    {"period": "术后1年以上", "type": "chronic_monitoring", "frequency": "每3-6个月1次", "tests": ["慢性排斥监测", "器官功能趋势分析", "并发症筛查"]},
]


class SurgeryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_surgery(self, surgery_in: SurgeryCreate) -> Optional[Surgery]:
        alloc_result = await self.db.execute(
            select(Allocation).where(Allocation.id == str(surgery_in.allocation_id))
        )
        allocation = alloc_result.scalar_one_or_none()
        if not allocation:
            return None

        surgery = Surgery(
            allocation_id=str(surgery_in.allocation_id),
            recipient_id=str(surgery_in.recipient_id),
            organ_id=str(surgery_in.organ_id),
            transplant_center_id=str(surgery_in.transplant_center_id),
            surgeon_id=str(surgery_in.surgeon_id),
            preop_check_status="pending",
            surgery_status="scheduled",
        )

        self.db.add(surgery)
        await self.db.flush()
        await self.db.refresh(surgery)

        immunosuppressant_plan = await self.generate_immunosuppressant_plan(
            organ_type="kidney",
            recipient_weight=None,
        )
        surgery.immunosuppressant_plan = json.dumps(
            [p.model_dump() if hasattr(p, "model_dump") else p for p in immunosuppressant_plan],
            ensure_ascii=False,
        )

        reminders = await self.generate_rejection_reminders(surgery.id)
        surgery.rejection_monitoring_reminders = json.dumps(
            [r.model_dump() if hasattr(r, "model_dump") else r for r in reminders],
            ensure_ascii=False,
        )

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
        preop_check_status: Optional[str] = None,
        transplant_center_id: Optional[str] = None,
    ) -> Tuple[List[Surgery], int]:
        query = select(Surgery)

        if surgery_status:
            query = query.where(Surgery.surgery_status == surgery_status)
        if preop_check_status:
            query = query.where(Surgery.preop_check_status == preop_check_status)
        if transplant_center_id:
            query = query.where(Surgery.transplant_center_id == transplant_center_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Surgery.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def upload_preop_data(
        self,
        upload_in: PreopDataUpload,
    ) -> Optional[Dict]:
        surgery = await self.get_surgery(str(upload_in.surgery_id))
        if not surgery:
            return None

        surgery.preop_data = json.dumps(upload_in.preop_data, ensure_ascii=False)

        check_result = await self.compare_preop_thresholds(upload_in.preop_data)

        if check_result["status"] == "passed":
            surgery.preop_check_status = "passed"
            surgery.preop_recheck_notes = None
        elif check_result["status"] == "recheck_recommended":
            surgery.preop_check_status = "recheck_recommended"
            notes = "需要复查的项目:\n" + "\n".join(check_result["recheck_items"])
            if check_result["warnings"]:
                notes += "\n\n警告项:\n" + "\n".join(check_result["warnings"])
            surgery.preop_recheck_notes = notes
        else:
            surgery.preop_check_status = "failed"
            notes = "不合格项目:\n" + "\n".join(check_result["failed_items"])
            if check_result["warnings"]:
                notes += "\n\n警告项:\n" + "\n".join(check_result["warnings"])
            surgery.preop_recheck_notes = notes

        await self.db.flush()
        await self.db.refresh(surgery)

        return {
            "surgery_id": surgery.id,
            "check_status": surgery.preop_check_status,
            "passed_count": check_result["passed_count"],
            "total_count": check_result["total_count"],
            "failed_items": check_result["failed_items"],
            "warnings": check_result["warnings"],
            "recheck_items": check_result["recheck_items"],
            "recheck_notes": surgery.preop_recheck_notes,
        }

    async def compare_preop_thresholds(
        self,
        preop_data: Dict,
        deviation_threshold: float = 0.15,
    ) -> Dict:
        failed_items: List[str] = []
        warnings: List[str] = []
        recheck_items: List[str] = []
        passed_count = 0
        total_count = 0

        for category_name, category_data in preop_data.items():
            if not isinstance(category_data, dict):
                continue
            reference = PREOP_REFERENCE_RANGES.get(category_name, {})

            for key, ref_info in reference.items():
                total_count += 1
                value = category_data.get(key)
                if value is None:
                    warnings.append(f"{category_name}/{ref_info.get('name', key)}: 数据缺失")
                    continue

                if ref_info.get("type") == "negative":
                    if str(value).lower() in ("positive", "阳", "阳性", "1", "true"):
                        failed_items.append(
                            f"{ref_info.get('name', key)}: 结果为阳性 - 不合格"
                        )
                    else:
                        passed_count += 1
                    continue

                try:
                    num_value = float(value)
                except (TypeError, ValueError):
                    warnings.append(f"{ref_info.get('name', key)}: 数据格式错误")
                    continue

                min_val = ref_info.get("min")
                max_val = ref_info.get("max")
                unit = ref_info.get("unit", "")
                is_failed = False
                is_warning = False

                if min_val is not None and num_value < min_val:
                    deviation = (min_val - num_value) / min_val if min_val > 0 else 1.0
                    if deviation > deviation_threshold:
                        failed_items.append(
                            f"{ref_info.get('name', key)}: {num_value}{unit} 低于下限 {min_val}{unit} (偏差{round(deviation*100,1)}%)"
                        )
                        is_failed = True
                    else:
                        warnings.append(
                            f"{ref_info.get('name', key)}: {num_value}{unit} 略低于下限 {min_val}{unit}"
                        )
                        recheck_items.append(ref_info.get("name", key))
                        is_warning = True

                if max_val is not None and num_value > max_val:
                    deviation = (num_value - max_val) / max_val if max_val > 0 else 1.0
                    if deviation > deviation_threshold:
                        failed_items.append(
                            f"{ref_info.get('name', key)}: {num_value}{unit} 高于上限 {max_val}{unit} (偏差{round(deviation*100,1)}%)"
                        )
                        is_failed = True
                    elif not is_failed:
                        warnings.append(
                            f"{ref_info.get('name', key)}: {num_value}{unit} 略高于上限 {max_val}{unit}"
                        )
                        recheck_items.append(ref_info.get("name", key))
                        is_warning = True

                if not is_failed and not is_warning:
                    passed_count += 1

        if failed_items:
            status = "failed"
        elif recheck_items:
            status = "recheck_recommended"
        else:
            status = "passed"

        return {
            "status": status,
            "passed_count": passed_count,
            "total_count": total_count,
            "failed_items": failed_items,
            "warnings": warnings,
            "recheck_items": recheck_items,
        }

    async def generate_immunosuppressant_plan(
        self,
        organ_type: str,
        recipient_weight: Optional[float] = None,
    ) -> List[ImmunosuppressantPlan]:
        plans = []

        for item in IMMUNOSUPPRESSANT_PROTOCOLS.get("induction", []):
            plan = ImmunosuppressantPlan(
                drug=item["drug"],
                dose=item["dose"],
                frequency=item["frequency"],
                duration=item["duration"],
            )
            plans.append(plan)

        maintenance_key = f"maintenance_{organ_type}"
        if maintenance_key not in IMMUNOSUPPRESSANT_PROTOCOLS:
            maintenance_key = "maintenance_kidney"

        for item in IMMUNOSUPPRESSANT_PROTOCOLS.get(maintenance_key, []):
            plan = ImmunosuppressantPlan(
                drug=item["drug"],
                dose=item["dose"],
                frequency=item["frequency"],
                duration=item["duration"],
            )
            plans.append(plan)

        return plans

    async def update_immunosuppressant_plan(
        self,
        surgery_id: str,
        new_plans: List[ImmunosuppressantPlan],
    ) -> Optional[Surgery]:
        surgery = await self.get_surgery(surgery_id)
        if not surgery:
            return None

        surgery.immunosuppressant_plan = json.dumps(
            [p.model_dump() for p in new_plans],
            ensure_ascii=False,
        )

        await self.db.flush()
        await self.db.refresh(surgery)
        return surgery

    async def add_blood_concentration_data(
        self,
        surgery_id: str,
        data_in: BloodConcentrationData,
    ) -> Optional[Dict]:
        surgery = await self.get_surgery(surgery_id)
        if not surgery:
            return None

        try:
            existing_data = json.loads(surgery.blood_concentration_data) if surgery.blood_concentration_data else []
            if not isinstance(existing_data, list):
                existing_data = []
        except (json.JSONDecodeError, TypeError):
            existing_data = []

        adjustment_result = await self.calculate_dose_adjustment(data_in)

        record = data_in.model_dump()
        record["dose_adjustment"] = adjustment_result["adjustment"]
        record["recommendation"] = adjustment_result["recommendation"]

        existing_data.append(record)
        surgery.blood_concentration_data = json.dumps(existing_data, ensure_ascii=False)

        await self.db.flush()
        await self.db.refresh(surgery)

        return {
            "surgery_id": surgery.id,
            "record": record,
            "adjustment_needed": adjustment_result["needed"],
            "recommendation": adjustment_result["recommendation"],
            "historical_count": len(existing_data),
        }

    async def calculate_dose_adjustment(
        self,
        data_in: BloodConcentrationData,
    ) -> Dict:
        drug_target_ranges = {
            "他克莫司": {"early": (10, 15), "mid": (8, 12), "late": (5, 10)},
            "环孢素A": {"early": (200, 400), "mid": (150, 300), "late": (100, 200)},
            "霉酚酸": {"all": (1.5, 3.5)},
            "西罗莫司": {"all": (5, 15)},
            "依维莫司": {"all": (3, 8)},
        }

        target_range = None
        for drug_key, ranges in drug_target_ranges.items():
            if drug_key in data_in.drug:
                if "all" in ranges:
                    target_range = ranges["all"]
                else:
                    today = date.today()
                    surgery_date = data_in.date
                    months_diff = (today.year - surgery_date.year) * 12 + (today.month - surgery_date.month)
                    if months_diff <= 1:
                        target_range = ranges["early"]
                    elif months_diff <= 6:
                        target_range = ranges["mid"]
                    else:
                        target_range = ranges["late"]
                break

        if target_range is None:
            return {
                "needed": False,
                "adjustment": data_in.dose_adjustment,
                "recommendation": "无此药物的标准参考范围，建议临床评估",
            }

        concentration = data_in.concentration
        low, high = target_range
        needed = False
        recommendation = ""
        adjustment = data_in.dose_adjustment

        if concentration < low:
            needed = True
            deficit_pct = ((low - concentration) / low) * 100
            if deficit_pct > 30:
                recommendation = f"血药浓度明显偏低({concentration}ng/mL, 目标{low}-{high}ng/mL), 建议增加剂量20-30%"
            else:
                recommendation = f"血药浓度略低({concentration}ng/mL, 目标{low}-{high}ng/mL), 建议小幅增加剂量10-15%"
        elif concentration > high:
            needed = True
            excess_pct = ((concentration - high) / high) * 100
            if excess_pct > 50:
                recommendation = f"血药浓度明显偏高({concentration}ng/mL, 目标{low}-{high}ng/mL), 建议减少剂量30%并密切监测毒副作用"
            else:
                recommendation = f"血药浓度略高({concentration}ng/mL, 目标{low}-{high}ng/mL), 建议减少剂量10-20%"
        else:
            recommendation = f"血药浓度正常({concentration}ng/mL, 目标{low}-{high}ng/mL), 维持当前剂量"

        return {
            "needed": needed,
            "adjustment": adjustment,
            "recommendation": recommendation,
            "target_range": target_range,
        }

    async def generate_rejection_reminders(
        self,
        surgery_id: str,
    ) -> List[RejectionReminder]:
        reminders = []

        surgery = await self.get_surgery(surgery_id)
        base_date = date.today()
        if surgery and surgery.surgery_date:
            base_date = surgery.surgery_date.date() if isinstance(surgery.surgery_date, datetime) else surgery.surgery_date

        for schedule in REJECTION_MONITORING_SCHEDULE:
            reminder = RejectionReminder(
                date=base_date,
                type=schedule["type"],
                status=(
                    f"{schedule['period']} - {schedule['frequency']}\n"
                    f"检测项目: {', '.join(schedule['tests'])}"
                ),
            )
            reminders.append(reminder)

        return reminders

    async def update_surgery_status(
        self,
        surgery_id: str,
        new_status: str,
        notes: Optional[str] = None,
    ) -> Optional[Surgery]:
        surgery = await self.get_surgery(surgery_id)
        if not surgery:
            return None

        surgery.surgery_status = new_status

        if new_status == "in_progress" and not surgery.surgery_date:
            surgery.surgery_date = datetime.utcnow()
        elif new_status == "completed":
            organ_result = await self.db.execute(
                select(Organ).where(Organ.id == surgery.organ_id)
            )
            organ = organ_result.scalar_one_or_none()
            if organ:
                organ.status = "transplanted"

            recipient_result = await self.db.execute(
                select(Recipient).where(Recipient.id == surgery.recipient_id)
            )
            recipient = recipient_result.scalar_one_or_none()
            if recipient:
                recipient.status = "transplanted"

        await self.db.flush()
        await self.db.refresh(surgery)
        return surgery

    async def check_reaction_alert(
        self,
        surgery_id: str,
    ) -> Optional[Dict]:
        surgery = await self.get_surgery(surgery_id)
        if not surgery:
            return None

        try:
            blood_data = json.loads(surgery.blood_concentration_data) if surgery.blood_concentration_data else []
        except (json.JSONDecodeError, TypeError):
            blood_data = []

        alerts = []
        if len(blood_data) >= 2:
            recent = blood_data[-3:] if len(blood_data) >= 3 else blood_data
            concentrations = [d.get("concentration", 0) for d in recent if isinstance(d, dict)]
            if len(concentrations) >= 2:
                avg = sum(concentrations) / len(concentrations)
                first = concentrations[0]
                last = concentrations[-1]
                if first > 0:
                    change_pct = ((last - first) / first) * 100
                    if change_pct > 30:
                        alerts.append(
                            f"血药浓度近期上升{round(change_pct,1)}%, 需警惕排斥反应或代谢变化"
                        )
                    elif change_pct < -25:
                        alerts.append(
                            f"血药浓度近期下降{round(abs(change_pct),1)}%, 需评估依从性或药物相互作用"
                        )

        return {
            "surgery_id": surgery_id,
            "has_alerts": len(alerts) > 0,
            "alerts": alerts,
            "total_records": len(blood_data),
            "recommendation": (
                "建议: 加强排斥反应监测，必要时进行穿刺活检和DSA检测"
                if alerts
                else "排斥反应相关指标稳定，按计划随访"
            ),
        }
