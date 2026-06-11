# -*- coding: utf-8 -*-
"""Step 4 組裝：把所有 out_NN.json 合併成最終 Alpaca 訓練檔。
- input: 套 sanitizer 清掉殘留法律詞
- 核心爭議: 用 agent 的 grounded_disputes
- 責任類型: 從 structured_cases.json 撈
- 適用法條: 過濾量刑/程序法條 + 條件式(自首刑62 / 過失相抵民217) + 去重
- instruction: 6 種輪替
- output: 【核心爭議】【責任類型】【適用法條】三行
輸出: data/colloquial/training_pairs.json
"""
import json, glob, re

BASE = "/home/under115b/work/Traffic_Legal_LM"
OUT_DIR = f"{BASE}/data/colloquial/out"
STRUCT = f"{BASE}/data/extracted/structured_cases.json"
RESULT = f"{BASE}/data/colloquial/training_pairs.json"

INSTRUCTIONS = [
    "請依據以下車禍經過，分析其法律爭點、可能成立的責任類型與相關法條。",
    "以下是一則車禍求助文，請判斷核心爭議、當事人可能負擔的責任類型，以及適用的法條。",
    "閱讀這起交通事故的描述，整理出法律上的爭點、責任歸屬類型與可能引用的條文。",
    "這起車禍在法律上有哪些爭議？涉及刑事還是民事責任？可能適用哪些法條？",
    "請就下列事故經過，做交通事故的法律分析（爭點、責任類型、適用法條）。",
    "幫我看一下這個車禍案例，法律上的關鍵爭點、責任種類和相關法律規定是什麼。",
]

# ---- sanitizer：殘留法律詞 → 白話（長詞先換）----
SANITIZE = [
    ("代位求償", "向對方求償"),
    ("代位向對方求償", "向對方求償"),
    ("代位向", "向"),
    ("代位", ""),
    ("未注意車前狀況", "沒注意前面"),
    ("疏未注意", "沒注意到"),
    ("應讓直行車先行", "要讓直行車先過"),
    ("應讓直行車先走", "要讓直行車先過"),
    ("應讓直行車", "要讓直行車"),
    ("貿然", "直接"),
    ("過失相抵", "各自有責任"),
    ("與有過失", "雙方都有責任"),
    ("侵權行為", ""),
]
def sanitize(t):
    for a, b in SANITIZE:
        t = t.replace(a, b)
    return re.sub(r"\s{2,}", " ", t).strip()

# ---- 法條過濾 ----
ALWAYS_FILTER = ["刑法第41條","刑法第50條","刑法第51條","刑法第53條","刑法第55條",
                 "刑法第57條","刑法第71條","刑法第74條","刑法第75條",
                 "民法第203條","民法第229條","民法第233條"]
COND_SELF = "刑法第62條"
COND_COMP = "民法第217條"

def dedup_laws(laws):
    def base(l):
        m = re.match(r"(.+?第\d+(?:-\d+)?條)", l); return m.group(1) if m else l
    def seg(l):
        for s in ["前段","後段","但書"]:
            if l.endswith(s): return s
        return ""
    def detail(l): return ("項" in l, "款" in l, len(l))
    keep = []
    for a in laws:
        red = False
        for b in laws:
            if a != b and base(a)==base(b) and seg(a)==seg(b) and detail(b) > detail(a):
                red = True; break
        if not red and a not in keep: keep.append(a)
    return keep

def filter_laws(laws, keep_self, keep_comp):
    out = []
    for l in laws:
        if any(l.startswith(p) for p in ALWAYS_FILTER): continue
        if l.startswith(COND_SELF) and not keep_self: continue
        if l.startswith(COND_COMP) and not keep_comp: continue
        out.append(l)
    return dedup_laws(out)

struct_list = json.load(open(STRUCT, encoding="utf-8"))
struct = {d["JID"]: d for d in struct_list}
# fallback: (court,year,type,num) -> correct JID for agent-mangled dates
struct_base4 = {tuple(d["JID"].split(",")[:4]): d["JID"] for d in struct_list}

pairs, skipped_empty, leak_residual = [], [], []
LEAK_CHECK = ["貿然","疏未注意","未注意車前狀況","與有過失","過失相抵","侵權行為","代位","刑法第","民法第","條第"]
i = 0
for f in sorted(glob.glob(f"{OUT_DIR}/out_[0-9][0-9].json")):
    for d in json.load(open(f, encoding="utf-8")):
        if d["action"] != "rewrite": continue
        jid = d["JID"]
        if jid not in struct:
            jid = struct_base4.get(tuple(jid.split(",")[:4]), jid)
        if jid not in struct: continue  # truly unknown, skip
        s = struct[jid]
        disp = d.get("grounded_disputes", [])
        if not disp: continue
        keep_comp = "與有過失" in disp
        laws = filter_laws(s["適用法條"], d.get("has_self_surrender_cue", False), keep_comp)
        if not laws:
            skipped_empty.append(jid); continue
        inp = sanitize(d["input"])
        hits = [w for w in LEAK_CHECK if w in inp]
        if hits: leak_residual.append((jid, hits))
        out = (f"【核心爭議】{'、'.join(disp)}\n"
               f"【責任類型】{'、'.join(s['責任類型'])}\n"
               f"【適用法條】{'、'.join(laws)}")
        pairs.append({"instruction": INSTRUCTIONS[i % 6], "input": inp, "output": out,
                      "_jid": jid, "_source": s["_source"]})
        i += 1

json.dump(pairs, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"組裝完成: {len(pairs)} 筆 -> {RESULT}")
print(f"  刑事 {sum(1 for p in pairs if p['_source']=='criminal')} / 民事 {sum(1 for p in pairs if p['_source']=='civil')}")
print(f"  因法條過濾後為空而剔除: {len(skipped_empty)} 筆")
print(f"  sanitize 後仍殘留法律詞: {len(leak_residual)} 筆")
for jid, hits in leak_residual[:20]:
    print(f"    ⚠ {jid}: {hits}")
