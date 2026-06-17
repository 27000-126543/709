import json

FOLLOWUP_ABNORMAL_THRESHOLDS = {
    "kidney_function": {
        "creatinine": {
            "name": "肌酐",
            "min": 44, "max": 133, "unit": "μmol/L",
        },
        "urea": {
            "name": "尿素氮",
            "min": 2.5, "max": 7.5, "unit": "mmol/L",
        },
    },
    "liver_function": {
        "alt": {
            "name": "谷丙转氨酶 (ALT)",
            "min": 0, "max": 40, "unit": "U/L",
        },
        "ast": {
            "name": "谷草转氨酶 (AST)",
            "min": 0, "max": 40, "unit": "U/L",
        },
    },
    "infection_markers": {
        "crp": {
            "name": "C反应蛋白 (CRP)",
            "min": 0, "max": 10, "unit": "mg/L",
        },
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
                    print(f"  [DEBUG] 类别 {category_name} 无阈值配置，跳过")
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
                            print(f"  [DEBUG] {category_name}.{key} 值为 None，跳过")
                            continue

                        try:
                            num_value = float(value)
                        except (TypeError, ValueError):
                            print(f"  [DEBUG] {category_name}.{key} 无法转数字: {value}，跳过")
                            continue

                        min_val = threshold.get("min")
                        max_val = threshold.get("max")
                        unit = threshold.get("unit", "")
                        name = threshold.get("name", key)

                        print(f"  [DEBUG] 检查 {name} = {num_value}{unit}, 范围 [{min_val}, {max_val}]")

                        if min_val is not None and num_value < min_val:
                            deviation_pct = ((min_val - num_value) / min_val) * 100 if min_val > 0 else 100
                            severity = "严重" if deviation_pct > 30 else "轻度"
                            abnormal_flags.append(name)
                            alert_detail.append(
                                f"{name}: {num_value}{unit} 低于下限{min_val}{unit} (低{round(deviation_pct,1)}%) [{severity}]"
                            )
                            continue

                        if max_val is not None and num_value > max_val:
                            deviation_pct = ((num_val - max_val) / max_val) * 100 if max_val > 0 else 100
                            severity = "严重" if deviation_pct > 50 else "轻度"
                            abnormal_flags.append(name)
                            alert_detail.append(
                                f"{name}: {num_value}{unit} 高于上限{max_val}{unit} (高{round(deviation_pct,1)}%) [{severity}]"
                            )
                            print(f"    → 检测到异常！高于上限")
                    except Exception as e:
                        print(f"  [DEBUG] {category_name}.{key} 处理异常: {e}")
                        continue
            except Exception as e:
                print(f"  [DEBUG] 类别 {category_name} 处理异常: {e}")
                continue
    except Exception as e:
        print(f"  [DEBUG] 整体异常: {e}")
        pass

    return abnormal_flags, alert_detail

print("=== 测试1: 肌酐200, ALT=120, CRP=50 ===")
test_data = {
    "kidney_function": {"creatinine": 200},
    "liver_function": {"alt": 120},
    "infection_markers": {"crp": 50},
}
flags, details = detect_abnormalities(test_data)
print(f"\n结果: {len(flags)} 项异常")
for i, f in enumerate(flags):
    print(f"  {i+1}. {f}")
    if i < len(details):
        print(f"     {details[i]}")

print("\n=== 测试2: 全大写键名 ===")
test_data2 = {
    "kidney_function": {"CREATININE": 200},
}
flags2, details2 = detect_abnormalities(test_data2)
print(f"结果: {len(flags2)} 项异常")

print("\n=== 测试3: 字符串数字 ===")
test_data3 = {
    "kidney_function": {"creatinine": "200"},
}
flags3, details3 = detect_abnormalities(test_data3)
print(f"结果: {len(flags3)} 项异常")
