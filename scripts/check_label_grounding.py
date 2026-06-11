# -*- coding: utf-8 -*-
"""檢查核心爭議標籤是否「接地」於事故摘要（而非只在完整判決書理由段）。
重跑 Step 3 的 DISPUTE_RULES，但只比對『事故摘要』，看哪些標籤在摘要裡找不到根據。"""
import json
from collections import Counter

BASE = "/home/under115b/work/Traffic_Legal_LM"
data = json.load(open(f"{BASE}/data/extracted/structured_cases.json", encoding="utf-8"))

DISPUTE_RULES = {
    "支線道未讓幹線道":   [("支線道", "幹線道")],
    "閃紅燈未停讓":      ["閃紅燈"],
    "閃黃燈未減速":      ["閃黃燈"],
    "左方車未讓右方車":  ["左方車未讓", ("左方", "右方")],
    "轉彎車未讓直行車":  ["轉彎車未讓", ("轉彎", "直行"), ("左轉", "未讓"), ("右轉", "未讓")],
    "變換車道未讓直行車": ["變換車道", ("變換", "直行")],
    "未注意車前狀況":    ["未注意車前狀況", "未保持安全距離", "車前狀況"],
    "違反號誌":         ["闖紅燈", ("紅燈", "號誌"), "闖越紅燈"],
    "與有過失":         ["與有過失", "過失比例", ("被害人", "過失"), "過失相抵", ("訴外人", "過失")],
    "過失致死致重傷":   ["過失致死", "過失致重傷", "死亡"],
    "過失傷害成立":     ["過失傷害"],
    "民事損害賠償":     ["損害賠償", ("賠償", "民事")],
}

def matches(text, rules):
    for r in rules:
        if isinstance(r, tuple):
            if all(x in text for x in r):
                return True
        elif r in text:
            return True
    return False

# 結果型標籤：用語意接地（摘要有傷亡/財損即可推得），不靠字面關鍵字
OUTCOME_GROUNDING = {
    "過失傷害成立":   ["傷", "受傷", "傷害"],
    "過失致死致重傷": ["死亡", "不治", "重傷", "死"],
    "民事損害賠償":   ["賠", "求償", "受損", "修復", "修理", "損害", "毀損"],
}
# 情境型標籤：必須有具體動態描述，維持字面關鍵字
SCENARIO = {"支線道未讓幹線道","閃紅燈未停讓","閃黃燈未減速","左方車未讓右方車",
            "轉彎車未讓直行車","變換車道未讓直行車","未注意車前狀況","違反號誌"}

def grounded_in_summary(text):
    g = set()
    for lab, rules in DISPUTE_RULES.items():
        if lab in OUTCOME_GROUNDING:
            if any(k in text for k in OUTCOME_GROUNDING[lab]):
                g.add(lab)
        else:
            if matches(text, rules):
                g.add(lab)
    return g

total = len(data)
dropped = Counter()       # 標籤在 stored 但摘要找不到根據（= 不可學雜訊）
n_cases_lose = 0
n_labels_total = 0
n_labels_dropped = 0
fully_ungrounded = 0      # 整筆所有爭議都不接地

for d in data:
    s = d["事故摘要"]
    stored = set(d["核心爭議"])
    M = grounded_in_summary(s)
    ungrounded = stored - M
    n_labels_total += len(stored)
    n_labels_dropped += len(ungrounded)
    if ungrounded:
        n_cases_lose += 1
        for lab in ungrounded:
            dropped[lab] += 1
    if stored and not (stored & M):
        fully_ungrounded += 1

print(f"總案例: {total}, 總標籤數: {n_labels_total}")
print(f"摘要找不到根據的標籤(不可學): {n_labels_dropped} ({n_labels_dropped/n_labels_total*100:.1f}% of labels)")
print(f"至少掉 1 個標籤的案例: {n_cases_lose} ({n_cases_lose/total*100:.1f}%)")
print(f"整筆爭議全不接地的案例: {fully_ungrounded} ({fully_ungrounded/total*100:.1f}%)")
print("\n各標籤『在摘要找不到根據』次數：")
for lab, c in dropped.most_common():
    print(f"  {lab}: {c}")
