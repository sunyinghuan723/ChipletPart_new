#!/bin/bash

# Set colors for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to display help/usage information
show_help() {
    echo -e "${BLUE}Usage: $0 <test_case_name> [options]${NC}"
    echo
    echo "Options:"
    echo "  --reach <value>       Specify reach value (default: 0.50)"
    echo "  --separation <value>  Specify separation value (default: 0.25)"
    echo "  --tech <node>         Specify tech node for standard partitioning (default: 7nm)"
    echo "  --seed <value>        Specify random seed (default: 42)"
    echo "  --genetic             Use genetic tech partitioning algorithm"
    echo "  --canonical-ga        Use canonical genetic algorithm for technology assignment"
    echo "  --tech-enum           Enumerate all canonical technology assignments up to specified max partitions"
    echo "  --max-partitions <n>  Maximum number of partitions for tech enumeration (default: 4)"
    echo "  --detailed-output     Generate detailed output for each tech assignment evaluation"
    echo "  --tech-nodes <nodes>  Specify comma-separated list of tech nodes for genetic partitioning"
    echo "                        Example: --tech-nodes 7nm,10nm,14nm,28nm"
    echo "  --generations <num>   Specify number of generations for genetic algorithm (default: 50)"
    echo "  --population <num>    Specify population size for genetic algorithm (default: 50)"
    echo "  --evaluate-partition  Specify path to partition file for evaluation"
    echo "  --thermal             Enable thermal-aware evaluation with DeepOHeat 2D checkpoint"
    echo "  --thermal-mock        Enable deterministic mock thermal evaluation"
    echo "  --thermal-output-dir <dir>"
    echo "                        Directory for thermal instance JSON/result files"
    echo "  --thermal-budget <K>  Peak temperature budget in Kelvin (default: 330)"
    echo "  --thermal-lambda-peak <value>"
    echo "                        Peak-temperature penalty weight (default: 0.001)"
    echo "  --thermal-device <dev>"
    echo "                        Thermal inference device: auto,cpu,cuda,cuda:0,cuda:1 (default: auto)"
    echo "  --thermal-grid <n>    Use n x n thermal raster grid (default: 20)"
    echo "  --thermal-model <pth> Override DeepOHeat 2D checkpoint path"
    echo "  --thermal-python <py> Override DeepOHeat Python path"
    echo "  --thermal-script <py> Override DeepOHeat inference adapter path"
    echo "  --thermal-cache       Cache repeated thermal inference results"
    echo "  --thermal-allow-fallback"
    echo "                        Fall back to cost-only objective if thermal inference fails"
    echo "  --help                Display this help message"
    echo
    echo "Examples:"
    echo "  $0 design1 --tech 5nm"
    echo "  $0 design2 --genetic --tech-nodes 7nm,10nm,14nm --seed 123"
    echo "  $0 design3 --canonical-ga --tech-nodes 7nm,14nm,28nm --generations 30"
    echo "  $0 design4 --tech-enum --tech-nodes 7nm,14nm,28nm --max-partitions 3"
    echo "  $0 ga100 --tech-enum --tech-nodes 7nm,14nm --max-partitions 2 --thermal"
}

# Check if no arguments were provided
if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

# Check if the first argument is --help
if [ "$1" = "--help" ]; then
    show_help
    exit 0
fi

# Parse the first argument as the test case name
TEST_CASE_NAME="$1"
shift  # Remove the first argument

