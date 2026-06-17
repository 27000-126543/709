from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Optional, List, Tuple, Dict
from datetime import datetime
import json
import uuid

from app.models import Consumable, ReplenishmentRequest, ConsumableTransaction
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
        available = consumable.stock_quantity - (consumable.outbound_quota_locked or 0)
        safety_level = consumable.safety_stock_level or 0

        result = {
            "consumable_id": consumable.id,
            "name": consumable.name,
            "current_stock": consumable.stock_quantity,
            "locked_quota": consumable.outbound_quota_locked or 0,
            "available": available,
            "safety_level": safety_level,
            "below_safety": available < safety_level,
            "action": None,
        }

        if consumable.replenishment_request_id:
            try:
                existing_req = await self.db.execute(
                    select(ReplenishmentRequest).where(
                        ReplenishmentRequest.id == consumable.replenishment_request_id,
                        ReplenishmentRequest.status.in_(["submitted", "under_review", "approved", "ordered", "shipped", "partially_received"]),
                    )
                )
                if existing_req.scalar_one_or_none():
                    result["action"] = "replenishment_in_progress"
                    return result
            except Exception:
                pass

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

            try:
                await self._create_auto_replenishment(consumable, int(replenish_qty))
            except Exception:
                pass
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
        try:
            existing = await self.db.execute(
                select(ReplenishmentRequest).where(
                    ReplenishmentRequest.consumable_id == consumable.id,
                    ReplenishmentRequest.status.in_(["submitted", "under_review", "approved", "ordered", "shipped", "partially_received"]),
                )
            )
            if existing.scalar_one_or_none():
                return {"replenishment_request_id": None, "skipped": True, "reason": "已有进行中的补货申请"}
        except Exception:
            return {"replenishment_request_id": None, "skipped": True, "reason": "检查现有申请失败"}

        available = (consumable.stock_quantity or 0) - (consumable.outbound_quota_locked or 0)
        urgency = "routine"
        try:
            safety_level = consumable.safety_stock_level or 0
            if available <= safety_level * 0.3:
                urgency = "emergency"
            elif available <= safety_level * 0.6:
                urgency = "urgent"
        except Exception:
            pass

        request = None
        try:
            request = ReplenishmentRequest(
                consumable_id=consumable.id,
                request_code=f"AUTO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
                requested_quantity=quantity,
                current_stock=consumable.stock_quantity,
                safety_stock=consumable.safety_stock_level,
                urgency_level=urgency,
                supplier=consumable.supplier,
                estimated_cost=float(quantity) * float(consumable.unit_price or 0),
                status="submitted",
                requested_by="auto_system",
                requested_by_id="system_auto",
                notes=f"安全库存自动补货: 现有{consumable.stock_quantity}{consumable.unit}, 安全水位{consumable.safety_stock_level}{consumable.unit}, 可用{available}{consumable.unit}",
            )
            self.db.add(request)
            await self.db.flush()
            await self.db.refresh(request)
        except Exception as e:
            return {"replenishment_request_id": None, "skipped": True, "reason": f"创建补货申请失败: {str(e)}"}

        try:
            consumable.replenishment_request_id = request.id
            consumable.replenishment_status = "replenishing"
            await self.db.flush()
            await self.db.refresh(consumable)
        except Exception:
            pass

        return {
            "replenishment_request_id": request.id,
            "request_code": request.request_code,
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "requested_quantity": quantity,
            "status": request.status,
            "urgency_level": urgency,
            "supplier": consumable.supplier,
            "unit_price": consumable.unit_price,
            "estimated_cost": request.estimated_cost,
            "reason": request.notes,
            "created_at": request.created_at.isoformat() if request.created_at else None,
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

        request = None
        try:
            request = ReplenishmentRequest(
                consumable_id=consumable.id,
                request_code=f"MANUAL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
                requested_quantity=request_in.requested_quantity,
                current_stock=consumable.stock_quantity,
                safety_stock=consumable.safety_stock_level,
                urgency_level="routine",
                supplier=consumable.supplier,
                estimated_cost=float(request_in.requested_quantity) * float(consumable.unit_price or 0),
                status="submitted",
                requested_by=str(request_in.requested_by)[:100] if hasattr(request_in, 'requested_by') and request_in.requested_by else "manual",
                requested_by_id=str(request_in.requested_by) if hasattr(request_in, 'requested_by') and request_in.requested_by else None,
                notes=request_in.reason if hasattr(request_in, 'reason') and request_in.reason else "手动补货申请",
                expected_delivery_date=request_in.expected_arrival_date if hasattr(request_in, 'expected_arrival_date') else None,
            )
            self.db.add(request)
            await self.db.flush()
            await self.db.refresh(request)
        except Exception as e:
            return {"error": f"创建补货申请失败: {str(e)}"}

        try:
            consumable.replenishment_request_id = request.id
            consumable.replenishment_status = "replenishing"
            if consumable.status not in ("replenishing", "low", "critical"):
                consumable.status = "replenishing"
            await self.db.flush()
            await self.db.refresh(consumable)
        except Exception:
            pass

        return {
            "replenishment_request_id": request.id,
            "request_code": request.request_code,
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "category": consumable.category,
            "requested_quantity": request.requested_quantity,
            "unit": consumable.unit,
            "reason": request.notes,
            "status": request.status,
            "supplier": consumable.supplier,
            "unit_price": consumable.unit_price,
            "estimated_cost": request.estimated_cost,
            "created_by": request.requested_by,
            "created_at": request.created_at.isoformat() if request.created_at else None,
        }

    async def approve_replenishment(
        self,
        request_id: str,
        approver_id: str,
        approver_name: str,
        approved_quantity: Optional[int] = None,
        approval_notes: Optional[str] = None,
    ) -> Optional[Dict]:
        req_result = await self.db.execute(
            select(ReplenishmentRequest).where(ReplenishmentRequest.id == request_id)
        )
        request = req_result.scalar_one_or_none()
        if not request:
            return {"success": False, "error": "补货申请不存在"}

        if request.status not in ("submitted", "under_review"):
            return {
                "success": False,
                "error": f"当前申请状态为'{request.status}', 无法审批",
                "request_id": request_id,
            }

        consumable = await self.get_consumable(request.consumable_id)

        try:
            request.status = "approved"
            request.approved_by = str(approver_name)[:100] if approver_name else None
            request.approved_by_id = str(approver_id) if approver_id else None
            request.approved_at = datetime.utcnow()
            request.notes = (request.notes or "") + (f"\n审批备注: {approval_notes}" if approval_notes else "")
            if approved_quantity:
                request.requested_quantity = approved_quantity
            await self.db.flush()
            await self.db.refresh(request)
        except Exception as e:
            return {"success": False, "error": f"审批失败: {str(e)}"}

        try:
            if consumable:
                consumable.replenishment_status = "approved"
                await self.db.flush()
                await self.db.refresh(consumable)
        except Exception:
            pass

        return {
            "success": True,
            "consumable_id": request.consumable_id,
            "consumable_name": consumable.name if consumable else "",
            "replenishment_request_id": request.id,
            "request_code": request.request_code,
            "approved_quantity": request.requested_quantity,
            "approver_id": approver_id,
            "approver_name": approver_name,
            "approval_notes": approval_notes,
            "status": "approved",
            "next_step": "已通过审批，请安排采购下单",
            "approved_at": request.approved_at.isoformat() if request.approved_at else None,
        }

    async def reject_replenishment(
        self,
        request_id: str,
        rejecter_id: str,
        rejecter_name: str,
        rejection_reason: str,
    ) -> Optional[Dict]:
        req_result = await self.db.execute(
            select(ReplenishmentRequest).where(ReplenishmentRequest.id == request_id)
        )
        request = req_result.scalar_one_or_none()
        if not request:
            return {"success": False, "error": "补货申请不存在"}

        if request.status not in ("submitted", "under_review"):
            return {
                "success": False,
                "error": f"当前申请状态为'{request.status}', 无法拒绝",
                "request_id": request_id,
            }

        consumable = await self.get_consumable(request.consumable_id)

        try:
            request.status = "rejected"
            request.rejected_by = str(rejecter_name)[:100] if rejecter_name else None
            request.rejected_at = datetime.utcnow()
            request.rejection_reason = rejection_reason
            await self.db.flush()
            await self.db.refresh(request)
        except Exception as e:
            return {"success": False, "error": f"拒绝失败: {str(e)}"}

        try:
            if consumable:
                consumable.replenishment_status = "none"
                consumable.replenishment_request_id = None
                available = (consumable.stock_quantity or 0) - (consumable.outbound_quota_locked or 0)
                if available < (consumable.safety_stock_level or 0) * 0.3:
                    consumable.status = "critical"
                elif available < (consumable.safety_stock_level or 0):
                    consumable.status = "low"
                else:
                    consumable.status = "normal"
                await self.db.flush()
                await self.db.refresh(consumable)
        except Exception:
            pass

        return {
            "success": True,
            "consumable_id": request.consumable_id,
            "consumable_name": consumable.name if consumable else "",
            "replenishment_request_id": request.id,
            "request_code": request.request_code,
            "rejecter_id": rejecter_id,
            "rejecter_name": rejecter_name,
            "rejection_reason": rejection_reason,
            "status": "rejected",
            "rejected_at": request.rejected_at.isoformat() if request.rejected_at else None,
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
        request_id: str,
        arrived_quantity: int,
        received_by: Optional[str] = None,
        batch_number: Optional[str] = None,
        arrival_notes: Optional[str] = None,
    ) -> Optional[Dict]:
        req_result = await self.db.execute(
            select(ReplenishmentRequest).where(ReplenishmentRequest.id == request_id)
        )
        request = req_result.scalar_one_or_none()
        if not request:
            return {"success": False, "error": "补货申请不存在"}

        if request.status not in ("ordered", "shipped", "approved", "partially_received"):
            return {
                "success": False,
                "error": f"当前申请状态为'{request.status}', 无法确认到货",
                "request_id": request_id,
            }

        consumable = await self.get_consumable(request.consumable_id)
        if not consumable:
            return {"success": False, "error": "耗材不存在"}

        try:
            request.status = "received"
            request.received_quantity = (request.received_quantity or 0) + arrived_quantity
            request.received_date = datetime.utcnow()
            request.received_by = str(received_by)[:100] if received_by else None
            request.notes = (request.notes or "") + (f"\n到货备注: {arrival_notes}" if arrival_notes else "") + (f"\n批次号: {batch_number}" if batch_number else "")
            await self.db.flush()
            await self.db.refresh(request)
        except Exception as e:
            return {"success": False, "error": f"确认到货失败: {str(e)}"}

        txn_id = None
        try:
            consumable.stock_quantity = (consumable.stock_quantity or 0) + arrived_quantity

            transaction = ConsumableTransaction(
                consumable_id=consumable.id,
                transaction_type="replenishment",
                quantity=arrived_quantity,
                reference_id=str(request.id),
                notes=f"补货入库, 申请单: {request.request_code}, 批次: {batch_number or '-'}",
            )
            self.db.add(transaction)
            await self.db.flush()
            await self.db.refresh(transaction)
            txn_id = transaction.id

            available = consumable.stock_quantity - (consumable.outbound_quota_locked or 0)
            if available >= (consumable.safety_stock_level or 0):
                consumable.status = "normal"
                consumable.replenishment_status = "completed"
                consumable.replenishment_request_id = None
            else:
                consumable.status = "low"
                consumable.replenishment_status = "partially"
            await self.db.flush()
            await self.db.refresh(consumable)
        except Exception:
            pass

        return {
            "success": True,
            "consumable_id": consumable.id,
            "consumable_name": consumable.name,
            "replenishment_request_id": request.id,
            "request_code": request.request_code,
            "arrived_quantity": arrived_quantity,
            "total_received": request.received_quantity,
            "unit": consumable.unit,
            "new_stock_quantity": consumable.stock_quantity,
            "batch_number": batch_number,
            "arrival_notes": arrival_notes,
            "transaction_id": txn_id,
            "consumable_status": consumable.status,
            "replenishment_status": request.status,
            "arrived_at": request.received_date.isoformat() if request.received_date else None,
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
