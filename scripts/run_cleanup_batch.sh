#!/bin/bash
# Cleanup Pipeline Batch Runner
# This script runs the cleanup pipeline in batches with configurable settings
# Features:
# - Batch processing with delays between runs
# - Logging with timestamps
# - Error handling and retry logic
# - Status monitoring
# - Configurable batch size and intervals

set -e  # Exit on any error

# Default configuration
DEFAULT_BATCH_COUNT=5
DEFAULT_DELAY_MINUTES=0
DEFAULT_MAX_RETRIES=3
DEFAULT_LOG_LEVEL="INFO"
DEFAULT_ARTICLES_PER_BATCH=10
DEFAULT_BATCH_DELAY_SECONDS=30

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$PROJECT_ROOT/logs"
CLEANUP_SCRIPT="$SCRIPT_DIR/cleanup_pipeline_batched.py"

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

# Log file with timestamp
LOG_FILE="$LOGS_DIR/cleanup_batch_$(date +%Y%m%d_%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Function to run a single cleanup pipeline
run_cleanup_pipeline() {
    local attempt="$1"
    local max_attempts="$2"
    local articles_per_batch="$3"
    local batch_delay="$4"
    local max_batches="$5"
    
    log_message "INFO" "Starting cleanup pipeline (attempt $attempt/$max_attempts)..."
    log_message "INFO" "  - Articles per batch: $articles_per_batch"
    log_message "INFO" "  - Delay between article batches: ${batch_delay}s"
    if [[ -n "$max_batches" && "$max_batches" != "unlimited" ]]; then
        log_message "INFO" "  - Max article batches: $max_batches"
    else
        log_message "INFO" "  - Max article batches: unlimited"
    fi
    
    # Change to project root for proper import paths
    cd "$PROJECT_ROOT"
    
    # Build arguments for the batched pipeline
    local args=(
        --batch-size "$articles_per_batch"
        --delay "$batch_delay"
    )
    
    if [[ -n "$max_batches" && "$max_batches" != "unlimited" ]]; then
        args+=(--max-batches "$max_batches")
    fi
    
    if $PYTHON_CMD "$CLEANUP_SCRIPT" "${args[@]}"; then
        log_message "SUCCESS" "Cleanup pipeline completed successfully"
        return 0
    else
        local exit_code=$?
        log_message "ERROR" "Cleanup pipeline failed with exit code $exit_code"
        return $exit_code
    fi
}

# Function to wait with countdown
wait_with_countdown() {
    local wait_minutes="$1"
    local wait_seconds=$((wait_minutes * 60))
    
    log_message "INFO" "Waiting $wait_minutes minutes before next batch..."
    
    while [[ $wait_seconds -gt 0 ]]; do
        local minutes=$((wait_seconds / 60))
        local seconds=$((wait_seconds % 60))
        printf "\rNext run in: %02d:%02d" $minutes $seconds
        sleep 1
        ((wait_seconds--))
    done
    echo
}

# Function to display usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Cleanup Pipeline Batch Runner

OPTIONS:
    -c, --count NUMBER      Number of batches to run (default: $DEFAULT_BATCH_COUNT)
    -d, --delay MINUTES     Delay between batches in minutes (default: $DEFAULT_DELAY_MINUTES, 0=no delay)
    -r, --retries NUMBER    Maximum retries per batch (default: $DEFAULT_MAX_RETRIES)
    -a, --articles NUMBER   Articles per batch (default: $DEFAULT_ARTICLES_PER_BATCH)
    -s, --batch-delay SEC   Seconds delay between article batches (default: $DEFAULT_BATCH_DELAY_SECONDS)
    -m, --max-batches NUM   Max article batches per run (default: unlimited)
    -l, --log-level LEVEL   Log level (INFO, WARNING, ERROR) (default: $DEFAULT_LOG_LEVEL)
    -o, --once              Run only once (ignore count and delay)
    -h, --help              Show this help message

EXAMPLES:
    $0                      # Run 5 batches, 10 articles each, consecutively 
    $0 -a 5                 # Run with 5 articles per batch
    $0 -a 20 -s 60          # 20 articles per batch, 60s delays between article batches
    $0 -c 10 -d 15          # Run 10 pipeline batches with 15 minute delays
    $0 --once -a 5          # Run once with 5 articles per batch
    $0 -a 10 -m 5           # Max 5 article batches per pipeline run (50 articles total)
    $0 -c 3 -a 15 -s 30     # 3 pipeline runs, 15 articles per batch, 30s delays

LOGS:
    Batch logs are saved to: $LOGS_DIR/cleanup_batch_TIMESTAMP.log
EOF
}