# Default values
DEFAULT_REACH="0.50"
DEFAULT_SEPARATION="0.25"
DEFAULT_TECH="7nm"
DEFAULT_SEED="42"
DEFAULT_GENERATIONS="50"
DEFAULT_POPULATION="50"
DEFAULT_MAX_PARTITIONS="4"
USE_GENETIC=false
USE_CANONICAL_GA=false
USE_TECH_ENUM=false
DETAILED_OUTPUT=false
TECH_NODES=""
EVALUATE_PARTITION=""
ENABLE_THERMAL=false
THERMAL_MOCK=false
THERMAL_OUTPUT_DIR=""
THERMAL_BUDGET="330"
THERMAL_LAMBDA_PEAK="0.001"
THERMAL_LAMBDA_AVG="0"
THERMAL_GRID_X="20"
THERMAL_GRID_Y="20"
THERMAL_DEVICE="auto"
THERMAL_MODEL_PATH=""
THERMAL_PYTHON=""
THERMAL_SCRIPT=""
THERMAL_BACKEND="legacy_2d_power_map"
THERMAL_CACHE=false
THERMAL_ALLOW_FALLBACK=false

# Parse command line arguments
while [ "$#" -gt 0 ]; do
    case "$1" in
        --help)
            show_help
            exit 0
            ;;
        --reach)
            DEFAULT_REACH="$2"
            shift 2
            ;;
        --separation)
            DEFAULT_SEPARATION="$2"
            shift 2
            ;;
        --tech)
            DEFAULT_TECH="$2"
            shift 2
            ;;
        --seed)
            DEFAULT_SEED="$2"
            shift 2
            ;;
        --genetic)
            USE_GENETIC=true
            shift
            ;;
        --canonical-ga)
            USE_CANONICAL_GA=true
            shift
            ;;
        --tech-enum)
            USE_TECH_ENUM=true
            shift
            ;;
        --max-partitions)
            DEFAULT_MAX_PARTITIONS="$2"
            shift 2
            ;;
        --detailed-output)
            DETAILED_OUTPUT=true
            shift
            ;;
        --tech-nodes)
            TECH_NODES="$2"
            shift 2
            ;;
        --generations)
            DEFAULT_GENERATIONS="$2"
            shift 2
            ;;
        --population)
            DEFAULT_POPULATION="$2"
            shift 2
            ;;
        --evaluate-partition)
            EVALUATE_PARTITION="$2"
            shift 2
            ;;
        --thermal|--enable-thermal|--enable_thermal)
            ENABLE_THERMAL=true
            shift
            ;;
        --thermal-mock|--thermal_use_mock)
            ENABLE_THERMAL=true
            THERMAL_MOCK=true
            THERMAL_BACKEND="mock"
            shift
            ;;
        --thermal-output-dir|--thermal_dump_instances)
            THERMAL_OUTPUT_DIR="$2"
            shift 2
            ;;
        --thermal-budget|--thermal_budget)
            THERMAL_BUDGET="$2"
            shift 2
            ;;
        --thermal-lambda-peak|--thermal_lambda_peak)
            THERMAL_LAMBDA_PEAK="$2"
            shift 2
            ;;
        --thermal-lambda-avg|--thermal_lambda_avg)
            THERMAL_LAMBDA_AVG="$2"
            shift 2
            ;;
        --thermal-device|--thermal_device)
            THERMAL_DEVICE="$2"
            shift 2
            ;;
        --thermal-grid)
            THERMAL_GRID_X="$2"
            THERMAL_GRID_Y="$2"
            shift 2
            ;;
        --thermal-grid-x|--thermal_grid_x)
            THERMAL_GRID_X="$2"
            shift 2
            ;;
        --thermal-grid-y|--thermal_grid_y)
            THERMAL_GRID_Y="$2"
            shift 2
            ;;
        --thermal-model|--thermal_model_path)
            THERMAL_MODEL_PATH="$2"
            shift 2
            ;;
        --thermal-python|--thermal_python)
            THERMAL_PYTHON="$2"
            shift 2
            ;;
        --thermal-script|--thermal_inference_script)
            THERMAL_SCRIPT="$2"
            shift 2
            ;;
        --thermal-backend|--thermal_backend)
            THERMAL_BACKEND="$2"
            shift 2
            ;;
        --thermal-cache|--thermal_cache)
            THERMAL_CACHE=true
            shift
            ;;
        --thermal-allow-fallback|--thermal_allow_fallback)
            THERMAL_ALLOW_FALLBACK=true
            shift
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Check if multiple algorithms are specified
if ([ "$USE_GENETIC" = true ] && [ "$USE_CANONICAL_GA" = true ]) || \
   ([ "$USE_GENETIC" = true ] && [ "$USE_TECH_ENUM" = true ]) || \
   ([ "$USE_CANONICAL_GA" = true ] && [ "$USE_TECH_ENUM" = true ]); then
    echo -e "${RED}Error: Cannot use multiple algorithm options together.${NC}"
    echo -e "${YELLOW}Please specify only one algorithm approach (--genetic, --canonical-ga, or --tech-enum).${NC}"
    exit 1
