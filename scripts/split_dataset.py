# -*- coding: utf-8 -*-
"""Step 5：把 training_pairs.json 切成 train/val/test。
- test: 與 mar_test.json 共享的 18 個 JID（固定，不隨機）
- val : 50（依刑/民比例，從剩餘中取）
- train: 其餘
train/val 只留 instruction/input/output（LlamaFactory 用）；test 額外保留 _jid/_source。
"""
import json, random

BASE = "/home/under115b/work/Traffic_Legal_LM"
SRC = f"{BASE}/data/colloquial/training_pairs.json"
MAR_TEST = f"{BASE}/data/mar_test.json"
OUT_DIR = f"{BASE}/data/colloquial"
SEED = 42

# 固定 test JIDs：與 mar_test.json 共享的 18 筆
mar_jids = {d["jid"] for d in json.load(open(MAR_TEST, encoding="utf-8"))}

data = json.load(open(SRC, encoding="utf-8"))
test = [d for d in data if d["_jid"] in mar_jids]
rest = [d for d in data if d["_jid"] not in mar_jids]

# val: 50 依刑/民比例，從 rest 中取
crim = [d for d in rest if d["_source"] == "criminal"]
civ  = [d for d in rest if d["_source"] == "civil"]
random.seed(SEED); random.shuffle(crim); random.shuffle(civ)

n_rest = len(crim) + len(civ)
val_c = round(50 * len(crim) / n_rest)
val_v = 50 - val_c
val = crim[:val_c] + civ[:val_v]
train = crim[val_c:] + civ[val_v:]

random.shuffle(train); random.shuffle(val); random.shuffle(test)

def strip(d):  # train/val 只留三欄
    return {"instruction": d["instruction"], "input": d["input"], "output": d["output"]}

json.dump([strip(d) for d in train], open(f"{OUT_DIR}/train.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump([strip(d) for d in val],   open(f"{OUT_DIR}/val.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(test, open(f"{OUT_DIR}/test.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"train {len(train)} / val {len(val)} / test {len(test)}")
print(f"  test 組成: 刑 {sum(1 for d in test if d['_source']=='criminal')} / 民 {sum(1 for d in test if d['_source']=='civil')}")
print(f"  val  組成: 刑 {val_c} / 民 {val_v}")
print(f"輸出: {OUT_DIR}/train.json, val.json, test.json")
