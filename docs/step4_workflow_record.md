# Step 4 白話化改寫流程記錄

> 用途：作為報告撰寫的參考資料。記錄從設計、執行到最終結果的完整過程。

---

## 一、任務背景與目標

### 任務定義

Step 4 的目標是把 Step 3 產出的 1,918 筆判決書結構化資料，透過「白話化改寫」轉換成可供 LlamaFactory 微調 Llama-3-Taiwan-8B 使用的 Alpaca 格式訓練對。

具體來說，每一筆資料包含：

- **原始輸入**：判決書中的「事故摘要」欄位，以法律文書語氣撰寫
- **改寫目標**：轉換成 PTT/Dcard 風格的第一人稱口語求助文（假想一位當事人在論壇求助）
- **訓練輸出**：三行結構化標籤——【核心爭議】【責任類型】【適用法條】

### 為什麼要做白話化改寫？

模型訓練時，input 應盡量模擬使用者的真實提問方式，而非判決書的法律語氣。若直接用事故摘要當 input，模型在推理時會遇到語域落差（training-inference mismatch）：使用者用白話問，但模型從來沒見過白話的 input。

---

## 二、Pipeline 整體設計

```
structured_cases.json（1,918 筆）
        ↓ make_chunks.py
  32 個 chunk（每個 60 筆，最後一個 58 筆）
        ↓ 32 個背景 Sub-agent（Sonnet 4.6 並行）
  out_00.json … out_31.json（每筆含改寫或 skip）
        ↓ build_insurer_fixup.py + fixup agent + patch_fixup.py
  保險代位視角修正
        ↓ sanitize_and_assemble.py
  training_pairs.json（1,759 筆）
        ↓ split_dataset.py
  train.json / val.json / test.json
```

### 為何用背景 Sub-agent 並行？

單一 agent 處理 1,918 筆的 token 量（含每筆事故摘要約 300 字 + prompt 規則）會超出 context 限制，且串行耗時過長。切成 60 筆一個 chunk，讓 32 個 Sonnet 4.6 sub-agent 並行（每波 4 個），既可在單一 context 內處理完整，又大幅縮短總時間。

---

## 三、關鍵設計決策

### 3.1 Output Schema（Sub-agent 的輸出格式）

每一筆輸出記錄包含：

```json
{
  "JID": "...",
  "action": "rewrite" | "skip",
  "skip_reason": "...",
  "input": "改寫後的白話文（80-250 字）",
  "grounded_disputes": ["核心爭議標籤", ...],
  "has_self_surrender_cue": true | false
}
```

`action=skip` 的案例不進入訓練集，`grounded_disputes` 是 agent 根據改寫後的 input 嚴格判斷出的爭議標籤（非原始核心爭議的直接複製）。

### 3.2 Grounded Disputes（語意接地）

這是整個設計中最核心的一個概念。

原始 `structured_cases.json` 裡的核心爭議標籤，有相當大比例（約 47.8%）是從判決書全文的「法律推理」段落抽取的，不一定能從事故摘要本身推出。如果訓練時直接用原始標籤，模型等於在學習「從描述推出一個它根本看不到依據的結論」，這種不可學習性（unlearnability）會嚴重降低訓練效果。

**解法**：要求 agent 在改寫完 input 後，嚴格判斷哪些標籤能從改寫後的文字推出；不能推出的直接拿掉，能推出但原始清單沒有的則補上。固定 12 類標籤清單如下：

> 轉彎車未讓直行車、變換車道未讓直行車、支線道未讓幹線道、左方車未讓右方車、違反號誌、未注意車前狀況、閃紅燈未停讓、閃黃燈未減速、與有過失、過失致死致重傷、過失傷害成立、民事損害賠償

### 3.3 法條過濾（Learnability Filtering）

原始適用法條中有約 25% 是量刑或程序性條文（如刑法第 57 條量刑審酌、刑法第 74 條緩刑），從事故描述根本推不出來。這些一律過濾掉：

**永遠過濾**：刑法第 41/50/51/53/55/57/71/74/75 條，民法第 203/229/233 條

**條件保留**：
- 刑法第 62 條（自首減刑）：僅在 `has_self_surrender_cue=true` 時保留（即改寫的 input 中有具體自首事實，且原始法條確實引用刑法第 62 條）
- 民法第 217 條（過失相抵）：僅在 `grounded_disputes` 包含「與有過失」時保留

