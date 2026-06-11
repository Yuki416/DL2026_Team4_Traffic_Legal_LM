# -*- coding: utf-8 -*-
"""組裝 7 筆 pilot 的 Alpaca 檔（套用可學習性規則）。

規則：
1. 適用法條：過濾量刑/程序/利息類（無法從事故描述推得）
   - 自首(刑62)：input 有自首線索才留
   - 過失相抵(民217)：input 有對方過失線索才留（跟與有過失連動）
2. 核心爭議：input 無對方過失線索 → 拿掉「與有過失」
3. 法條去重：同條同段，保留含項/款的較精細版本
"""
import json, re
from pathlib import Path

BASE = "/home/under115b/work/Traffic_Legal_LM"
SRC = f"{BASE}/data/extracted/structured_cases.json"
OUT_DIR = Path(f"{BASE}/data/colloquial")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "training_pairs_pilot.json"

INSTRUCTIONS = [
    "請依據以下車禍經過，分析其法律爭點、可能成立的責任類型與相關法條。",
    "以下是一則車禍求助文，請判斷核心爭議、當事人可能負擔的責任類型，以及適用的法條。",
    "閱讀這起交通事故的描述，整理出法律上的爭點、責任歸屬類型與可能引用的條文。",
    "這起車禍在法律上有哪些爭議？涉及刑事還是民事責任？可能適用哪些法條？",
    "請就下列事故經過，做交通事故的法律分析（爭點、責任類型、適用法條）。",
    "幫我看一下這個車禍案例，法律上的關鍵爭點、責任種類和相關法律規定是什麼。",
]

# 一律過濾（量刑/程序/利息，無法從事故事實推得）
ALWAYS_FILTER = ["刑法第41條", "刑法第50條", "刑法第51條", "刑法第53條",
                 "刑法第55條", "刑法第57條", "刑法第71條", "刑法第74條",
                 "刑法第75條", "民法第203條", "民法第229條", "民法第233條"]
COND_SELF_SURRENDER = "刑法第62條"   # 自首：input 有線索才留
COND_COMPARATIVE    = "民法第217條"  # 過失相抵：input 有對方過失線索才留


def filter_laws(laws, keep_self_surrender, keep_comparative):
    out = []
    for l in laws:
        if any(l.startswith(p) for p in ALWAYS_FILTER):
            continue
        if l.startswith(COND_SELF_SURRENDER) and not keep_self_surrender:
            continue
        if l.startswith(COND_COMPARATIVE) and not keep_comparative:
            continue
        out.append(l)
    return dedup_laws(out)


def dedup_laws(laws):
    def base(l):
        m = re.match(r"(.+?第\d+(?:-\d+)?條)", l)
        return m.group(1) if m else l
    def seg(l):
        for s in ["前段", "後段", "但書"]:
            if l.endswith(s):
                return s
        return ""
    def detail(l):
        return ("項" in l, "款" in l, len(l))
    keep = []
    for a in laws:
        redundant = False
        for b in laws:
            if a == b:
                continue
            if base(a) == base(b) and seg(a) == seg(b) and detail(b) > detail(a):
                redundant = True
                break
        if not redundant and a not in keep:
            keep.append(a)
    return keep


def filter_disputes(disputes, keep_comparative):
    if not keep_comparative:
        return [d for d in disputes if d != "與有過失"]
    return disputes


