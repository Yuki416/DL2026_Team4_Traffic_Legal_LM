---
title: 第一週開發流程（5/26 – 6/1）
---

## 目標

拿到第一版訓練資料 + 跑出第一個微調模型（即使爛也要跑出來）

**milestone**: 週末前有一個可推論的 LoRA 微調模型

---

## 任務分配總覽

| Owner | 任務 | 預估時數 | 狀態 |
|---|---|---|---|
| B | 註冊司法院資料開放平臺，下載裁判書壓縮檔至 HDD（已下載 2、3 月份） | 1 hr | ✅ 完成 |
| B | 解壓並篩出路口路權判決（刑事 899 + 民事 1,260 = 2,159 筆） | 2 hr | ✅ 完成 |
| B | 隨機抽 30 筆人工確認品質（需 8 成以上符合才繼續） | 0.5 hr | ✅ 完成（27/30 通過，已修正篩選條件） |
| B | 把篩選出的判決貼給 Claude Code 做結構化抽取（先跑 20 筆送 A 確認） | 3 hr | 待完成 |
| B | 確認品質後繼續跑完全部，再做白話化改寫 | 2 hr | 待完成 |
| B | 切分 train/val/test，上傳 HF `traffic-accident-legal-qa` | 1 hr | 待完成 |
| C | 人工標註評估集 50 筆（test set 洗掉 output 後重新標） | 3 hr | 待完成 |
| C | 開始 Gradio demo 基本版 | 2 hr | 待完成 |
| A | 確認 B 的 20 筆抽取品質（調整 prompt） | 0.5 hr | 待完成 |
| A | 寫資料載入腳本（從 HF 下載，轉成 LlamaFactory alpaca 格式） | 2 hr | 待完成 |
| A | 跑出第一版 LoRA 微調 | 2 hr | 待完成 |
| 全員 | 週日週會：看第一版結果、討論問題 | 1 hr | 待完成 |

---

## 資料集建立流程（B 負責，A 最終確認）

> 📌 專案目標與議題定義見 [專案規劃.md](專案規劃.md)。

> ✅ **實作現況（2026-06-08）**：以 3 月份司法院裁判書（105,384 筆）為來源，採**雙 pipeline** 篩選：
> - 刑事 pipeline（`02_filter.py`）：三層篩選 → **899 筆**
> - 民事 pipeline（`02b_filter_civil.py`）：兩層篩選 → **1,260 筆**
> - 合併去重 → **2,159 筆**（`traffic_cases_merged.json`）
>
> 篩選方式、案類/案由/關鍵字的完整分析見 [3月份資料集.md](data/final_fine_tuning_data/3月份資料集.md)。
> 民事 pipeline 是為了補足二月份「行政/民事責任缺席」而新增；行政（交通裁決）目前仍缺，見專案規劃的待處理缺口。

### 資料夾結構

```
/mnt/8tb_hdd/traffic_legal_lm/
└── raw/              # 司法院壓縮檔解壓後的巢狀 JSON（勿放 SSD）

data/                 # 專案目錄下（SSD），只放篩選後的小檔案
├── filtered/         # 篩選後的車禍判決
├── extracted/        # 結構化抽取結果
├── colloquial/       # 白話化後的訓練配對
└── final/            # train / val / test 切分完成

scripts/
├── 02_filter.py
├── 05_split.py
```

環境需求：
```bash
pip install pandas tqdm
```

---

### Step 1：從司法院下載裁判書

1. 註冊 https://opendata.judicial.gov.tw/（用學校 email，通常自動核准）
2. 找到「裁判書」資料集，下載**最近 2 個月**的壓縮檔
3. 解壓到 HDD：

```bash
mkdir -p /mnt/8tb_hdd/traffic_legal_lm/raw
unzip 裁判書_202404.zip -d /mnt/8tb_hdd/traffic_legal_lm/raw/202404
unzip 裁判書_202405.zip -d /mnt/8tb_hdd/traffic_legal_lm/raw/202405
```

司法院 JSON 欄位說明：
```json
{
  "JID":    "TPDM,113,交簡,1234,20240315,1",
  "JCASE":  "交簡",
  "JTITLE": "過失傷害",
  "JFULL":  "判決書全文..."
}
```

---

### Step 2：篩選路口路權判決（`02_filter.py`）

```python
import json
from pathlib import Path
from tqdm import tqdm

DATA_ROOTS = [
    Path("/mnt/8tb_hdd/traffic_legal_lm/raw/202404"),
    Path("/mnt/8tb_hdd/traffic_legal_lm/raw/202405"),
]

TARGET_CASE_TYPES = ["交簡", "交訴", "交易", "交上易", "交上訴"]
TARGET_TITLES     = ["過失傷害", "過失致死", "過失致重傷", "損害賠償"]
PATH_KEYWORDS     = ["路口", "轉彎", "直行", "支線道", "幹線道",
                     "閃紅燈", "閃黃燈", "禮讓", "貿然", "未讓"]

results = []
for root in DATA_ROOTS:
    all_jsons = list(root.rglob("*.json"))
    print(f"{root.name}: {len(all_jsons)} 筆")
    for json_path in tqdm(all_jsons):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            if not any(t in doc.get("JCASE", "")  for t in TARGET_CASE_TYPES): continue
            if not any(t in doc.get("JTITLE", "") for t in TARGET_TITLES):     continue
            if not any(k in doc.get("JFULL", "")  for k in PATH_KEYWORDS):     continue
            results.append(doc)
        except Exception:
            continue

print(f"篩選後: {len(results)} 筆")
with open("data/filtered/traffic_cases.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
```

---

### Step 2.5：人工抽 30 筆確認品質

