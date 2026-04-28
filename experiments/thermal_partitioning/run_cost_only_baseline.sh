#!/usr/bin/env bash
set -euo pipefail

: "${CHIPLET_BUILD:?set CHIPLET_BUILD}"
: "${TESTCASE:?set TESTCASE}"
: "${PARTITION_FILE:?set PARTITION_FILE}"

"${CHIPLET_BUILD}/bin/chipletPart" "${PARTITION_FILE}" \
  "${TESTCASE}/io_definitions.xml" \
  "${TESTCASE}/layer_definitions.xml" \
  "${TESTCASE}/wafer_process_definitions.xml" \
  "${TESTCASE}/assembly_process_definitions.xml" \
  "${TESTCASE}/test_definitions.xml" \
  "${TESTCASE}/block_level_netlist.xml" \
  "${TESTCASE}/block_definitions.txt" \
  0.50 0.25 "${TECH_NODE:-14nm}" \
  --seed "${SEED:-42}"
