#!/usr/bin/env bash
set -euo pipefail

: "${CHIPLET_BUILD:?set CHIPLET_BUILD}"
: "${TESTCASE:?set TESTCASE}"
: "${PARTITION_FILE:?set PARTITION_FILE}"
: "${THERMAL_MODEL:?set THERMAL_MODEL}"
: "${THERMAL_PYTHON:?set THERMAL_PYTHON}"
: "${DEEPOHEAT_ROOT:?set DEEPOHEAT_ROOT}"

"${CHIPLET_BUILD}/bin/chipletPart" "${PARTITION_FILE}" \
  "${TESTCASE}/io_definitions.xml" \
  "${TESTCASE}/layer_definitions.xml" \
  "${TESTCASE}/wafer_process_definitions.xml" \
  "${TESTCASE}/assembly_process_definitions.xml" \
  "${TESTCASE}/test_definitions.xml" \
  "${TESTCASE}/block_level_netlist.xml" \
  "${TESTCASE}/block_definitions.txt" \
  0.50 0.25 "${TECH_NODE:-14nm}" \
  --seed "${SEED:-42}" \
  --enable_thermal \
  --thermal_backend package_thermal \
  --thermal_model_path "${THERMAL_MODEL}" \
  --thermal_python "${THERMAL_PYTHON}" \
  --thermal_inference_script "${DEEPOHEAT_ROOT}/package_thermal/infer_package.py" \
  --thermal_budget "${THERMAL_BUDGET:-330}" \
  --thermal_lambda_peak "${LAMBDA_PEAK:-0.001}" \
  --thermal_lambda_avg "${LAMBDA_AVG:-0}" \
  --thermal_grid_x "${GRID_X:-32}" \
  --thermal_grid_y "${GRID_Y:-32}" \
  --thermal_dump_instances "${OUT_DIR:-/tmp/chipletpart_thermal_package}" \
  --thermal_device "${THERMAL_DEVICE:-auto}"
