#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source /home/ubuntu/AIC_Shared/aic-env.sh
exec "${AIC_LLAMA_BIN:-/home/ubuntu/AIC_Shared/tools/llama-b11429/llama-b11429/llama-server}" \
  -m "${AIC_MODEL:-/home/ubuntu/AIC_Project/storage/models/qwen2.5-1.5b-instruct-q4_k_m.gguf}" \
  -ngl 0 -t 2 -tb 2 -np 1 -c 4096 --host 127.0.0.1 --port 8081 --alias aic-assistant
