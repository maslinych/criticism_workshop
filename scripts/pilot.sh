#!/usr/bin/env bash
# Pilot run in sample mode (approval point 3): the analyst and the reviewer on the
# articles of corpus_sample/, each followed by its checks and report.
#
# Usage (from the project folder, with LITELLM_BASE_URL and LITELLM_API_KEY set):
#   scripts/pilot.sh            start a fresh pilot; earlier sample results are moved
#                               to data/annotation/sample-before-<date>/, not deleted
#   scripts/pilot.sh --resume   continue a pilot that stopped; nothing is moved
#
# It can run unattended: a stage that stops early (network trouble, too many
# articles too slow for the service) is started again after a pause, up to three
# times; finished work is never redone. Everything printed goes to the terminal and
# to logs/pilot-<date>.out. The reports are in reports/*-sample.md.

set -u
cd "$(dirname "$0")/.."

resume=no
case "${1:-}" in
  --resume) resume=yes ;;
  "") ;;
  *) echo "usage: scripts/pilot.sh [--resume]"; exit 2 ;;
esac

if [ -z "${LITELLM_BASE_URL:-}" ] || [ -z "${LITELLM_API_KEY:-}" ]; then
  echo "Set LITELLM_BASE_URL and LITELLM_API_KEY first (export them in this terminal)."
  exit 2
fi

pause=${PILOT_PAUSE:-600}   # seconds to wait before starting a stopped stage again
stamp=$(date +%Y%m%d-%H%M%S)
mkdir -p logs
out="logs/pilot-$stamp.out"
exec > >(tee -a "$out") 2>&1

say() { echo "$(date +%H:%M:%S) pilot: $*"; }

say "started; output also in $out"
say "code: commit $(git rev-parse --short HEAD) on branch $(git branch --show-current)"
if ! git diff --quiet HEAD -- config.yaml prompts/ src/; then
  say "WARNING: config.yaml, prompts/ or src/ have uncommitted changes; the run cannot be traced to a commit:"
  git status --short -- config.yaml prompts/ src/
fi

if [ "$resume" = no ] && [ -d data/annotation/sample ]; then
  keep="data/annotation/sample-before-$stamp"
  mv data/annotation/sample "$keep"
  say "earlier sample results moved to $keep"
fi

# Run one stage; if it stops early, wait and start it again (it continues where it stopped).
run_stage() {
  local try
  for try in 1 2 3; do
    say "uv run ncse $* --sample (try $try)"
    if uv run ncse "$@" --sample; then
      return 0
    fi
    if [ "$try" -lt 3 ]; then
      say "the stage stopped early; trying again in $((pause / 60)) minutes"
      sleep "$pause"
    fi
  done
  say "the stage still stops early after 3 tries; see the messages above"
  return 1
}

uv run ncse estimate --sample

status=0
run_stage analyse || status=1
uv run ncse check analyst --sample || status=1
run_stage review || status=1
uv run ncse check reviewer --sample || status=1

say "finished (status $status). Reports: reports/03-analyst-checks-sample.md, reports/04-review-checks-sample.md"
say "articles that failed can be tried again with: uv run ncse analyse --sample --retry-failed"
exit $status
