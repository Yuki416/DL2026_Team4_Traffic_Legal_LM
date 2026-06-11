# 交接文件：Step 4 白話化改寫（chunk_20 起接手）

> 給接手的 Claude Code：請完整讀完本檔再執行。所有路徑都是絕對路徑。
> 工作目錄：`/home/under115b/work/Traffic_Legal_LM`。`python3` 已在
> `/home/under115b/work/.claude/settings.local.json` 允許清單，可直接執行。

## 背景（你需要知道的脈絡）

這是 Llama-3-Taiwan-8B 的交通事故法律問答資料集（三月份）。Step 3 已產出
`data/extracted/structured_cases.json`（1,918 筆，每筆有 JID、_source、事故摘要、
核心爭議、適用法條）。

**Step 4** = 把每筆「事故摘要」改寫成 PTT/Dcard 口語求助文（input），組成 Alpaca
訓練對。已把 1,918 筆切成 32 個 chunk（每 60 筆）放在 `data/colloquial/chunks/`。
**chunks 00–19 已完成**，輸出在 `data/colloquial/out/out_00.json … out_19.json`。
**你的任務：完成 chunks 20–31，然後組裝、切分、登錄。**

改寫的完整規則在 `scripts/subagent_prompt.md`（已定版，含：駕駛視角不要用保險公司
第一人稱、逐詞掃描移除法律術語、grounded_disputes 嚴格判斷、SKIP 條件、寫檔方式）。

---

## STEP 1：跑 chunks 20–31（3 波，每波 4 個背景 sub-agent，Sonnet 4.6）

對 chunk_20 到 chunk_31，每個開一個**背景** Agent（`model: sonnet`、
`run_in_background: true`、`subagent_type: general-purpose`），prompt 如下（把 NN
換成 20、21、…、31）：

```
完整任務指令在 /home/under115b/work/Traffic_Legal_LM/scripts/subagent_prompt.md，
請先用 Read 工具讀取它並完全照做（特別注意：規則1的「車主/駕駛視角、不要用保險公司
第一人稱」、規則3的逐詞掃描、grounded_disputes 的嚴格判斷）。

本次參數，把指令裡所有 {CHUNK}/{OUT}/{NN} 換成：
- {CHUNK} = /home/under115b/work/Traffic_Legal_LM/data/colloquial/chunks/chunk_NN.json
- {OUT}   = /home/under115b/work/Traffic_Legal_LM/data/colloquial/out/out_NN.json
- {NN}    = NN

完成後回報：總筆數（應 60，chunk_31 為 58）、rewrite 幾筆、skip 幾筆、用 python3 還是 Write。
```

建議分 3 波並行：第一波 20–23、第二波 24–27、第三波 28–31。每波等 4 個都完成
再開下一波（背景 agent 完成會自動通知）。

驗證每個 out 檔已落地：
```
ls /home/under115b/work/Traffic_Legal_LM/data/colloquial/out/out_*.json | wc -l   # 應 32
python3 /home/under115b/work/Traffic_Legal_LM/scripts/validate_out.py             # 看洩漏/接地/筆數
```

---

## STEP 2：殘留「保險公司視角」總修正（一次處理全部 32 chunk）

部分案是保險代位求償，少數仍被寫成保險公司第一人稱。偵測並建修正包：
```
python3 /home/under115b/work/Traffic_Legal_LM/scripts/build_insurer_fixup.py
```
若印出「無殘留」→ 跳過本步。若有，會產生 `chunks/fixup_insurer2.json`，開**一個**
背景 agent 重寫（駕駛視角），prompt：

```
完整任務指令在 /home/under115b/work/Traffic_Legal_LM/scripts/subagent_prompt.md，先 Read 它照做。
這批是保險代位案，之前誤寫成保險公司第一人稱，全部改用車主/駕駛視角重寫
（發問者是當事駕駛，不是保險公司）。
- {CHUNK} = /home/under115b/work/Traffic_Legal_LM/data/colloquial/chunks/fixup_insurer2.json
- {OUT}   = /home/under115b/work/Traffic_Legal_LM/data/colloquial/out/fixup_insurer2_out.json
- {NN}    = fixup2
完成後確認沒有保險公司第一人稱、沒有「代位」。
```
回貼：
```
python3 /home/under115b/work/Traffic_Legal_LM/scripts/patch_fixup.py /home/under115b/work/Traffic_Legal_LM/data/colloquial/out/fixup_insurer2_out.json
```

---

## STEP 3：組裝最終訓練檔

```
python3 /home/under115b/work/Traffic_Legal_LM/scripts/sanitize_and_assemble.py
```
產出 `data/colloquial/training_pairs.json`。這步會：
- 對 input 套 **sanitizer**（代位求償→向對方求償、貿然→直接、未注意車前狀況→
  沒注意前面、與有過失→雙方都有責任、侵權行為→刪…）
- 核心爭議 = agent 的 grounded_disputes
- 適用法條 = 過濾量刑/程序條文（刑41/50/51/53/55/57/71/74/75、民203/229/233）+
  條件式（刑62 自首僅 has_self_surrender_cue=true 時留、民217 僅與有過失成立時留）+ 去重
- instruction = 6 種輪替；output = 【核心爭議】【責任類型】【適用法條】三行
- 印出「sanitize 後仍殘留法律詞」數，**應為 0 或極少**；若有殘留 JID，回報即可

---

## STEP 4：切分 train/val/test（本地，不上傳 HuggingFace）

```
python3 /home/under115b/work/Traffic_Legal_LM/scripts/split_dataset.py
```
產出 `train.json` / `val.json` / `test.json`（在 `data/colloquial/`）。
- test = 刑 15 + 民 15 = 30（保留 _jid 供人工核對）
- val = 50（依比例）；train = 其餘

---

## STEP 5：在 LlamaFactory 登錄資料集

把以下加進 LlamaFactory 的 `dataset_info.json`（路徑視你的 LlamaFactory 安裝位置；
若不確定，先問使用者 LlamaFactory 的根目錄）：
```json
"traffic_legal_0603": {
  "file_name": "/home/under115b/work/Traffic_Legal_LM/data/colloquial/train.json",
  "columns": { "prompt": "instruction", "query": "input", "response": "output" }
}
```
（val/test 同理可另登錄，或訓練時用 val_size 切分。）

---

## 完成後回報

請回報：32 chunks 總筆數、skip 總數、training_pairs.json 最終筆數（刑/民）、
sanitize 殘留洩漏數、train/val/test 各筆數。然後就完成 Step 4–6 了。

## 注意事項
- sub-agent 一律 `model: sonnet`（= Sonnet 4.6）、背景執行、寫檔用 python3。
- 不要改 `subagent_prompt.md` 的規則（已定版）。
- 每個 out_NN.json 應 60 筆（含 rewrite + skip 兩種 action），chunk_31 為 58。
- 若某 agent 卡權限：python3 已允許，確認用絕對路徑、不要 cd。
