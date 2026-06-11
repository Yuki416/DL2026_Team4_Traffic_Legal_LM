import json, shutil, os

SRC = "/workspace/data/extracted/structured_cases.json"
BAK = "/workspace/data/extracted/structured_cases.json.bak"

REF_PATTERNS = ["引用檢察官", "聲請簡易判決處刑書之記載", "引用起訴書之記載",
                "引用原審", "犯罪事實及證據，除", "犯罪事實與證據，除",
                "其餘事實、理由、聲明均詳見附件", "詳見附件"]
PROC_PATTERNS = ["證據能力部分", "證據證明係公務員違背法定程序", "刑事訴訟法第158條"]

data = json.load(open(SRC, encoding="utf-8"))

remove, keep = [], []
for d in data:
    s = d.get("事故摘要", "").replace(" ", "").replace("\n", "")
    has_ref = any(p in s for p in REF_PATTERNS)
    has_proc = any(p in s for p in PROC_PATTERNS)
    # 與 scan 一致：先判 ref，ref 不中才判 proc
    if (not has_ref) and has_proc:
        remove.append(d)
    else:
        keep.append(d)

print(f"原始: {len(data)} 筆")
print(f"將刪除 [B] 證據能力/程序段: {len(remove)} 筆")
for d in remove:
    print(f"  - [{d['_source']}] {d['JID']}")
    print(f"    {d['事故摘要'].replace(chr(10),'')[:80]}")
print(f"保留: {len(keep)} 筆")

# 備份後寫回
if not os.path.exists(BAK):
    shutil.copy(SRC, BAK)
    print(f"已備份原檔 -> {BAK}")
with open(SRC, "w", encoding="utf-8") as f:
    json.dump(keep, f, ensure_ascii=False, indent=2)
print(f"已寫回 {SRC}（{len(keep)} 筆）")
