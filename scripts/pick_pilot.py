import json

data = json.load(open('/workspace/data/extracted/structured_cases.json', encoding='utf-8'))
by_id = {d['JID']: d for d in data}

# 指定 7 筆（含 [A] 混合與測 SKIP）
named = [
    "KMEM,115,城交簡,15,20260317,1",   # 刑 clean 轉彎未讓直行
    "MLDM,114,交易,120,20260303,1",    # 刑 [A] 混合，事實藏在「更正」句 → 測 salvage
    "PCDM,115,交簡,469,20260330,1",    # 刑 [A] 「處有期徒刑…引用起訴書如附件」→ 測 SKIP/salvage
    "ULDV,114,簡,102,20260305,1",      # 民 clean 變換車道
    "ULDV,114,簡上,27,20260309,1",     # 民 clean 轉彎+酒駕
    "CDEV,114,橋簡,562,20260331,1",    # 民 [D] 停字標路口
    "MLDV,114,苗簡,849,20260305,1",    # 民 違規超車撞損
]

picked = [by_id[j] for j in named if j in by_id]
picked_ids = set(named)

# 自動補 3 筆：刑事過失致死、刑事違反號誌、民事純損害賠償
def find(src, must_labels, n=1):
    out = []
    for d in data:
        if d['JID'] in picked_ids: continue
        if d['_source'] != src: continue
        if all(l in d['核心爭議'] for l in must_labels):
            out.append(d); picked_ids.add(d['JID'])
            if len(out) >= n: break
    return out

picked += find('criminal', ['過失致死致重傷'], 1)
picked += find('criminal', ['違反號誌'], 1)
picked += find('civil', ['民事損害賠償'], 1)

print(f"挑出 {len(picked)} 筆\n")
for i, d in enumerate(picked, 1):
    s = d['事故摘要'].replace(' ', '')
    print(f"########## #{i}  [{d['_source']}] {d['JID']}  ({d['JTITLE']}) ##########")
    print(f"核心爭議: {d['核心爭議']}")
    print(f"責任類型: {d['責任類型']}")
    print(f"適用法條: {d['適用法條']}")
    print(f"事故摘要: {s}")
    print()
