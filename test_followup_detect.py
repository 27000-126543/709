import sys
sys.path.insert(0, '.')

from app.services.followup_service import FOLLOWUP_ABNORMAL_THRESHOLDS
import asyncio

async def test():
    from app.services.followup_service import FollowUpService
    from sqlalchemy.ext.asyncio import AsyncSession
    
    service = FollowUpService.__new__(FollowUpService)
    service.db = None
    
    test_data = {
        "kidney_function": {"creatinine": 200},
        "liver_function": {"alt": 120},
        "infection_markers": {"crp": 50},
    }
    
    flags, details = await service.detect_abnormalities(test_data)
    print(f"异常项数量: {len(flags)}")
    for i, f in enumerate(flags):
        print(f"  {i+1}. {f}")
        if i < len(details):
            print(f"     {details[i]}")
    
    print(f"\n详细: {details}")

asyncio.run(test())
