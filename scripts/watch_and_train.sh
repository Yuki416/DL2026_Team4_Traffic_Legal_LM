#!/bin/bash
# 等 Llama 模型下載完成後自動啟動 Round 1 微調

MODEL_DIR="/mnt/8tb_hdd/under115b/traffic_legal_lm/models/Llama-3-Taiwan-8B-Instruct"
TOTAL_SHARDS=4
LOG="/workspace/train_round1.log"
YAML="/workspace/scripts/train_round1.yaml"

echo "[$(date '+%H:%M:%S')] 監控啟動，等待 $TOTAL_SHARDS 個 safetensors shard..."

while true; do
    DONE=$(ls "$MODEL_DIR"/*.safetensors 2>/dev/null | wc -l)
    echo "[$(date '+%H:%M:%S')] shard 完成: $DONE / $TOTAL_SHARDS"

    if [ "$DONE" -ge "$TOTAL_SHARDS" ]; then
        echo "[$(date '+%H:%M:%S')] 下載完成！開始微調..."
        break
    fi

    sleep 30
done

echo "[$(date '+%H:%M:%S')] ===== 開始 Round 1 LoRA 微調 =====" | tee -a "$LOG"
NCCL_P2P_DISABLE=1 NCCL_IB_DISABLE=1 llamafactory-cli train "$YAML" 2>&1 | tee -a "$LOG"
echo "[$(date '+%H:%M:%S')] ===== 訓練結束 =====" | tee -a "$LOG"
