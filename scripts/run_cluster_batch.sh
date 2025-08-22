#!/bin/bash
# Cluster Pipeline Batch Runner
# This script runs the cluster pipeline in batches with configurable settings
# Features:
# - Batch processing with delays between runs
# - Configurable similarity thresholds
# - Logging with timestamps
# - Error handling and retry logic
# - Status monitoring
# - Threshold tuning for different batches

set -e  # Exit on any error

# Default configuration
DEFAULT_BATCH_COUNT=3
DEFAULT_DELAY_MINUTES=0
DEFAULT_MAX_RETRIES=2
DEFAULT_THRESHOLD=0.82
DEFAULT_MERGE_THRESHOLD=0.9
DEFAULT_LOG_LEVEL="INFO"

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$PROJECT_ROOT/logs"
CLUSTER_SCRIPT="$SCRIPT_DIR/cluster_pipeline.py"

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

# Log file with timestamp
LOG_FILE="$LOGS_DIR/cluster_batch_$(date +%Y%m%d_%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Function to log messages with timestamp
log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local colored_message=""
    
    case "$level" in
        "INFO")
            colored_message="${BLUE}[INFO]${NC} $message"
            ;;
        "SUCCESS")
            colored_message="${GREEN}[SUCCESS]${NC} $message"
            ;;
        "WARNING")
            colored_message="${YELLOW}[WARNING]${NC} $message"
            ;;
        "ERROR")
            colored_message="${RED}[ERROR]${NC} $message"
            ;;
        "CLUSTER")
            colored_message="${PURPLE}[CLUSTER]${NC} $message"
            ;;
        *)
            colored_message="[$level] $message"
            ;;
    esac
    
    echo -e "$colored_message"
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# Function to check if virtual environment exists and activate it
setup_python_env() {
    if [[ -d "$PROJECT_ROOT/venv" ]]; then
        log_message "INFO" "Activating virtual environment..."
        source "$PROJECT_ROOT/venv/bin/activate"
        PYTHON_CMD="python"
    elif [[ -d "$PROJECT_ROOT/.venv" ]]; then
        log_message "INFO" "Activating virtual environment (.venv)..."
        source "$PROJECT_ROOT/.venv/bin/activate"
        PYTHON_CMD="python"
    else
        log_message "WARNING" "No virtual environment found, using system Python3"
        PYTHON_CMD="python3"
    fi
    
    # Verify Python is available
    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        log_message "ERROR" "Python interpreter not found"
        exit 1
    fi
    
    log_message "INFO" "Using Python: $(which $PYTHON_CMD)"
    log_message "INFO" "Python version: $($PYTHON_CMD --version)"
}

# Function to run clustering pipeline with custom thresholds
run_cluster_pipeline() {
    local attempt="$1"
    local max_attempts="$2"
    local threshold="$3"
    local merge_threshold="$4"
    local batch_num="$5"
    
    log_message "CLUSTER" "Starting clustering pipeline (batch $batch_num, attempt $attempt/$max_attempts)..."
    log_message "CLUSTER" "  - Similarity threshold: $threshold"
    log_message "CLUSTER" "  - Merge threshold: $merge_threshold"
    
    # Change to project root for proper import paths
    cd "$PROJECT_ROOT"
    
    # Create a temporary Python script to run with custom thresholds
    local temp_script=$(mktemp)
    cat > "$temp_script" << EOF
import sys
sys.path.insert(0, "$PROJECT_ROOT/src")
from scripts.cluster_pipeline import process_new

if __name__ == "__main__":
    process_new(threshold=$threshold, merge_threshold=$merge_threshold)
EOF
    
    if $PYTHON_CMD "$temp_script"; then
        log_message "SUCCESS" "Clustering pipeline completed successfully (batch $batch_num)"
        rm -f "$temp_script"
        return 0
    else
        local exit_code=$?
        log_message "ERROR" "Clustering pipeline failed with exit code $exit_code (batch $batch_num)"
        rm -f "$temp_script"
        return $exit_code
    fi
}

# Function to calculate dynamic thresholds based on batch number
calculate_thresholds() {
    local batch_num="$1"
    local base_threshold="$2"
    local base_merge_threshold="$3"
    local progressive_tuning="$4"
    
    if [[ "$progressive_tuning" == true ]]; then
        # Gradually decrease thresholds for more aggressive clustering in later batches
        local threshold_adjustment=$(echo "scale=3; ($batch_num - 1) * 0.01" | bc -l)
        local new_threshold=$(echo "scale=3; $base_threshold - $threshold_adjustment" | bc -l)
        local new_merge_threshold=$(echo "scale=3; $base_merge_threshold - $threshold_adjustment" | bc -l)
        
        # Ensure thresholds don't go below minimum values
        local min_threshold=0.70
        local min_merge_threshold=0.80
        
        if (( $(echo "$new_threshold < $min_threshold" | bc -l) )); then
            new_threshold=$min_threshold
        fi
        
        if (( $(echo "$new_merge_threshold < $min_merge_threshold" | bc -l) )); then
            new_merge_threshold=$min_merge_threshold
        fi
        
        echo "$new_threshold $new_merge_threshold"
    else
        echo "$base_threshold $base_merge_threshold"
    fi
}

