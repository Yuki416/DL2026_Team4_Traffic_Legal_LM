# -*- coding: utf-8 -*-
import json, glob, os, re

BASE = "/home/under115b/work/Traffic_Legal_LM"
OUT_DIR = f"{BASE}/data/colloquial/out"
CHUNK_DIR = f"{BASE}/data/colloquial/chunks"

VALID12 = {"轉彎車未讓直行車","變換車道未讓直行車","支線道未讓幹線道","左方車未讓右方車",
           "違反號誌","未注意車前狀況","閃紅燈未停讓","閃黃燈未減速","與有過失",
           "過失致死致重傷","過失傷害成立","民事損害賠償"}
# 嚴格洩漏詞（標籤本身/法律套語/法條）
LEAK = ["貿然","疏未注意","應讓直行車","與有過失","未注意車前狀況","過失相抵",
        "侵權行為","代位","刑法第","民法第","保險法第","條第","道路交通安全規則",
        "道路交通管理處罰條例","強制汽車責任保險法"]

out_files = sorted(glob.glob(f"{OUT_DIR}/out_*.json"))
print(f"已產出 {len(out_files)} 個 out 檔\n")

tot=tot_rw=tot_sk=0
leak_rows=[]
bad_schema=bad_label=bad_count=0
all_lens=[]
for of in out_files:
    nn = re.search(r"out_(\d+)\.json", of).group(1)
    cf = f"{CHUNK_DIR}/chunk_{nn}.json"
    out = json.load(open(of, encoding="utf-8"))
    chunk = json.load(open(cf, encoding="utf-8"))
    by_id = {d["JID"]: d for d in chunk}
    if len(out) != len(chunk): bad_count+=1
    rw=sum(1 for d in out if d["action"]=="rewrite")
    sk=sum(1 for d in out if d["action"]=="skip")
    tot+=len(out); tot_rw+=rw; tot_sk+=sk
    for d in out:
        if not all(k in d for k in ("JID","action","input","grounded_disputes","has_self_surrender_cue")):
            bad_schema+=1
        if d["action"]=="rewrite":
            all_lens.append(len(d["input"]))
            for g in d["grounded_disputes"]:
                if g not in VALID12: bad_label+=1
            hits=[w for w in LEAK if w in d["input"]]
            if hits: leak_rows.append((d["JID"], hits, d["input"]))
    print(f"  chunk_{nn}: {len(out)} 筆（rw={rw}, skip={sk}）{'⚠筆數不符' if len(out)!=len(chunk) else ''}")

print(f"\n總計: {tot} 筆 | rewrite {tot_rw} | skip {tot_sk}（skip率 {tot_sk/tot*100:.1f}%）")
print(f"schema缺欄位: {bad_schema} | 非12類標籤: {bad_label} | 筆數不符檔案: {bad_count}")
if all_lens:
    print(f"input 長度: min={min(all_lens)} max={max(all_lens)} 平均={sum(all_lens)//len(all_lens)}")
print(f"洩漏筆數: {len(leak_rows)} / {tot_rw} rewrite（{len(leak_rows)/max(tot_rw,1)*100:.1f}%）")
for jid, hits, inp in leak_rows:
    print(f"  ⚠ {jid}: {hits}")
    print(f"     {inp[:120]}")
