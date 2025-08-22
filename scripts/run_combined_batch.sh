#!/bin/bash
# Combined Pipeline Batch Runner
# This script runs both cleanup and cluster pipelines in sequence with configurable settings
# Features:
# - Sequential execution: cleanup -> clustering
# - Configurable intervals and batch counts
# - Independent retry logic for each pipeline
# - Comprehensive logging
# - Flexible scheduling options

set -e  # Exit on any error

# Default configuration
DEFAULT_COMBINED_CYCLES=3
DEFAULT_CLEANUP_BATCHES=2
DEFAULT_CLUSTER_BATCHES=1
DEFAULT_CLEANUP_DELAY=0
DEFAULT_CLUSTER_DELAY=0
DEFAULT_CYCLE_DELAY=120
DEFAULT_MAX_RETRIES=3

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$PROJECT_ROOT/logs"

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

# Log file with timestamp
LOG_FILE="$LOGS_DIR/combined_batch_$(date +%Y%m%d_%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
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
        "CLEANUP")
            colored_message="${CYAN}[CLEANUP]${NC} $message"
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

# Function to wait with countdown
wait_with_countdown() {
    local wait_minutes="$1"
    local description="$2"
    local wait_seconds=$((wait_minutes * 60))
    
    log_message "INFO" "Waiting $wait_minutes minutes $description..."
    
    while [[ $wait_seconds -gt 0 ]]; do
        local hours=$((wait_seconds / 3600))
        local minutes=$(((wait_seconds % 3600) / 60))
        local seconds=$((wait_seconds % 60))
        printf "\r$description in: %02d:%02d:%02d" $hours $minutes $seconds
        sleep 1
        ((wait_seconds--))
    done
    echo
}

# Function to run cleanup batches
run_cleanup_batches() {
    local batch_count="$1"
    local delay_minutes="$2"
    local max_retries="$3"
    
    log_message "CLEANUP" "Starting cleanup pipeline batches (count: $batch_count, delay: $delay_minutes min)"
    
    if [[ $batch_count -eq 1 ]]; then
        if "$SCRIPT_DIR/run_cleanup_batch.sh" --once --retries "$max_retries"; then
            log_message "SUCCESS" "Cleanup batch completed successfully"
            return 0
        else
            log_message "ERROR" "Cleanup batch failed"
            return 1
        fi
    else
        if "$SCRIPT_DIR/run_cleanup_batch.sh" --count "$batch_count" --delay "$delay_minutes" --retries "$max_retries"; then
            log_message "SUCCESS" "All cleanup batches completed successfully"
            return 0
        else
            log_message "ERROR" "Cleanup batches failed"
            return 1
        fi
    fi
}

# Function to run cluster batches
run_cluster_batches() {
    local batch_count="$1"
    local delay_minutes="$2"
    local max_retries="$3"
    local progressive="$4"
    local threshold="$5"
    local merge_threshold="$6"
    
    log_message "CLUSTER" "Starting cluster pipeline batches (count: $batch_count, delay: $delay_minutes min)"
    
    local cluster_args=()
    cluster_args+=(--retries "$max_retries")
    
    if [[ -n "$threshold" ]]; then
        cluster_args+=(--threshold "$threshold")
    fi
    
    if [[ -n "$merge_threshold" ]]; then
        cluster_args+=(--merge-threshold "$merge_threshold")
    fi
    
    if [[ "$progressive" == true ]]; then
        cluster_args+=(--progressive)
    fi
    
    if [[ $batch_count -eq 1 ]]; then
        cluster_args+=(--once)
    else
        cluster_args+=(--count "$batch_count" --delay "$delay_minutes")
    fi
    
    if "$SCRIPT_DIR/run_cluster_batch.sh" "${cluster_args[@]}"; then
        log_message "SUCCESS" "All cluster batches completed successfully"
        return 0
    else
        log_message "ERROR" "Cluster batches failed"
        return 1
    fi
}

# Function to display usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Combined Pipeline Batch Runner

This script runs cleanup and clustering pipelines in sequence across multiple cycles.
Each cycle consists of:
1. Cleanup pipeline batches (process new articles)
2. Optional delay between cleanup and clustering
3. Clustering pipeline batches (cluster processed articles)
4. Optional delay before next cycle

