#!/usr/bin/env bash
# Trigger Docker image publish: docker-publish.yml (workflow_dispatch).
#
# Input matches .github/workflows/docker-publish.yml:
#   release_tag — required semver tag present on remote, e.g. v3.0.6
#
# Prerequisites: gh auth with workflow scope; GH_REPO if not in repo clone.
#
# Usage:
#   ./scripts/github_dispatch_docker_publish.sh --tag v3.0.6 [--ref BRANCH] [--dry-run]
#
#   --ref  branch for the workflow run file (default: repo default branch); workflow checks out release_tag.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_github_dispatch_common.sh
source "$SCRIPT_DIR/_github_dispatch_common.sh"

TAG=""
REF=""
DRY_RUN=0

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      require_option_value "$@"
      TAG="$2"
      shift 2
      ;;
    --ref)
      require_option_value "$@"
      REF="$2"
      shift 2
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

if [[ -z "$TAG" ]]; then
  echo "Required: --tag vX.Y.Z (semver release tag)" >&2
  usage 1
fi

if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Warning: tag '$TAG' does not match v*.*.* pattern expected by docker-publish.yml" >&2
fi

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
  print_dry_run_cmd "${gh_prefix[@]}" workflow run docker-publish.yml \
    --ref "$REF" -f "release_tag=$TAG"
  exit 0
fi

"${gh_prefix[@]}" workflow run docker-publish.yml \
  --ref "$REF" -f "release_tag=$TAG"

echo "Dispatched docker-publish.yml ref=$REF release_tag=$TAG."
if [[ -n "${GH_REPO:-}" ]]; then
  echo "Watch: gh -R ${GH_REPO} run list --workflow=docker-publish.yml"
else
  echo "Watch: gh run list --workflow=docker-publish.yml"
fi
