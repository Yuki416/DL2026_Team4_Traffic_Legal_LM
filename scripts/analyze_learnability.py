# -*- coding: utf-8 -*-
"""量化 output 欄位的『可學習性』疑慮：
1. 與有過失 佔比（最常見標籤，但常是理由段結論，事故摘要未必有訊號）
2. 適用法條中『量刑/程序/利息』類條文的佔比（無法從事故描述推得）
3. 只有 1 條法條 / 含冗餘法條形式 的案例數
"""
import json
from collections import Counter

BASE = "/home/under115b/work/Traffic_Legal_LM"
data = json.load(open(f"{BASE}/data/extracted/structured_cases.json", encoding="utf-8"))
total = len(data)

# --- 1. 與有過失 ---
n_fault = sum(1 for d in data if "與有過失" in d["核心爭議"])
print(f"總筆數: {total}")
print(f"[1] 含『與有過失』: {n_fault} ({n_fault/total*100:.1f}%)  <- 最常見標籤")

# --- 2. 量刑/程序/利息類法條（無法從事故事實推得）---
# 刑事：量刑(57)、自首(62)、易科(41)、數罪併罰(50,51,53)、想像競合(55)、緩刑(74,75)、執行(71)
# 民事：遲延利息(229,203,233)、訴訟相關
NON_SUBSTANTIVE = [
    "刑法第41條", "刑法第50條", "刑法第51條", "刑法第53條", "刑法第55條",
    "刑法第57條", "刑法第62條", "刑法第71條", "刑法第74條", "刑法第75條",
    "民法第203條", "民法第229條", "民法第233條",
]
def is_non_sub(law):
    return any(law.startswith(p) for p in NON_SUBSTANTIVE)

total_refs = 0
non_sub_refs = 0
cases_with_nonsub = 0
for d in data:
    laws = d["適用法條"]
    total_refs += len(laws)
    ns = [l for l in laws if is_non_sub(l)]
    non_sub_refs += len(ns)
    if ns:
        cases_with_nonsub += 1

print(f"\n[2] 法條引用總數: {total_refs}")
print(f"    其中量刑/程序/利息類: {non_sub_refs} ({non_sub_refs/total_refs*100:.1f}%)")
print(f"    至少含 1 條此類法條的案例: {cases_with_nonsub} ({cases_with_nonsub/total*100:.1f}%)")

# 細分各條出現次數
cnt = Counter()
for d in data:
    for l in d["適用法條"]:
        for p in NON_SUBSTANTIVE:
            if l.startswith(p):
                cnt[p] += 1
print("    細分：")
for p, c in cnt.most_common():
    print(f"      {p}*: {c}")

# --- 3. 只有 1 條法條 / 冗餘形式 ---
one_law = sum(1 for d in data if len(d["適用法條"]) == 1)
print(f"\n[3] 只有 1 條法條: {one_law} ({one_law/total*100:.1f}%)")

# 冗餘：同一條同時有『X條前段』與『X條第1項前段』等
def has_redundant(laws):
    for a in laws:
        for b in laws:
            if a != b and b.startswith(a.replace("前段","").replace("後段","")[:6]):
                # 粗略：同條號不同精細度
                import re
                ma = re.match(r"(.+?第\d+條)", a)
                mb = re.match(r"(.+?第\d+條)", b)
                if ma and mb and ma.group(1)==mb.group(1) and a!=b:
                    # 一個是另一個的前綴
                    if a.replace("前段","").replace("後段","") in b or b.replace("前段","").replace("後段","") in a:
                        return True
    return False
redundant = sum(1 for d in data if has_redundant(d["適用法條"]))
print(f"    含疑似冗餘法條形式（同條不同精細度並存）: {redundant} ({redundant/total*100:.1f}%)")