OPTIONS:
    -n, --cycles NUMBER           Number of combined cycles to run (default: $DEFAULT_COMBINED_CYCLES)
    --cleanup-batches NUMBER      Cleanup batches per cycle (default: $DEFAULT_CLEANUP_BATCHES)
    --cluster-batches NUMBER      Cluster batches per cycle (default: $DEFAULT_CLUSTER_BATCHES)
    --cleanup-delay MINUTES       Delay between cleanup batches (default: $DEFAULT_CLEANUP_DELAY, 0=no delay)
    --cluster-delay MINUTES       Delay between cluster batches (default: $DEFAULT_CLUSTER_DELAY, 0=no delay)
    --cycle-delay MINUTES         Delay between cycles (default: $DEFAULT_CYCLE_DELAY)
    -r, --retries NUMBER          Max retries per batch (default: $DEFAULT_MAX_RETRIES)
    -t, --threshold FLOAT         Clustering similarity threshold
    -m, --merge-threshold FLOAT   Clustering merge threshold
    -p, --progressive             Enable progressive clustering threshold tuning
    --cleanup-only                Run only cleanup pipelines
    --cluster-only                Run only clustering pipelines
    --once                        Run one cycle only
    -h, --help                    Show this help message

EXAMPLES:
    $0                            # 3 cycles: consecutive cleanup → consecutive cluster → repeat
    $0 --once                     # Run one complete cycle (all batches consecutive)
    $0 -n 5 --cycle-delay 180     # Run 5 cycles with 3-hour delays between cycles
    $0 --cleanup-only -n 2        # Run only cleanup batches (consecutive)
    $0 --cluster-only -p          # Run only clustering with progressive tuning
    $0 --cleanup-batches 3 --cluster-batches 2  # Custom batch counts (all consecutive)

WORKFLOW:
    For each cycle:
    1. Run cleanup pipeline batches
    2. Wait (if both pipelines enabled)
    3. Run clustering pipeline batches
    4. Wait before next cycle (if not last cycle)

LOGS:
    Combined logs saved to: $LOGS_DIR/combined_batch_TIMESTAMP.log
EOF
}

# Parse command line arguments
COMBINED_CYCLES="$DEFAULT_COMBINED_CYCLES"
CLEANUP_BATCHES="$DEFAULT_CLEANUP_BATCHES"
CLUSTER_BATCHES="$DEFAULT_CLUSTER_BATCHES"
CLEANUP_DELAY="$DEFAULT_CLEANUP_DELAY"
CLUSTER_DELAY="$DEFAULT_CLUSTER_DELAY"
CYCLE_DELAY="$DEFAULT_CYCLE_DELAY"
MAX_RETRIES="$DEFAULT_MAX_RETRIES"
THRESHOLD=""
MERGE_THRESHOLD=""
PROGRESSIVE_TUNING=false
CLEANUP_ONLY=false
CLUSTER_ONLY=false
RUN_ONCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--cycles)
            COMBINED_CYCLES="$2"
            shift 2
            ;;
        --cleanup-batches)
            CLEANUP_BATCHES="$2"
            shift 2
            ;;
        --cluster-batches)
            CLUSTER_BATCHES="$2"
            shift 2
            ;;
        --cleanup-delay)
            CLEANUP_DELAY="$2"
            shift 2
            ;;
        --cluster-delay)
            CLUSTER_DELAY="$2"
            shift 2
            ;;
        --cycle-delay)
            CYCLE_DELAY="$2"
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
        --cleanup-only)
            CLEANUP_ONLY=true
            shift
            ;;
        --cluster-only)
            CLUSTER_ONLY=true
            shift
            ;;
        --once)
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
if [[ "$CLEANUP_ONLY" == true ]] && [[ "$CLUSTER_ONLY" == true ]]; then
    log_message "ERROR" "Cannot specify both --cleanup-only and --cluster-only"
    exit 1
fi

if [[ "$RUN_ONCE" == true ]]; then
    COMBINED_CYCLES=1
fi

# Validate numeric arguments
for arg in COMBINED_CYCLES CLEANUP_BATCHES CLUSTER_BATCHES CLEANUP_DELAY CLUSTER_DELAY CYCLE_DELAY MAX_RETRIES; do
    if ! [[ "${!arg}" =~ ^[0-9]+$ ]] || [[ "${!arg}" -lt 0 ]]; then
        log_message "ERROR" "$arg must be a non-negative integer"
        exit 1
    fi
done

