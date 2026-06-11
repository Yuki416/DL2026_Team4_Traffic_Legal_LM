# -*- coding: utf-8 -*-
"""
比較兩個模型在 18 筆共享 test set 上的表現：
  - round2_sonnet46_lora  （本次訓練，我們的資料集）
  - round2_gpt4o_baseline_lora（基準線，GPT-4o 資料集）

metrics:
  - 責任類型 accuracy（刑/民，最公平的比較指標）
  - 核心爭議 F1（各自對照各自的 ground truth 標籤）
  - 適用法條 article F1（擷取條文號後算 precision/recall/F1）

輸出：
  eval/eval_results.json    — 逐筆結果
  eval/eval_summary.json    — 彙整指標
"""

import json, re, os, sys
from llamafactory.chat import ChatModel

BASE   = "/workspace"
TEST   = f"{BASE}/data/colloquial/test.json"
MAR_TEST = f"{BASE}/data/mar_test.json"
OUT_DIR  = f"{BASE}/eval"
os.makedirs(OUT_DIR, exist_ok=True)

# ---------- 模型設定 ----------
MODELS = {
    "sonnet46": {
        "adapter": f"{BASE}/models/round2_sonnet46_lora",
        "instruction_mode": "our",   # 用 test.json 裡的 instruction
    },
    "gpt4o": {
        "adapter": f"{BASE}/models/round2_gpt4o_baseline_lora",
        "instruction_mode": "gpt4o", # 用 GPT-4o 的 instruction
    },
}
BASE_MODEL = "/mnt/8tb_hdd/under115b/traffic_legal_lm/models/Llama-3-Taiwan-8B-Instruct"

# ---------- 測試資料 ----------
our_test  = json.load(open(TEST, encoding="utf-8"))         # 18 筆，我們的格式
mar_test  = {d["jid"]: d for d in json.load(open(MAR_TEST, encoding="utf-8"))}

# 建 jid 對照（test.json 有 _jid）
our_by_jid = {d["_jid"]: d for d in our_test}

# GPT-4o instruction 按刑/民選擇
def gpt4o_instruction(source):
    if source == "criminal":
        return "請判斷以下車禍刑事情境的核心爭議、責任類型與適用法條"
    return "請判斷以下車禍民事求償情境的核心爭議、責任類型與適用法條"

# ---------- Parser ----------
def parse_our(text):
    """解析 【核心爭議】...【責任類型】...【適用法條】... 格式"""
    d = {}
    m = re.search(r"【核心爭議】(.+)", text)
    d["disputes"] = [x.strip() for x in m.group(1).split("、")] if m else []
    m = re.search(r"【責任類型】(.+)", text)
    d["resp_type"] = m.group(1).strip() if m else ""
    m = re.search(r"【適用法條】(.+)", text)
    d["laws"] = [x.strip() for x in m.group(1).split("、")] if m else []
    return d

def parse_gpt4o(text):
    """解析 JSON 格式 output，容錯處理"""
    try:
        # 有時模型會多輸出前置文字
        start = text.find("{")
        obj = json.loads(text[start:]) if start >= 0 else {}
        return {
            "disputes": obj.get("核心爭議", []),
            "resp_type": "、".join(obj.get("責任類型", [])),
            "laws": obj.get("適用法條", []),
        }
    except Exception:
        return {"disputes": [], "resp_type": "", "laws": []}

def extract_articles(law_list):
    """從法條字串列表提取 '刑法第X條' 等基礎條文號"""
    arts = set()
    for l in law_list:
        m = re.match(r"(.+?第\d+(?:-\d+)?條)", str(l))
        if m:
            arts.add(m.group(1))
    return arts

def f1(pred_set, gold_set):
    if not pred_set and not gold_set:
        return 1.0, 1.0, 1.0
    if not pred_set or not gold_set:
        return 0.0, 0.0, 0.0
    tp = len(pred_set & gold_set)
    p  = tp / len(pred_set)
    r  = tp / len(gold_set)
    f  = 2*p*r/(p+r) if (p+r) > 0 else 0.0
    return p, r, f

def resp_type_normalize(s):
    if "刑" in s: return "criminal"
    if "民" in s: return "civil"
    return s.strip()

# ---------- 推論 ----------
all_results = []