# Function to wait with countdown
wait_with_countdown() {
    local wait_minutes="$1"
    local wait_seconds=$((wait_minutes * 60))
    
    log_message "INFO" "Waiting $wait_minutes minutes before next clustering batch..."
    
    while [[ $wait_seconds -gt 0 ]]; do
        local hours=$((wait_seconds / 3600))
        local minutes=$(((wait_seconds % 3600) / 60))
        local seconds=$((wait_seconds % 60))
        printf "\rNext clustering run in: %02d:%02d:%02d" $hours $minutes $seconds
        sleep 1
        ((wait_seconds--))
    done
    echo
}

# Function to display usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Cluster Pipeline Batch Runner

OPTIONS:
    -c, --count NUMBER        Number of batches to run (default: $DEFAULT_BATCH_COUNT)
    -d, --delay MINUTES       Delay between batches in minutes (default: $DEFAULT_DELAY_MINUTES, 0=no delay)
    -r, --retries NUMBER      Maximum retries per batch (default: $DEFAULT_MAX_RETRIES)
    -t, --threshold FLOAT     Base similarity threshold (default: $DEFAULT_THRESHOLD)
    -m, --merge-threshold FLOAT  Base merge threshold (default: $DEFAULT_MERGE_THRESHOLD)
    -p, --progressive         Enable progressive threshold tuning
    -l, --log-level LEVEL     Log level (INFO, WARNING, ERROR) (default: $DEFAULT_LOG_LEVEL)
    -o, --once                Run only once (ignore count and delay)
    -h, --help                Show this help message

PROGRESSIVE TUNING:
    When enabled with -p, thresholds are gradually decreased by 0.01 per batch
    to make clustering more aggressive in later batches.

EXAMPLES:
    $0                        # Run 3 batches consecutively (no delays)
    $0 -c 5 -d 30 -p          # Run 5 batches with 30 min delays and progressive tuning
    $0 --once -t 0.85         # Run once with higher threshold
    $0 -c 2 -t 0.80 -m 0.88   # Run 2 batches consecutively with custom thresholds
    $0 -p -c 4                # Progressive tuning across 4 consecutive batches

LOGS:
    Batch logs are saved to: $LOGS_DIR/cluster_batch_TIMESTAMP.log
EOF
}

# Parse command line arguments
BATCH_COUNT="$DEFAULT_BATCH_COUNT"
DELAY_MINUTES="$DEFAULT_DELAY_MINUTES"
MAX_RETRIES="$DEFAULT_MAX_RETRIES"
THRESHOLD="$DEFAULT_THRESHOLD"
MERGE_THRESHOLD="$DEFAULT_MERGE_THRESHOLD"
LOG_LEVEL="$DEFAULT_LOG_LEVEL"
RUN_ONCE=false
PROGRESSIVE_TUNING=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--count)
            BATCH_COUNT="$2"
            shift 2
            ;;
        -d|--delay)
            DELAY_MINUTES="$2"
            shift 2
            ;;
        -r|--retries)
            MAX_RETRIES="$2"
            shift 2
            ;;
        -t|--threshold)
            THRESHOLD="$2"
            shift 2
            ;;
        -m|--merge-threshold)
            MERGE_THRESHOLD="$2"
            shift 2
            ;;
        -p|--progressive)
            PROGRESSIVE_TUNING=true
            shift
            ;;
        -l|--log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        -o|--once)
            RUN_ONCE=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            log_message "ERROR" "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate arguments
if ! [[ "$BATCH_COUNT" =~ ^[0-9]+$ ]] || [[ "$BATCH_COUNT" -lt 1 ]]; then
    log_message "ERROR" "Batch count must be a positive integer"
    exit 1
fi

if ! [[ "$DELAY_MINUTES" =~ ^[0-9]+$ ]] || [[ "$DELAY_MINUTES" -lt 0 ]]; then
    log_message "ERROR" "Delay must be a non-negative integer"
    exit 1
fi

if ! [[ "$MAX_RETRIES" =~ ^[0-9]+$ ]] || [[ "$MAX_RETRIES" -lt 1 ]]; then
    log_message "ERROR" "Max retries must be a positive integer"
    exit 1
fi

