#!/bin/bash
set -u

PROM_FILE="/var/lib/node_exporter/textfile_collector/ai_platform_inspect.prom"
LOG_FILE="/var/log/ai-platform-inspect.log"
MODEL_DIR="/root/ai-inference-platform/data/hf-cache/models/Qwen3-8B"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

VLLM_STATE=$(systemctl is-active vllm 2>/dev/null)
[ "$VLLM_STATE" = "active" ] && VLLM_UP=1 || VLLM_UP=0
VLLM_RESTARTS=$(systemctl show vllm -p NRestarts --value 2>/dev/null || echo 0)

nvidia-smi >/dev/null 2>&1 && GPU_OK=1 || GPU_OK=0

command -v nvidia-ctk >/dev/null 2>&1 && TOOLKIT_OK=1 || TOOLKIT_OK=0

if [ -d "$MODEL_DIR" ]; then
    MODEL_OK=1
    MODEL_SIZE=$(du -sm "$MODEL_DIR" 2>/dev/null | awk '{print $1}')
else
    MODEL_OK=0
    MODEL_SIZE=0
fi

DISK_AVAIL=$(df -B1 --output=avail / | tail -n 1 | tr -d ' ')
DISK_SIZE=$(df -B1 --output=size / | tail -n 1 | tr -d ' ')
DISK_FREE_PCT=$(awk -v a="$DISK_AVAIL" -v s="$DISK_SIZE" 'BEGIN{printf "%.4f", a/s}')

curl -sf -m 5 http://127.0.0.1:8000/v1/models >/dev/null 2>&1 && API_OK=1 || API_OK=0

mkdir -p "$(dirname "$PROM_FILE")"
TMP=$(mktemp)
cat > "$TMP" << PROM
# HELP ai_platform_vllm_up vllm service active (1=yes)
# TYPE ai_platform_vllm_up gauge
ai_platform_vllm_up ${VLLM_UP}
# HELP ai_platform_vllm_restarts_total vllm restarts
# TYPE ai_platform_vllm_restarts_total counter
ai_platform_vllm_restarts_total ${VLLM_RESTARTS}
# HELP ai_platform_gpu_ok nvidia-smi works (1=yes)
# TYPE ai_platform_gpu_ok gauge
ai_platform_gpu_ok ${GPU_OK}
# HELP ai_platform_toolkit_ok nvidia-container-toolkit present (1=yes)
# TYPE ai_platform_toolkit_ok gauge
ai_platform_toolkit_ok ${TOOLKIT_OK}
# HELP ai_platform_model_dir_ok model weights dir exists (1=yes)
# TYPE ai_platform_model_dir_ok gauge
ai_platform_model_dir_ok ${MODEL_OK}
# HELP ai_platform_model_size_mb model weights size
# TYPE ai_platform_model_size_mb gauge
ai_platform_model_size_mb ${MODEL_SIZE}
# HELP ai_platform_disk_free_ratio disk free on /
# TYPE ai_platform_disk_free_ratio gauge
ai_platform_disk_free_ratio ${DISK_FREE_PCT}
# HELP ai_platform_vllm_api_ok vllm api reachable (1=yes)
# TYPE ai_platform_vllm_api_ok gauge
ai_platform_vllm_api_ok ${API_OK}
# HELP ai_platform_inspect_last_run last run unix ts
# TYPE ai_platform_inspect_last_run gauge
ai_platform_inspect_last_run $(date +%s)
PROM
mv "$TMP" "$PROM_FILE"
chmod 644 "$PROM_FILE"

echo "$(ts) vllm=${VLLM_STATE} restarts=${VLLM_RESTARTS} gpu=${GPU_OK} toolkit=${TOOLKIT_OK} model=${MODEL_OK}(${MODEL_SIZE}MB) disk_free=${DISK_FREE_PCT} api=${API_OK}" >> "$LOG_FILE"

[ "$VLLM_UP" = "1" ] && [ "$GPU_OK" = "1" ] && [ "$API_OK" = "1" ]
