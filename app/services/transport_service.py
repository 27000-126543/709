from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta
import json

from app.models import Transport, Allocation, Organ
from app.schemas.transport import TransportCreate, TransportUpdate
from app.schemas.common import AlertType
from app.config import get_settings
from app.services.matching_utils import haversine_distance

settings = get_settings()


class TransportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_transport(self, transport_in: TransportCreate) -> Optional[Transport]:
        alloc_result = await self.db.execute(
            select(Allocation).where(Allocation.id == str(transport_in.allocation_id))
        )
        allocation = alloc_result.scalar_one_or_none()
        if not allocation:
            return None

        organ_result = await self.db.execute(
            select(Organ).where(Organ.id == str(transport_in.organ_id))
        )
        organ = organ_result.scalar_one_or_none()
        if not organ:
            return None

        transport = Transport(
            allocation_id=str(transport_in.allocation_id),
            organ_id=str(transport_in.organ_id),
            retrieval_team_id=str(transport_in.retrieval_team_id),
            origin_hospital=transport_in.origin_hospital,
            destination_hospital=transport_in.destination_hospital,
            status="pending",
            estimated_arrival=transport_in.estimated_arrival,
            alert_triggered=False,
            emergency_plan_activated=False,
            route_deviation_km=0.0,
        )

        self.db.add(transport)
        await self.db.flush()
        await self.db.refresh(transport)

        if organ:
            organ.status = "in_transit"

        await self.db.flush()
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
        retrieval_team_id: Optional[str] = None,
        alert_triggered: Optional[bool] = None,
    ) -> Tuple[List[Transport], int]:
        query = select(Transport)

        if status:
            query = query.where(Transport.status == status)
        if retrieval_team_id:
            query = query.where(Transport.retrieval_team_id == retrieval_team_id)
        if alert_triggered is not None:
            query = query.where(Transport.alert_triggered == alert_triggered)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Transport.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_transport_status(
        self,
        transport_id: str,
        transport_in: TransportUpdate,
    ) -> Optional[Dict]:
        transport = await self.get_transport(transport_id)
        if not transport:
            return None

        prev_lat = transport.current_latitude
        prev_lon = transport.current_longitude
        prev_temp = transport.current_temperature

        update_data = transport_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(transport, key, value)

        if "status" in update_data and update_data["status"] == "in_progress":
            if not transport.departure_time:
                transport.departure_time = datetime.utcnow()

            organ_result = await self.db.execute(
                select(Organ).where(Organ.id == transport.organ_id)
            )
            organ = organ_result.scalar_one_or_none()
            if organ:
                organ.status = "in_transit"
                if not organ.retrieval_time:
                    organ.retrieval_time = datetime.utcnow()

        if "status" in update_data and update_data["status"] == "delivered":
            transport.actual_arrival = datetime.utcnow()
            organ_result = await self.db.execute(
                select(Organ).where(Organ.id == transport.organ_id)
            )
            organ = organ_result.scalar_one_or_none()
            if organ:
                organ.status = "delivered"

        alerts: List[Dict] = []

        temp_alert = self._check_temperature(transport.current_temperature)
        if temp_alert:
            alerts.append(temp_alert)

        route_alert = self._check_route_deviation(transport.route_deviation_km)
        if route_alert:
            alerts.append(route_alert)

        location_alert = self._check_location_deviation(
            prev_lat, prev_lon,
            transport.current_latitude, transport.current_longitude,
        )
        if location_alert:
            alerts.append(location_alert)

        if alerts:
            result = await self.trigger_alert(transport_id, alerts)
            return result

        await self.db.flush()
        await self.db.refresh(transport)

        return {
            "transport": transport,
            "alerts": [],
            "emergency_activated": False,
        }

    def _check_temperature(self, current_temp: Optional[float]) -> Optional[Dict]:
        if current_temp is None:
            return None

        temp_min = settings.TRANSPORT_TEMP_MIN
        temp_max = settings.TRANSPORT_TEMP_MAX

        if current_temp < temp_min or current_temp > temp_max:
            severity = "critical" if abs(current_temp - (temp_min + temp_max) / 2) > 5 else "warning"
            return {
                "alert_type": AlertType.temperature.value,
                "severity": severity,
                "detail": (
                    f"温度异常: 当前{current_temp}°C, 正常范围{temp_min}-{temp_max}°C, "
                    f"偏差{round(abs(current_temp - temp_min if current_temp < temp_min else current_temp - temp_max), 2)}°C"
                ),
                "data": {
                    "current": current_temp,
                    "min": temp_min,
                    "max": temp_max,
                },
            }
        return None

    def _check_route_deviation(self, deviation_km: Optional[float]) -> Optional[Dict]:
        if deviation_km is None or deviation_km <= settings.TRANSPORT_MAX_DEVIATION_KM:
            return None

        return {
            "alert_type": AlertType.route_deviation.value,
            "severity": "warning" if deviation_km < settings.TRANSPORT_MAX_DEVIATION_KM * 2 else "critical",
            "detail": (
                f"路线偏离: 当前偏离{round(deviation_km, 2)}km, 阈值{settings.TRANSPORT_MAX_DEVIATION_KM}km"
            ),
            "data": {
                "deviation_km": deviation_km,
                "threshold_km": settings.TRANSPORT_MAX_DEVIATION_KM,
            },
        }

    def _check_location_deviation(
        self,
        prev_lat: Optional[float],
        prev_lon: Optional[float],
        curr_lat: Optional[float],
        curr_lon: Optional[float],
    ) -> Optional[Dict]:
        if None in (prev_lat, prev_lon, curr_lat, curr_lon):
            return None

        distance = haversine_distance(prev_lat, prev_lon, curr_lat, curr_lon)

        max_expected_distance_km = 100.0
        if distance > max_expected_distance_km:
            return {
                "alert_type": AlertType.route_deviation.value,
                "severity": "warning",
                "detail": (
                    f"位置异常: 短时间移动{round(distance, 2)}km, 超过预期阈值{max_expected_distance_km}km"
                ),
                "data": {
                    "distance_jumped_km": distance,
                    "prev_coords": (prev_lat, prev_lon),
                    "curr_coords": (curr_lat, curr_lon),
                },
            }
        return None

    async def trigger_alert(
        self,
        transport_id: str,
        alerts: List[Dict],
    ) -> Dict:
        transport = await self.get_transport(transport_id)
        if not transport:
            return {"success": False, "error": "Transport not found"}

        transport.alert_triggered = True

        alert_types = list(set(a["alert_type"] for a in alerts))
        transport.alert_type = ",".join(alert_types)
        transport.alert_detail = json.dumps(alerts, ensure_ascii=False)

        has_critical = any(a.get("severity") == "critical" for a in alerts)
        emergency_activated = False

        if has_critical:
            emergency_result = await self.activate_emergency_plan(transport_id, alerts)
            emergency_activated = emergency_result.get("activated", False)

        if has_critical:
            transport.status = "emergency"

        await self.db.flush()
        await self.db.refresh(transport)

        await self._notify_stakeholders(transport, alerts, emergency_activated)

        return {
            "success": True,
            "transport": transport,
            "alerts": alerts,
            "emergency_activated": emergency_activated,
            "notifications_sent": await self._build_notification_targets(transport),
        }

    async def activate_emergency_plan(
        self,
        transport_id: str,
        alerts: List[Dict],
    ) -> Dict:
        transport = await self.get_transport(transport_id)
        if not transport:
            return {"activated": False, "error": "Transport not found"}

        transport.emergency_plan_activated = True

        plan_steps = []
        for alert in alerts:
            alert_type = alert.get("alert_type")
            if alert_type == AlertType.temperature.value:
                plan_steps.append({
                    "step": 1,
                    "action": "检查冷藏设备运行状态",
                    "priority": "high",
                    "responsible": "运输团队",
                })
                plan_steps.append({
                    "step": 2,
                    "action": "准备备用冷藏箱和冰袋",
                    "priority": "high",
                    "responsible": "运输团队",
                })
                plan_steps.append({
                    "step": 3,
                    "action": "联系就近移植中心准备临时接收",
                    "priority": "medium",
                    "responsible": "调度协调员",
                })
            elif alert_type == AlertType.route_deviation.value:
                plan_steps.append({
                    "step": 1,
                    "action": "重新规划最优运输路线",
                    "priority": "high",
                    "responsible": "运输团队+导航系统",
                })
                plan_steps.append({
                    "step": 2,
                    "action": "通知目的地医院预计到达时间变更",
                    "priority": "high",
                    "responsible": "调度协调员",
                })
            elif alert_type == AlertType.delay.value:
                plan_steps.append({
                    "step": 1,
                    "action": "评估器官冷缺血剩余时间",
                    "priority": "high",
                    "responsible": "器官获取外科医生",
                })
                plan_steps.append({
                    "step": 2,
                    "action": "协调备用运输方案(直升机/高铁)",
                    "priority": "high",
                    "responsible": "调度协调员",
                })

        transport.emergency_plan_detail = json.dumps({
            "triggered_at": datetime.utcnow().isoformat(),
            "trigger_alerts": alerts,
            "plan_steps": plan_steps,
            "status": "in_progress",
        }, ensure_ascii=False)

        await self.db.flush()
        await self.db.refresh(transport)

        return {
            "activated": True,
            "transport_id": transport.id,
            "plan_steps": plan_steps,
        }

    async def _notify_stakeholders(
        self,
        transport: Transport,
        alerts: List[Dict],
        emergency_activated: bool,
    ) -> bool:
        return True

    async def _build_notification_targets(self, transport: Transport) -> List[Dict]:
        targets = []
        if transport.retrieval_team_id:
            targets.append({
                "recipient_type": "transport_team",
                "recipient_id": transport.retrieval_team_id,
                "role": "运输团队",
            })

        allocation_result = await self.db.execute(
            select(Allocation).where(Allocation.id == transport.allocation_id)
        )
        allocation = allocation_result.scalar_one_or_none()
        if allocation:
            if allocation.transplant_center_id:
                targets.append({
                    "recipient_type": "transplant_center",
                    "recipient_id": allocation.transplant_center_id,
                    "role": "移植中心",
                })
            targets.append({
                "recipient_type": "coordinator",
                "recipient_id": "coordinator_dispatch",
                "role": "调度协调员",
            })

        return targets

    async def resolve_alert(
        self,
        transport_id: str,
        resolution_notes: str,
    ) -> Optional[Transport]:
        transport = await self.get_transport(transport_id)
        if not transport:
            return None

        transport.alert_triggered = False
        old_detail = json.loads(transport.alert_detail) if transport.alert_detail else {}
        old_detail["resolved_at"] = datetime.utcnow().isoformat()
        old_detail["resolution_notes"] = resolution_notes
        transport.alert_detail = json.dumps(old_detail, ensure_ascii=False)

        if transport.status == "emergency":
            transport.status = "in_progress"

        await self.db.flush()
        await self.db.refresh(transport)
        return transport

    async def deactivate_emergency_plan(
        self,
        transport_id: str,
        deactivation_notes: str,
    ) -> Optional[Transport]:
        transport = await self.get_transport(transport_id)
        if not transport:
            return None

        transport.emergency_plan_activated = False
        old_detail = json.loads(transport.emergency_plan_detail) if transport.emergency_plan_detail else {}
        old_detail["deactivated_at"] = datetime.utcnow().isoformat()
        old_detail["deactivation_notes"] = deactivation_notes
        old_detail["status"] = "completed"
        transport.emergency_plan_detail = json.dumps(old_detail, ensure_ascii=False)

        await self.db.flush()
        await self.db.refresh(transport)
        return transport

    async def check_for_timed_out_transports(self) -> List[Transport]:
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Transport).where(
                Transport.status.in_(["pending", "in_progress"]),
                Transport.estimated_arrival < now,
            )
        )
        transports = list(result.scalars().all())

        for transport in transports:
            if not transport.alert_triggered:
                await self.trigger_alert(
                    transport.id,
                    [{
                        "alert_type": AlertType.delay.value,
                        "severity": "warning",
                        "detail": (
                            f"运输超时: 预计到达{transport.estimated_arrival.isoformat()}, "
                            f"已超时{round((now - transport.estimated_arrival).total_seconds() / 60, 1)}分钟"
                        ),
                    }],
                )

        return transports

    async def delete_transport(self, transport_id: str) -> bool:
        transport = await self.get_transport(transport_id)
        if not transport:
            return False
        await self.db.delete(transport)
        await self.db.flush()
        return True

    async def list_active_transports_with_alerts(self) -> List[Transport]:
        result = await self.db.execute(
            select(Transport).where(
                Transport.status.in_(["pending", "in_progress", "emergency"])
            ).order_by(Transport.alert_triggered.desc(), Transport.updated_at.desc())
        )
        return list(result.scalars().all())
