FOLLOWUP_ABNORMAL_THRESHOLDS = {
    "kidney_function": {
        "creatinine": {"name": "肌酐", "min": 44, "max": 133, "unit": "μmol/L"},
        "urea": {"name": "尿素氮", "min": 2.5, "max": 7.5, "unit": "mmol/L"},
    },
    "liver_function": {
        "alt": {"name": "谷丙转氨酶 (ALT)", "min": 0, "max": 40, "unit": "U/L"},
        "ast": {"name": "谷草转氨酶 (AST)", "min": 0, "max": 40, "unit": "U/L"},
    },
    "infection_markers": {
        "crp": {"name": "C反应蛋白 (CRP)", "min": 0, "max": 10, "unit": "mg/L"},
        "procalcitonin": {"name": "降钙素原 (PCT)", "min": 0, "max": 0.5, "unit": "ng/mL"},
    },
    "drug_levels": {
        "tacrolimus": {"name": "他克莫司浓度", "min": 5, "max": 15, "unit": "ng/mL"},
        "cyclosporine": {"name": "环孢素浓度", "min": 100, "max": 300, "unit": "ng/mL"},
    },
    "blood_routine": {
        "wbc": {"name": "白细胞计数 (WBC)", "min": 3.5, "max": 9.5, "unit": "×10⁹/L"},
    },
}

def detect_abnormalities(followup_data):
    abnormal_flags = []
    alert_detail = []

    if not isinstance(followup_data, dict):
        return abnormal_flags, alert_detail

    try:
        for category_name, category_data in followup_data.items():
            try:
                if not isinstance(category_data, dict):
                    continue
                thresholds = FOLLOWUP_ABNORMAL_THRESHOLDS.get(category_name, {})
                if not thresholds:
                    continue

                for key, threshold in thresholds.items():
                    try:
                        value = category_data.get(key)
                        if value is None:
                            alt_keys = [key, key.upper(), key.lower(), key.replace("_", "")]
                            for ak in alt_keys:
                                if ak in category_data:
                                    value = category_data[ak]
                                    break
                        if value is None:
                            continue

                        if threshold.get("type") == "negative":
                            if str(value).lower() in ("positive", "阳", "阳性", "1", "true"):
                                abnormal_flags.append(threshold.get("name", key))
                                alert_detail.append(
                                    f"{threshold.get('name', key)}: 检测为阳性，需高度警惕排斥或感染风险"
                                )
                            continue

                        try:
                            num_value = float(value)
                        except (TypeError, ValueError):
                            if isinstance(value, str):
                                try:
                                    num_value = float(''.join(c for c in value if c.isdigit() or c in '.-'))
                                except (TypeError, ValueError):
                                    continue
                            else:
                                continue

                        min_val = threshold.get("min")
                        max_val = threshold.get("max")
                        unit = threshold.get("unit", "")
                        name = threshold.get("name", key)

                        if min_val is not None and num_value < min_val:
                            deviation_pct = ((min_val - num_value) / min_val) * 100 if min_val > 0 else 100
                            severity = "严重" if deviation_pct > 30 else "轻度"
                            abnormal_flags.append(name)
                            alert_detail.append(
                                f"{name}: {num_value}{unit} 低于下限{min_val}{unit} (低{round(deviation_pct,1)}%) [{severity}]"
                            )
                            continue

                        if max_val is not None and num_value > max_val:
                            deviation_pct = ((num_value - max_val) / max_val) * 100 if max_val > 0 else 100
                            severity = "严重" if deviation_pct > 50 else "轻度"
                            abnormal_flags.append(name)
                            alert_detail.append(
                                f"{name}: {num_value}{unit} 高于上限{max_val}{unit} (高{round(deviation_pct,1)}%) [{severity}]"
                            )
                    except Exception as e:
                        print(f"  [WARN] {category_name}.{key} 处理出错: {e}")
                        continue
            except Exception as e:
                print(f"  [WARN] 类别 {category_name} 处理出错: {e}")
                continue
    except Exception as e:
        print(f"  [WARN] 整体处理出错: {e}")
        pass

    return abnormal_flags, alert_detail

print("=" * 60)
print("测试1: 肌酐200, ALT=120, CRP=50 (全超上限)")
print("=" * 60)
test_data = {
    "kidney_function": {"creatinine": 200},
    "liver_function": {"alt": 120},
    "infection_markers": {"crp": 50},
}
flags, details = detect_abnormalities(test_data)
print(f"\n✅ 检测到 {len(flags)} 项异常")
for i, f in enumerate(flags):
    print(f"  {i+1}. {f}")
    if i < len(details):
        print(f"     {details[i]}")
assert len(flags) == 3, f"预期3项异常，实际{len(flags)}项"

print("\n" + "=" * 60)
print("测试2: 混合超上限+正常+低于下限")
print("=" * 60)
test_data2 = {
    "kidney_function": {"creatinine": 20, "urea": 5.0},
    "liver_function": {"alt": 120},
    "drug_levels": {"tacrolimus": 10},
}
flags2, details2 = detect_abnormalities(test_data2)
print(f"\n✅ 检测到 {len(flags2)} 项异常")
for i, f in enumerate(flags2):
    print(f"  {i+1}. {f}")
    if i < len(details2):
        print(f"     {details2[i]}")
assert len(flags2) == 2, f"预期2项异常(肌酐低+ALT高)，实际{len(flags2)}项"

print("\n" + "=" * 60)
print("测试3: 字符串数字 + 大写键名")
print("=" * 60)
test_data3 = {
    "kidney_function": {"CREATININE": "200.5"},
    "infection_markers": {"CRP": "15.3"},
}
flags3, details3 = detect_abnormalities(test_data3)
print(f"\n✅ 检测到 {len(flags3)} 项异常")
for i, f in enumerate(flags3):
    print(f"  {i+1}. {f}")
    if i < len(details3):
        print(f"     {details3[i]}")
assert len(flags3) == 2, f"预期2项异常，实际{len(flags3)}项"

print("\n" + "=" * 60)
print("测试4: 空数据/全正常")
print("=" * 60)
test_data4 = {
    "kidney_function": {"creatinine": 80},
    "liver_function": {"alt": 25},
}
flags4, details4 = detect_abnormalities(test_data4)
print(f"✅ 检测到 {len(flags4)} 项异常 (预期0)")
assert len(flags4) == 0, f"预期0项异常，实际{len(flags4)}项"

print("\n" + "=" * 60)
print("✅ 所有测试通过！异常检测逻辑正常工作")
print("=" * 60)
