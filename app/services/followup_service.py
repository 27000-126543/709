from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta, date
import json

from app.models import FollowUp, FollowUpAlert, Recipient, Surgery
from app.schemas.followup import FollowUpCreate
from app.schemas.common import FollowUpType


FOLLOWUP_ABNORMAL_THRESHOLDS: Dict[str, Dict] = {
    "kidney_function": {
        "creatinine": {
            "name": "肌酐",
            "min": 44, "max": 133, "unit": "μmol/L",
            "trend_warning_days": 7, "trend_change_pct": 20,
        },
        "urea": {
            "name": "尿素氮",
            "min": 2.5, "max": 7.5, "unit": "mmol/L",
            "trend_warning_days": 7, "trend_change_pct": 20,
        },
        "egfr": {
            "name": "肾小球滤过率",
            "min": 60, "max": None, "unit": "mL/min/1.73m²",
            "trend_warning_days": 30, "trend_change_pct": -15,
        },
        "urine_protein": {
            "name": "尿蛋白",
            "min": 0, "max": 0.15, "unit": "g/24h",
            "trend_warning_days": 7, "trend_change_pct": 50,
        },
    },
    "liver_function": {
        "alt": {
            "name": "谷丙转氨酶",
            "min": 0, "max": 40, "unit": "U/L",
            "trend_warning_days": 7, "trend_change_pct": 30,
        },
        "ast": {
            "name": "谷草转氨酶",
            "min": 0, "max": 40, "unit": "U/L",
            "trend_warning_days": 7, "trend_change_pct": 30,
        },
        "total_bilirubin": {
            "name": "总胆红素",
            "min": 3.4, "max": 20.5, "unit": "μmol/L",
            "trend_warning_days": 7, "trend_change_pct": 30,
        },
        "albumin": {
            "name": "白蛋白",
            "min": 35, "max": 55, "unit": "g/L",
            "trend_warning_days": 30, "trend_change_pct": -10,
        },
    },
    "cardiac_markers": {
        "troponin": {
            "name": "肌钙蛋白",
            "min": 0, "max": 0.04, "unit": "ng/mL",
            "trend_warning_days": 3, "trend_change_pct": 50,
        },
        "bnp": {
            "name": "脑钠肽",
            "min": 0, "max": 100, "unit": "pg/mL",
            "trend_warning_days": 7, "trend_change_pct": 30,
        },
        "lvef": {
            "name": "左室射血分数",
            "min": 50, "max": None, "unit": "%",
            "trend_warning_days": 30, "trend_change_pct": -10,
        },
    },
    "immunosuppression": {
        "tacrolimus_level": {
            "name": "他克莫司血药浓度",
            "min": 5, "max": 15, "unit": "ng/mL",
            "trend_warning_days": 7, "trend_change_pct": 30,
        },
        "cyclosporine_level": {
            "name": "环孢素血药浓度",
            "min": 100, "max": 400, "unit": "ng/mL",
            "trend_warning_days": 7, "trend_change_pct": 30,
        },
        "wbc": {
            "name": "白细胞计数",
            "min": 4, "max": 10, "unit": "×10⁹/L",
            "trend_warning_days": 7, "trend_change_pct": 25,
        },
    },
    "infection_markers": {
        "temperature": {
            "name": "体温",
            "min": 36.0, "max": 37.3, "unit": "°C",
            "trend_warning_days": 1, "trend_change_pct": 3,
        },
        "crp": {
            "name": "C反应蛋白",
            "min": 0, "max": 10, "unit": "mg/L",
            "trend_warning_days": 3, "trend_change_pct": 50,
        },
        "procalcitonin": {
            "name": "降钙素原",
            "min": 0, "max": 0.05, "unit": "ng/mL",
            "trend_warning_days": 3, "trend_change_pct": 100,
        },
    },
    "pulmonary_function": {
        "fev1": {
            "name": "第一秒用力呼气容积(占预计值%)",
            "min": 70, "max": None, "unit": "%",
            "trend_warning_days": 30, "trend_change_pct": -10,
        },
        "fvc": {
            "name": "用力肺活量(占预计值%)",
            "min": 70, "max": None, "unit": "%",
            "trend_warning_days": 30, "trend_change_pct": -10,
        },
        "dlco": {
            "name": "一氧化碳弥散量(占预计值%)",
            "min": 60, "max": None, "unit": "%",
            "trend_warning_days": 30, "trend_change_pct": -15,
        },
    },
    "general": {
        "weight": {
            "name": "体重",
            "min": None, "max": None, "unit": "kg",
            "trend_warning_days": 30, "trend_change_pct": 10,
        },
        "blood_pressure_systolic": {
            "name": "收缩压",
            "min": 90, "max": 140, "unit": "mmHg",
            "trend_warning_days": 7, "trend_change_pct": 15,
        },
        "blood_pressure_diastolic": {
            "name": "舒张压",
            "min": 60, "max": 90, "unit": "mmHg",
            "trend_warning_days": 7, "trend_change_pct": 15,
        },
        "fasting_glucose": {
            "name": "空腹血糖",
            "min": 3.9, "max": 7.0, "unit": "mmol/L",
            "trend_warning_days": 7, "trend_change_pct": 20,
        },
    },
    "dsa_monitoring": {
        "mfi_class_i": {
            "name": "I类DSA平均荧光强度",
            "min": 0, "max": 1000, "unit": "MFI",
            "trend_warning_days": 30, "trend_change_pct": 50,
        },
        "mfi_class_ii": {
            "name": "II类DSA平均荧光强度",
            "min": 0, "max": 1000, "unit": "MFI",
            "trend_warning_days": 30, "trend_change_pct": 50,
        },
        "c1q_binding": {
            "name": "C1q结合型DSA",
            "type": "negative",
        },
    },
}