fi

# Define the base directory where the executable and test data are located
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${BASE_DIR}/build"
EXECUTABLE="${BUILD_DIR}/bin/chipletPart"
TEST_DATA_DIR="${BASE_DIR}/test_data/${TEST_CASE_NAME}"

# Create results directory for this test case if it doesn't exist
mkdir -p "${BASE_DIR}/results/"

# Define file paths for the input files
IO="${TEST_DATA_DIR}/io_definitions.xml"
LAYER="${TEST_DATA_DIR}/layer_definitions.xml"
WAFER="${TEST_DATA_DIR}/wafer_process_definitions.xml"
ASSEMBLY="${TEST_DATA_DIR}/assembly_process_definitions.xml"
TEST="${TEST_DATA_DIR}/test_definitions.xml"
NETLIST="${TEST_DATA_DIR}/block_level_netlist.xml"
BLOCKS="${TEST_DATA_DIR}/block_definitions.txt"

# Check that all required files exist
for file in "$IO" "$LAYER" "$WAFER" "$ASSEMBLY" "$TEST" "$NETLIST" "$BLOCKS"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}Error: File not found: $file${NC}"
        echo "Please ensure the test data exists in ${TEST_DATA_DIR}."
        exit 1
    fi
done

THERMAL_ARGS=()
if [ "$ENABLE_THERMAL" = true ]; then
    DEEPOHEAT_DIR="${BASE_DIR}/../DeepOHeat"
    DEFAULT_THERMAL_MODEL="${DEEPOHEAT_DIR}/DeepOHeat/2d_power_map/log/experiment_1/checkpoints/model_epoch_10000.pth"
    DEFAULT_THERMAL_PYTHON="${DEEPOHEAT_DIR}/.conda/deepoheat-py38/bin/python"
    DEFAULT_LEGACY_THERMAL_SCRIPT="${DEEPOHEAT_DIR}/scripts/infer_package.py"
    DEFAULT_PACKAGE_THERMAL_SCRIPT="${DEEPOHEAT_DIR}/package_thermal/infer_package.py"

    if [ -z "$THERMAL_MODEL_PATH" ]; then
        THERMAL_MODEL_PATH="$DEFAULT_THERMAL_MODEL"
    fi
    if [ -z "$THERMAL_PYTHON" ]; then
        THERMAL_PYTHON="$DEFAULT_THERMAL_PYTHON"
    fi
    if [ -z "$THERMAL_SCRIPT" ]; then
        if [ "$THERMAL_BACKEND" = "package_thermal" ]; then
            THERMAL_SCRIPT="$DEFAULT_PACKAGE_THERMAL_SCRIPT"
        else
            THERMAL_SCRIPT="$DEFAULT_LEGACY_THERMAL_SCRIPT"
        fi
    fi

    THERMAL_RUN_ID="${TEST_CASE_NAME}_thermal_seed${DEFAULT_SEED}_$(date +%Y%m%d_%H%M%S)"
    if [ -z "$THERMAL_OUTPUT_DIR" ]; then
        THERMAL_OUTPUT_DIR="${BASE_DIR}/results/thermal/${THERMAL_RUN_ID}"
    fi
    THERMAL_INSTANCE_DIR="${THERMAL_OUTPUT_DIR}/instances"
    THERMAL_MANIFEST="${THERMAL_OUTPUT_DIR}/manifest.jsonl"
    mkdir -p "$THERMAL_INSTANCE_DIR"

    THERMAL_ARGS=(
        --enable_thermal
        --thermal_backend "$THERMAL_BACKEND"
        --thermal_budget "$THERMAL_BUDGET"
        --thermal_lambda_peak "$THERMAL_LAMBDA_PEAK"
        --thermal_lambda_avg "$THERMAL_LAMBDA_AVG"
        --thermal_grid_x "$THERMAL_GRID_X"
        --thermal_grid_y "$THERMAL_GRID_Y"
        --thermal_dump_instances "$THERMAL_INSTANCE_DIR"
        --thermal_dump_manifest "$THERMAL_MANIFEST"
        --thermal_dump_prefix "$THERMAL_RUN_ID"
        --thermal_source_testcase "$TEST_CASE_NAME"
        --thermal_run_id "$THERMAL_RUN_ID"
        --thermal_candidate_source "chipletpart_search"
        --thermal_search_stage "search_candidate"
        --thermal_seed "$DEFAULT_SEED"
        --thermal_device "$THERMAL_DEVICE"
    )

    if [ "$THERMAL_MOCK" = true ]; then
        THERMAL_ARGS+=(--thermal_use_mock)
    else
        if [ ! -f "$THERMAL_MODEL_PATH" ]; then
            echo -e "${RED}Error: Thermal model not found: $THERMAL_MODEL_PATH${NC}"
            exit 1
        fi
        if [ ! -x "$THERMAL_PYTHON" ]; then
            echo -e "${RED}Error: Thermal Python is not executable: $THERMAL_PYTHON${NC}"
            exit 1
        fi
        if [ ! -f "$THERMAL_SCRIPT" ]; then
            echo -e "${RED}Error: Thermal inference script not found: $THERMAL_SCRIPT${NC}"
            exit 1
        fi
        THERMAL_ARGS+=(
            --thermal_model_path "$THERMAL_MODEL_PATH"
            --thermal_python "$THERMAL_PYTHON"
            --thermal_inference_script "$THERMAL_SCRIPT"
        )
    fi
    if [ "$THERMAL_CACHE" = true ]; then
        THERMAL_ARGS+=(--thermal_cache)
    fi
    if [ "$THERMAL_ALLOW_FALLBACK" = true ]; then
        THERMAL_ARGS+=(--thermal_allow_fallback)
    fi

    echo -e "${CYAN}Thermal-aware evaluation enabled${NC}"
    echo -e "${BLUE}Thermal backend: ${THERMAL_BACKEND}${NC}"
    echo -e "${BLUE}Thermal model: ${THERMAL_MODEL_PATH}${NC}"
    echo -e "${BLUE}Thermal Python: ${THERMAL_PYTHON}${NC}"
    echo -e "${BLUE}Thermal device: ${THERMAL_DEVICE}${NC}"
    echo -e "${BLUE}Thermal grid: ${THERMAL_GRID_X}x${THERMAL_GRID_Y}${NC}"
    echo -e "${BLUE}Thermal output directory: ${THERMAL_OUTPUT_DIR}${NC}"
