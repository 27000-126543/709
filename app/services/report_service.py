from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_
from typing import Optional, List, Tuple, Dict
from datetime import datetime, date, timedelta
import json
import io
import csv

from app.models import Donor, Allocation, Transport, Recipient, Consumable, Surgery, Organ
from app.schemas.report import ReportQuery, ReportData, ReportResponse


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_daily_report(
        self,
        report_date: Optional[date] = None,
        province: Optional[str] = None,
        transplant_center_id: Optional[str] = None,
    ) -> ReportResponse:
        if report_date is None:
            report_date = date.today()

        start_dt = datetime.combine(report_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)

        donor_query = select(Donor)
        allocation_query = select(Allocation)
        transport_query = select(Transport)
        recipient_query = select(Recipient)
        consumable_query = select(Consumable)

        if province:
            donor_query = donor_query.where(Donor.province == province)
            allocation_query = allocation_query.where(Allocation.province == province)

        donor_result = await self.db.execute(donor_query)
        all_donors = list(donor_result.scalars().all())

        allocation_result = await self.db.execute(allocation_query)
        all_allocations = list(allocation_result.scalars().all())

        transport_result = await self.db.execute(transport_query)
        all_transports = list(transport_result.scalars().all())

        recipient_result = await self.db.execute(recipient_query)
        all_recipients = list(recipient_result.scalars().all())

        consumable_result = await self.db.execute(consumable_query)
        all_consumables = list(consumable_result.scalars().all())

        province_groups: Dict[str, Dict[str, List]] = {}
        for donor in all_donors:
            p = donor.province or "未知"
            if p not in province_groups:
                province_groups[p] = {"donors": [], "allocations": [], "transports": [], "consumables": []}
            province_groups[p]["donors"].append(donor)

        center_groups: Dict[str, Dict[str, List]] = {}
        for alloc in all_allocations:
            cid = alloc.transplant_center_id or "未知中心"
            if cid not in center_groups:
                center_groups[cid] = {"allocations": [], "surgeries": [], "recipients": []}
            center_groups[cid]["allocations"].append(alloc)

        transplant_centers_map: Dict[str, Dict[str, List]] = {}
        for alloc in all_allocations:
            p = alloc.province or "未知"
            cid = alloc.transplant_center_id or "未知中心"
            key = f"{p}|{cid}"
            if key not in transplant_centers_map:
                transplant_centers_map[key] = {"province": p, "center_id": cid, "allocations": [], "transports": []}
            transplant_centers_map[key]["allocations"].append(alloc)

        for t in all_transports:
            for key, data in transplant_centers_map.items():
                alloc_ids = [a.id for a in data["allocations"]]
                if t.allocation_id in alloc_ids:
                    data["transports"].append(t)
                    break

        report_data_items: List[ReportData] = []

        for key, center_data in transplant_centers_map.items():
            p = center_data["province"]
            cid = center_data["center_id"]
            if province and p != province:
                continue
            if transplant_center_id and str(cid) != str(transplant_center_id):
                continue

            allocations = center_data["allocations"]
            transports = center_data["transports"]

            donation_count = sum(
                1 for d in all_donors if d.province == p
                and d.created_at >= start_dt and d.created_at < end_dt
            )

            donor_count_total = len([d for d in all_donors if d.province == p])

            total_allocs = len(allocations)
            completed_allocs = len([a for a in allocations if a.status == "completed"])
            allocation_success_rate = (
                round(completed_allocs / total_allocs * 100, 2)
                if total_allocs > 0 else 0.0
            )

            total_transports = len(transports)
            on_time_transports = 0
            for t in transports:
                if t.estimated_arrival and t.actual_arrival:
                    if t.actual_arrival <= t.estimated_arrival:
                        on_time_transports += 1
                elif t.status == "delivered":
                    on_time_transports += 1
            transport_on_time_rate = (
                round(on_time_transports / total_transports * 100, 2)
                if total_transports > 0 else 0.0
            )

            transplanted_recipients = [
                r for r in all_recipients
                if r.transplant_center_id == cid and r.status == "transplanted"
            ]
            deceased_count = len([
                r for r in all_recipients
                if r.transplant_center_id == cid and r.status == "deceased"
            ])
            total_transplanted = len(transplanted_recipients) + deceased_count
            if total_transplanted > 0:
                recipient_survival_rate = round(
                    len(transplanted_recipients) / total_transplanted * 100, 2
                )
            else:
                recipient_survival_rate = 100.0 if len(transplanted_recipients) > 0 else 0.0

            consumable_consumption: Dict[str, float] = {}
            for cat in ["surgical", "preservation", "testing", "general"]:
                cat_items = [c for c in all_consumables if c.category == cat]
                total_value = sum(
                    (c.unit_price or 0) * max(0, (
                        (c.stock_quantity or 0) + 0
                    ))
                    for c in cat_items
                )
                consumable_consumption[cat] = round(total_value, 2)
                consumable_consumption[f"{cat}_count"] = len(cat_items)

            center_name = f"移植中心-{cid}"

            rd = ReportData(
                province=p,
                transplant_center_id=int(cid) if str(cid).isdigit() else cid,
                transplant_center_name=center_name,
                donation_count=donation_count,
                allocation_success_rate=allocation_success_rate,
                transport_on_time_rate=transport_on_time_rate,
                recipient_survival_rate=recipient_survival_rate,
                consumable_consumption=consumable_consumption,
            )
            report_data_items.append(rd)

        report_data_items.sort(key=lambda x: (-x.allocation_success_rate, x.province))

        return ReportResponse(
            report_date=report_date,
            generated_at=datetime.utcnow(),
            data=report_data_items,
        )

    async def get_report_overview(
        self,
        start_date: date,
        end_date: date,
        province: Optional[str] = None,
    ) -> Dict:
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        donor_query = select(
            func.count(Donor.id),
            func.count(Donor.id).filter(Donor.status == "verified"),
            func.count(Donor.id).filter(Donor.status == "rejected"),
            func.count(Donor.id).filter(Donor.status == "organ_retrieved"),
        ).where(Donor.created_at >= start_dt, Donor.created_at <= end_dt)

        if province:
            donor_query = donor_query.where(Donor.province == province)

        donor_stats = (await self.db.execute(donor_query)).first() or (0, 0, 0, 0)

        organ_query = select(
            func.count(Organ.id),
            func.count(Organ.id).filter(Organ.status == "available"),
            func.count(Organ.id).filter(Organ.status == "allocated"),
            func.count(Organ.id).filter(Organ.status == "transplanted"),
            func.count(Organ.id).filter(Organ.status == "discarded"),
        )
        organ_stats = (await self.db.execute(organ_query)).first() or (0, 0, 0, 0, 0)

        allocation_query = select(
            func.count(Allocation.id),
            func.count(Allocation.id).filter(Allocation.status == "pending"),
            func.count(Allocation.id).filter(Allocation.status == "provincial_approved"),
            func.count(Allocation.id).filter(Allocation.status == "national_approved"),
            func.count(Allocation.id).filter(Allocation.status == "completed"),
            func.count(Allocation.id).filter(Allocation.status == "rejected"),
        ).where(Allocation.created_at >= start_dt, Allocation.created_at <= end_dt)
        if province:
            allocation_query = allocation_query.where(Allocation.province == province)
        alloc_stats = (await self.db.execute(allocation_query)).first() or (0, 0, 0, 0, 0, 0)

        transport_query = select(
            func.count(Transport.id),
            func.count(Transport.id).filter(Transport.status == "pending"),
            func.count(Transport.id).filter(Transport.status == "in_progress"),
            func.count(Transport.id).filter(Transport.status == "delivered"),
            func.count(Transport.id).filter(Transport.alert_triggered == True),
            func.count(Transport.id).filter(Transport.emergency_plan_activated == True),
        )
        transport_stats = (await self.db.execute(transport_query)).first() or (0, 0, 0, 0, 0, 0)

        recipient_query = select(
            func.count(Recipient.id),
            func.count(Recipient.id).filter(Recipient.status == "waiting"),
            func.count(Recipient.id).filter(Recipient.status == "matched"),
            func.count(Recipient.id).filter(Recipient.status == "transplanted"),
            func.count(Recipient.id).filter(Recipient.status == "deceased"),
        )
        recipient_stats = (await self.db.execute(recipient_query)).first() or (0, 0, 0, 0, 0)

        surgery_query = select(
            func.count(Surgery.id),
            func.count(Surgery.id).filter(Surgery.surgery_status == "scheduled"),
            func.count(Surgery.id).filter(Surgery.surgery_status == "in_progress"),
            func.count(Surgery.id).filter(Surgery.surgery_status == "completed"),
            func.count(Surgery.id).filter(Surgery.preop_check_status == "passed"),
            func.count(Surgery.id).filter(Surgery.preop_check_status == "recheck_recommended"),
        ).where(Surgery.created_at >= start_dt, Surgery.created_at <= end_dt)
        surgery_stats = (await self.db.execute(surgery_query)).first() or (0, 0, 0, 0, 0, 0)

        total_alloc = alloc_stats[0] or 0
        completed_alloc = alloc_stats[4] or 0
        total_transport = transport_stats[0] or 0
        delivered_transport = transport_stats[3] or 0

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": (end_date - start_date).days + 1,
            },
            "donor_stats": {
                "total_registered": donor_stats[0] or 0,
                "verified": donor_stats[1] or 0,
                "rejected": donor_stats[2] or 0,
                "organs_retrieved": donor_stats[3] or 0,
                "verification_rate": round(
                    (donor_stats[1] or 0) / max(donor_stats[0] or 1, 1) * 100, 2
                ),
            },
            "organ_stats": {
                "total_organs": organ_stats[0] or 0,
                "available": organ_stats[1] or 0,
                "allocated": organ_stats[2] or 0,
                "transplanted": organ_stats[3] or 0,
                "discarded": organ_stats[4] or 0,
                "utilization_rate": round(
                    (organ_stats[3] or 0) / max(organ_stats[0] or 1, 1) * 100, 2
                ),
            },
            "allocation_stats": {
                "total": total_alloc,
                "pending": alloc_stats[1] or 0,
                "provincial_approved": alloc_stats[2] or 0,
                "national_approved": alloc_stats[3] or 0,
                "completed": completed_alloc,
                "rejected": alloc_stats[5] or 0,
                "success_rate": round(
                    completed_alloc / max(total_alloc, 1) * 100, 2
                ),
            },
            "transport_stats": {
                "total": total_transport,
                "pending": transport_stats[1] or 0,
                "in_progress": transport_stats[2] or 0,
                "delivered": delivered_transport,
                "alerts": transport_stats[4] or 0,
                "emergencies": transport_stats[5] or 0,
                "on_time_rate": round(
                    delivered_transport / max(total_transport, 1) * 100, 2
                ),
            },
            "recipient_stats": {
                "total": recipient_stats[0] or 0,
                "waiting": recipient_stats[1] or 0,
                "matched": recipient_stats[2] or 0,
                "transplanted": recipient_stats[3] or 0,
                "deceased": recipient_stats[4] or 0,
                "survival_rate": round(
                    (recipient_stats[3] or 0) / max(
                        (recipient_stats[3] or 0) + (recipient_stats[4] or 0), 1
                    ) * 100, 2
                ),
            },
            "surgery_stats": {
                "total": surgery_stats[0] or 0,
                "scheduled": surgery_stats[1] or 0,
                "in_progress": surgery_stats[2] or 0,
                "completed": surgery_stats[3] or 0,
                "preop_passed": surgery_stats[4] or 0,
                "preop_recheck_needed": surgery_stats[5] or 0,
                "completion_rate": round(
                    (surgery_stats[3] or 0) / max(surgery_stats[0] or 1, 1) * 100, 2
                ),
            },
            "kpis": {
                "donor_per_day": round((donor_stats[0] or 0) / max((end_date - start_date).days + 1, 1), 2),
                "organ_yield": round((organ_stats[0] or 0) / max(donor_stats[0] or 1, 1), 2),
                "avg_matching_score": 0.0,
                "approval_cycle_hours": 0.0,
            },
        }

    async def export_report_to_excel(
        self,
        report: ReportResponse,
    ) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([f"全国器官捐献与移植运营报表 - {report.report_date.isoformat()}"])
        writer.writerow([f"生成时间: {report.generated_at.isoformat()}"])
        writer.writerow([])

        headers = [
            "省份",
            "移植中心ID",
            "移植中心名称",
            "捐献量(例)",
            "分配成功率(%)",
            "运输准时率(%)",
            "受者存活率(%)",
            "耗材-外科类",
            "耗材-保存类",
            "耗材-检测类",
            "耗材-通用类",
        ]
        writer.writerow(headers)

        for rd in report.data:
            cc = rd.consumable_consumption or {}
            writer.writerow([
                rd.province,
                rd.transplant_center_id,
                rd.transplant_center_name,
                rd.donation_count,
                rd.allocation_success_rate,
                rd.transport_on_time_rate,
                rd.recipient_survival_rate,
                cc.get("surgical", 0),
                cc.get("preservation", 0),
                cc.get("testing", 0),
                cc.get("general", 0),
            ])

        writer.writerow([])
        writer.writerow(["汇总统计"])

        total_donation = sum(rd.donation_count for rd in report.data)
        avg_alloc = round(
            sum(rd.allocation_success_rate for rd in report.data) / max(len(report.data), 1), 2
        )
        avg_transport = round(
            sum(rd.transport_on_time_rate for rd in report.data) / max(len(report.data), 1), 2
        )
        avg_survival = round(
            sum(rd.recipient_survival_rate for rd in report.data) / max(len(report.data), 1), 2
        )

        writer.writerow(["中心数量", len(report.data)])
        writer.writerow(["总捐献量", total_donation])
        writer.writerow(["平均分配成功率", f"{avg_alloc}%"])
        writer.writerow(["平均运输准时率", f"{avg_transport}%"])
        writer.writerow(["平均受者存活率", f"{avg_survival}%"])

        csv_bytes = output.getvalue().encode("utf-8-sig")

        excel_header = b"Excel-Report:"
        return excel_header + csv_bytes

    async def export_report_to_csv(
        self,
        report: ReportResponse,
    ) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)

        headers = [
            "省份",
            "移植中心ID",
            "移植中心名称",
            "捐献量",
            "分配成功率(%)",
            "运输准时率(%)",
            "受者存活率(%)",
            "外科耗材",
            "保存耗材",
            "检测耗材",
            "通用耗材",
        ]
        writer.writerow(headers)

        for rd in report.data:
            cc = rd.consumable_consumption or {}
            writer.writerow([
                rd.province,
                rd.transplant_center_id,
                rd.transplant_center_name,
                rd.donation_count,
                rd.allocation_success_rate,
                rd.transport_on_time_rate,
                rd.recipient_survival_rate,
                cc.get("surgical", 0),
                cc.get("preservation", 0),
                cc.get("testing", 0),
                cc.get("general", 0),
            ])

        return output.getvalue().encode("utf-8-sig")

    async def get_province_rankings(
        self,
        start_date: date,
        end_date: date,
        metric: str = "donation_count",
        top_n: int = 10,
    ) -> List[Dict]:
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        donor_query = select(Donor).where(
            Donor.created_at >= start_dt, Donor.created_at <= end_dt
        )
        donor_result = await self.db.execute(donor_query)
        donors = list(donor_result.scalars().all())

        province_stats: Dict[str, Dict] = {}
        for d in donors:
            p = d.province or "未知"
            if p not in province_stats:
                province_stats[p] = {
                    "province": p,
                    "donation_count": 0,
                    "verified": 0,
                    "rejected": 0,
                }
            province_stats[p]["donation_count"] += 1
            if d.status == "verified":
                province_stats[p]["verified"] += 1
            elif d.status == "rejected":
                province_stats[p]["rejected"] += 1

        alloc_query = select(Allocation).where(
            Allocation.created_at >= start_dt, Allocation.created_at <= end_dt
        )
        alloc_result = await self.db.execute(alloc_query)
        allocations = list(alloc_result.scalars().all())

        for a in allocations:
            p = a.province or "未知"
            if p not in province_stats:
                province_stats[p] = {
                    "province": p, "donation_count": 0, "verified": 0, "rejected": 0
                }
            if "allocation_count" not in province_stats[p]:
                province_stats[p]["allocation_count"] = 0
                province_stats[p]["allocation_completed"] = 0
            province_stats[p]["allocation_count"] += 1
            if a.status == "completed":
                province_stats[p]["allocation_completed"] += 1

        rankings = list(province_stats.values())

        for r in rankings:
            dc = r.get("donation_count", 0)
            if dc > 0:
                r["verification_rate"] = round(
                    r.get("verified", 0) / dc * 100, 2
                )
            else:
                r["verification_rate"] = 0.0
            ac = r.get("allocation_count", 0)
            if ac > 0:
                r["allocation_success_rate"] = round(
                    r.get("allocation_completed", 0) / ac * 100, 2
                )
            else:
                r["allocation_success_rate"] = 0.0

        reverse = True
        if metric in ["rejected"]:
            reverse = False
        rankings.sort(key=lambda x: x.get(metric, 0), reverse=reverse)

        for i, r in enumerate(rankings[:top_n]):
            r["rank"] = i + 1

        return rankings[:top_n]

    async def get_center_rankings(
        self,
        start_date: date,
        end_date: date,
        metric: str = "allocation_success_rate",
        top_n: int = 20,
    ) -> List[Dict]:
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        alloc_query = select(Allocation).where(
            Allocation.created_at >= start_dt, Allocation.created_at <= end_dt
        )
        alloc_result = await self.db.execute(alloc_query)
        allocations = list(alloc_result.scalars().all())

        center_stats: Dict[str, Dict] = {}
        for a in allocations:
            cid = a.transplant_center_id or "未知"
            if cid not in center_stats:
                center_stats[cid] = {
                    "center_id": cid,
                    "province": a.province or "未知",
                    "allocation_count": 0,
                    "allocation_completed": 0,
                    "allocation_rejected": 0,
                }
            center_stats[cid]["allocation_count"] += 1
            if a.status == "completed":
                center_stats[cid]["allocation_completed"] += 1
            elif a.status == "rejected":
                center_stats[cid]["allocation_rejected"] += 1

        transport_query = select(Transport)
        transport_result = await self.db.execute(transport_query)
        transports = list(transport_result.scalars().all())

        alloc_center_map = {a.id: a.transplant_center_id for a in allocations}
        for t in transports:
            cid = alloc_center_map.get(t.allocation_id)
            if cid:
                if cid not in center_stats:
                    center_stats[cid] = {"center_id": cid, "province": "未知"}
                if "transport_total" not in center_stats[cid]:
                    center_stats[cid]["transport_total"] = 0
                    center_stats[cid]["transport_delivered"] = 0
                    center_stats[cid]["transport_ontime"] = 0
                center_stats[cid]["transport_total"] += 1
                if t.status == "delivered":
                    center_stats[cid]["transport_delivered"] += 1
                    if t.actual_arrival and t.estimated_arrival and t.actual_arrival <= t.estimated_arrival:
                        center_stats[cid]["transport_ontime"] += 1

        rankings = list(center_stats.values())

        for r in rankings:
            ac = r.get("allocation_count", 0)
            if ac > 0:
                r["allocation_success_rate"] = round(
                    r.get("allocation_completed", 0) / ac * 100, 2
                )
            else:
                r["allocation_success_rate"] = 0.0
            tt = r.get("transport_total", 0)
            if tt > 0:
                r["transport_on_time_rate"] = round(
                    r.get("transport_ontime", 0) / tt * 100, 2
                )
            else:
                r["transport_on_time_rate"] = 0.0

        rankings.sort(key=lambda x: x.get(metric, 0), reverse=True)

        for i, r in enumerate(rankings[:top_n]):
            r["rank"] = i + 1

        return rankings[:top_n]
