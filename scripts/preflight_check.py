# -*- coding: utf-8 -*-
"""開跑前的確定性風險檢查 + 產生測試 chunk。"""
import json, re
from pathlib import Path

BASE = "/home/under115b/work/Traffic_Legal_LM"
data = json.load(open(f"{BASE}/data/extracted/structured_cases.json", encoding="utf-8"))
total = len(data)

ALWAYS_FILTER = ["刑法第41條","刑法第50條","刑法第51條","刑法第53條","刑法第55條",
                 "刑法第57條","刑法第71條","刑法第74條","刑法第75條",
                 "民法第203條","民法第229條","民法第233條"]
COND = ["刑法第62條", "民法第217條"]  # 條件式，最壞情況也被拿掉

def worst_case_laws(laws):
    return [l for l in laws if not any(l.startswith(p) for p in ALWAYS_FILTER+COND)]

# 風險 1：過濾後空法條（最壞情況：自首/過失相抵都沒線索也拿掉）
empty_law = [d for d in data if len(worst_case_laws(d["適用法條"]))==0]
print(f"[風險1] 最壞情況過濾後『空法條』: {len(empty_law)} ({len(empty_law)/total*100:.1f}%)")
for d in empty_law[:8]:
    print(f"    [{d['_source']}] {d['JID']}  原法條={d['適用法條']}")

# 風險 2：拿掉與有過失後空爭議（只有與有過失這一個標籤的案例）
only_fault = [d for d in data if d["核心爭議"]==["與有過失"]]
print(f"\n[風險2] 核心爭議只有『與有過失』一項（拿掉會變空）: {len(only_fault)} ({len(only_fault)/total*100:.1f}%)")
for d in only_fault[:8]:
    print(f"    [{d['_source']}] {d['JID']}")

# 風險 3：事故摘要含可能誤導改寫的特殊字（先看比例，非阻斷）
print(f"\n[參考] 總案例 {total}（刑 {sum(1 for d in data if d['_source']=='criminal')} / 民 {sum(1 for d in data if d['_source']=='civil')}）")

# 產生 3 筆測試 chunk
PILOT = {"KMEM,115,城交簡,15,20260317,1","ULDV,114,簡,102,20260305,1",
         "ULDV,114,簡上,27,20260309,1","MLDV,114,苗簡,849,20260305,1",
         "KSDM,115,交簡,495,20260327,1","KSDM,115,交簡,297,20260309,1",
         "ULDV,115,簡,8,20260313,1"}

def pick(pred):
    for d in data:
        if d["JID"] in PILOT: continue
        if pred(d):
            PILOT.add(d["JID"]); return d
    return None

# t1: 刑事，同時有 與有過失 + 刑法第62條（測兩個 cue）
t1 = pick(lambda d: d["_source"]=="criminal" and "與有過失" in d["核心爭議"]
          and any(l.startswith("刑法第62條") for l in d["適用法條"])
          and len(d["事故摘要"])>120)
# t2: 民事，有 與有過失（測對方過失判斷）
t2 = pick(lambda d: d["_source"]=="civil" and "與有過失" in d["核心爭議"]
          and len(d["事故摘要"])>150)
# t3: [A] 該 skip 的（引用起訴書/聲請簡判書）
t3 = pick(lambda d: ("聲請簡易判決處刑書之記載" in d["事故摘要"].replace(" ","")
          or "引用檢察官起訴書" in d["事故摘要"].replace(" ",""))
          and len(d["事故摘要"].replace(" ",""))<150)

test_cases = [t for t in (t1,t2,t3) if t]
# 只保留 sub-agent 需要的欄位
slim = [{"JID":d["JID"],"_source":d["_source"],"事故摘要":d["事故摘要"],
         "核心爭議":d["核心爭議"],"適用法條":d["適用法條"]} for d in test_cases]

OUT = Path(f"{BASE}/data/colloquial/test_chunk.json")
OUT.parent.mkdir(parents=True, exist_ok=True)
json.dump(slim, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\n已產生測試 chunk: {OUT}（{len(slim)} 筆）")
for d in slim:
    print(f"  - [{d['_source']}] {d['JID']}")
    print(f"    爭議={d['核心爭議']} 法條={d['適用法條']}")
    print(f"    摘要={d['事故摘要'][:80].replace(chr(10),'')}...")
