# -*- coding: utf-8 -*-
"""偵測所有 out_NN.json 裡殘留的「保險公司第一人稱」案例，
建立修正包 chunks/fixup_insurer2.json，供一個 fixup agent 重寫（駕駛視角）。"""
import json, glob

BASE = "/home/under115b/work/Traffic_Legal_LM"
STRUCT = f"{BASE}/data/extracted/structured_cases.json"

INSURER = ["我（保險公司","我(保險公司","我們（保險","我們(保險","我是保險公司",
           "我承保","我們承保","被保戶","我的被保戶","我們的被保戶","我們保戶",
           "保險公司）承保","保險公司)承保","我（保險","我(保險"]

jids = []
for f in sorted(glob.glob(f"{BASE}/data/colloquial/out/out_[0-9][0-9].json")):
    for d in json.load(open(f, encoding="utf-8")):
        if d["action"] == "rewrite" and any(m in d["input"] for m in INSURER):
            jids.append(d["JID"])

print(f"殘留保險視角: {len(jids)} 筆")
if jids:
    full = {d["JID"]: d for d in json.load(open(STRUCT, encoding="utf-8"))}
    slim = [{"JID": j, "_source": full[j]["_source"], "事故摘要": full[j]["事故摘要"],
             "核心爭議": full[j]["核心爭議"], "適用法條": full[j]["適用法條"]} for j in jids]
    json.dump(slim, open(f"{BASE}/data/colloquial/chunks/fixup_insurer2.json","w",encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"已寫 chunks/fixup_insurer2.json（{len(slim)} 筆）")
else:
    print("無殘留，免修正包。")
