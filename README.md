# Traffic_Legal_LM

台灣交通事故法律分析助理 — 以 [Llama-3-Taiwan-8B-Instruct-rc2](https://huggingface.co/yentinglin/Llama-3-Taiwan-8B-Instruct-rc2) 為基底，
透過 LoRA 微調，讓模型能根據使用者以**口語描述**的車禍事故，自動分析：

- **核心爭議**（從 12 類封閉標籤中選擇）
- **責任類型**（刑事 / 民事 / 行政）
- **適用法條**（道路交通安全規則、刑法、民法等）

> 本 repo 同時包含兩條獨立的資料集建置路線（本團隊 Step1-4 規則式 pipeline + Claude Sonnet 4.6 改寫，
> 以及教學組以 GPT-4o 直接抽取），並以相同基底模型分別微調、在共享的 18 筆 test set 上做對照評估，
> 詳見 [`report.md`](report.md)。

---

## 1. 專案目標

1. 將台灣司法院公開的交通事故判決書，轉換成「使用者口語提問 → 結構化法律分析」的監督式微調資料集
2. 比較兩種資料集建置方式（規則式抽取 + LLM 改寫 vs. 端到端 LLM 抽取）對微調結果的影響
3. 以 LoRA 微調 Llama-3-Taiwan-8B-Instruct-rc2，並用 Gradio demo 展示三個模型（Base / GPT-4o LoRA / Sonnet LoRA）的回答差異

---

## 2. 處理流程（Step1–4）

```
司法院資料開放平台「裁判書」資料集（202602 / 202603，20260516 更新版）
        ↓ 手動下載 .rar 壓縮檔並解壓
data/raw/                              ← 原始判決書 JSON（已 gitignore，見第 4 節）
        ↓ Step1 規則式篩選
        │   scripts/02_filter.py        （刑事：JCASE 含「交」+ JTITLE 過失傷害/致死/致重傷 等）
        │   scripts/02b_filter_civil.py （民事：JTITLE 含「交通」+「損害賠償/侵權行為」）
data/filtered/traffic_cases*.json      ← 篩選後判決書
        ↓ Step2 人工 QC（scripts/qc_sample.py 等）
        ↓ Step3 結構化抽取（規則式，零 LLM）
        │   scripts/03_extract.py
data/extracted/structured_cases.json   ← 1,918 筆結構化資料（事故摘要 / 核心爭議 / 責任類型 / 適用法條）
        ↓ Step4 白話化改寫（Claude Sonnet 4.6，32 個並行 sub-agent）
        │   scripts/make_chunks.py → 32 個 chunk → out_00~31.json
        │   scripts/sanitize_and_assemble.py
data/colloquial/training_pairs.json    ← 1,759 筆 Alpaca 格式訓練對
        ↓ scripts/split_dataset.py
data/colloquial/{train,val,test}.json  ← 1,691 / 50 / 18 筆
```

Step4 的詳細設計與執行紀錄見 [`docs/step4_workflow_record.md`](docs/step4_workflow_record.md)。

12 類核心爭議標籤：轉彎車未讓直行車、變換車道未讓直行車、支線道未讓幹線道、左方車未讓右方車、違反號誌、
未注意車前狀況、閃紅燈未停讓、閃黃燈未減速、與有過失、過失致死致重傷、過失傷害成立、民事損害賠償。

法條範圍經 [`scripts/analyze_learnability.py`](scripts/analyze_learnability.py) 分析，過濾掉「無法從事故描述本身學到」的
量刑/程序/利息類條文（如刑法第41/50/51/53/55/57/71/74/75條、民法第203/229/233條）。

---

## 3. 目錄結構

```
Traffic_Legal_LM/
├── data/
│   ├── raw/                       # 原始判決書（gitignore，公開資料來源見第4節）
│   ├── filtered/                  # Step1 篩選結果
│   ├── extracted/                 # Step3 結構化抽取結果（1,918 筆）
│   ├── colloquial/                # Step4 最終訓練資料（本團隊資料集）
│   ├── final_fine_tuning_data/    # 教學組 GPT-4o 資料集（2 月）
│   ├── traffic_202603_alpaca_gpt4o_outputs/  # 教學組 GPT-4o 中間產物（3 月）
│   ├── mar_gpt4o_train.json / mar_gpt4o_val.json / mar_test.json  # 教學組 GPT-4o 資料集（3 月）
│   └── dataset_info.json          # LLaMA-Factory 資料集註冊
├── scripts/
│   ├── 02_filter.py / 02b_filter_civil.py   # Step1 篩選
│   ├── 03_extract.py              # Step3 結構化抽取
│   ├── make_chunks.py / sanitize_and_assemble.py / split_dataset.py  # Step4 切分與組裝
│   ├── analyze_learnability.py    # 法條可學習性分析
│   ├── train_round1.yaml / train_round2_sonnet46.yaml / train_round2_gpt4o_baseline.yaml  # LLaMA-Factory 訓練設定
│   ├── eval_comparison.py         # Round2 兩模型對照評估
│   ├── upload_models_to_hf.py     # 將 LoRA adapter 上傳到 Hugging Face Hub
│   └── test_*.py                  # Docker 環境驗證腳本
├── models/                         # LoRA adapter（gitignore，見第5節 Hugging Face Hub 連結）
├── eval/                           # 評估結果（eval_results.json / eval_summary.json / test_cases.json）
├── demo/                           # Gradio demo（app.py：Base / GPT-4o LoRA / Sonnet LoRA 三模型對照）
├── docs/                           # 開發流程記錄（Step4 workflow 等）
├── report.md                       # 完整分析報告（資料集品質、Round1/2 模型對照評估）
├── Dockerfile                      # 訓練環境（CUDA 12.1 + LLaMA-Factory）
└── LICENSE                         # MIT License
```

---

## 4. 資料集

### 4.1 公開資料（原始判決書）

- 來源：[司法院資料開放平台](https://opendata.judicial.gov.tw/)「裁判書」資料集
- 取得方式：於平台註冊帳號（學校 email 通常自動核准）後，下載「裁判書」202602、202603 月份壓縮檔（20260516 更新版），解壓至 `data/raw/`
- `data/raw/` 已加入 `.gitignore`（不上傳，原始解壓後約 1.9GB）

### 4.2 本團隊資料集（`data/colloquial/`）

- 由上述公開判決書經 Step1-4 處理而成，**全程可重現**（規則式 pipeline 全部開源在 `scripts/`，
  Step4 改寫的 prompt 見 [`scripts/subagent_prompt.md`](scripts/subagent_prompt.md)）
- 格式：Alpaca（`instruction` / `input` / `output`），`output` 為三行結構化標籤：
  ```
  【核心爭議】違反號誌、未注意車前狀況、過失傷害成立
  【責任類型】刑事
  【適用法條】道路交通安全規則第90條第1項、刑法第284條前段、刑法第62條前段
  ```
- 規模：train 1,691 筆 / val 50 筆 / test 18 筆（共 1,759 筆）
- 對應 LLaMA-Factory dataset 名稱：`traffic_legal_0603_train` / `traffic_legal_0603_val`

### 4.3 教學組 GPT-4o 資料集（`data/final_fine_tuning_data/`、`data/mar_gpt4o_*.json`）

- 由教學組以 GPT-4o 直接對判決書做端到端抽取（2 月份、3 月份兩批），輸出為較長的自由格式 JSON
- 用於 Round1（`traffic_law_round1`）與 Round2 對照組（`traffic_law_mar_gpt4o_train` / `traffic_law_mar_gpt4o_val`）
- 與本團隊資料集的差異分析見 `report.md` 第八章

---

## 5. 模型

3 個 LoRA adapter 皆以 [yentinglin/Llama-3-Taiwan-8B-Instruct-rc2](https://huggingface.co/yentinglin/Llama-3-Taiwan-8B-Instruct-rc2)
為基底，使用 LLaMA-Factory 訓練，已上傳至 Hugging Face Hub：

| 模型 | Hugging Face | 說明 |
|---|---|---|
| Round 1 LoRA | [traffic-legal-lm/round1-lora](https://huggingface.co/traffic-legal-lm/round1-lora) | 初版小規模資料集，驗證訓練流程用 |
| Round 2 — 本團隊資料集 | [traffic-legal-lm/round2-sonnet46-lora](https://huggingface.co/traffic-legal-lm/round2-sonnet46-lora) | `data/colloquial/`，12 類封閉核心爭議標籤、過濾過後法條 |
| Round 2 — GPT-4o baseline | [traffic-legal-lm/round2-gpt4o-baseline-lora](https://huggingface.co/traffic-legal-lm/round2-gpt4o-baseline-lora) | 教學組 GPT-4o 資料集，自由格式、法條範圍較廣 |

### 訓練方式

- 框架：[LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory)（容器內以 `pip install llamafactory` 安裝，見 `Dockerfile`）
- 方法：LoRA，`lora_target=all`，rank=16，alpha=32，dropout=0.05
- Round1：per_device_batch=4 / grad_accum=2，3 epochs
- Round2（兩個模型設定相同）：per_device_batch=2 / grad_accum=4（有效 batch=16），2 epochs，
  lr=2e-4（cosine, warmup 10%），bf16，gradient checkpointing，依 `eval_loss` 做 early stopping
- 完整設定見 `scripts/train_round1.yaml`、`scripts/train_round2_sonnet46.yaml`、`scripts/train_round2_gpt4o_baseline.yaml`

---

## 6. 評估結果

於兩個 Round2 模型共享的 18 筆 test set 上評估（`scripts/eval_comparison.py`，結果見 `eval/eval_summary.json`）：

| 指標 | Round2-Sonnet46 | Round2-GPT4o-baseline |
|---|---|---|
| 責任類型 accuracy | 1.0 | 1.0 |
| 適用法條 F1 | 0.573（precision 0.586 / recall 0.627） | 0.701（precision 0.753 / recall 0.694） |
| 核心爭議 F1 | 0.811（precision 0.833 / recall 0.83） | — （自由生成句子，無封閉 ground truth） |

兩種路線的取捨（輸出格式、可驗證性、法條範圍與噪音等）詳細分析見 [`report.md`](report.md) 第八章。

---

## 7. 使用方式

### 7.1 環境建置

```bash
docker build -t legal-lora:latest .
```

容器基於 `nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04`，內含 PyTorch 2.5.1+cu121、LLaMA-Factory、bitsandbytes。

```bash
# 驗證環境
docker run --gpus all --rm -v $(pwd):/workspace -w /workspace \
  legal-lora:latest python scripts/test_setup.py

# GPU 記憶體用量
docker run --gpus all --rm -v $(pwd):/workspace -w /workspace \
  legal-lora:latest python scripts/test_gpu_memory.py
```

### 7.2 重現資料處理 pipeline

```bash
# 先於 https://opendata.judicial.gov.tw/ 申請帳號，下載「裁判書」202602/202603 月份壓縮檔並解壓至 data/raw/
python scripts/02_filter.py               # Step1 刑事篩選
python scripts/02b_filter_civil.py        # Step1 民事篩選
python scripts/03_extract.py              # Step3 結構化抽取
# Step4 白話化改寫需透過 Claude sub-agent，prompt 見 scripts/subagent_prompt.md
python scripts/split_dataset.py           # 切分 train/val/test
```

### 7.3 訓練

```bash
llamafactory-cli train scripts/train_round2_sonnet46.yaml
```

### 7.4 載入模型推論

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base_model_id = "yentinglin/Llama-3-Taiwan-8B-Instruct-rc2"
adapter_id = "traffic-legal-lm/round2-sonnet46-lora"

tokenizer = AutoTokenizer.from_pretrained(base_model_id)
model = AutoModelForCausalLM.from_pretrained(base_model_id, torch_dtype="bfloat16", device_map="auto")
model = PeftModel.from_pretrained(model, adapter_id)
```

### 7.5 Demo

`demo/app.py` 為 Gradio 介面，同時載入 Base model、GPT-4o LoRA、Sonnet LoRA 三個模型，可並排比較回答：

```bash
python demo/app.py
```

---

## 8. 文件索引

- [`report.md`](report.md) — 完整分析報告：資料集品質問題、Step1-4 pipeline 設計、Round1/2 模型對照評估
- [`docs/step4_workflow_record.md`](docs/step4_workflow_record.md) — Step4 白話化改寫設計與執行紀錄
- [`roadmap.md`](roadmap.md)、[`專案規劃.md`](專案規劃.md)、[`資料集製作.md`](資料集製作.md)、
  [`如何結構化抽取判決書.md`](如何結構化抽取判決書.md) — 開發歷程文件

---

## 9. 授權

本 repo 程式碼採 [MIT License](LICENSE)。

基底模型 [Llama-3-Taiwan-8B-Instruct-rc2](https://huggingface.co/yentinglin/Llama-3-Taiwan-8B-Instruct-rc2)
採 [Llama 3 Community License](https://huggingface.co/yentinglin/Llama-3-Taiwan-8B-Instruct-rc2/blob/main/LICENSE)，
使用本專案 LoRA adapter 時請一併遵守該授權條款。

---

## 10. 團隊成員

| 姓名 | GitHub |
|---|---|
| [TODO] | [TODO] |
| [TODO] | [TODO] |
| [TODO] | [TODO] |
