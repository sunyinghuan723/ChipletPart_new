#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ROOT="${OUT_ROOT:-/tmp/chipletpart_lambda_sweep}"
mkdir -p "${OUT_ROOT}"

for lambda in ${LAMBDA_VALUES:-0 0.0001 0.001 0.01}; do
  echo "[THERMAL-EXP] lambda_peak=${lambda}"
  LAMBDA_PEAK="${lambda}" \
  OUT_DIR="${OUT_ROOT}/lambda_${lambda}" \
  bash "${SCRIPT_DIR}/run_thermal_package_surrogate.sh" \
    > "${OUT_ROOT}/lambda_${lambda}.log" 2>&1
done