# Parse command line arguments
BATCH_COUNT="$DEFAULT_BATCH_COUNT"
DELAY_MINUTES="$DEFAULT_DELAY_MINUTES"
MAX_RETRIES="$DEFAULT_MAX_RETRIES"
LOG_LEVEL="$DEFAULT_LOG_LEVEL"
ARTICLES_PER_BATCH="$DEFAULT_ARTICLES_PER_BATCH"
BATCH_DELAY_SECONDS="$DEFAULT_BATCH_DELAY_SECONDS"
MAX_BATCHES="unlimited"
RUN_ONCE=false

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
        -a|--articles)
            ARTICLES_PER_BATCH="$2"
            shift 2
            ;;
        -s|--batch-delay)
            BATCH_DELAY_SECONDS="$2"
            shift 2
            ;;
        -m|--max-batches)
            MAX_BATCHES="$2"
            shift 2
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

if ! [[ "$ARTICLES_PER_BATCH" =~ ^[0-9]+$ ]] || [[ "$ARTICLES_PER_BATCH" -lt 1 ]]; then
    log_message "ERROR" "Articles per batch must be a positive integer"
    exit 1
fi

if ! [[ "$BATCH_DELAY_SECONDS" =~ ^[0-9]+$ ]] || [[ "$BATCH_DELAY_SECONDS" -lt 0 ]]; then
    log_message "ERROR" "Batch delay must be a non-negative integer"
    exit 1
fi

if [[ "$MAX_BATCHES" != "unlimited" ]] && (! [[ "$MAX_BATCHES" =~ ^[0-9]+$ ]] || [[ "$MAX_BATCHES" -lt 1 ]]); then
    log_message "ERROR" "Max batches must be a positive integer or 'unlimited'"
    exit 1
fi

# Main execution
main() {
    log_message "INFO" "=== Cleanup Pipeline Batch Runner Started ==="
    log_message "INFO" "Configuration:"
    log_message "INFO" "  - Pipeline batches: $BATCH_COUNT"
    log_message "INFO" "  - Delay between pipeline batches: $DELAY_MINUTES minutes"
    log_message "INFO" "  - Max retries per pipeline batch: $MAX_RETRIES"
    log_message "INFO" "  - Articles per batch: $ARTICLES_PER_BATCH"
    log_message "INFO" "  - Delay between article batches: $BATCH_DELAY_SECONDS seconds"
    log_message "INFO" "  - Max article batches per pipeline run: $MAX_BATCHES"
    log_message "INFO" "  - Log file: $LOG_FILE"
    log_message "INFO" "  - Run once: $RUN_ONCE"
    
    # Setup Python environment
    setup_python_env
    
    # Verify cleanup script exists
    if [[ ! -f "$CLEANUP_SCRIPT" ]]; then
        log_message "ERROR" "Cleanup script not found: $CLEANUP_SCRIPT"
        exit 1
    fi
    
    local successful_runs=0
    local failed_runs=0
    
    if [[ "$RUN_ONCE" == true ]]; then
        BATCH_COUNT=1
    fi
    
    # Run batches
    for ((batch=1; batch<=BATCH_COUNT; batch++)); do
        log_message "INFO" "--- Starting Batch $batch of $BATCH_COUNT ---"
        
        local success=false
        for ((attempt=1; attempt<=MAX_RETRIES; attempt++)); do
            if run_cleanup_pipeline "$attempt" "$MAX_RETRIES" "$ARTICLES_PER_BATCH" "$BATCH_DELAY_SECONDS" "$MAX_BATCHES"; then
                success=true
                ((successful_runs++))
                break
            else
                if [[ $attempt -lt $MAX_RETRIES ]]; then
                    log_message "WARNING" "Attempt $attempt failed, retrying in 60 seconds..."
                    sleep 60
                fi
            fi
        done
        
        if [[ "$success" == false ]]; then
            log_message "ERROR" "Batch $batch failed after $MAX_RETRIES attempts"
            ((failed_runs++))
        fi
        
        # Wait before next batch (except for the last one or if running once)
        if [[ $batch -lt $BATCH_COUNT ]] && [[ "$RUN_ONCE" == false ]] && [[ $DELAY_MINUTES -gt 0 ]]; then
            wait_with_countdown "$DELAY_MINUTES"
        fi
    done
    
    # Final summary
    log_message "INFO" "=== Cleanup Pipeline Batch Runner Completed ==="
    log_message "INFO" "Summary:"
    log_message "INFO" "  - Total batches: $BATCH_COUNT"
    log_message "SUCCESS" "  - Successful runs: $successful_runs"
    if [[ $failed_runs -gt 0 ]]; then
        log_message "ERROR" "  - Failed runs: $failed_runs"
    else
        log_message "INFO" "  - Failed runs: $failed_runs"
    fi
    
    if [[ $failed_runs -gt 0 ]]; then
        exit 1
    fi
}

# Handle script interruption
trap 'log_message "WARNING" "Script interrupted by user"; exit 130' INT TERM

# Run main function
main "$@"
