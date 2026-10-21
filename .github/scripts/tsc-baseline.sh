#!/usr/bin/env bash
# Type-check the vis package with tsc and fail when the errors outnumber the
# baseline.
#
# usage: tsc-baseline.sh MAX_ERRORS
#
#   MAX_ERRORS  ceiling for the "error TS" lines of
#               `tsc --noEmit -p src/frontend/packages/nowvis`
#
# The bundle is built by webpack and babel, which strip the types without
# checking them, so a type error never fails the build: this check is what
# keeps the count from growing. It fails when the count goes above the
# ceiling, and only notes when it goes below, so that the ceiling comes down
# in the same PR that removes errors. Run it after `npm ci` and the build of
# the bundle: the vis imports the other packages through their `lib/`, which
# only the build writes, and without it every such import is one more error
# (TS2307, "Cannot find module '@noworkflow/...'").
set -u

max_errors=$1
root=$(cd "$(dirname "$0")/../.." && pwd)
tsc="$root/src/frontend/node_modules/.bin/tsc"
summary=${GITHUB_STEP_SUMMARY:-/dev/stdout}

if [ ! -x "$tsc" ]; then
  echo "::error title=tsc baseline::$tsc not found; run npm ci in src/frontend first"
  exit 1
fi

# Paths in the output are relative to the repository root.
output=$(cd "$root" && "$tsc" --noEmit -p src/frontend/packages/nowvis 2>&1)
status=$?
errors=$(grep -E ': error TS[0-9]+:' <<<"$output" || true)
count=$(grep -c . <<<"$errors" || true)

problem=""
note=""
if [ "$status" -ne 0 ] && [ "$count" -eq 0 ]; then
  problem="tsc exited with $status without reporting a type error"
elif [ "$count" -gt "$max_errors" ]; then
  problem="$count type errors, above the baseline of $max_errors"
  if grep -q "error TS2307: Cannot find module '@noworkflow/" <<<"$errors"; then
    problem="$problem (TS2307 for @noworkflow/*: build the bundle first)"
  fi
elif [ "$count" -lt "$max_errors" ]; then
  note="$count type errors, below the baseline of $max_errors: lower the baseline to $count in this PR"
fi

{
  echo "### tsc (src/frontend/packages/nowvis)"
  echo
  echo "- type errors: $count (baseline $max_errors)"
  [ -n "$problem" ] && echo "- **failed:** $problem"
  [ -n "$note" ] && echo "- $note"
  if [ -n "$errors" ]; then
    echo
    echo '```'
    echo "$errors"
    echo '```'
  fi
} >>"$summary"

if [ -n "$problem" ]; then
  echo "$output"
  echo "::error title=tsc baseline::$problem"
  exit 1
fi
if [ -n "$note" ]; then
  echo "::notice title=tsc baseline::$note"
fi
