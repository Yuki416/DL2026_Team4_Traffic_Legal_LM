# -*- coding: utf-8 -*-
"""把 fixup agent 的輸出，依 JID 貼回對應的 out_NN.json。
用法: python3 patch_fixup.py <fixup_out.json>
"""
import json, glob, sys

BASE = "/home/under115b/work/Traffic_Legal_LM"
fixup_path = sys.argv[1] if len(sys.argv) > 1 else f"{BASE}/data/colloquial/out/fixup_insurer2_out.json"
fix = {d["JID"]: d for d in json.load(open(fixup_path, encoding="utf-8"))}

patched = 0
for f in sorted(glob.glob(f"{BASE}/data/colloquial/out/out_[0-9][0-9].json")):
    data = json.load(open(f, encoding="utf-8")); changed = False
    for i, d in enumerate(data):
        if d["JID"] in fix:
            data[i] = fix[d["JID"]]; patched += 1; changed = True
    if changed:
        json.dump(data, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("patched", f.split("/")[-1])
print(f"共替換 {patched} 筆（fixup 共 {len(fix)} 筆）")
