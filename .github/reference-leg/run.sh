#!/usr/bin/env bash
# Run the test suite on the CI reference leg from any machine with Docker
# (on macOS, colima or Docker Desktop; on Apple silicon the image runs under
# Rosetta).
#
# usage: .github/reference-leg/run.sh [pytest arguments]
#
#   GOLDEN=overwrite .github/reference-leg/run.sh -m golden   # rewrite goldens
#   GOLDEN=require .github/reference-leg/run.sh               # what CI runs
#   PLATFORM=linux/arm64 .github/reference-leg/run.sh -k strace
#                                   # the host's architecture (Apple silicon)
#
# The Python version is the reference leg's in .github/workflows/ci.yml. The
# checkout is mounted at /work and the container runs as the calling user,
# so the goldens it writes belong to that user. The venv and uv's cache live
# outside the checkout, under ~/.cache/noworkflow-reference/, and survive
# between runs; `.venv` of the host is never touched. PYTHONPYCACHEPREFIX
# keeps the host's __pycache__ (compiled with host paths) out of the run.
# The venv has the `demo` extra (as the reference leg of CI) and the `paper`
# group, and the image has SWI-Prolog for the paper's query, Graphviz for
# the tests that run `dot` and strace for those of `--external-tracer
# strace` (#206), as the legs of CI; the container gets SYS_PTRACE, and
# NOW_STRACE passes through. Under Rosetta (Apple silicon) strace exits
# with an empty log, the backend falls back to argv and those tests skip
# (`NOW_STRACE=require` fails them): they run on an x86_64 host, or with
# PLATFORM set to the host's architecture, which builds the image and
# keeps the venv apart for it; goldens are recorded on linux/amd64 only.
# `-m paper` runs
# without the extra instead, in the environment of the `paper-example` job,
# which has no matplotlib. The tests of the paper's running
# example run here, and their goldens are recorded here like the others.
# The tests of the vis in a browser skip here: the image has no Chrome and
# the venv no `browser` group (the vis-browser job of ci.yml runs them).
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
python=$(sed -n 's/.*python: "\([0-9.]*\)".*reference: true.*/\1/p' \
  "$root/.github/workflows/ci.yml")
if [ -z "$python" ]; then
  echo "no 'reference: true' leg in .github/workflows/ci.yml" >&2
  exit 1
fi
platform="${PLATFORM:-linux/amd64}"
tag="$python"
[ "$platform" = "linux/amd64" ] || tag="$python-${platform##*/}"
image="noworkflow-reference:$tag"
cache="${XDG_CACHE_HOME:-$HOME/.cache}/noworkflow-reference/$tag"
mkdir -p "$cache/venv" "$cache/uv"

extra="--extra demo"
prev=""
for arg in "$@"; do
  [ "$prev" = "-m" ] && [ "$arg" = "paper" ] && extra=""
  prev=$arg
done

docker build --quiet --platform "$platform" --build-arg PLATFORM="$platform" \
  --build-arg PYTHON="$python" -t "$image" "$here" >/dev/null
docker run --rm --platform "$platform" \
  --user "$(id -u):$(id -g)" \
  -e GOLDEN="${GOLDEN:-}" \
  -e EXTRA="$extra" \
  -e NOW_LEAK_CHECK="${NOW_LEAK_CHECK:-fail}" \
  -e NOW_STRACE="${NOW_STRACE:-}" \
  --cap-add SYS_PTRACE \
  -v "$root":/work \
  -v "$cache/venv":/opt/venv \
  -v "$cache/uv":/opt/uv-cache \
  "$image" \
  bash -c 'uv sync --locked $EXTRA --group paper --python "$PYTHON" --quiet \
    && uv run --no-sync pytest -p no:cacheprovider "$@"' bash "$@"
