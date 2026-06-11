# -*- coding: utf-8 -*-
"""把 1,918 筆切成多個 chunk，供 sub-agent 平行改寫。
每個 chunk 只保留 sub-agent 需要的欄位。"""
import json
from pathlib import Path

BASE = "/home/under115b/work/Traffic_Legal_LM"
data = json.load(open(f"{BASE}/data/extracted/structured_cases.json", encoding="utf-8"))

CHUNK_SIZE = 60
CHUNK_DIR = Path(f"{BASE}/data/colloquial/chunks")
CHUNK_DIR.mkdir(parents=True, exist_ok=True)

slim = [{"JID": d["JID"], "_source": d["_source"], "事故摘要": d["事故摘要"],
         "核心爭議": d["核心爭議"], "適用法條": d["適用法條"]} for d in data]

n_chunks = (len(slim) + CHUNK_SIZE - 1) // CHUNK_SIZE
for i in range(n_chunks):
    part = slim[i*CHUNK_SIZE:(i+1)*CHUNK_SIZE]
    path = CHUNK_DIR / f"chunk_{i:02d}.json"
    json.dump(part, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"總 {len(slim)} 筆 → {n_chunks} 個 chunk（每塊 {CHUNK_SIZE} 筆）")
print(f"chunk 目錄: {CHUNK_DIR}")
import os
sizes = [len(json.load(open(CHUNK_DIR/f'chunk_{i:02d}.json',encoding='utf-8'))) for i in range(n_chunks)]
print(f"各塊筆數: {sizes[:5]}... 最後一塊 {sizes[-1]}")
