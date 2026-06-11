import json
from pathlib import Path
from tqdm import tqdm

DATA_ROOTS    = [Path("data/raw/202603")]
OUTPUT_PATH   = "data/filtered/traffic_cases.json"

TARGET_TITLES = [
    "過失傷害", "過失致死", "過失致重傷", "過失重傷害",
]
PATH_KEYWORDS = ["路口", "轉彎", "直行", "支線道", "幹線道",
                 "閃紅燈", "閃黃燈", "禮讓", "貿然", "未讓"]
# 整案被駁回的模式（和解撤告 → 告訴乃論，無法院事實認定）
FULL_DISMISS_PATTERNS = ["本件公訴不受理", "本案公訴不受理"]
# 有定罪才是實質判決，即使有部分不受理也保留
CONVICTION_PATTERNS   = ["處有期徒刑", "處拘役", "處罰金"]

Path("data/filtered").mkdir(parents=True, exist_ok=True)

results = []
for root in DATA_ROOTS:
    all_jsons = list(root.rglob("*.json"))
    print(f"{root.name}: {len(all_jsons)} 筆")
    for json_path in tqdm(all_jsons):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            if "交" not in doc.get("JCASE", ""):                                    continue
            if not any(t in doc.get("JTITLE", "") for t in TARGET_TITLES):         continue
            if (any(p in doc.get("JFULL", "") for p in FULL_DISMISS_PATTERNS) and
                    not any(c in doc.get("JFULL", "") for c in CONVICTION_PATTERNS)): continue
            if not any(k in doc.get("JFULL", "")  for k in PATH_KEYWORDS):         continue
            results.append(doc)
        except Exception:
            continue

print(f"篩選後: {len(results)} 筆")
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"已存至 {OUTPUT_PATH}")
