import ast
import os
import sys

files_to_check = [
    "app/schemas/__init__.py",
    "app/schemas/match.py",
    "app/schemas/report.py",
    "app/models/__init__.py",
    "app/models/followup.py",
    "app/services/matching_utils.py",
    "app/services/donor_service.py",
    "app/services/__init__.py",
    "app/services/match_engine.py",
    "app/services/allocation_service.py",
    "app/services/transport_service.py",
    "app/services/approval_service.py",
    "app/services/surgery_service.py",
    "app/services/followup_service.py",
    "app/services/consumable_service.py",
    "app/services/report_service.py",
    "app/routers/notification.py",
]

print("=" * 60)
print("AST 语法检查")
print("=" * 60)

ok = 0
fails = []
for f in files_to_check:
    full_path = os.path.join(os.path.dirname(__file__), f)
    try:
        with open(full_path, "r", encoding="utf-8") as fp:
            source = fp.read()
        ast.parse(source, filename=f)
        print(f"[OK] {f}")
        ok += 1
    except SyntaxError as e:
        fails.append((f, str(e)))
        print(f"[FAIL] {f}")
        print(f"  Error: {e}")
    except Exception as e:
        fails.append((f, str(e)))
        print(f"[FAIL] {f}")
        print(f"  Error: {e}")

print()
print(f"结果: {ok}/{len(files_to_check)} 通过")
if fails:
    print()
    print("错误详情:")
    for f, err in fails:
        print(f"  - {f}: {err}")
    sys.exit(1)
