#!/usr/bin/env bash
# Lists the locked versions of a uv.lock, or the difference between two locks.
#
#   lock_versions.sh [LOCK]           "name version", sorted, one line per locked version
#   lock_versions.sh BEFORE AFTER     "< name version" only in BEFORE, "> name version" only in AFTER
#
# LOCK, BEFORE and AFTER are a path to a lock file or a git ref, read as
# <ref>:uv.lock. Without arguments: the working tree's lock at the repository
# root. To compare a ref with the lock that `uv lock` just wrote, give the path
# of the working tree's lock as AFTER:
#
#   lock_versions.sh origin/main uv.lock        # from the repository root
#
# A package the lock resolves differently per Python version (the lock's
# resolution-markers; uv calls each one a fork) appears once per locked
# version. The project itself (editable, no version in the lock) is not
# printed. The difference is computed with comm, not diff: it needs no
# temporary file. Exit status 1 when an argument is neither a file nor a ref
# whose tree has uv.lock; otherwise 0, whether or not the two locks differ.
set -u

check() {
  [ -f "$1" ] && return 0
  git rev-parse -q --verify "$1:uv.lock" >/dev/null 2>&1 && return 0
  echo "error: $1 is neither a lock file nor a ref whose tree has uv.lock" >&2
  exit 1
}

versions() {
  if [ -f "$1" ]; then cat "$1"; else git show "$1:uv.lock"; fi | awk -F'"' '
    /^\[/                  { inpkg = ($0 == "[[package]]"); name = "" }
    inpkg && /^name = /    { name = $2 }
    inpkg && /^version = / { if (name != "") print name " " $2 }
  ' | LC_ALL=C sort
}

if [ $# -ge 2 ]; then
  check "$1"
  check "$2"
  LC_ALL=C comm -3 <(versions "$1") <(versions "$2") \
    | awk -F'\t' '$1 == "" { print "> " $2; next } { print "< " $1 }'
  exit 0
fi

if [ $# -eq 1 ]; then
  SRC=$1
else
  TOP=$(git rev-parse --show-toplevel 2>/dev/null) || TOP=.
  SRC="$TOP/uv.lock"
fi
check "$SRC"
versions "$SRC"
