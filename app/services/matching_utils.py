import math
import json
from typing import Optional

from app.schemas.common import BloodType
from app.config import get_settings

settings = get_settings()


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def parse_hla(hla_str: Optional[str]) -> dict:
    if not hla_str:
        return {"A": [], "B": [], "DR": [], "C": [], "DQ": [], "DP": []}
    try:
        if isinstance(hla_str, str):
            try:
                return json.loads(hla_str)
            except json.JSONDecodeError:
                pass
        loci = {"A": [], "B": [], "DR": [], "C": [], "DQ": [], "DP": []}
        parts = hla_str.replace("，", ",").split(",")
        for part in parts:
            part = part.strip()
            for locus in loci:
                if part.upper().startswith(locus):
                    allele = part[len(locus):].strip("*: ")
                    if allele:
                        loci[locus].append(allele)
                    break
        return loci
    except Exception:
        return {"A": [], "B": [], "DR": [], "C": [], "DQ": [], "DP": []}


def hla_match_score(donor_hla_str: Optional[str], recipient_hla_str: Optional[str]) -> tuple[int, int]:
    donor_hla = parse_hla(donor_hla_str)
    recipient_hla = parse_hla(recipient_hla_str)

    matched = 0
    total = 0
    important_loci = ["A", "B", "DR"]

    for locus in important_loci:
        donor_alleles = donor_hla.get(locus, [])
        recipient_alleles = recipient_hla.get(locus, [])
        total += 2

        d_set = set()
        for a in donor_alleles:
            base = a.split(":")[0] if ":" in a else a
            d_set.add(base)

        r_set = set()
        for a in recipient_alleles:
            base = a.split(":")[0] if ":" in a else a
            r_set.add(base)

        for allele in d_set:
            if allele in r_set:
                matched += min(2, len([a for a in donor_alleles if a.startswith(allele)]))

    if total == 0:
        return 0, 6

    return min(matched, 6), 6


def hla_score_normalized(donor_hla: Optional[str], recipient_hla: Optional[str]) -> float:
    matched, total = hla_match_score(donor_hla, recipient_hla)
    if total == 0:
        return 0.5
    return matched / total


def is_blood_compatible(donor_blood: str, recipient_blood: str) -> bool:
    compatibility = {
        BloodType.O.value: [BloodType.A.value, BloodType.B.value, BloodType.AB.value, BloodType.O.value],
        BloodType.A.value: [BloodType.A.value, BloodType.AB.value],
        BloodType.B.value: [BloodType.B.value, BloodType.AB.value],
        BloodType.AB.value: [BloodType.AB.value],
    }
    return recipient_blood in compatibility.get(donor_blood, [])


def blood_type_score(donor_blood: str, recipient_blood: str) -> float:
    if donor_blood == recipient_blood:
        return 1.0
    if is_blood_compatible(donor_blood, recipient_blood):
        return 0.7
    return 0.0


def pra_score(recipient_pra: Optional[float]) -> float:
    if recipient_pra is None:
        return 1.0
    pra = max(0.0, min(100.0, recipient_pra))
    return (100.0 - pra) / 100.0


def geography_score(distance_km: float, max_reference_km: float = 2000.0) -> float:
    if distance_km <= 0:
        return 1.0
    if distance_km >= max_reference_km:
        return 0.0
    return 1.0 - (distance_km / max_reference_km)


URGENCY_SCORE_MAP = {
    "emergency": 1.0,
    "priority": 0.75,
    "routine": 0.4,
}


def urgency_score(urgency_level: str) -> float:
    return URGENCY_SCORE_MAP.get(urgency_level, 0.0)


PROVINCE_COORDS = {
    "北京市": (39.9042, 116.4074),
    "天津市": (39.3434, 117.3616),
    "上海市": (31.2304, 121.4737),
    "重庆市": (29.5630, 106.5516),
    "河北省": (38.0428, 114.5149),
    "山西省": (37.8706, 112.5489),
    "辽宁省": (41.8057, 123.4315),
    "吉林省": (43.8171, 125.3235),
    "黑龙江省": (45.8038, 126.5350),
    "江苏省": (32.0603, 118.7969),
    "浙江省": (30.2741, 120.1551),
    "安徽省": (31.8206, 117.2272),
    "福建省": (26.0745, 119.2965),
    "江西省": (28.6820, 115.8579),
    "山东省": (36.6512, 117.1201),
    "河南省": (34.7466, 113.6254),
    "湖北省": (30.5928, 114.3055),
    "湖南省": (28.2282, 112.9388),
    "广东省": (23.1291, 113.2644),
    "海南省": (20.0174, 110.3492),
    "四川省": (30.5728, 104.0668),
    "贵州省": (26.6470, 106.6302),
    "云南省": (25.0389, 102.7183),
    "陕西省": (34.3416, 108.9398),
    "甘肃省": (36.0611, 103.8343),
    "青海省": (36.6171, 101.7782),
    "台湾省": (25.0330, 121.5654),
    "内蒙古自治区": (40.8426, 111.7490),
    "广西壮族自治区": (22.8170, 108.3665),
    "西藏自治区": (29.6520, 91.1721),
    "宁夏回族自治区": (38.4872, 106.2309),
    "新疆维吾尔自治区": (43.7928, 87.6177),
    "香港特别行政区": (22.3193, 114.1694),
    "澳门特别行政区": (22.1987, 113.5439),
}


def get_province_coords(province: Optional[str]) -> Optional[tuple[float, float]]:
    if not province:
        return None
    return PROVINCE_COORDS.get(province)


def calculate_geography_score_by_province(donor_province: Optional[str], recipient_province: Optional[str]) -> float:
    donor_coords = get_province_coords(donor_province)
    recipient_coords = get_province_coords(recipient_province)

    if not donor_coords or not recipient_coords:
        return 0.5

    distance = haversine_distance(donor_coords[0], donor_coords[1], recipient_coords[0], recipient_coords[1])
    return geography_score(distance)


def calculate_distance_by_province(donor_province: Optional[str], recipient_province: Optional[str]) -> float:
    donor_coords = get_province_coords(donor_province)
    recipient_coords = get_province_coords(recipient_province)

    if not donor_coords or not recipient_coords:
        return 0.0

    return haversine_distance(donor_coords[0], donor_coords[1], recipient_coords[0], recipient_coords[1])