# JID -> (改寫 input, 有無對方過失線索, 有無自首線索)
REWRITES = [
    ("KMEM,115,城交簡,15,20260317,1",
     "上禮拜開公司的貨車要右轉，我看前面沒車就轉了，結果完全沒注意到後面同方向有一台機車從我右邊騎上來，閃避不及就撞上去了。對方人摔在地上，送醫院說鎖骨骨折、膝蓋韌帶還有手指也斷了，傷得不輕。當下我有留在現場跟警察承認是我撞的。現在很怕，這樣我會被判過失傷害嗎？對方傷成這樣我是不是刑事民事都跑不掉…",
     False, True),   # 無對方過失線索；有自首
    ("ULDV,114,簡,102,20260305,1",
     "前陣子在國道開車，我在內側車道想說打方向燈切到中線，結果後面一台小貨車不知道在幹嘛，自己先去撞到內側護欄，彈回來又從後面撞上我，我整台車被推去撞到旁邊在等的大貨車，直接全損報廢。保險公司已經理賠我了，現在好像要跟對方求償。可是對方一直說我那時候在變換車道也有不對，想問這種情況到底是他全錯，還是我切車道也要分一點責任？",
     True, False),   # 有對方過失/雙方過失線索；無自首
    ("ULDV,114,簡上,27,20260309,1",
     "想請教大家，我那天晚上騎機車直行過一個路口，對方開車要左轉，結果他根本沒讓我，直接切過來撞上我。我整個人連車摔出去，傷得超嚴重，頭部撕裂傷、顱內出血、髖關節脫臼、臉骨折牙齒也掉了好幾顆，住院到現在。後來才知道對方那天還有喝酒，酒測超標。想問這種對方左轉撞我直行、又有酒駕的情況，民事我可以求償哪些？醫藥費精神慰撫金他要賠多少？",
     False, False),  # 我方無過失線索 → 拿掉與有過失
    ("MLDV,114,苗簡,849,20260305,1",
     "我開車經過一個國小前面的路段，正常行駛，結果旁邊一台車硬要超車，超車時就直接擦撞到我，車被撞得不輕，修理花了快四十萬。我車子有保險，保險公司先賠我了，現在他們要去跟對方求償，對方那邊不太想認帳。想問這種對方違規超車撞到我的，他應該賠多少才合理？修車折舊的部分要算誰的？",
     False, False),  # 無我方過失線索 → 拿掉與有過失
    ("KSDM,115,交簡,495,20260327,1",
     "出事了，心情很亂。我開營業小客車載客，在慢車道想超前面同方向一台機車，從他右邊切過去，可能距離抓太近，兩台車就擦撞，騎士整個人倒在地上。送醫院開了腦部的刀，住加護病房，結果幾天後人還是走了。我真的不是故意的…現在這種情況會被判什麼罪？過失致死是不是要關？我有在現場等警察也有承認。家屬那邊民事賠償又要怎麼談…",
     False, True),   # 無對方過失線索；有自首
    ("KSDM,115,交簡,297,20260309,1",
     "晚上開車經過一個有紅綠燈的路口，我要左轉，那時候其實是紅燈，想說沒什麼車就轉了，結果旁邊一台直行的車剛好過來，兩台就撞在一起。對方有受傷，檢查說頭部鈍傷有腦震盪，還有胸口跟膝蓋挫傷。我知道闖紅燈是我不對啦…想問這樣我會被告過失傷害嗎？紅燈左轉撞到人是不是責任全在我？大概要賠多少？",
     False, False),  # 無自首線索 → 拿掉刑62
    ("ULDV,115,簡,8,20260313,1",
     "我開車正常通過一個路口，我這邊是綠燈，結果側面一台車直接闖紅燈衝出來撞上我，車被撞得很慘，估修理費居然要四百多萬，超過全損標準。我車子有保全險，保險公司用全損賠了我，聽說現在要跟那個闖紅燈的人代位求償。想問這種對方百分百闖紅燈的，他要負全部賠償責任嗎？車子全損是賠修理費還是車子的價值？",
     False, False),  # 對方全責，我方無過失
]

by_id = {d["JID"]: d for d in json.load(open(SRC, encoding="utf-8"))}

def fmt_output(disputes, resp, laws):
    return (f"【核心爭議】{'、'.join(disputes)}\n"
            f"【責任類型】{'、'.join(resp)}\n"
            f"【適用法條】{'、'.join(laws)}")

pairs = []
for i, (jid, inp, keep_comp, keep_self) in enumerate(REWRITES):
    d = by_id[jid]
    raw_disp, raw_law = d["核心爭議"], d["適用法條"]
    disp = filter_disputes(raw_disp, keep_comp)
    laws = filter_laws(raw_law, keep_self, keep_comp)
    pairs.append({
        "instruction": INSTRUCTIONS[i % 6],
        "input": inp,
        "output": fmt_output(disp, d["責任類型"], laws),
        "_jid": jid, "_source": d["_source"],
        "_raw_disp": raw_disp, "_raw_law": raw_law,
    })

# 存檔（去掉 _raw 偵錯欄位）
clean = [{k: v for k, v in p.items() if not k.startswith("_raw")} for p in pairs]
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(clean, f, ensure_ascii=False, indent=2)

print(f"已寫出 {len(pairs)} 筆 -> {OUT}\n")
for p in pairs:
    print("=" * 72)
    print(f"[{p['_source']}] {p['_jid']}")
    print(f"  原始爭議: {p['_raw_disp']}")
    print(f"  原始法條: {p['_raw_law']}")
    print(f"  --- 修正後 ---")
    print(f"instruction: {p['instruction']}")
    print(f"input: {p['input']}")
    print(f"output:\n{p['output']}")
