import json
from pathlib import Path

DATA_ROOT = Path("/mnt/8tb_hdd/under115b/traffic_legal_lm/raw/202603")
TARGET_TITLES = ["過失傷害", "過失致死", "過失致重傷", "過失重傷害"]
PATH_KEYWORDS = ["路口","轉彎","直行","支線道","幹線道","閃紅燈","閃黃燈","禮讓","貿然","未讓"]

# 幾種判斷「整案被駁回」的模式
FULL_DISMISS_PATTERNS = ["本件公訴不受理", "本案公訴不受理"]
# 有定罪才算實質判決（主文含量刑）
CONVICTION_PATTERNS = ["處有期徒刑", "處拘役", "處罰金"]

count_total   = 0
count_any     = 0   # 含「公訴不受理」（任何位置）
count_full    = 0   # 含「本件/本案公訴不受理」（整案駁回）
count_partial = 0   # 含「公訴不受理」但也有定罪（部分罪名）

for json_path in DATA_ROOT.rglob("*.json"):
    try:
        doc = json.load(open(json_path, encoding="utf-8"))
        if "交" not in doc.get("JCASE", ""): continue
        if not any(t in doc.get("JTITLE", "") for t in TARGET_TITLES): continue
        jfull = doc.get("JFULL", "")
        if not any(k in jfull for k in PATH_KEYWORDS): continue

        count_total += 1
        has_any  = "公訴不受理" in jfull
        has_full = any(p in jfull for p in FULL_DISMISS_PATTERNS)
        has_conv = any(c in jfull for c in CONVICTION_PATTERNS)

        if has_any:
            count_any += 1
            if has_full and not has_conv:
                count_full += 1
            elif has_any and has_conv:
                count_partial += 1
    except:
        continue

print(f"通過三層篩選（含路口關鍵字）: {count_total} 筆")
print(f"含「公訴不受理」（任何位置）: {count_any} 筆 ({count_any/count_total*100:.1f}%)")
print(f"  ├─ 整案駁回（本件/本案公訴不受理，無定罪）: {count_full} 筆")
print(f"  └─ 部分不受理（有定罪）: {count_partial} 筆")
print(f"排除整案駁回後剩: {count_total - count_full} 筆")