fi

# Check if we're evaluating an existing partition
if [ -n "$EVALUATE_PARTITION" ]; then
    if [ ! -f "$EVALUATE_PARTITION" ]; then
        echo -e "${RED}Error: Partition file not found: $EVALUATE_PARTITION${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Evaluating partition file: ${EVALUATE_PARTITION}${NC}"
    
    # Run ChipletPart in evaluation mode
    "$EXECUTABLE" \
        "$EVALUATE_PARTITION" \
        "$IO" \
        "$LAYER" \
        "$WAFER" \
        "$ASSEMBLY" \
        "$TEST" \
        "$NETLIST" \
        "$BLOCKS" \
        "$DEFAULT_REACH" \
        "$DEFAULT_SEPARATION" \
        "$DEFAULT_TECH" \
        --seed "$DEFAULT_SEED" \
        "${THERMAL_ARGS[@]}"
        
    exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}Partition evaluation completed successfully!${NC}"
    else
        echo -e "${RED}Partition evaluation failed with exit code $exit_code${NC}"
    fi
    
    exit $exit_code
fi

# Build the command based on which algorithm we're using
if [ "$USE_TECH_ENUM" = true ]; then
    # Make sure tech nodes are provided for technology enumeration
    if [ -z "$TECH_NODES" ]; then
        echo -e "${YELLOW}Warning: No tech nodes specified for technology enumeration. Using default: 7nm,14nm,28nm${NC}"
        TECH_NODES="7nm,14nm,28nm"
    fi
    
    echo -e "${CYAN}====================================================================${NC}"
    echo -e "${CYAN}     Running Technology Enumeration for test case: ${TEST_CASE_NAME}   ${NC}"
    echo -e "${CYAN}====================================================================${NC}"
    echo -e "${GREEN}Using Technology Enumeration to find optimal assignments${NC}"
    echo
    echo -e "${BLUE}Tech nodes: ${TECH_NODES}${NC}"
    echo -e "${BLUE}Maximum partitions: ${DEFAULT_MAX_PARTITIONS}${NC}"
    echo -e "${BLUE}Reach: ${DEFAULT_REACH}, Separation: ${DEFAULT_SEPARATION}${NC}"
    echo -e "${BLUE}Random seed: ${DEFAULT_SEED}${NC}"
    echo -e "${BLUE}Detailed output: ${DETAILED_OUTPUT}${NC}"
    
    # Create detailed output flag if needed
    DETAIL_FLAG=""
    if [ "$DETAILED_OUTPUT" = true ]; then
        DETAIL_FLAG="--detailed-output"
    fi
    
    # Run the executable with technology enumeration
    "$EXECUTABLE" \
        "$IO" \
        "$LAYER" \
        "$WAFER" \
        "$ASSEMBLY" \
        "$TEST" \
        "$NETLIST" \
        "$BLOCKS" \
        "$DEFAULT_REACH" \
        "$DEFAULT_SEPARATION" \
        --tech-enum \
        --tech-nodes "$TECH_NODES" \
        --max-partitions "$DEFAULT_MAX_PARTITIONS" \
        $DETAIL_FLAG \
        --seed "$DEFAULT_SEED" \
        "${THERMAL_ARGS[@]}"
        
