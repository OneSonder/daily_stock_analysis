#!/usr/bin/env bash
# Trigger GitHub Actions: daily_analysis.yml (workflow_dispatch).
#
# Prerequisites: gh CLI authenticated with workflow scope (gh auth login).
# Override repo when not in a clone: GH_REPO=owner/name ./scripts/github_dispatch_daily_analysis.sh ...
#
# Usage:
#   ./scripts/github_dispatch_daily_analysis.sh [--ref BRANCH] [--mode MODE] [--force-run] [--dry-run]
#
#   --mode   full | market-only | stocks-only   (default: full)
#   --ref    git branch for the workflow run (default: repo default branch)
#   --dry-run print gh command only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_github_dispatch_common.sh
source "$SCRIPT_DIR/_github_dispatch_common.sh"

REF=""
MODE="full"
FORCE_RUN="false"
DRY_RUN=0

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
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

# #region agent log
_github_debug_log "B" "github_dispatch_daily_analysis" "parsed_args" \
  "{\"ref\":\"${REF}\",\"mode\":\"${MODE}\",\"force_run\":\"${FORCE_RUN}\",\"dry_run\":${DRY_RUN}}"
# #endregion

case "$MODE" in
  full|market-only|stocks-only) ;;
  *)
    echo "Invalid --mode: $MODE (use full, market-only, or stocks-only)" >&2
    exit 1
    ;;
esac

if [[ "$DRY_RUN" -eq 0 ]] && ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install: https://cli.github.com/" >&2
  exit 1
fi

if [[ -z "$REF" ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    REF="DEFAULT_BRANCH"
  elif [[ -n "${GH_REPO:-}" ]]; then
    REF="$(gh -R "${GH_REPO}" repo view --json defaultBranchRef --jq '.defaultBranchRef.name')"
  else
    REF="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')"
  fi
fi

if [[ -n "${GH_REPO:-}" ]]; then
  gh_prefix=(gh -R "${GH_REPO}")
else
  gh_prefix=(gh)
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  print_dry_run_cmd "${gh_prefix[@]}" workflow run daily_analysis.yml \
    --ref "$REF" -f "mode=$MODE" -f "force_run=$FORCE_RUN"
  exit 0
fi

"${gh_prefix[@]}" workflow run daily_analysis.yml \
  --ref "$REF" -f "mode=$MODE" -f "force_run=$FORCE_RUN"

echo "Dispatched daily_analysis.yml on ref=$REF (mode=$MODE force_run=$FORCE_RUN)."
if [[ -n "${GH_REPO:-}" ]]; then
  echo "Watch runs: gh -R ${GH_REPO} run list --workflow=daily_analysis.yml"
  echo "Or:         gh -R ${GH_REPO} run watch"
else
  echo "Watch runs: gh run list --workflow=daily_analysis.yml"
  echo "Or:         gh run watch"
fi
