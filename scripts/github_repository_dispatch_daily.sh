#!/usr/bin/env bash
# Trigger repository_dispatch type run-daily-analysis → repository_dispatch_analysis.yml
# → delegates to daily_analysis.yml (same inputs as workflow_dispatch).
#
# Prerequisites: gh CLI authenticated (repo scope + contents for api; dispatch uses token permissions).
#
# Optional: jq for safe JSON. Without jq, only ASCII mode/ref values are supported (typical use).
#
# curl fallback (replace OWNER REPO TOKEN):
#   curl -L -X POST \
#     -H "Accept: application/vnd.github+json" \
#     -H "Authorization: Bearer TOKEN" \
#     https://api.github.com/repos/OWNER/REPO/dispatches \
#     -d '{"event_type":"run-daily-analysis","client_payload":{"ref":"main","mode":"full","force_run":false}}'
#
# Usage:
#   GH_REPO=owner/name ./scripts/github_repository_dispatch_daily.sh [--ref BRANCH] [--mode MODE] [--force-run] [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_github_dispatch_common.sh
source "$SCRIPT_DIR/_github_dispatch_common.sh"

REF=""
MODE="full"
FORCE_RUN="false"
DRY_RUN=0

usage() {
  sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      require_option_value "$@"
      REF="$2"
      shift 2
      ;;
    --mode)
      require_option_value "$@"
      MODE="$2"
      shift 2
      ;;
    --force-run)
      FORCE_RUN="true"
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage 1
      ;;
  esac
done

case "$MODE" in
  full|market-only|stocks-only) ;;
  *)
    echo "Invalid --mode: $MODE" >&2
    exit 1
    ;;
esac

if [[ "$DRY_RUN" -eq 0 ]] && ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install: https://cli.github.com/" >&2
  exit 1
fi

resolve_owner_repo() {
  if [[ -n "${GH_REPO:-}" ]]; then
    OWNER="${GH_REPO%%/*}"
    REPO="${GH_REPO#*/}"
    if [[ "$OWNER" == "$GH_REPO" || -z "$OWNER" || -z "$REPO" ]]; then
      echo "GH_REPO must be owner/name, got: $GH_REPO" >&2
      exit 1
    fi
    return
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    OWNER="<owner>"
    REPO="<repo>"
    return
  fi
  local full
  full="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
  OWNER="${full%%/*}"
  REPO="${full#*/}"
}

build_body() {
  local force_json="false"
  [[ "$FORCE_RUN" == "true" ]] && force_json="true"

  if command -v jq >/dev/null 2>&1; then
    jq -nc \
      --arg et "run-daily-analysis" \
      --arg mode "$MODE" \
      --argjson force_run "$force_json" \
      --arg ref "$REF" \
      '{
        event_type: $et,
        client_payload: (
          {mode: $mode, force_run: $force_run}
          + (if ($ref | length) > 0 then {ref: $ref} else {} end)
        )
      }'
    return
  fi

  local force_lc="false"
  [[ "$FORCE_RUN" == "true" ]] && force_lc="true"
  if [[ "$REF" =~ [^a-zA-Z0-9._/-] || "$MODE" =~ [^a-zA-Z0-9._/-] ]]; then
    echo "Install jq to use arbitrary --ref/--mode characters." >&2
    exit 1
  fi
  if [[ -n "$REF" ]]; then
    printf '{"event_type":"run-daily-analysis","client_payload":{"ref":"%s","mode":"%s","force_run":%s}}' \
      "$REF" "$MODE" "$force_lc"
  else
    printf '{"event_type":"run-daily-analysis","client_payload":{"mode":"%s","force_run":%s}}' \
      "$MODE" "$force_lc"
  fi
}

resolve_owner_repo

BODY="$(build_body)"

# #region agent log
_github_debug_log "C" "github_repository_dispatch_daily" "dispatch_body" \
  "{\"owner\":\"${OWNER}\",\"repo\":\"${REPO}\",\"body_chars\":${#BODY}}"
# #endregion

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "POST /repos/$OWNER/$REPO/dispatches"
  echo "$BODY"
  exit 0
fi

gh api \
  --method POST \
  "repos/$OWNER/$REPO/dispatches" \
  --input - <<<"$BODY"

echo "Posted repository_dispatch run-daily-analysis to $OWNER/$REPO (mode=$MODE force_run=$FORCE_RUN)."
if [[ -n "${GH_REPO:-}" ]]; then
  echo "Relay workflow: gh -R ${GH_REPO} run list --workflow=repository_dispatch_analysis.yml"
else
  echo "Relay workflow: gh run list --workflow=repository_dispatch_analysis.yml"
fi