### 3.4 禁用詞規則（Sanitizer）

改寫後的 input 不能出現任何法律套語，否則模型學到的是「從法律文字推法律標籤」，而非「從口語描述推法律標籤」。禁用詞及其替換規則：

| 禁用詞 | 替換為 |
|--------|--------|
| 代位求償 | 向對方求償 |
| 代位（其他用法） | （刪除）|
| 未注意車前狀況 | 沒注意前面 |
| 疏未注意 | 沒注意到 |
| 應讓直行車先行 | 要讓直行車先過 |
| 貿然 | 直接 |
| 過失相抵 | 各自有責任 |
| 與有過失 | 雙方都有責任 |
| 侵權行為 | （刪除）|

這份規則分兩層執行：
1. **Prompt 規則**：在 sub-agent 的改寫指令裡就明確列出，要求改寫時直接避開
2. **Sanitizer**：組裝腳本（`sanitize_and_assemble.py`）再做一次字串替換，作為最後防線

### 3.5 SKIP 條件

以下案例由 agent 判斷為 skip，不進入訓練集：
- 事故摘要實際上是量刑理由段（「被告犯後態度、刑法第57條審酌…」）
- 事故摘要為起訴書附件引用（無獨立描述）
- 事故摘要為傳聞證據能力/程序說明
- 事故摘要只有傷勢或結果，缺乏完整的事故動態（誰撞誰、如何發生）
- 文字截斷或明顯不完整

### 3.6 視角規則：保險代位求償案

部分民事案原告是保險公司（代位求償，即保險公司代被保戶向肇事方求償）。若直接讓 agent 寫第一人稱，有時會誤寫成保險公司的視角（「我（保險公司）承保...」）。

**規則**：此類案例一律改用車主/駕駛視角（「我的車有買車體險，理賠後保險公司說要去跟對方求償…」），發問者永遠是當事人，不是保險公司。

### 3.7 Instruction 輪替

Alpaca 格式的 `instruction` 欄位設計了 6 種不同措辭的提問方式，在組裝時以 `i % 6` 輪替分配，避免模型過擬合到單一提示語氣。

---

## 四、執行過程與遭遇的問題

### 問題 1：背景 Sub-agent 卡權限

**現象**：第一批 sub-agent 啟動後沒有輸出，卡在等待 python3 指令的權限確認。

**原因**：`/home/under115b/work/.claude/settings.local.json` 的允許清單沒有 `python3` 指令，sub-agent 在背景執行時無法自動獲得授權。

**解法**：在 settings.local.json 加入 `"Bash(python3:*)"` 和 `"Bash(python:*)"` 後，sub-agent 可直接執行寫檔腳本。

---

### 問題 2：Sub-agent 遇到 Session Limit 中途中斷

**現象**：第七波（chunks 24-27）中，chunks 24 和 25 的 sub-agent 因流量達上限而中斷，out 檔要麼不存在、要麼只有 30 筆（不完整）。

**偵測方式**：啟動後確認每個 out 檔的實際筆數。

**解法**：刪除不完整的 out_25.json，重新對 chunk_24 和 chunk_25 各啟動一個 sub-agent。

---

### 問題 3：保險公司第一人稱視角殘留

**現象**：全部 32 個 chunk 完成後，執行 `build_insurer_fixup.py` 偵測，發現 out_04、out_08、out_17 共 12 筆仍以保險公司視角改寫。

**原因**：這些民事案的事故摘要本來就以保險公司為原告視角描述，agent 沒有徹底轉換。

**解法**：啟動一個專門的 fixup agent，把這 12 筆抽出來重寫（指令強調必須用車主/駕駛視角），完成後用 `patch_fixup.py` 依 JID 比對貼回原 out 檔。

---

### 問題 4：Agent 修改 JID 日期欄位

**現象**：執行 `sanitize_and_assemble.py` 時，發現 11 個 JID 在 `structured_cases.json` 裡查不到。

**原因**：這 11 個 JID 的「日期」欄位（JID 的第 5 段）被 agent 改寫成其他日期（例如原始是 `20260319` 被改成 `20260323`）。JID 其他部分（法院代碼、年度、案件類型、案號）正確，只有日期欄位偏差。

