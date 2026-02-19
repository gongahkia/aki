#!/usr/bin/env bash
# jikai_debug.sh — tail/filter the jikai tui log for debugging
set -euo pipefail

LOG="${JIKAI_LOG:-$(dirname "$0")/../logs/tui.log}"
MODE="${1:-tail}"
LINES="${2:-50}"
FILTER="${3:-}"

RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
DIM='\033[2m'; RESET='\033[0m'; BOLD='\033[1m'

_colorize() {
    while IFS= read -r line; do
        case "$line" in
            *ERROR*|*"✗"*|*FAIL*)  printf "${RED}%s${RESET}\n" "$line" ;;
            *WARN*|*"⚠"*)          printf "${YELLOW}%s${RESET}\n" "$line" ;;
            *GENERATE*|*GEN*)      printf "${CYAN}%s${RESET}\n" "$line" ;;
            *session*)             printf "${BOLD}%s${RESET}\n" "$line" ;;
            *)                     printf "${DIM}%s${RESET}\n" "$line" ;;
        esac
    done
}

_usage() {
    cat << EOF
usage: jikai_debug.sh [mode] [lines] [filter]

modes:
  tail     live tail of log (default)
  last N   show last N lines (default: 50)
  errors   show only ERROR lines
  session  show current/last session only
  grep STR grep log for string

env:
  JIKAI_LOG  override log path (default: logs/tui.log)

examples:
  ./scripts/jikai_debug.sh tail
  ./scripts/jikai_debug.sh last 100
  ./scripts/jikai_debug.sh errors
  ./scripts/jikai_debug.sh grep GENERATE
  ./scripts/jikai_debug.sh session
EOF
    exit 0
}

[[ ! -f "$LOG" ]] && { echo "log not found: $LOG"; exit 1; }

case "$MODE" in
    help|-h|--help) _usage ;;
    tail)
        echo -e "${BOLD}=== live tail: $LOG ===${RESET}"
        tail -f "$LOG" | _colorize ;;
    last)
        echo -e "${BOLD}=== last $LINES lines ===${RESET}"
        tail -n "$LINES" "$LOG" | _colorize ;;
    errors)
        echo -e "${BOLD}=== errors/failures ===${RESET}"
        grep -iE 'error|fail|exception|traceback' "$LOG" | _colorize ;;
    session)
        echo -e "${BOLD}=== current/last session ===${RESET}"
        tac "$LOG" | awk '/=== TUI session (started|ended) ===/{print; if (found) exit; found=1; next} found{print}' | tac | _colorize ;;
    grep)
        [[ -z "$FILTER" ]] && { echo "provide filter string as 3rd arg"; exit 1; }
        echo -e "${BOLD}=== grep: $FILTER ===${RESET}"
        grep -i "$FILTER" "$LOG" | _colorize ;;
    *)
        echo "unknown mode: $MODE"; _usage ;;
esac
