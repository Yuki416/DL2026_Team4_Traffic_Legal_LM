import json
from pathlib import Path
from tqdm import tqdm

DATA_ROOT   = Path("/mnt/8tb_hdd/under115b/traffic_legal_lm/raw/202603")
OUTPUT_PATH = "data/filtered/traffic_cases_civil.json"

# 第一層：JTITLE 同時含「交通」+「損害賠償或侵權行為」
# 確保是交通事故民事案件，排除一般債務、婚姻等無關損害賠償
JTITLE_TRAFFIC_MARKER = "交通"
JTITLE_TYPES = ["損害賠償", "侵權行為"]

# 第二層：排除程序裁定（無實體事實內容）
# JCASE 結尾為「補」的均為各地法院補充裁判費裁定，無事故描述
# 例：補、中補、北補、板補、雄補、重補 等

# 第三層：事故內容關鍵字（OR 邏輯）
# 比刑事篩選更寬鬆，因民事判決書不一定有「貿然」等法律套語
# 但一定有描述碰撞/路口的詞
CIVIL_KEYWORDS = [
    # 沿用刑事篩選的路口路權詞
    "路口", "轉彎", "直行", "支線道", "幹線道",
    "閃紅燈", "閃黃燈", "禮讓", "貿然", "未讓",
    # 民事判決書特有的事故描述詞
    "車禍", "碰撞", "撞擊", "交通事故", "闖紅燈", "肇事",
]

Path("data/filtered").mkdir(parents=True, exist_ok=True)

all_jsons = list(DATA_ROOT.rglob("*.json"))
print(f"掃描 {len(all_jsons)} 筆...")

results = []
for json_path in tqdm(all_jsons):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            doc = json.load(f)

        jtitle = doc.get("JTITLE", "")
        jcase  = doc.get("JCASE", "")
        jfull  = doc.get("JFULL", "")

        # 第一層：JTITLE 篩選
        if JTITLE_TRAFFIC_MARKER not in jtitle:
            continue
        if not any(t in jtitle for t in JTITLE_TYPES):
            continue

        # 第二層：排除程序裁定（JCASE 結尾為「補」）
        if jcase.endswith("補"):
            continue

        # 第三層：事故內容關鍵字
        if not any(k in jfull for k in CIVIL_KEYWORDS):
            continue

        results.append(doc)

    except Exception:
        continue

print(f"篩選後（民事）: {len(results)} 筆")
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"已存至 {OUTPUT_PATH}")
