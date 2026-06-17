from app.schemas import *

print("所有Schema导入成功!")
print(f"共导出 {len(__all__)} 个类")
print("\n导出列表:")
for item in __all__:
    print(f"  - {item}")