**解法**：在 `sanitize_and_assemble.py` 加入 fallback 邏輯——若完整 JID 查無此案，則改用前四欄（法院+年度+類型+案號）比對，找到對應的正確 JID 再查 struct。11 筆全部成功對應到正確資料。

---

### 問題 5：`_source` 欄位缺失

**現象**：部分 out 記錄沒有 `_source`（criminal/civil）欄位。

**原因**：sub-agent 的 output schema 規格裡並未要求 agent 回傳 `_source`，各個 agent 回傳的完整性不一致。

**解法**：組裝腳本改為從 `struct[jid]["_source"]` 讀取（來自 structured_cases.json），這個欄位保證存在。

---

### 問題 6：「應讓直行車」未納入 Sanitize 清單

**現象**：`validate_out.py` 在 2 筆 input 中偵測到「應讓直行車」殘留（這是 prompt 規則要求移除的法律套語）。

**解法**：在 `sanitize_and_assemble.py` 的 SANITIZE 清單新增三條規則（覆蓋先行、先走等變體）：`應讓直行車先行`、`應讓直行車先走`、`應讓直行車` 統一替換為「要讓直行車（先過/對應口語）」。

---

## 五、最終結果

### 改寫統計

| 項目 | 數值 |
|------|------|
| 輸入案例 | 1,918 筆 |
| rewrite（成功改寫） | 1,764 筆 |
| skip（無法改寫） | 154 筆（8.0%） |
| 法條過濾後為空剔除 | 5 筆 |
| **最終訓練對數** | **1,759 筆** |
| 刑事案 | 783 筆（44.5%）|
| 民事案 | 976 筆（55.5%）|
| sanitize 後殘留法律詞 | **0 筆** |

### Skip 原因分布（154 筆）

依各 chunk agent 回報，主要原因：
- 量刑理由/論罪科刑段落（無事故動態）
- 起訴書附件引用（無獨立描述）
- 傳聞證據能力、程序說明段落
- 事故動態不完整或文字截斷
- 僅傷勢/結果陳述，缺碰撞過程

### Train/Val/Test 切分（SEED=42）

| 集合 | 筆數 | 刑事 | 民事 |
|------|------|------|------|
| train.json | 1,679 | — | — |
| val.json | 50 | 22 | 28 |
| test.json | 30 | 15 | 15 |

test 集依刑/民各 15 筆抽取，保留 `_jid` 和 `_source` 欄位供人工核對；train/val 只留 Alpaca 三欄（instruction/input/output）。

### 輸出檔案位置

```
Traffic_Legal_LM/data/colloquial/
├── training_pairs.json    # 完整 1,759 筆（含 _jid/_source）
├── train.json             # 1,679 筆
├── val.json               # 50 筆
└── test.json              # 30 筆（含 _jid/_source 供回溯）
```

---

## 六、品質控管設計

### 分層防守

| 層次 | 機制 | 負責方 |
|------|------|--------|
| 改寫時 | Prompt 規則（禁用詞、視角、長度、標籤接地）| Sub-agent |
| 改寫後 | `validate_out.py` 洩漏偵測 | 主流程 |
| 組裝時 | Sanitizer 字串替換（最後防線）| Assembly script |
| 組裝後 | 殘留洩漏計數（應為 0）| Assembly script 輸出 |

### validate_out.py 的檢查項目

- 每個 out 檔筆數是否等於對應 chunk 的輸入筆數
- 所有欄位是否齊全（JID/action/input/grounded_disputes）
- grounded_disputes 是否在固定 12 類清單內
- input 是否含有洩漏詞（貿然/疏未注意/未注意車前狀況/與有過失/過失相抵/侵權行為/代位/法條條號）
- input 長度分布（80-250 字範圍）

---

## 七、使用的工具與模型

| 元件 | 細節 |
|------|------|
| 改寫模型 | Claude Sonnet 4.6（`claude-sonnet-4-6`）|
| 主協調模型 | Claude Opus 4.8 → 後半段切換為 Sonnet 4.6 |
| 執行方式 | Agent tool，`run_in_background=true`，每波 4 個並行 |
| 改寫 Chunk 大小 | 60 筆/chunk（32 個 chunk）|
| 寫檔方式 | Sub-agent 寫 Python 腳本再用 python3 執行 |
| 資料格式 | Alpaca（instruction/input/output）|
| 微調目標框架 | LlamaFactory |
