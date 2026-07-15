#!/usr/bin/env bash

set -u

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: $0 <test-case-name> [source-root-or-case-directory]"
    echo
    echo "The optional source may be either a directory containing the case"
    echo "directly or a parent directory containing <test-case-name>."
    echo "Default: <repository>/cost_model/test_cases"
}

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    printf '%bError: expected one or two arguments.%b\n' "$RED" "$NC" >&2
    usage >&2
    exit 1
fi

TEST_CASE_NAME="$1"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ARG="${2:-${SCRIPT_DIR}/cost_model/test_cases}"

if [ -f "${SOURCE_ARG}/io_definitions.xml" ]; then
    SOURCE_DIR="$(cd -- "$SOURCE_ARG" && pwd)"
else
    SOURCE_DIR="${SOURCE_ARG%/}/${TEST_CASE_NAME}"
fi

DEST_DIR="${SCRIPT_DIR}/test_data/${TEST_CASE_NAME}"

if [ ! -d "$SOURCE_DIR" ]; then
    printf '%bError: source testcase directory not found: %s%b\n' \
        "$RED" "$SOURCE_DIR" "$NC" >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
printf '%bPreparing %s from %s%b\n' \
    "$YELLOW" "$DEST_DIR" "$SOURCE_DIR" "$NC"

copy_case_file() {
    local destination_name="$1"
    shift
    local source_name=""
    local source_path=""
    local destination_path="${DEST_DIR}/${destination_name}"

    for source_name in "$@"; do
        source_path="${SOURCE_DIR}/${source_name}"
        if [ -f "$source_path" ]; then
            break
        fi
        source_path=""
    done

    if [ -z "$source_path" ]; then
        printf '%bMissing source file in %s (tried: %s)%b\n' \
            "$RED" "$SOURCE_DIR" "$*" "$NC" >&2
        return 1
    fi

    cp -- "$source_path" "$destination_path"
    printf '  %s -> %s\n' "$source_name" "$destination_name"
}

status=0
copy_case_file "io_definitions.xml" "io_definitions.xml" || status=1
copy_case_file "layer_definitions.xml" "layer_definitions.xml" || status=1
copy_case_file "wafer_process_definitions.xml" "wafer_process_definitions.xml" || status=1
copy_case_file "assembly_process_definitions.xml" "assembly_process_definitions.xml" || status=1
copy_case_file "test_definitions.xml" "test_definitions.xml" || status=1
copy_case_file "block_level_netlist.xml" \
    "block_level_netlist_ws-${TEST_CASE_NAME}.xml" "block_level_netlist.xml" || status=1
copy_case_file "block_definitions.txt" \
    "block_definitions_ws-${TEST_CASE_NAME}.txt" "block_definitions.txt" || status=1

if [ "$status" -ne 0 ]; then
    printf '%bTestcase setup was incomplete; see the missing files above.%b\n' \
        "$RED" "$NC" >&2
    exit "$status"
fi

printf '%bTestcase ready: %s%b\n' "$GREEN" "$DEST_DIR" "$NC"
echo "Run: ./run_chiplet_test.sh ${TEST_CASE_NAME}"
