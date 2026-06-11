# -*- coding: utf-8 -*-
"""上傳 3 個 Round1/Round2 LoRA adapter 到 Hugging Face Hub (org: traffic-legal-lm)。
為每個 adapter 重寫 README.md（model card），並排除 checkpoint-* 中間存檔後上傳。
"""
import os
import tempfile
from huggingface_hub import HfApi, create_repo, upload_folder

TOKEN = os.environ["HF_TOKEN"]
ORG = "traffic-legal-lm"
BASE = "/home/under115b/work/Traffic_Legal_LM/models"

CARD_HEADER = """---
license: llama3
base_model: yentinglin/Llama-3-Taiwan-8B-Instruct-rc2
library_name: peft
language:
- zh
tags:
- lora
- llama-factory
- traffic-law
- legal-nlp
- zh-tw
pipeline_tag: text-generation
---

"""

USAGE = """## 使用方式

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base_model_id = "yentinglin/Llama-3-Taiwan-8B-Instruct-rc2"
adapter_id = "{repo_id}"

tokenizer = AutoTokenizer.from_pretrained(base_model_id)
model = AutoModelForCausalLM.from_pretrained(base_model_id, torch_dtype="bfloat16", device_map="auto")
model = PeftModel.from_pretrained(model, adapter_id)
```

更完整的處理流程、資料集與評估說明請見專案 repo：
[Traffic_Legal_LM](https://github.com/Yuki416/DL2026_Team4_Traffic_Legal_LM)
"""

MODELS = {
    "round1-lora": {
        "dir": "round1_lora",
        "title": "Round 1 LoRA — Traffic Legal LM (初版基準)",
        "body": """# Round 1 LoRA — Traffic Legal LM

第一輪 LoRA 微調，使用 `traffic_law_round1`（初版小規模資料集）對
[yentinglin/Llama-3-Taiwan-8B-Instruct-rc2](https://huggingface.co/yentinglin/Llama-3-Taiwan-8B-Instruct-rc2)
進行微調，主要用於驗證 LLaMA-Factory 訓練流程。後續 Round 2 的兩個模型
（`round2-sonnet46-lora` / `round2-gpt4o-baseline-lora`）已取代本模型作為正式比較對象。

## 訓練設定

- Base model: `yentinglin/Llama-3-Taiwan-8B-Instruct-rc2`
- Dataset: `traffic_law_round1`
- Method: LoRA, `lora_target=all`, rank=16, alpha=32, dropout=0.05
- Batch size: per_device=4, grad_accum=2（有效 batch=8）
- Epochs: 3, lr=2e-4 (cosine, warmup 10%), bf16

## 訓練結果

- train_loss: 0.145（無 eval set）

""",
    },
    "round2-sonnet46-lora": {
        "dir": "round2_sonnet46_lora",
        "title": "Round 2 LoRA — Sonnet 4.6 資料集",
        "body": """# Round 2 LoRA — Sonnet 4.6 資料集

第二輪 LoRA 微調，使用本團隊 Step1-4 流程（規則式篩選 + 結構化抽取 +
Claude Sonnet 4.6 白話化改寫）產出的 `traffic_legal_0603_train/val` 資料集，對
[yentinglin/Llama-3-Taiwan-8B-Instruct-rc2](https://huggingface.co/yentinglin/Llama-3-Taiwan-8B-Instruct-rc2)
進行微調。輸出格式為簡潔三行（責任類型 / 適用法條 / 核心爭議，核心爭議為
12 類封閉標籤）。

## 訓練設定

- Base model: `yentinglin/Llama-3-Taiwan-8B-Instruct-rc2`
- Dataset: `traffic_legal_0603_train` / `traffic_legal_0603_val`
- Method: LoRA, `lora_target=all`, rank=16, alpha=32, dropout=0.05
- Batch size: per_device=2, grad_accum=4（有效 batch=16）
- Epochs: 2, lr=2e-4 (cosine, warmup 10%), bf16, gradient checkpointing
- Early stopping: 依 eval_loss（eval_steps=100）

## 訓練結果

- train_loss: 0.210, eval_loss: 0.155

## 評估結果（18 筆共享 test set，與 round2-gpt4o-baseline-lora 對照）

| 指標 | 數值 |
|---|---|
| 責任類型 accuracy | 1.0 |
| 適用法條 F1 | 0.573 (precision 0.586 / recall 0.627) |
| 核心爭議 F1 | 0.811 (precision 0.833 / recall 0.83) |

詳細逐案分析見 repo 內 `report.md` 第八章與 `eval/eval_summary.json`。

""",
    },
    "round2-gpt4o-baseline-lora": {
        "dir": "round2_gpt4o_baseline_lora",
        "title": "Round 2 LoRA — GPT-4o 資料集 (baseline)",
        "body": """# Round 2 LoRA — GPT-4o 資料集 (baseline)

第二輪 LoRA 微調的對照組，使用教學組以 GPT-4o 抽取的 `traffic_law_mar_gpt4o_train/val`
資料集（2026 年 3 月版），對
[yentinglin/Llama-3-Taiwan-8B-Instruct-rc2](https://huggingface.co/yentinglin/Llama-3-Taiwan-8B-Instruct-rc2)
進行微調。輸出為較長的 JSON 格式，適用法條範圍較廣（未經過濾）、核心爭議為
自由生成的句子（無封閉標籤）。

## 訓練設定

- Base model: `yentinglin/Llama-3-Taiwan-8B-Instruct-rc2`
- Dataset: `traffic_law_mar_gpt4o_train` / `traffic_law_mar_gpt4o_val`
- Method: LoRA, `lora_target=all`, rank=16, alpha=32, dropout=0.05
- Batch size: per_device=2, grad_accum=4（有效 batch=16）
- Epochs: 2, lr=2e-4 (cosine, warmup 10%), bf16, gradient checkpointing
- Early stopping: 依 eval_loss（eval_steps=100）

## 訓練結果

- train_loss: 0.103, eval_loss: 0.0535

## 評估結果（18 筆共享 test set，與 round2-sonnet46-lora 對照）

| 指標 | 數值 |
|---|---|
| 責任類型 accuracy | 1.0 |
| 適用法條 F1 | 0.701 (precision 0.753 / recall 0.694) |

核心爭議為自由生成句子，無封閉 ground truth，因此不計算 F1。
詳細逐案分析見 repo 內 `report.md` 第八章與 `eval/eval_summary.json`。

""",
    },
}

api = HfApi(token=TOKEN)

for slug, cfg in MODELS.items():
    repo_id = f"{ORG}/{slug}"
    local_dir = os.path.join(BASE, cfg["dir"])

    print(f"=== {repo_id} ===")
    create_repo(repo_id, token=TOKEN, repo_type="model", exist_ok=True)

    readme_content = CARD_HEADER + cfg["body"] + USAGE.format(repo_id=repo_id)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(readme_content)
        tmp_readme = f.name

    api.upload_file(
        path_or_fileobj=tmp_readme,
        path_in_repo="README.md",
        repo_id=repo_id,
        commit_message="Add model card",
    )
    os.unlink(tmp_readme)

    upload_folder(
        repo_id=repo_id,
        folder_path=local_dir,
        token=TOKEN,
        ignore_patterns=["checkpoint-*", "README.md"],
        commit_message="Upload LoRA adapter",
    )
    print(f"Done: https://huggingface.co/{repo_id}")

print("ALL DONE")