for model_name, cfg in MODELS.items():
    print(f"\n{'='*50}")
    print(f"載入模型: {model_name}")
    print(f"{'='*50}")

    chat_model = ChatModel(dict(
        model_name_or_path=BASE_MODEL,
        adapter_name_or_path=cfg["adapter"],
        template="llama3",
        finetuning_type="lora",
        infer_dtype="bfloat16",
    ))

    for item in our_test:
        jid    = item["_jid"]
        source = item["_source"]
        input_text = item["input"]

        # instruction
        if cfg["instruction_mode"] == "our":
            instruction = item["instruction"]
        else:
            instruction = gpt4o_instruction(source)

        # 推論
        messages = [{"role": "user", "content": f"{instruction}\n\n{input_text}"}]
        response = chat_model.chat(messages)[0].response_text

        # 解析
        if cfg["instruction_mode"] == "our":
            pred = parse_our(response)
            gold = parse_our(item["output"])
        else:
            pred = parse_gpt4o(response)
            # GPT-4o ground truth 從 mar_test 取
            mar_item = mar_test.get(jid, {})
            gold_raw = parse_gpt4o(mar_item.get("output", "{}"))
            gold = gold_raw

        # 責任類型
        pred_rt = resp_type_normalize(pred["resp_type"])
        gold_rt = source  # ground truth 就是 _source

        # 適用法條 F1
        pred_arts = extract_articles(pred["laws"])
        gold_arts = extract_articles(gold["laws"])
        law_p, law_r, law_f1 = f1(pred_arts, gold_arts)

        result = {
            "jid": jid,
            "source": source,
            "model": model_name,
            "input": input_text,
            "pred_raw": response,
            "pred_resp_type": pred_rt,
            "gold_resp_type": gold_rt,
            "resp_correct": pred_rt == gold_rt,
            "pred_disputes": pred["disputes"],
            "gold_disputes": gold["disputes"],
            "pred_laws": list(pred_arts),
            "gold_laws": list(gold_arts),
            "law_precision": round(law_p, 3),
            "law_recall": round(law_r, 3),
            "law_f1": round(law_f1, 3),
        }

        # 核心爭議 F1（只在格式相同時才可比）
        if cfg["instruction_mode"] == "our":
            p_d = set(pred["disputes"])
            g_d = set(gold["disputes"])
            dp, dr, df = f1(p_d, g_d)
            result["dispute_precision"] = round(dp, 3)
            result["dispute_recall"]    = round(dr, 3)
            result["dispute_f1"]        = round(df, 3)

        all_results.append(result)
        print(f"  [{model_name}] {jid} | 責任: {'✅' if result['resp_correct'] else '❌'} | law_f1={law_f1:.2f}")

    del chat_model  # 釋放 VRAM 再載下一個

# ---------- 彙整 ----------
summary = {}
for model_name in MODELS:
    rows = [r for r in all_results if r["model"] == model_name]
    n = len(rows)
    resp_acc = sum(r["resp_correct"] for r in rows) / n
    law_f1   = sum(r["law_f1"] for r in rows) / n
    law_p    = sum(r["law_precision"] for r in rows) / n
    law_r    = sum(r["law_recall"] for r in rows) / n
    entry = {
        "n": n,
        "resp_type_accuracy": round(resp_acc, 3),
        "law_precision_avg":  round(law_p, 3),
        "law_recall_avg":     round(law_r, 3),
        "law_f1_avg":         round(law_f1, 3),
    }
    if model_name == "sonnet46":
        disp_f1 = sum(r.get("dispute_f1", 0) for r in rows) / n
        disp_p  = sum(r.get("dispute_precision", 0) for r in rows) / n
        disp_r  = sum(r.get("dispute_recall", 0) for r in rows) / n
        entry["dispute_precision_avg"] = round(disp_p, 3)
        entry["dispute_recall_avg"]    = round(disp_r, 3)
        entry["dispute_f1_avg"]        = round(disp_f1, 3)
    summary[model_name] = entry

json.dump(all_results, open(f"{OUT_DIR}/eval_results.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(summary,    open(f"{OUT_DIR}/eval_summary.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)

print("\n" + "="*50)
print("評估完成")
print("="*50)
for model_name, s in summary.items():
    print(f"\n[{model_name}]")
    print(f"  責任類型 accuracy : {s['resp_type_accuracy']*100:.1f}%")
    print(f"  適用法條 F1       : {s['law_f1_avg']:.3f}  (P={s['law_precision_avg']:.3f} R={s['law_recall_avg']:.3f})")
    if "dispute_f1_avg" in s:
        print(f"  核心爭議 F1       : {s['dispute_f1_avg']:.3f}  (P={s['dispute_precision_avg']:.3f} R={s['dispute_recall_avg']:.3f})")
print(f"\n結果已儲存至 {OUT_DIR}/")