elif [ "$USE_CANONICAL_GA" = true ]; then
    # Make sure tech nodes are provided for canonical GA
    if [ -z "$TECH_NODES" ]; then
        echo -e "${YELLOW}Warning: No tech nodes specified for canonical GA. Using default: 7nm,14nm,28nm${NC}"
        TECH_NODES="7nm,14nm,28nm"
    fi
    
    echo -e "${CYAN}====================================================================${NC}"
    echo -e "${CYAN}         Running Canonical GA for test case: ${TEST_CASE_NAME}        ${NC}"
    echo -e "${CYAN}====================================================================${NC}"
    echo -e "${GREEN}Using full Canonical Genetic Algorithm implementation${NC}"
    echo -e "${GREEN}with improved error handling and memory safety${NC}"
    echo
    echo -e "${BLUE}Tech nodes: ${TECH_NODES}${NC}"
    echo -e "${BLUE}Generations: ${DEFAULT_GENERATIONS}, Population size: ${DEFAULT_POPULATION}${NC}"
    echo -e "${BLUE}Reach: ${DEFAULT_REACH}, Separation: ${DEFAULT_SEPARATION}${NC}"
    echo -e "${BLUE}Random seed: ${DEFAULT_SEED}${NC}"
    
    # Run the executable with canonical GA
    "$EXECUTABLE" \
        "$IO" \
        "$LAYER" \
        "$WAFER" \
        "$ASSEMBLY" \
        "$TEST" \
        "$NETLIST" \
        "$BLOCKS" \
        "$DEFAULT_REACH" \
        "$DEFAULT_SEPARATION" \
        --canonical-ga \
        --tech-nodes "$TECH_NODES" \
        --generations "$DEFAULT_GENERATIONS" \
        --population "$DEFAULT_POPULATION" \
        --seed "$DEFAULT_SEED" \
        "${THERMAL_ARGS[@]}"
        
