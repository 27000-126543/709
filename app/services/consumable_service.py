from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple, Dict
from datetime import datetime
import json
import uuid

from app.models import Consumable
from app.schemas.consumable import (
    ConsumableCreate,
    ConsumableUpdate,
    ReplenishmentRequestCreate,
    ReplenishmentRequestUpdate,
)
from app.schemas.common import (
    ConsumableStatus,
    ReplenishmentStatus,
    ConsumableCategory,
)


class ConsumableService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_consumable(self, consumable_in: ConsumableCreate) -> Consumable:
        consumable = Consumable(
            name=consumable_in.name,
            category=consumable_in.category.value,
            stock_quantity=consumable_in.stock_quantity,
            safety_stock_level=consumable_in.safety_stock_level,
            unit=consumable_in.unit,
            unit_price=consumable_in.unit_price,
            supplier=consumable_in.supplier,
            status="normal",
            outbound_quota_locked=0,
        )

        self.db.add(consumable)
        await self.db.flush()
        await self.db.refresh(consumable)

        await self._check_safety_stock(consumable)
        return consumable

    async def get_consumable(self, consumable_id: str) -> Optional[Consumable]:
        result = await self.db.execute(
            select(Consumable).where(Consumable.id == consumable_id)
        )
        return result.scalar_one_or_none()

    async def list_consumables(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        status: Optional[str] = None,
        low_stock_only: bool = False,
    ) -> Tuple[List[Consumable], int]:
        query = select(Consumable)

        if category:
            query = query.where(Consumable.category == category)
        if status:
            query = query.where(Consumable.status == status)
        if low_stock_only:
            query = query.where(
                Consumable.stock_quantity <= Consumable.safety_stock_level
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Consumable.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_consumable(
        self,
        consumable_id: str,
        consumable_in: ConsumableUpdate,
    ) -> Optional[Consumable]:
        consumable = await self.get_consumable(consumable_id)
        if not consumable:
            return None

        update_data = consumable_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(consumable, key, value)

        await self._check_safety_stock(consumable)
        await self.db.flush()
        await self.db.refresh(consumable)
        return consumable

    async def delete_consumable(self, consumable_id: str) -> bool:
        consumable = await self.get_consumable(consumable_id)
        if not consumable:
            return False
        await self.db.delete(consumable)
        await self.db.flush()
        return True

    async def _check_safety_stock(self, consumable: Consumable) -> Dict:
        available = consumable.stock_quantity - consumable.outbound_quota_locked
        safety_level = consumable.safety_stock_level

        result = {
            "consumable_id": consumable.id,
            "name": consumable.name,
            "current_stock": consumable.stock_quantity,
            "locked_quota": consumable.outbound_quota_locked,
            "available": available,
            "safety_level": safety_level,
            "below_safety": available < safety_level,
            "action": None,
        }

        if consumable.status in ("replenishing",) and consumable.replenishment_status in (
            "pending", "approved", "procuring"
        ):
            result["action"] = "replenishment_in_progress"
            return result

        if available < safety_level:
            critical_threshold = safety_level * 0.3
            if available <= critical_threshold:
                consumable.status = "critical"
                result["action"] = "auto_replenishment_critical"
            else:
                consumable.status = "low"
                result["action"] = "auto_replenishment_low"

            replenish_qty = max(
                safety_level * 3 - available,
                safety_level,
            )
            result["suggested_replenish_qty"] = int(replenish_qty)

            if consumable.replenishment_status not in ("pending", "approved", "procuring"):
                await self._create_auto_replenishment(consumable, int(replenish_qty))
        else:
            if consumable.status in ("low", "critical"):
                consumable.status = "normal"
                result["action"] = "status_restored_normal"

        return result

    async def _create_auto_replenishment(
        self,
        consumable: Consumable,
        quantity: int,
    ) -> Dict:
        request_id = uuid.uuid4().hex

        consumable.replenishment_request_id = request_id
        consumable.replenishment_status = "pending"

        await self.db.flush()
        await self.db.refresh(consumable)

        return {
            "replenishment_request_id": request_id,
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "requested_quantity": quantity,
            "status": "pending",
            "supplier": consumable.supplier,
            "unit_price": consumable.unit_price,
            "estimated_cost": quantity * (consumable.unit_price or 0),
            "reason": f"安全库存自动补货: 现有{consumable.stock_quantity}{consumable.unit}, 安全水位{consumable.safety_stock_level}{consumable.unit}",
            "created_at": datetime.utcnow().isoformat(),
        }

    async def check_all_safety_stocks(self) -> List[Dict]:
        result = await self.db.execute(select(Consumable))
        consumables = list(result.scalars().all())

        alerts: List[Dict] = []
        for c in consumables:
            check_result = await self._check_safety_stock(c)
            if check_result.get("below_safety"):
                alerts.append(check_result)

        await self.db.flush()
        alerts.sort(key=lambda x: x["available"] / max(x["safety_level"], 1))
        return alerts

    async def create_replenishment_request(
        self,
        request_in: ReplenishmentRequestCreate,
    ) -> Optional[Dict]:
        consumable = await self.get_consumable(str(request_in.consumable_id))
        if not consumable:
            return None

        request_id = uuid.uuid4().hex

        consumable.replenishment_request_id = request_id
        consumable.replenishment_status = "pending"
        consumable.status = "replenishing"

        await self.db.flush()
        await self.db.refresh(consumable)

        return {
            "replenishment_request_id": request_id,
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "category": consumable.category,
            "requested_quantity": request_in.requested_quantity,
            "unit": consumable.unit,
            "reason": request_in.reason,
            "status": "pending_approval",
            "supplier": consumable.supplier,
            "unit_price": consumable.unit_price,
            "estimated_cost": request_in.requested_quantity * (consumable.unit_price or 0),
            "created_by": "system",
            "created_at": datetime.utcnow().isoformat(),
        }

    async def approve_replenishment(
        self,
        consumable_id: str,
        approver_id: str,
        approver_name: str,
        approved_quantity: Optional[int] = None,
        approval_notes: Optional[str] = None,
    ) -> Optional[Dict]:
        consumable = await self.get_consumable(consumable_id)
        if not consumable:
            return None

        if consumable.replenishment_status != "pending":
            return {
                "success": False,
                "error": f"当前补货状态为'{consumable.replenishment_status}', 无法审批",
                "consumable_id": consumable_id,
            }

        consumable.replenishment_status = "approved"

        await self._sync_purchase_order(consumable, approved_quantity, approver_id)

        await self.db.flush()
        await self.db.refresh(consumable)

        return {
            "success": True,
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "replenishment_request_id": consumable.replenishment_request_id,
            "approved_quantity": approved_quantity,
            "approver_id": approver_id,
            "approver_name": approver_name,
            "approval_notes": approval_notes,
            "status": "approved",
            "next_step": "采购同步中",
            "approved_at": datetime.utcnow().isoformat(),
        }

    async def reject_replenishment(
        self,
        consumable_id: str,
        rejecter_id: str,
        rejecter_name: str,
        rejection_reason: str,
    ) -> Optional[Dict]:
        consumable = await self.get_consumable(consumable_id)
        if not consumable:
            return None

        if consumable.replenishment_status != "pending":
            return {
                "success": False,
                "error": f"当前补货状态为'{consumable.replenishment_status}', 无法拒绝",
            }

        consumable.replenishment_status = "none"
        consumable.replenishment_request_id = None

        available = consumable.stock_quantity - consumable.outbound_quota_locked
        if available < consumable.safety_stock_level * 0.3:
            consumable.status = "critical"
        elif available < consumable.safety_stock_level:
            consumable.status = "low"
        else:
            consumable.status = "normal"

        await self.db.flush()
        await self.db.refresh(consumable)

        return {
            "success": True,
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "replenishment_request_id": consumable.replenishment_request_id,
            "rejecter_id": rejecter_id,
            "rejecter_name": rejecter_name,
            "rejection_reason": rejection_reason,
            "status": "rejected",
            "rejected_at": datetime.utcnow().isoformat(),
        }

    async def _sync_purchase_order(
        self,
        consumable: Consumable,
        quantity: Optional[int],
        approver_id: str,
    ) -> Dict:
        if consumable.replenishment_status == "approved":
            consumable.replenishment_status = "procuring"

        return {
            "purchase_order_id": f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "supplier": consumable.supplier,
            "unit_price": consumable.unit_price,
            "order_quantity": quantity or consumable.safety_stock_level * 3,
            "status": "synced_to_supplier",
            "synced_by": approver_id,
            "synced_at": datetime.utcnow().isoformat(),
        }

    async def confirm_purchase_arrival(
        self,
        consumable_id: str,
        arrived_quantity: int,
        batch_number: Optional[str] = None,
        arrival_notes: Optional[str] = None,
    ) -> Optional[Dict]:
        consumable = await self.get_consumable(consumable_id)
        if not consumable:
            return None

        consumable.stock_quantity += arrived_quantity
        consumable.replenishment_status = "arrived"

        available = consumable.stock_quantity - consumable.outbound_quota_locked
        if available >= consumable.safety_stock_level:
            consumable.status = "normal"
            consumable.replenishment_status = "none"
            consumable.replenishment_request_id = None

        await self.db.flush()
        await self.db.refresh(consumable)

        return {
            "success": True,
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "arrived_quantity": arrived_quantity,
            "unit": consumable.unit,
            "new_stock_quantity": consumable.stock_quantity,
            "batch_number": batch_number,
            "arrival_notes": arrival_notes,
            "status": consumable.status,
            "arrived_at": datetime.utcnow().isoformat(),
        }

    async def lock_outbound_quota(
        self,
        consumable_id: str,
        quantity: int,
        lock_reason: str,
        allocation_id: Optional[str] = None,
        transplant_center_id: Optional[str] = None,
    ) -> Optional[Dict]:
        consumable = await self.get_consumable(consumable_id)
        if not consumable:
            return None

        available = consumable.stock_quantity - consumable.outbound_quota_locked
        if quantity > available:
            return {
                "success": False,
                "error": f"可用库存不足: 需要{quantity}{consumable.unit}, 实际可用{available}{consumable.unit}",
                "consumable_id": consumable_id,
                "requested": quantity,
                "available": available,
            }

        consumable.outbound_quota_locked += quantity

        await self._check_safety_stock(consumable)
        await self.db.flush()
        await self.db.refresh(consumable)

        return {
            "success": True,
            "lock_id": f"LOCK-{uuid.uuid4().hex[:12].upper()}",
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "locked_quantity": quantity,
            "unit": consumable.unit,
            "lock_reason": lock_reason,
            "allocation_id": allocation_id,
            "transplant_center_id": transplant_center_id,
            "remaining_stock": consumable.stock_quantity,
            "remaining_available": consumable.stock_quantity - consumable.outbound_quota_locked,
            "total_locked": consumable.outbound_quota_locked,
            "locked_at": datetime.utcnow().isoformat(),
        }

    async def unlock_outbound_quota(
        self,
        consumable_id: str,
        quantity: int,
        unlock_reason: str,
    ) -> Optional[Dict]:
        consumable = await self.get_consumable(consumable_id)
        if not consumable:
            return None

        if quantity > consumable.outbound_quota_locked:
            return {
                "success": False,
                "error": f"解锁数量超过已锁定数量: 解锁{quantity}, 已锁定{consumable.outbound_quota_locked}",
            }

        consumable.outbound_quota_locked -= quantity
        await self._check_safety_stock(consumable)

        await self.db.flush()
        await self.db.refresh(consumable)

        return {
            "success": True,
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "unlocked_quantity": quantity,
            "unit": consumable.unit,
            "unlock_reason": unlock_reason,
            "remaining_locked": consumable.outbound_quota_locked,
            "available": consumable.stock_quantity - consumable.outbound_quota_locked,
            "unlocked_at": datetime.utcnow().isoformat(),
        }

    async def confirm_outbound(
        self,
        consumable_id: str,
        quantity: int,
        recipient_info: Dict,
    ) -> Optional[Dict]:
        consumable = await self.get_consumable(consumable_id)
        if not consumable:
            return None

        if quantity > consumable.outbound_quota_locked:
            return {
                "success": False,
                "error": f"出库数量超过锁定配额: 出库{quantity}, 已锁定{consumable.outbound_quota_locked}",
            }

        consumable.stock_quantity -= quantity
        consumable.outbound_quota_locked -= quantity

        await self._check_safety_stock(consumable)
        await self.db.flush()
        await self.db.refresh(consumable)

        return {
            "success": True,
            "outbound_id": f"OUT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "outbound_quantity": quantity,
            "unit": consumable.unit,
            "unit_price": consumable.unit_price,
            "total_cost": quantity * (consumable.unit_price or 0),
            "recipient_info": recipient_info,
            "remaining_stock": consumable.stock_quantity,
            "outbound_at": datetime.utcnow().isoformat(),
        }

    async def get_inventory_summary(self) -> Dict:
        result = await self.db.execute(
            select(
                func.count(Consumable.id),
                func.sum(Consumable.stock_quantity),
                func.sum(Consumable.stock_quantity * Consumable.unit_price),
                func.count(Consumable.id).filter(Consumable.status == "normal"),
                func.count(Consumable.id).filter(Consumable.status == "low"),
                func.count(Consumable.id).filter(Consumable.status == "critical"),
                func.count(Consumable.id).filter(Consumable.status == "replenishing"),
                func.count(Consumable.id).filter(Consumable.replenishment_status == "pending"),
                func.count(Consumable.id).filter(Consumable.replenishment_status == "procuring"),
                func.sum(Consumable.outbound_quota_locked),
            )
        )
        row = result.first() or ()

        categories_result = await self.db.execute(
            select(
                Consumable.category,
                func.count(Consumable.id),
                func.sum(Consumable.stock_quantity),
            ).group_by(Consumable.category)
        )
        category_breakdown = []
        for cat_row in categories_result.all():
            category_breakdown.append({
                "category": cat_row[0],
                "item_count": cat_row[1] or 0,
                "total_quantity": cat_row[2] or 0,
            })

        return {
            "summary_date": datetime.utcnow().isoformat(),
            "total_items": row[0] or 0,
            "total_quantity": row[1] or 0,
            "total_value": round(row[2] or 0, 2),
            "status_breakdown": {
                "normal": row[3] or 0,
                "low_stock": row[4] or 0,
                "critical": row[5] or 0,
                "replenishing": row[6] or 0,
            },
            "replenishment_pipeline": {
                "pending_approval": row[7] or 0,
                "in_procurement": row[8] or 0,
            },
            "total_locked_quota": row[9] or 0,
            "available_quantity": (row[1] or 0) - (row[9] or 0),
            "category_breakdown": category_breakdown,
        }

    async def batch_import_stock(
        self,
        import_items: List[Dict],
    ) -> Dict:
        success_count = 0
        fail_count = 0
        errors: List[Dict] = []
        results: List[Dict] = []

        for idx, item in enumerate(import_items):
            try:
                consumable_id = item.get("consumable_id") or item.get("id")
                delta = item.get("quantity_delta") or item.get("adjustment_quantity") or 0
                reason = item.get("reason") or "批量导入调整"

                if not consumable_id:
                    fail_count += 1
                    errors.append({"index": idx, "error": "缺少consumable_id"})
                    continue

                consumable = await self.get_consumable(str(consumable_id))
                if not consumable:
                    fail_count += 1
                    errors.append({"index": idx, "error": f"耗材不存在: {consumable_id}"})
                    continue

                new_qty = consumable.stock_quantity + delta
                if new_qty < 0:
                    fail_count += 1
                    errors.append({"index": idx, "error": f"调整后数量为负: {new_qty}"})
                    continue

                consumable.stock_quantity = new_qty
                await self._check_safety_stock(consumable)

                results.append({
                    "index": idx,
                    "consumable_id": consumable.id,
                    "name": consumable.name,
                    "delta": delta,
                    "new_quantity": consumable.stock_quantity,
                    "reason": reason,
                })
                success_count += 1
            except Exception as e:
                fail_count += 1
                errors.append({"index": idx, "error": str(e)})

        await self.db.flush()

        return {
            "imported_at": datetime.utcnow().isoformat(),
            "total_items": len(import_items),
            "success_count": success_count,
            "fail_count": fail_count,
            "success_results": results,
            "errors": errors,
        }