# Validate threshold values (basic float check)
if ! [[ "$THRESHOLD" =~ ^[0-9]*\.?[0-9]+$ ]] || (( $(echo "$THRESHOLD < 0 || $THRESHOLD > 1" | bc -l) )); then
    log_message "ERROR" "Threshold must be a float between 0 and 1"
    exit 1
fi

if ! [[ "$MERGE_THRESHOLD" =~ ^[0-9]*\.?[0-9]+$ ]] || (( $(echo "$MERGE_THRESHOLD < 0 || $MERGE_THRESHOLD > 1" | bc -l) )); then
    log_message "ERROR" "Merge threshold must be a float between 0 and 1"
    exit 1
fi

# Check if bc is available for threshold calculations
if ! command -v bc &> /dev/null; then
    log_message "ERROR" "bc calculator is required for threshold calculations. Please install bc."
    exit 1
fi

# Main execution
main() {
    log_message "INFO" "=== Cluster Pipeline Batch Runner Started ==="
    log_message "INFO" "Configuration:"
    log_message "INFO" "  - Batch count: $BATCH_COUNT"
    log_message "INFO" "  - Delay between batches: $DELAY_MINUTES minutes"
    log_message "INFO" "  - Max retries per batch: $MAX_RETRIES"
    log_message "INFO" "  - Base similarity threshold: $THRESHOLD"
    log_message "INFO" "  - Base merge threshold: $MERGE_THRESHOLD"
    log_message "INFO" "  - Progressive tuning: $PROGRESSIVE_TUNING"
    log_message "INFO" "  - Log file: $LOG_FILE"
    log_message "INFO" "  - Run once: $RUN_ONCE"
    
    # Setup Python environment
    setup_python_env
    
    # Verify cluster script exists
    if [[ ! -f "$CLUSTER_SCRIPT" ]]; then
        log_message "ERROR" "Cluster script not found: $CLUSTER_SCRIPT"
        exit 1
    fi
    
    local successful_runs=0
    local failed_runs=0
    
    if [[ "$RUN_ONCE" == true ]]; then
        BATCH_COUNT=1
    fi
    
    # Run batches
    for ((batch=1; batch<=BATCH_COUNT; batch++)); do
        log_message "INFO" "--- Starting Clustering Batch $batch of $BATCH_COUNT ---"
        
        # Calculate thresholds for this batch
        read current_threshold current_merge_threshold <<< $(calculate_thresholds "$batch" "$THRESHOLD" "$MERGE_THRESHOLD" "$PROGRESSIVE_TUNING")
        
        if [[ "$PROGRESSIVE_TUNING" == true ]]; then
            log_message "CLUSTER" "Adjusted thresholds for batch $batch:"
            log_message "CLUSTER" "  - Similarity threshold: $current_threshold (was $THRESHOLD)"
            log_message "CLUSTER" "  - Merge threshold: $current_merge_threshold (was $MERGE_THRESHOLD)"
        fi
        
        local success=false
        for ((attempt=1; attempt<=MAX_RETRIES; attempt++)); do
            if run_cluster_pipeline "$attempt" "$MAX_RETRIES" "$current_threshold" "$current_merge_threshold" "$batch"; then
                success=true
                ((successful_runs++))
                break
            else
                if [[ $attempt -lt $MAX_RETRIES ]]; then
                    log_message "WARNING" "Attempt $attempt failed, retrying in 2 minutes..."
                    sleep 120
                fi
            fi
        done
        
        if [[ "$success" == false ]]; then
            log_message "ERROR" "Clustering batch $batch failed after $MAX_RETRIES attempts"
            ((failed_runs++))
        fi
        
        # Wait before next batch (except for the last one or if running once)
        if [[ $batch -lt $BATCH_COUNT ]] && [[ "$RUN_ONCE" == false ]] && [[ $DELAY_MINUTES -gt 0 ]]; then
            wait_with_countdown "$DELAY_MINUTES"
        fi
    done
    
    # Final summary
    log_message "INFO" "=== Cluster Pipeline Batch Runner Completed ==="
    log_message "INFO" "Summary:"
    log_message "INFO" "  - Total batches: $BATCH_COUNT"
    log_message "SUCCESS" "  - Successful runs: $successful_runs"
    if [[ $failed_runs -gt 0 ]]; then
        log_message "ERROR" "  - Failed runs: $failed_runs"
    else
        log_message "INFO" "  - Failed runs: $failed_runs"
    fi
    
    if [[ "$PROGRESSIVE_TUNING" == true ]]; then
        log_message "INFO" "Progressive tuning was enabled - thresholds were adjusted across batches"
    fi
    
    if [[ $failed_runs -gt 0 ]]; then
        exit 1
    fi
}

# Handle script interruption
trap 'log_message "WARNING" "Script interrupted by user"; exit 130' INT TERM

# Run main function
main "$@"