隨機抽 30 筆打開看，確認：
- 真的是路口車禍（不是停車場、不是高速公路）
- 有清楚的肇責爭議
- 有引用法條（道交安全規則、刑法 284 等）

> ✅ **8 成以上符合才繼續**。不到 6 成要調整關鍵字重篩。

---

### Step 3：結構化抽取（交給 Claude Code 處理）

把判決書文字貼給 Claude Code，要求輸出以下格式的 JSON：

```
請從以下判決書中抽取結構化資訊，回傳 JSON，包含四個欄位：
- 事故摘要（150-250 字，客觀第三人視角，用 A/B 代稱，不用訴訟用語）
- 核心爭議（1-3 個，只能從清單選：轉彎車未讓直行車／支線道未讓幹線道／
  閃紅燈未讓閃黃燈／左方車未讓右方車／紅燈右轉／與有過失／過失傷害成立／
  過失致死致重傷／民事損害賠償，不符合回傳「其他」）
- 責任類型（1-3 個，只能從：刑事／民事／行政）
- 適用法條（只列判決書實際引用的，格式：「法律名稱 第X條」）

[判決書全文貼在這裡]
```

貼的內容就是 `JFULL` 欄位的值（判決書全文）。Claude Code 回傳 JSON 後，加上 `"JID"` 欄位一起手動存入 `data/extracted/structured_cases.json`。

> ✅ **先做 20 筆給 A 確認，品質 OK 才繼續。**
> A 確認時檢查三點：
> 1. 事故摘要是否合理、有沒有保留關鍵事實？
> 2. 爭議標籤是否準確？有沒有亂選？
> 3. 法條是否真的是判決書裡有提到的？

---

### Step 4：白話化改寫（交給 Claude Code 處理）

把 Step 3 產出的「事故摘要」貼給 Claude Code，要求改寫：

```
請把以下事故摘要改寫成台灣民眾在 PTT/Dcard 發文求助的口語風格：
- 第一人稱（「我」）
- 口語化，可以有情緒
- 不用法律術語
- 保留所有關鍵事實（時間/地點/雙方動作/受傷情況）
- 結尾用問句求助
- 可以有少量網路用語，但不要太誇張
- 100-200 字

[事故摘要貼在這裡]
```

Claude Code 回傳白話文後，和 Step 3 的結構化標籤組合成訓練配對，格式：

```json
{
  "instruction": "請判斷以下車禍情境的核心爭議、責任類型與適用法條",
  "input": "（白話文）",
  "output": "{\n  \"核心爭議\": [...],\n  \"責任類型\": [...],\n  \"適用法條\": [...]\n}"
}
```

存入 `data/colloquial/training_pairs.json`。

> ✅ 抽 10 筆確認白話程度夠口語、關鍵事實沒有遺漏。

---

### Step 5：切分資料集並上傳 HF（`05_split.py`）

```python
import json, random
from collections import Counter

with open("data/colloquial/training_pairs.json", "r", encoding="utf-8") as f:
    data = json.load(f)

random.seed(42)
random.shuffle(data)

n = len(data)
train = data[:int(n * 0.8)]
val   = data[int(n * 0.8):int(n * 0.9)]
test  = data[int(n * 0.9):]

for name, subset in [("train", train), ("val", val), ("test", test)]:
    with open(f"data/final/traffic_law_{name}.json", "w", encoding="utf-8") as f:
        json.dump(subset, f, ensure_ascii=False, indent=2)

print(f"訓練: {len(train)} 筆 / 驗證: {len(val)} 筆 / 測試: {len(test)} 筆")

def label_dist(subset):
    labels = []
    for item in subset:
        output = json.loads(item["output"])
        labels.extend(output["核心爭議"])
    return Counter(labels)

print("\n訓練集議題分布:", label_dist(train))
print("測試集議題分布:", label_dist(test))
```

上傳至 HuggingFace：
```python
from huggingface_hub import HfApi
api = HfApi()
api.upload_folder(
    folder_path="data/final/",
    repo_id="traffic-legal-lm/traffic-accident-legal-qa",
    repo_type="dataset",
)
```

---

### Step 6：註冊到 LlamaFactory（A 負責，10 分鐘）

在 LlamaFactory repo 的 `data/dataset_info.json` 裡新增：

```json
{
  "traffic_law_train": {
    "file_name": "/path/to/your/data/final/traffic_law_train.json",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  }
}
```

然後在訓練設定檔指定 `dataset: traffic_law_train` 就能讓 LlamaFactory 找到資料。

---

### Step 7：人工標註評估集（C 負責）

1. 從 `test` 的 50 筆，把 `output` 欄位洗掉
2. 你和另一位組員各自重新標一遍（核心爭議 / 責任類型 / 適用法條）
3. 比對差異，討論定案
4. 存成 `data/final/traffic_law_eval_gold.json`，上傳 HF

> 這 50 筆是最終評估的 ground truth，**不能用 GPT-4o 標**（避免污染）。

---

## 三個關鍵守則

1. **不要一次跑完全部**：先 20 筆 → A 確認 → 再 50 筆 → 再確認 → 才跑全部
2. **每步都存中間檔**：raw → filtered → extracted → colloquial → final
3. **Claude Code 跳過的直接略過**：遇到極端案件（如重大死亡事故）Claude Code 可能不處理，直接略過那筆

---

## 週日週會確認事項

- [ ] B：training_pairs.json 有幾筆？類別分布平均嗎？
- [ ] B：資料集已上傳 HF？
- [ ] C：人工評估集 50 筆完成？
- [ ] A：第一版微調模型跑出來了？推論一筆結果給大家看
- [ ] 全員：討論第一版結果，決定第二週重點（補資料 or 調訓練參數）
