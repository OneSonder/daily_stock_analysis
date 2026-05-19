# Shared helpers for github_* dispatch scripts (source only).
GITHUB_DEBUG_LOG="${GITHUB_DEBUG_LOG:-/Users/antonychoi/Downloads/Trae/.cursor/debug-389a47.log}"

_github_debug_log() {
  # #region agent log
  local hypothesis_id="$1" location="$2" message="$3" data="${4:-{}}"
  printf '%s\n' \
    "{\"sessionId\":\"389a47\",\"hypothesisId\":\"${hypothesis_id}\",\"location\":\"${location}\",\"message\":\"${message}\",\"data\":${data},\"timestamp\":$(($(date +%s)*1000))}" \
    >>"$GITHUB_DEBUG_LOG" 2>/dev/null || true
  # #endregion
}

# Require a non-empty value that is not another flag (fixes silent exit from `shift 2` under set -e).
require_option_value() {
  local flag="$1"
  if [[ $# -lt 2 || -z "${2:-}" || "${2:0:2}" == -- ]]; then
    _github_debug_log "A" "require_option_value" "missing_flag_value" "{\"flag\":\"${flag}\"}"
    echo "Error: ${flag} requires a value" >&2
    exit 1
  fi
}

print_dry_run_cmd() {
  printf '%s\n' "$*"
}
