import json

data = json.load(open('/workspace/data/extracted/structured_cases.json'))
total = len(data)

# 高信心 skip：引用他文書（檢察官起訴書/聲請簡易判決處刑書/附件），無實際事故經過
REF_PATTERNS = ["引用檢察官", "聲請簡易判決處刑書之記載", "引用起訴書之記載",
                "引用原審", "犯罪事實及證據，除", "犯罪事實與證據，除",
                "其餘事實、理由、聲明均詳見附件", "詳見附件"]
# 證據能力 / 程序段（抽錯段落，非事故事實）
PROC_PATTERNS = ["證據能力部分", "證據證明係公務員違背法定程序", "刑事訴訟法第158條"]

# 放寬後的事故動詞（補上衝撞/撞及/砸中等）
ACCIDENT_WORDS = ["碰撞","撞擊","擦撞","追撞","衝撞","撞及","撞到","撞上","砸中",
                  "肇事","車禍","事故","受傷","死亡","倒地","骨折","傷害",
                  "輾","滑落","失控","翻覆","摔"]

ref_attach, proc_seg, too_short_empty, no_acc = [], [], [], []

for d in data:
    s = d.get("事故摘要","").replace(" ","").replace("\n","")
    L = len(s)
    has_ref  = any(p in s for p in REF_PATTERNS)
    has_proc = any(p in s for p in PROC_PATTERNS)
    has_acc  = any(w in s for w in ACCIDENT_WORDS)
    if has_ref:
        ref_attach.append(d)
    elif has_proc:
        proc_seg.append(d)
    elif L < 60 and not has_acc:
        too_short_empty.append(d)
    elif not has_acc:
        no_acc.append(d)

skip_ids = set()
for grp in (ref_attach, proc_seg, too_short_empty):
    for d in grp:
        skip_ids.add(d["JID"])

print(f"總筆數: {total}")
print(f"[A] 引用他文書(無事故經過): {len(ref_attach)}")
print(f"[B] 證據能力/程序段(抽錯段): {len(proc_seg)}")
print(f"[C] 過短且無事故動詞(<60字): {len(too_short_empty)}")
print(f"--> 高信心 skip 合計: {len(skip_ids)} 筆，保留 {total-len(skip_ids)} 筆")
print(f"[D] 放寬後仍無事故動詞(交給 sub-agent 判斷): {len(no_acc)} 筆")

def show(grp, name, n=6):
    print(f"\n===== {name} (前{n}) =====")
    for d in grp[:n]:
        s = d['事故摘要'].replace(' ','').replace(chr(10),'')
        print(f"- [{d['_source']}] {d['JID']} len={len(s)}")
        print(f"  {s[:100]}")

show(ref_attach, "[A] 引用他文書")
show(proc_seg, "[B] 證據能力/程序段")
show(too_short_empty, "[C] 過短且空")
show(no_acc, "[D] 放寬後仍無動詞")