# Main execution
main() {
    log_message "INFO" "=== Combined Pipeline Batch Runner Started ==="
    log_message "INFO" "Configuration:"
    log_message "INFO" "  - Total cycles: $COMBINED_CYCLES"
    log_message "INFO" "  - Cleanup batches per cycle: $CLEANUP_BATCHES"
    log_message "INFO" "  - Cluster batches per cycle: $CLUSTER_BATCHES"
    log_message "INFO" "  - Cleanup delay: $CLEANUP_DELAY minutes"
    log_message "INFO" "  - Cluster delay: $CLUSTER_DELAY minutes"
    log_message "INFO" "  - Cycle delay: $CYCLE_DELAY minutes"
    log_message "INFO" "  - Max retries: $MAX_RETRIES"
    log_message "INFO" "  - Cleanup only: $CLEANUP_ONLY"
    log_message "INFO" "  - Cluster only: $CLUSTER_ONLY"
    log_message "INFO" "  - Progressive tuning: $PROGRESSIVE_TUNING"
    log_message "INFO" "  - Log file: $LOG_FILE"
    
    # Verify required scripts exist
    if [[ "$CLEANUP_ONLY" != true ]] && [[ ! -f "$SCRIPT_DIR/run_cluster_batch.sh" ]]; then
        log_message "ERROR" "Cluster batch script not found: $SCRIPT_DIR/run_cluster_batch.sh"
        exit 1
    fi
    
    if [[ "$CLUSTER_ONLY" != true ]] && [[ ! -f "$SCRIPT_DIR/run_cleanup_batch.sh" ]]; then
        log_message "ERROR" "Cleanup batch script not found: $SCRIPT_DIR/run_cleanup_batch.sh"
        exit 1
    fi
    
    local successful_cycles=0
    local failed_cycles=0
    local total_cleanup_success=0
    local total_cluster_success=0
    
    # Run cycles
    for ((cycle=1; cycle<=COMBINED_CYCLES; cycle++)); do
        log_message "INFO" "=== Starting Combined Cycle $cycle of $COMBINED_CYCLES ==="
        
        local cycle_success=true
        
        # Run cleanup batches
        if [[ "$CLUSTER_ONLY" != true ]]; then
            log_message "CLEANUP" "Phase 1: Cleanup pipeline batches"
            if run_cleanup_batches "$CLEANUP_BATCHES" "$CLEANUP_DELAY" "$MAX_RETRIES"; then
                ((total_cleanup_success++))
                log_message "SUCCESS" "Cleanup phase completed for cycle $cycle"
            else
                cycle_success=false
                log_message "ERROR" "Cleanup phase failed for cycle $cycle"
            fi
            
            # Delay between cleanup and clustering (if both are enabled)
            if [[ "$CLEANUP_ONLY" != true ]] && [[ $cycle_success == true ]]; then
                wait_with_countdown 5 "before clustering phase"
            fi
        fi
        
        # Run cluster batches
        if [[ "$CLEANUP_ONLY" != true ]] && [[ $cycle_success == true ]]; then
            log_message "CLUSTER" "Phase 2: Clustering pipeline batches"
            if run_cluster_batches "$CLUSTER_BATCHES" "$CLUSTER_DELAY" "$MAX_RETRIES" "$PROGRESSIVE_TUNING" "$THRESHOLD" "$MERGE_THRESHOLD"; then
                ((total_cluster_success++))
                log_message "SUCCESS" "Clustering phase completed for cycle $cycle"
            else
                cycle_success=false
                log_message "ERROR" "Clustering phase failed for cycle $cycle"
            fi
        fi
        
        # Update cycle counters
        if [[ $cycle_success == true ]]; then
            ((successful_cycles++))
            log_message "SUCCESS" "=== Cycle $cycle completed successfully ==="
        else
            ((failed_cycles++))
            log_message "ERROR" "=== Cycle $cycle failed ==="
        fi
        
        # Wait before next cycle (except for the last one)
        if [[ $cycle -lt $COMBINED_CYCLES ]]; then
            wait_with_countdown "$CYCLE_DELAY" "before next cycle"
        fi
    done
    
    # Final summary
    log_message "INFO" "=== Combined Pipeline Batch Runner Completed ==="
    log_message "INFO" "Final Summary:"
    log_message "INFO" "  - Total cycles: $COMBINED_CYCLES"
    log_message "SUCCESS" "  - Successful cycles: $successful_cycles"
    if [[ $failed_cycles -gt 0 ]]; then
        log_message "ERROR" "  - Failed cycles: $failed_cycles"
    else
        log_message "INFO" "  - Failed cycles: $failed_cycles"
    fi
    
    if [[ "$CLUSTER_ONLY" != true ]]; then
        log_message "INFO" "  - Successful cleanup phases: $total_cleanup_success"
    fi
    
    if [[ "$CLEANUP_ONLY" != true ]]; then
        log_message "INFO" "  - Successful cluster phases: $total_cluster_success"
    fi
    
    if [[ $failed_cycles -gt 0 ]]; then
        exit 1
    fi
}

# Handle script interruption
trap 'log_message "WARNING" "Script interrupted by user"; exit 130' INT TERM

# Run main function
main "$@"
