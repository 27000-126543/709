from fastapi import APIRouter
from typing import List

from app.routers.donor import router as donor_router
from app.routers.recipient import router as recipient_router
from app.routers.organ import router as organ_router
from app.routers.match import router as match_router
from app.routers.allocation import router as allocation_router
from app.routers.transport import router as transport_router
from app.routers.approval import router as approval_router
from app.routers.surgery import router as surgery_router
from app.routers.followup import router as followup_router
from app.routers.consumable import router as consumable_router
from app.routers.report import router as report_router
from app.routers.center import router as center_router
from app.routers.notification import router as notification_router


def get_routers() -> List[APIRouter]:
    return [
        donor_router,
        recipient_router,
        organ_router,
        match_router,
        allocation_router,
        transport_router,
        approval_router,
        surgery_router,
        followup_router,
        consumable_router,
        report_router,
        center_router,
        notification_router,
    ]


__all__ = ["get_routers"]
