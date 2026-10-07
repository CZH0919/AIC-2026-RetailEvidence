#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"
exec "${AIC_PY:-.venv/bin/python}" -m uvicorn app.main:app --app-dir backend \
  --host 127.0.0.1 --port "${AIC_PORT:-8000}" --workers 1
