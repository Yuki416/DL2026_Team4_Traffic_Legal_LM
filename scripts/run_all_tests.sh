#!/bin/bash
WORKDIR=/home/under115b/work/Traffic_Legal_LM
LOG=$WORKDIR/setup_verify.log

echo "[$(date)] Watcher started, waiting for image legal-lora:latest..." | tee -a "$LOG"

# Wait until image actually exists (not relying on log text)
while ! docker image inspect legal-lora:latest &>/dev/null; do
    sleep 30
done

echo "" | tee -a "$LOG"
echo "[$(date)] === 自動測試開始 ===" | tee -a "$LOG"

run_test() {
    local name=$1
    local script=$2
    echo "" | tee -a "$LOG"
    echo "[$(date)] --- $name ---" | tee -a "$LOG"
    docker run --gpus all --rm \
        -e NCCL_P2P_DISABLE=1 \
        -e NCCL_IB_DISABLE=1 \
        -v "$WORKDIR":/workspace \
        -v "$HOME/.cache/huggingface":/root/.cache/huggingface \
        -w /workspace \
        legal-lora:latest \
        python "$script" >> "$LOG" 2>&1
    if [ $? -eq 0 ]; then
        echo "[$(date)] $name: SUCCESS" | tee -a "$LOG"
    else
        echo "[$(date)] $name: FAILED" | tee -a "$LOG"
    fi
}

run_test "Test 1: GPU 記憶體用量" "scripts/test_gpu_memory.py"
run_test "Test 2: LoRA 訓練流程" "scripts/test_lora_dummy.py"
run_test "Test 3: 基線測試"     "scripts/test_baseline.py"

echo "" | tee -a "$LOG"
echo "[$(date)] === 全部測試完成 ===" | tee -a "$LOG"
