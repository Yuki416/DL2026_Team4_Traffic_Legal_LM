import json
from pathlib import Path

DATA_ROOT = Path("/mnt/8tb_hdd/under115b/traffic_legal_lm/raw/202603")
CIVIL_TITLES = ["損害賠償(交通)", "損害賠償（交通）", "侵權行為損害賠償(交通)", "侵權行為損害賠償（交通）"]

samples = []
for json_path in DATA_ROOT.rglob("*.json"):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        if any(t in doc.get("JTITLE", "") for t in CIVIL_TITLES):
            samples.append(doc)
            if len(samples) >= 4:
                break
    except Exception:
        continue

for s in samples:
    print(f"JID: {s.get('JID', '')}")
    print(f"JCASE: {s.get('JCASE', '')}  JTITLE: {s.get('JTITLE', '')}")
    print("JFULL (前 800 字):")
    print(s.get("JFULL", "")[:800])
    print("=" * 60)