elif [ "$USE_GENETIC" = true ]; then
    # Make sure tech nodes are provided for genetic partitioning
    if [ -z "$TECH_NODES" ]; then
        echo -e "${YELLOW}Warning: No tech nodes specified for genetic partitioning. Using default: 7nm,10nm,45nm${NC}"
        TECH_NODES="7nm,10nm,45nm"
    fi
    
    echo -e "${GREEN}Running genetic tech partitioning for test case: ${TEST_CASE_NAME}${NC}"
    echo -e "${BLUE}Tech nodes: ${TECH_NODES}${NC}"
    echo -e "${BLUE}Generations: ${DEFAULT_GENERATIONS}, Population size: ${DEFAULT_POPULATION}${NC}"
    
    # Run the executable using technology assignment mode instead of genetic tech partitioning
    echo "$EXECUTABLE" \
        "$IO" \
        "$LAYER" \
        "$WAFER" \
        "$ASSEMBLY" \
        "$TEST" \
        "$NETLIST" \
        "$BLOCKS" \
        "$DEFAULT_REACH" \
        "$DEFAULT_SEPARATION" \
        --genetic-tech-part \
        --tech-nodes "$TECH_NODES" \
        --generations "$DEFAULT_GENERATIONS" \
        --population "$DEFAULT_POPULATION" \
        --seed "$DEFAULT_SEED" \
        "${THERMAL_ARGS[@]}"
    "$EXECUTABLE" \
        "$IO" \
        "$LAYER" \
        "$WAFER" \
        "$ASSEMBLY" \
        "$TEST" \
        "$NETLIST" \
        "$BLOCKS" \
        "$DEFAULT_REACH" \
        "$DEFAULT_SEPARATION" \
        --genetic-tech-part \
        --tech-nodes "$TECH_NODES" \
        --generations "$DEFAULT_GENERATIONS" \
        --population "$DEFAULT_POPULATION" \
        --seed "$DEFAULT_SEED" \
        "${THERMAL_ARGS[@]}"
else
    echo -e "${GREEN}Running standard partitioning for test case: ${TEST_CASE_NAME}${NC}"
    echo -e "${BLUE}Tech node: ${DEFAULT_TECH}${NC}"
    
    # Run the executable with standard partitioning
    "$EXECUTABLE" \
        "$IO" \
        "$LAYER" \
        "$WAFER" \
        "$ASSEMBLY" \
        "$TEST" \
        "$NETLIST" \
        "$BLOCKS" \
        "$DEFAULT_REACH" \
        "$DEFAULT_SEPARATION" \
        "$DEFAULT_TECH" \
        --seed "$DEFAULT_SEED" \
        "${THERMAL_ARGS[@]}"
fi

exit_code=$?
if [ $exit_code -eq 0 ]; then
    if [ "$USE_TECH_ENUM" = true ]; then
        echo -e "${GREEN}Technology Enumeration completed successfully!${NC}"
    elif [ "$USE_CANONICAL_GA" = true ]; then
        echo -e "${GREEN}Canonical GA test completed successfully!${NC}"
        
        # List the output files from canonical GA
        echo -e "${BLUE}Generated output files:${NC}"
        ls -la "${BUILD_DIR}/bin/canonical_ga_result"*
    else
        echo -e "${GREEN}Test completed successfully!${NC}"
    fi
else
    echo -e "${RED}Test failed with exit code $exit_code${NC}"
fi

if [ "$USE_TECH_ENUM" = true ] || [ "$USE_CANONICAL_GA" = true ]; then
    echo -e "${CYAN}====================================================================${NC}"
    echo -e "${CYAN}                     Test Script Completed                          ${NC}"
    echo -e "${CYAN}====================================================================${NC}"
fi 

exit $exit_code
