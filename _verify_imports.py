import sys
import traceback

modules = [
    "app.config",
    "app.database",
    "app.models",
    "app.models.donor",
    "app.models.recipient",
    "app.models.organ",
    "app.models.match",
    "app.models.allocation",
    "app.models.transport",
    "app.models.approval",
    "app.models.surgery",
    "app.models.followup",
    "app.models.consumable",
    "app.models.report",
    "app.models.center",
    "app.models.notification",
    "app.schemas",
    "app.schemas.common",
    "app.schemas.donor",
    "app.schemas.recipient",
    "app.schemas.organ",
    "app.schemas.match",
    "app.schemas.allocation",
    "app.schemas.transport",
    "app.schemas.approval",
    "app.schemas.surgery",
    "app.schemas.followup",
    "app.schemas.consumable",
    "app.schemas.report",
    "app.schemas.center",
    "app.schemas.notification",
    "app.services",
    "app.services.matching_utils",
    "app.services.donor_service",
    "app.services.match_engine",
    "app.services.allocation_service",
    "app.services.transport_service",
    "app.services.approval_service",
    "app.services.surgery_service",
    "app.services.followup_service",
    "app.services.consumable_service",
    "app.services.report_service",
    "app.services.notification_service",
    "app.routers",
    "app.routers.donor",
    "app.routers.recipient",
    "app.routers.organ",
    "app.routers.match",
    "app.routers.allocation",
    "app.routers.transport",
    "app.routers.approval",
    "app.routers.surgery",
    "app.routers.followup",
    "app.routers.consumable",
    "app.routers.report",
    "app.routers.center",
    "app.routers.notification",
    "app.utils",
    "app.utils.scheduler",
    "app.utils.excel_exporter",
    "main",
]

ok = 0
fails = []
for m in modules:
    try:
        __import__(m)
        ok += 1
    except Exception as e:
        fails.append((m, str(e), traceback.format_exc()))

print(f"OK: {ok}/{len(modules)}")
for m, err, tb in fails:
    print(f"\n==== FAIL {m} ====")
    print(f"Error: {err}")
    print(f"Traceback:\n{tb}")
    print("=" * 50)