class FollowUpService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_followup(self, followup_in: FollowUpCreate) -> Optional[dict]:
        recipient_result = await self.db.execute(
            select(Recipient).where(Recipient.id == str(followup_in.recipient_id))
        )
        recipient = recipient_result.scalar_one_or_none()
        if not recipient:
            return None

        data_str = followup_in.data
        if isinstance(followup_in.data, dict):
            data_str = json.dumps(followup_in.data, ensure_ascii=False)

        abnormal_flags: List[str] = []
        alert_details_list: List[str] = []

        if isinstance(followup_in.data, dict):
            abnormal_flags, alert_details_list = await self.detect_abnormalities(followup_in.data)
        elif isinstance(followup_in.data, str) and followup_in.data:
            try:
                parsed_data = json.loads(followup_in.data)
                if isinstance(parsed_data, dict):
                    abnormal_flags, alert_details_list = await self.detect_abnormalities(parsed_data)
                    data_str = followup_in.data
            except (json.JSONDecodeError, TypeError):
                pass

        followup = FollowUp(
            recipient_id=str(followup_in.recipient_id),
            surgery_id=str(followup_in.surgery_id) if followup_in.surgery_id else None,
            followup_date=followup_in.followup_date,
            followup_type=followup_in.followup_type.value,
            data=data_str if isinstance(data_str, str) else json.dumps(data_str, ensure_ascii=False),
            abnormal_flags=json.dumps(abnormal_flags, ensure_ascii=False) if abnormal_flags else None,
            alert_triggered=len(abnormal_flags) > 0,
            alert_details=json.dumps(alert_details_list, ensure_ascii=False) if alert_details_list else None,
            doctor_id=str(followup_in.doctor_id) if followup_in.doctor_id else None,
            notes=followup_in.notes,
        )

        self.db.add(followup)
        await self.db.flush()
        await self.db.refresh(followup)

        alerts: List[FollowUpAlert] = []
        if len(abnormal_flags) > 0:
            severity = "medium"
            if len(abnormal_flags) >= 5:
                severity = "high"
            if any("严重" in a for a in alert_details_list):
                severity = "critical"

            main_alert = FollowUpAlert(
                record_id=followup.id,
                recipient_id=followup.recipient_id,
                surgery_id=followup.surgery_id,
                alert_type="lab_abnormal" if len(abnormal_flags) <= 3 else "organ_dysfunction",
                severity=severity,
                title=f"随访异常预警 - {len(abnormal_flags)}项指标异常",
                description="\n".join(alert_details_list[:10]),
                affected_parameter="; ".join(abnormal_flags[:5]),
                triggered_at=followup.followup_date,
            )
            self.db.add(main_alert)
            alerts.append(main_alert)

            for i, flag in enumerate(abnormal_flags[:5]):
                detail = alert_details_list[i] if i < len(alert_details_list) else flag
                alert_type = "lab_abnormal"
                if "肾功能" in flag or "liver" in flag.lower():
                    alert_type = "organ_dysfunction"
                elif "感染" in flag or "infection" in flag.lower():
                    alert_type = "infection"

                single_alert = FollowUpAlert(
                    record_id=followup.id,
                    recipient_id=followup.recipient_id,
                    surgery_id=followup.surgery_id,
                    alert_type=alert_type,
                    severity=severity,
                    title=f"指标异常: {flag}",
                    description=detail,
                    affected_parameter=flag,
                    triggered_at=followup.followup_date,
                )
                self.db.add(single_alert)
                alerts.append(single_alert)

            await self.db.flush()
            await self._notify_doctor(followup, abnormal_flags, alert_details_list)

        return {
            "followup": followup,
            "abnormal_flags": abnormal_flags,
            "alert_details": alert_details_list,
            "alert_triggered": len(abnormal_flags) > 0,
            "alerts_count": len(alerts),
        }

    async def get_followup(self, followup_id: str) -> Optional[FollowUp]:
        result = await self.db.execute(
            select(FollowUp).where(FollowUp.id == followup_id)
        )
        return result.scalar_one_or_none()

    async def list_followups(
        self,
        skip: int = 0,
        limit: int = 100,
        recipient_id: Optional[str] = None,
        surgery_id: Optional[str] = None,
        followup_type: Optional[str] = None,
        alert_triggered: Optional[bool] = None,
        doctor_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[List[FollowUp], int]:
        query = select(FollowUp)

        if recipient_id:
            query = query.where(FollowUp.recipient_id == recipient_id)
        if surgery_id:
            query = query.where(FollowUp.surgery_id == surgery_id)
        if followup_type:
            query = query.where(FollowUp.followup_type == followup_type)
        if alert_triggered is not None:
            query = query.where(FollowUp.alert_triggered == alert_triggered)
        if doctor_id:
            query = query.where(FollowUp.doctor_id == doctor_id)
        if start_date:
            query = query.where(FollowUp.followup_date >= start_date)
        if end_date:
            query = query.where(FollowUp.followup_date <= end_date)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(FollowUp.followup_date.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def detect_abnormalities(
        self,
        followup_data: Dict,
    ) -> Tuple[List[str], List[str]]:
        abnormal_flags: List[str] = []
        alert_detail: List[str] = []

        for category_name, category_data in followup_data.items():
            if not isinstance(category_data, dict):
                continue
            thresholds = FOLLOWUP_ABNORMAL_THRESHOLDS.get(category_name, {})

            for key, threshold in thresholds.items():
                value = category_data.get(key)
                if value is None:
                    continue

                if threshold.get("type") == "negative":
                    if str(value).lower() in ("positive", "阳", "阳性", "1", "true"):
                        abnormal_flags.append(f"{category_name}/{key}")
                        alert_detail.append(
                            f"{threshold.get('name', key)}: 检测为阳性，需高度警惕排斥或感染风险"
                        )
                    continue

                try:
                    num_value = float(value)
                except (TypeError, ValueError):
                    continue

                min_val = threshold.get("min")
                max_val = threshold.get("max")
                unit = threshold.get("unit", "")
                name = threshold.get("name", key)
                is_abnormal = False

                if min_val is not None and num_value < min_val:
                    is_abnormal = True
                    deviation_pct = ((min_val - num_value) / min_val) * 100 if min_val > 0 else 100
                    severity = "严重" if deviation_pct > 30 else "轻度"
                    abnormal_flags.append(f"{category_name}/{key}")
                    alert_detail.append(
                        f"{name}: {num_value}{unit} 低于下限{min_val}{unit} (低{round(deviation_pct,1)}%) [{severity}]"
                    )

                if max_val is not None and num_value > max_val:
                    is_abnormal = True
                    deviation_pct = ((num_val - max_val) / max_val) * 100 if max_val > 0 else 100
                    severity = "严重" if deviation_pct > 50 else "轻度"
                    abnormal_flags.append(f"{category_name}/{key}")
                    alert_detail.append(
                        f"{name}: {num_value}{unit} 高于上限{max_val}{unit} (高{round(deviation_pct,1)}%) [{severity}]"
                    )

        return abnormal_flags, alert_detail

    async def aggregate_followup_data(
        self,
        recipient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[Dict]:
        recipient_result = await self.db.execute(
            select(Recipient).where(Recipient.id == recipient_id)
        )
        recipient = recipient_result.scalar_one_or_none()
        if not recipient:
            return None

        query = select(FollowUp).where(FollowUp.recipient_id == recipient_id)
        if start_date:
            query = query.where(FollowUp.followup_date >= start_date)
        if end_date:
            query = query.where(FollowUp.followup_date <= end_date)
        query = query.order_by(FollowUp.followup_date.asc())

        result = await self.db.execute(query)
        followups = list(result.scalars().all())

        if not followups:
            return {
                "recipient_id": recipient_id,
                "recipient_name": recipient.name,
                "total_followups": 0,
                "period": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None,
                },
                "message": "无随访数据",
            }

        all_abnormal_flags: List[str] = []
        category_totals: Dict[str, Dict] = {}
        trend_data: Dict[str, List[Dict]] = {}
        alert_count = 0

        for fu in followups:
            fu_abnormal = json.loads(fu.abnormal_flags) if fu.abnormal_flags else []
            all_abnormal_flags.extend(fu_abnormal)
            if fu.alert_triggered:
                alert_count += 1

            try:
                fu_data = json.loads(fu.data) if fu.data else {}
            except (json.JSONDecodeError, TypeError):
                fu_data = {}

            for cat_name, cat_data in fu_data.items():
                if not isinstance(cat_data, dict):
                    continue
                if cat_name not in category_totals:
                    category_totals[cat_name] = {"measurements": 0, "abnormal": 0}
                    trend_data[cat_name] = {}
                category_totals[cat_name]["measurements"] += len(cat_data)

                for key, val in cat_data.items():
                    flag_key = f"{cat_name}/{key}"
                    if flag_key in fu_abnormal:
                        category_totals[cat_name]["abnormal"] += 1
                    if key not in trend_data[cat_name]:
                        trend_data[cat_name][key] = []
                    trend_data[cat_name][key].append({
                        "date": fu.followup_date.isoformat(),
                        "value": val,
                    })

        abnormal_flag_counts: Dict[str, int] = {}
        for flag in all_abnormal_flags:
            abnormal_flag_counts[flag] = abnormal_flag_counts.get(flag, 0) + 1

        summary = {
            "recipient_id": recipient_id,
            "recipient_name": recipient.name,
            "total_followups": len(followups),
            "alert_count": alert_count,
            "first_followup": followups[0].followup_date.isoformat(),
            "last_followup": followups[-1].followup_date.isoformat(),
            "period": {
                "start": start_date.isoformat() if start_date else followups[0].followup_date.isoformat(),
                "end": end_date.isoformat() if end_date else followups[-1].followup_date.isoformat(),
            },
            "category_summary": category_totals,
            "abnormal_flag_counts": dict(sorted(
                abnormal_flag_counts.items(), key=lambda x: -x[1]
            )),
            "alert_rate": round(alert_count / len(followups) * 100, 2) if followups else 0,
            "trend_data": trend_data,
            "followup_types": {},
        }

        for fu in followups:
            ft = fu.followup_type
            summary["followup_types"][ft] = summary["followup_types"].get(ft, 0) + 1

        return summary

    async def _notify_doctor(
        self,
        followup: FollowUp,
        abnormal_flags: List[str],
        alert_detail: List[str],
    ) -> bool:
        return True

    async def get_recipient_followup_summary(
        self,
        recipient_id: str,
    ) -> Optional[Dict]:
        recipient_result = await self.db.execute(
            select(Recipient).where(Recipient.id == recipient_id)
        )
        recipient = recipient_result.scalar_one_or_none()
        if not recipient:
            return None

        total_count = await self.db.execute(
            select(func.count(FollowUp.id)).where(FollowUp.recipient_id == recipient_id)
        )
        total = total_count.scalar() or 0

        alert_count = await self.db.execute(
            select(func.count(FollowUp.id)).where(
                FollowUp.recipient_id == recipient_id,
                FollowUp.alert_triggered == True,
            )
        )
        alerts = alert_count.scalar() or 0

        last_result = await self.db.execute(
            select(FollowUp).where(FollowUp.recipient_id == recipient_id)
            .order_by(FollowUp.followup_date.desc()).limit(1)
        )
        last_followup = last_result.scalar_one_or_none()

        today = date.today()
        if last_followup:
            last_fu_date = last_followup.followup_date.date() if isinstance(last_followup.followup_date, datetime) else last_followup.followup_date
            days_since_last = (today - last_fu_date).days
        else:
            days_since_last = None

        scheduled_result = await self.db.execute(
            select(Surgery).where(Surgery.recipient_id == recipient_id)
        )
        surgeries = list(scheduled_result.scalars().all())
        has_surgery = len(surgeries) > 0

        next_due_days = None
        if has_surgery and surgeries[0].surgery_date:
            surgery_dt = surgeries[0].surgery_date
            if isinstance(surgery_dt, datetime):
                surgery_date = surgery_dt.date()
            else:
                surgery_date = surgery_dt

            months_post_op = (today.year - surgery_date.year) * 12 + (today.month - surgery_date.month)
            if months_post_op <= 1:
                next_due_days = 7
            elif months_post_op <= 3:
                next_due_days = 14
            elif months_post_op <= 12:
                next_due_days = 30
            else:
                next_due_days = 90

        overdue_days = None
        if days_since_last is not None and next_due_days is not None:
            if days_since_last > next_due_days:
                overdue_days = days_since_last - next_due_days

        return {
            "recipient_id": recipient_id,
            "recipient_name": recipient.name,
            "status": recipient.status,
            "total_followups": total,
            "alert_followups": alerts,
            "alert_rate": round(alerts / total * 100, 2) if total > 0 else 0,
            "last_followup_date": last_followup.followup_date.isoformat() if last_followup else None,
            "days_since_last_followup": days_since_last,
            "next_followup_due_days": next_due_days,
            "is_overdue": overdue_days is not None and overdue_days > 0,
            "overdue_days": overdue_days,
            "last_followup_had_alert": last_followup.alert_triggered if last_followup else False,
            "recommendation": await self._get_followup_recommendation(
                recipient, total, alerts, days_since_last, overdue_days
            ),
        }

    async def _get_followup_recommendation(
        self,
        recipient: Recipient,
        total_followups: int,
        alert_count: int,
        days_since_last: Optional[int],
        overdue_days: Optional[int],
    ) -> List[str]:
        recommendations: List[str] = []

        if total_followups == 0:
            recommendations.append("建议尽快安排首次术后随访评估")
            return recommendations

        if overdue_days and overdue_days > 0:
            recommendations.append(f"随访已超期{overdue_days}天，请立即安排复诊")

        if alert_count > 0:
            alert_rate = alert_count / total_followups
            if alert_rate > 0.5:
                recommendations.append(f"异常率达{round(alert_rate*100,1)}%，建议加强监测频率并考虑专科会诊")
            elif alert_rate > 0.2:
                recommendations.append(f"异常率{round(alert_rate*100,1)}%，建议关注异常指标趋势")

        if days_since_last and days_since_last > 180:
            recommendations.append("超过半年未随访，建议进行全面评估")

        if not recommendations:
            recommendations.append("随访情况良好，请继续保持定期复查")

        return recommendations

    async def list_recipients_needing_followup(
        self,
        limit: int = 100,
    ) -> List[Dict]:
        today = date.today()

        surgeries_result = await self.db.execute(
            select(Surgery, Recipient)
            .join(Recipient, Surgery.recipient_id == Recipient.id)
            .where(Recipient.status == "transplanted")
            .order_by(Surgery.surgery_date.desc())
            .limit(limit * 2)
        )
        surgery_rows = surgeries_result.all()

        needing_followup: List[Dict] = []

        for surgery, recipient in surgery_rows:
            if not surgery.surgery_date:
                continue
            surgery_dt = surgery.surgery_date
            if isinstance(surgery_dt, datetime):
                surgery_date = surgery_dt.date()
            else:
                surgery_date = surgery_dt

            last_fu_result = await self.db.execute(
                select(FollowUp).where(FollowUp.recipient_id == recipient.id)
                .order_by(FollowUp.followup_date.desc()).limit(1)
            )
            last_followup = last_fu_result.scalar_one_or_none()

            months_post_op = (today.year - surgery_date.year) * 12 + (today.month - surgery_date.month)
            if months_post_op <= 1:
                expected_interval = 7
            elif months_post_op <= 3:
                expected_interval = 14
            elif months_post_op <= 12:
                expected_interval = 30
            else:
                expected_interval = 90

            if last_followup:
                last_fu_dt = last_followup.followup_date
                if isinstance(last_fu_dt, datetime):
                    last_fu_date = last_fu_dt.date()
                else:
                    last_fu_date = last_fu_dt
                days_since = (today - last_fu_date).days
            else:
                days_since = (today - surgery_date).days

            is_overdue = days_since > expected_interval
            days_overdue = days_since - expected_interval if is_overdue else 0

            if is_overdue or (days_since > expected_interval * 0.8):
                needing_followup.append({
                    "recipient_id": recipient.id,
                    "recipient_name": recipient.name,
                    "organ_type_needed": recipient.organ_type_needed,
                    "transplant_center_id": recipient.transplant_center_id,
                    "doctor_id": recipient.doctor_id,
                    "surgery_date": surgery_date.isoformat(),
                    "months_post_op": months_post_op,
                    "last_followup_date": (
                        last_followup.followup_date.isoformat() if last_followup else None
                    ),
                    "days_since_last_followup": days_since,
                    "expected_interval_days": expected_interval,
                    "is_overdue": is_overdue,
                    "days_overdue": days_overdue if is_overdue else 0,
                    "urgency": (
                        "critical" if days_overdue > expected_interval
                        else "high" if days_overdue > expected_interval * 0.5
                        else "medium" if is_overdue
                        else "low"
                    ),
                })

            if len(needing_followup) >= limit:
                break

        needing_followup.sort(key=lambda x: -x.get("days_overdue", 0))
        return needing_followup
