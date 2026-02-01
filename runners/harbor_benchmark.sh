#!/bin/bash
# Unified benchmark runner for CodeContextBench
# Supports multiple agents and benchmark sets via Harbor framework
#
# Usage:
#   harbor_benchmark.sh --benchmark terminal-bench --agent claude-baseline
#   harbor_benchmark.sh --benchmark 10figure --agent claude-mcp --tasks 50
#   harbor_benchmark.sh --collect-results jobs/baseline-* jobs/treatment-*

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
JOBS_DIR="${PROJECT_ROOT}/jobs"

# Default values
BENCHMARK="terminal-bench"
AGENT="claude-baseline"
N_TASKS=10
N_CONCURRENT=4
TASK_FILTER=""
COLLECT_MODE=false

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

print_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
    --benchmark BENCH       Benchmark dataset: terminal-bench, 10figure (default: terminal-bench)
    --agent AGENT          Agent implementation: claude-baseline, claude-mcp (default: claude-baseline)
    --tasks N              Number of tasks to run (default: 10)
    --concurrent N         Concurrent executions (default: 4)
    --task-filter PATTERN  Filter tasks by pattern (optional)
    --jobs-dir DIR         Directory for Harbor job outputs (default: ./jobs)
    --collect-results      Collect and compare results from job dirs
    --help                 Show this message

Examples:
    # Run baseline Claude on 10Figure, 50 tasks
    $(basename "$0") --benchmark 10figure --agent claude-baseline --tasks 50
    
    # Run Claude + Sourcegraph MCP, limit to 10 concurrent
    $(basename "$0") --benchmark terminal-bench --agent claude-mcp --concurrent 10
    
    # Collect results from two runs
    $(basename "$0") --collect-results jobs/baseline-20251217-161000 jobs/treatment-20251217-161500

EOF
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# ============================================================================
# Environment Validation
# ============================================================================

validate_environment() {
    log_info "Validating environment..."
    
    # Check Harbor CLI
    if ! command -v harbor &> /dev/null; then
        log_error "Harbor CLI not found in PATH"
        log_error "Install with: pip install harbor-cli"
        exit 1
    fi
    
    # Check required environment for agents
    case "$AGENT" in
        claude-baseline)
            if [ -z "$ANTHROPIC_API_KEY" ]; then
                log_error "ANTHROPIC_API_KEY not set for Claude baseline"
                log_error "Run: export ANTHROPIC_API_KEY='sk-...'"
                exit 1
            fi
            ;;
        claude-mcp)
            if [ -z "$ANTHROPIC_API_KEY" ]; then
                log_error "ANTHROPIC_API_KEY not set"
                exit 1
            fi
            if [ -z "$SRC_ACCESS_TOKEN" ]; then
                log_error "SRC_ACCESS_TOKEN not set for Sourcegraph MCP"
                log_error "Get token from: https://sourcegraph.sourcegraph.com/user/settings/tokens"
                exit 1
            fi
            if [ -z "$SOURCEGRAPH_URL" ]; then
                log_warn "SOURCEGRAPH_URL not set, using default"
                export SOURCEGRAPH_URL="https://sourcegraph.sourcegraph.com"
            fi
            ;;
        *)
            log_error "Unknown agent: $AGENT"
            exit 1
            ;;
    esac
    
    log_info "✓ Environment validated"
}

# ============================================================================
# Agent Selection & Import Path
# ============================================================================

get_agent_import_path() {
     local agent=$1
     case "$agent" in
         claude-baseline)
             echo "agents:BaselineClaudeCodeAgent"
             ;;
         claude-mcp)
             echo "agents:ClaudeCodeSourcegraphMCPAgent"
             ;;
         *)
             log_error "Unknown agent: $agent"
             exit 1
             ;;
     esac
 }

# ============================================================================
# Benchmark Execution
# ============================================================================

run_benchmark() {
    local benchmark=$1
    local agent=$2
    local n_tasks=$3
    local n_concurrent=$4
    
    log_info "Starting benchmark: $benchmark with agent: $agent"
    log_info "  Tasks: $n_tasks"
    log_info "  Concurrent: $n_concurrent"
    
    # Create timestamped job directory
    local run_timestamp=$(date +%Y%m%d-%H%M%S)
    local run_jobs_dir="${JOBS_DIR}/${agent}-${benchmark}-${run_timestamp}"
    mkdir -p "$run_jobs_dir"
    
    log_info "Job output directory: $run_jobs_dir"
    
    # Get agent import path
    local agent_import_path=$(get_agent_import_path "$agent")
    
    # Build Harbor command
    local harbor_cmd=(
        "harbor" "run"
        "-d" "${benchmark}@2.0"
        "--agent-import-path" "$agent_import_path"
        "--jobs-dir" "$run_jobs_dir"
        "-n" "$n_tasks"
        "--n-concurrent" "$n_concurrent"
    )
    
    # Add task filter if provided
    if [ -n "$TASK_FILTER" ]; then
        harbor_cmd+=("--task-filter" "$TASK_FILTER")
    fi
    
    log_info "Executing Harbor command:"
    log_info "${harbor_cmd[@]}"
    echo ""
    
    # Execute Harbor command
    "${harbor_cmd[@]}"
    
    log_info "✓ Benchmark complete!"
    echo "Results: $run_jobs_dir"
}

# ============================================================================
# Result Collection & Comparison
# ============================================================================

collect_results() {
    local baseline_dir=$1
    local treatment_dir=$2
    
    if [ -z "$baseline_dir" ] || [ -z "$treatment_dir" ]; then
        log_error "Must provide baseline and treatment directories"
        exit 1
    fi
    
    log_info "Collecting and comparing results..."
    log_info "  Baseline:  $baseline_dir"
    log_info "  Treatment: $treatment_dir"
    echo ""
    
    # Run comparison script
    python3 "$PROJECT_ROOT/runners/compare_results.py" "$baseline_dir" "$treatment_dir"
}

# ============================================================================
# Result Aggregation (for multiple benchmarks)
# ============================================================================

run_aggregator() {
    log_info "Running cross-benchmark aggregation..."
    python3 "$PROJECT_ROOT/runners/aggregator.py" \
        --runs "$JOBS_DIR" \
        --output "$JOBS_DIR/cross-benchmark-report.json"
}

# ============================================================================
# Main
# ============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --benchmark)
                BENCHMARK="$2"
                shift 2
                ;;
            --agent)
                AGENT="$2"
                shift 2
                ;;
            --tasks)
                N_TASKS="$2"
                shift 2
                ;;
            --concurrent)
                N_CONCURRENT="$2"
                shift 2
                ;;
            --task-filter)
                TASK_FILTER="$2"
                shift 2
                ;;
            --jobs-dir)
                JOBS_DIR="$2"
                shift 2
                ;;
            --collect-results)
                COLLECT_MODE=true
                shift
                # Remaining args are directories
                BASELINE_DIR="$1"
                TREATMENT_DIR="$2"
                shift 2
                ;;
            --help)
                print_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done
    
    # Check required tool is in PATH
    export PATH="$HOME/bin:$PATH"
    
    if [ "$COLLECT_MODE" = true ]; then
        # Collect and compare results mode
        collect_results "$BASELINE_DIR" "$TREATMENT_DIR"
    else
        # Normal benchmark execution mode
        validate_environment
        run_benchmark "$BENCHMARK" "$AGENT" "$N_TASKS" "$N_CONCURRENT"
    fi
}

# Run main function
main "$@"
