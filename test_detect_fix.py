import sys
sys.path.insert(0, '.')
import asyncio

async def test():
    from app.services.followup_service import FollowUpService, FOLLOWUP_ABNORMAL_THRESHOLDS
    
    service = FollowUpService.__new__(FollowUpService)
    service.db = None
    
    test_data = {
        "kidney_function": {"creatinine": 200, "urea": 10},
        "liver_function": {"alt": 120, "ast": 65},
        "infection_markers": {"crp": 50, "procalcitonin": 2.5},
    }
    
    flags, details = await service.detect_abnormalities(test_data)
    print(f"✅ 异常项数量: {len(flags)}")
    for i, f in enumerate(flags):
        print(f"  {i+1}. {f}")
        if i < len(details):
            print(f"     {details[i]}")
    
    assert len(flags) >= 6, f"应该检测到至少6项异常，实际只有{len(flags)}项"
    print("\n✅ 检测逻辑正常工作！")

asyncio.run(test())
