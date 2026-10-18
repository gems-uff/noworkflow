#!/usr/bin/env bash
# Checks a merge commit: what a human typed while resolving it, what either
# side may have lost, and the files of this project that git merges as text
# although no tool would produce the result (uv.lock, bundle.js, the test
# floor). Usage, from anywhere inside the repository:
#
#   "$(git rev-parse --show-toplevel)"/.claude/skills/merge-downstream/check_merge.sh [merge] [upstream] [upstream-parent]
#
# merge            default HEAD; a SHA, branch or tag of a two-parent merge
# upstream         default origin/main
# upstream-parent  which parent is the upstream side. Git's rule: parent 1 is
#                  whatever was checked out when the merge was made. 2
#                  (default) for a merge made on the branch (`git merge
#                  origin/main`, `git pull`); 1 for a merge made on main (a
#                  fork PR merged with a merge commit, and the merges of the
#                  history before the fast-forward rule).
#
# Every section prints what it measured; ATTENTION marks what a human has to
# read. The exit status carries no verdict: 0 after a report, whatever it
# says, and 1 when the arguments are refused. `uv lock --check` runs only when
# the merge is HEAD and pyproject.toml and uv.lock are unmodified in the tree.
# Needs git 2.38 or later (merge-tree --write-tree).
set -u

MERGE="${1:-HEAD}"
UPSTREAM="${2:-origin/main}"
UPSTREAM_PARENT="${3:-2}"

HERE=$(cd "$(dirname "$0")" && pwd)
LOCK_VERSIONS="$HERE/../dependencies/lock_versions.sh"

TOP=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "error: not inside a git repository" >&2; exit 1; }
# Every pathspec below is relative to the repository root.
cd "$TOP" || exit 1

if ! MERGE_C=$(git rev-parse -q --verify "$MERGE^{commit}"); then
  echo "error: $MERGE is not a commit" >&2; exit 1
fi
if ! git rev-parse -q --verify "$MERGE_C^2" >/dev/null; then
  echo "error: $MERGE is not a merge commit" >&2; exit 1
fi
if git rev-parse -q --verify "$MERGE_C^3" >/dev/null; then
  echo "error: $MERGE has more than two parents (an octopus merge); these checks assume two sides" >&2; exit 1
fi
if ! UPSTREAM_C=$(git rev-parse -q --verify "$UPSTREAM^{commit}"); then
  echo "error: $UPSTREAM is not a commit (run git fetch origin, or name the ref)" >&2; exit 1
fi
case "$UPSTREAM_PARENT" in
  1|2) ;;
  *) echo "error: upstream-parent must be 1 or 2" >&2; exit 1 ;;
esac

P1=$(git rev-parse "$MERGE_C^1")
P2=$(git rev-parse "$MERGE_C^2")
if [ "$UPSTREAM_PARENT" = 2 ]; then
  UP=$P2; BR=$P1
else
  UP=$P1; BR=$P2
fi
OTHER=$((3 - UPSTREAM_PARENT))
BASE=$(git merge-base "$P1" "$P2") || { echo "error: the two parents have no common ancestor" >&2; exit 1; }
MERGE_TREE=$(git rev-parse "$MERGE_C^{tree}")

short() { git rev-parse --short "$1"; }
# The files a side changed since the merge base of the two parents.
touched() { git diff --name-only "$BASE" "$1" -- "${@:2}"; }
remote_refs_at() { git branch -r --points-at "$1" 2>/dev/null | sed 's/^ *//' | tr '\n' ' ' | sed 's/ $//'; }

echo "### commit"
git log -1 --format='%h  %an  %ad%n%s' --date=iso "$MERGE_C"
for n in 1 2; do
  if [ "$n" = 1 ]; then P=$P1; else P=$P2; fi
  R=$(remote_refs_at "$P")
  echo "  parent $n: $(git log -1 --format='%h %s' "$P")${R:+   (remote refs here: $R)}"
done
echo "  upstream side: parent $UPSTREAM_PARENT ($(short "$UP")); branch side: parent $OTHER ($(short "$BR"))"
echo "  merge base of the parents: $(git log -1 --format='%h %s' "$BASE")"
UP_EMPTY=0
if [ "$BASE" = "$UP" ]; then
  UP_EMPTY=1
  echo "  the upstream side brought nothing: a --no-ff merge of the branch side."
  echo "  The questions about the upstream side below do not apply; the others do."
elif [ "$BASE" = "$BR" ]; then
  echo "  the branch side brought nothing: a fast-forward recorded as a merge --"
  echo "  or the sides are swapped (a merge made on main): rerun with $OTHER as the third argument."
fi
# A swapped choice shows on a merge that upstream does not contain yet: the
# branch side is already in upstream and the upstream side is not.
if ! git merge-base --is-ancestor "$MERGE_C" "$UPSTREAM_C" \
  && git merge-base --is-ancestor "$BR" "$UPSTREAM_C" \
  && ! git merge-base --is-ancestor "$UP" "$UPSTREAM_C"; then
  echo "  ATTENTION  parent $OTHER is in $UPSTREAM and parent $UPSTREAM_PARENT is not: the upstream side is probably parent $OTHER (third argument $OTHER)"
fi

echo
echo "### is the upstream parent the top of $UPSTREAM?"
if [ "$UP" = "$UPSTREAM_C" ]; then
  echo "  yes, it is the current top"
else
  MISSING=$(git rev-list --count "$MERGE_C".."$UPSTREAM_C")
  # Of the commits of upstream that the merge does not have, the ones
  # committed before the merge bound the lag it was made with from above: a
  # branch fast-forwarded into upstream after the merge brings commits dated
  # before it. The reflog is exact, as far back as this clone saw the ref.
  BEFORE=$(git rev-list --count --before="$(git log -1 --format=%cI "$MERGE_C")" "$MERGE_C".."$UPSTREAM_C")
  echo "  no. $UPSTREAM is at $(short "$UPSTREAM_C"); $MISSING commit(s) of it are not in the merge,"
  echo "  $BEFORE of them committed before the merge (an upper bound on the lag it was made with)."
  echo "  'git reflog show --date=iso $UPSTREAM' says what the ref pointed at, as far back as this clone saw it move."
fi

echo
echo "### was there manual intervention in the resolution?"
# Reconstruct the automatic merge and compare it with the recorded tree. What
# is left in the diff was typed by someone -- a conflict resolution or not.
AUTO_OUT=$(git -c core.quotePath=false merge-tree --write-tree --name-only "$P1" "$P2" 2>/dev/null)
AUTO_RC=$?
AUTO=$(printf '%s\n' "$AUTO_OUT" | head -1)
TYPED=""
CONFLICTED=""
if [ -z "$AUTO" ] || [ "$AUTO_RC" -gt 1 ]; then
  echo "  could not reconstruct it (git merge-tree --write-tree needs git 2.38 or later)"
  AUTO=""
else
  # With conflicts, the lines after the tree name the conflicted files, up to
  # a blank line.
  [ "$AUTO_RC" = 1 ] && CONFLICTED=$(printf '%s\n' "$AUTO_OUT" | sed -n '2,/^$/p' | sed '/^$/d')
  if [ "$AUTO" = "$MERGE_TREE" ]; then
    echo "  no: the recorded tree is identical to the automatic merge"
  else
    TYPED=$(git -c core.quotePath=false diff --name-only --no-renames "$AUTO" "$MERGE_TREE")
    echo "  yes, in these files:"
    git -c core.quotePath=false diff --numstat --no-renames "$AUTO" "$MERGE_TREE" | sed 's/^/    /'
    echo "  (read it: git diff $AUTO $MERGE_TREE -- <file>)"
  fi
  if [ -n "$CONFLICTED" ]; then
    echo "  the two parents conflict in:"
    printf '%s\n' "$CONFLICTED" | sed 's/^/    /'
    UNTYPED=$(printf '%s\n' "$CONFLICTED" | while IFS= read -r f; do
      printf '%s\n' "$TYPED" | grep -qxF -- "$f" || printf '%s\n' "$f"
    done)
    if [ -n "$UNTYPED" ]; then
      echo "  of those, these equal the reconstruction: a binary or modify/delete conflict has no markers, the"
      echo "  reconstruction already holds one side's version, and the resolution kept it:"
      printf '%s\n' "$UNTYPED" | sed 's/^/    /'
    fi
    # Markers left in a recorded file. The reconstruction labels them with the
    # parents' SHAs and git merge with HEAD and the ref, so the two trees never
    # compare equal: the markers are found by reading the file.
    CONF_ARR=()
    while IFS= read -r f; do [ -n "$f" ] && CONF_ARR+=("$f"); done <<<"$CONFLICTED"
    MARKERS=$(git -c core.quotePath=false grep -l -E '^(<<<<<<<|>>>>>>>)( |$)' "$MERGE_C" -- "${CONF_ARR[@]}" 2>/dev/null \
      | sed "s|^$MERGE_C:||")
    if [ -n "$MARKERS" ]; then
      while IFS= read -r f; do echo "  ATTENTION  $f -- conflict markers were committed"; done <<<"$MARKERS"
    fi
  fi
fi

echo
echo "### does the merge contain everything that is in $UPSTREAM?"
if git merge-base --is-ancestor "$UPSTREAM_C" "$MERGE_C"; then
  echo "  yes"
elif git merge-base --is-ancestor "$MERGE_C" "$UPSTREAM_C"; then
  echo "  the merge is already in $UPSTREAM; $(git rev-list --count "$MERGE_C".."$UPSTREAM_C") commits came after it (lag, not loss)"
else
  echo "  NO -- $(git rev-list --count "$MERGE_C".."$UPSTREAM_C") commits of $UPSTREAM are missing"
fi

echo
echo "### could something of either side have been discarded?"
# Content is lost by hand: a file git merged by itself kept both sides'
# changes. The candidates are the files typed above, the files that
# conflicted, and the names those files had before a rename on either side.
# For each candidate, the difference from a parent to the merge is suspect
# when that parent's side touched the file since the merge base: its added
# lines removed, or its removed lines (or a deleted file) brought back. Flags:
#   --no-renames          a renamed file shows as its old and its new path
#   core.quotePath=false  non-ASCII paths come out raw, not C-quoted
# numstat prints "-" for a binary file: it changed, with no line count.
CANDIDATES=$(printf '%s\n' "$TYPED" "$CONFLICTED" | sed '/^$/d')
if [ -n "$CANDIDATES" ]; then
  RENAMES=$(for S in "$UP" "$BR"; do git -c core.quotePath=false diff --name-status -M "$BASE" "$S"; done \
    | awk -F'\t' '$1 ~ /^R/ {print $3 "\t" $2}')
  OLD_NAMES=$(printf '%s\n' "$RENAMES" | while IFS=$'\t' read -r new old; do
    [ -n "$new" ] && printf '%s\n' "$CANDIDATES" | grep -qxF -- "$new" && printf '%s\n' "$old"
  done)
  CANDIDATES=$(printf '%s\n' "$CANDIDATES" "$OLD_NAMES" | sed '/^$/d' | LC_ALL=C sort -u)
fi
if [ -z "$AUTO" ]; then
  echo "  (not measured: there is no automatic merge to compare with)"
elif [ -z "$CANDIDATES" ]; then
  echo "  nothing was typed by hand and nothing conflicted, so nothing was discarded by hand"
else
  for side in upstream branch; do
    if [ "$side" = upstream ]; then P=$UP; else P=$BR; fi
    if [ "$side" = upstream ] && [ "$UP_EMPTY" = 1 ]; then continue; fi
    echo "  relative to the $side side ($(short "$P")):"
    FOUND=0
    while IFS=$'\t' read -r added removed f; do
      [ "$added$removed" != "00" ] || continue
      printf '%s\n' "$CANDIDATES" | grep -qxF -- "$f" || continue
      FOUND=1
      N=$(git log --oneline "$BASE".."$P" -- "$f" | wc -l | tr -d ' ')
      if [ "$N" -gt 0 ]; then
        echo "    ATTENTION  $f -- differs from it, and the $side side touched it $N time(s) since the merge base"
      else
        echo "    ok         $f -- the $side side did not touch it; the difference is the other side's"
      fi
    done < <(git -c core.quotePath=false diff --numstat --no-renames "$P" "$MERGE_C")
    [ "$FOUND" = 0 ] && echo "    no candidate file differs from it"
  done
fi

echo
echo "### uv.lock"
LOCK_IN_MERGE=0
if ! git cat-file -e "$MERGE_C:uv.lock" 2>/dev/null; then
  echo "  the merge has no uv.lock: a tree older than the lock. Nothing goes through uv there."
else
  LOCK_IN_MERGE=1
  if ! git cat-file -e "$UP:uv.lock" 2>/dev/null; then
    echo "  the upstream side has no uv.lock; the lock came from the branch side"
  elif ! git cat-file -e "$BR:uv.lock" 2>/dev/null; then
    echo "  the branch side had no uv.lock: the merge brought it. uv sync --locked puts .venv on it."
  elif git diff --quiet "$UP" "$MERGE_C" -- uv.lock; then
    echo "  identical to the upstream side's"
  else
    echo "  differs from the upstream side's ($(git diff --numstat "$UP" "$MERGE_C" -- uv.lock | awk '{print $1"+/"$2"-"}'))"
    if [ -x "$LOCK_VERSIONS" ]; then
      CHANGED=$("$LOCK_VERSIONS" "$UP" "$MERGE_C" 2>&1)
      if [ -z "$CHANGED" ]; then
        echo "  no locked version differs: the difference is in hashes, markers or dependency lists"
      else
        echo "  locked versions that differ (< upstream side, > merge; one line per locked version):"
        printf '%s\n' "$CHANGED" | sed 's/^/    /'
        echo "  relative to upstream a healthy catch-up merge only adds (>); a changed version of a package both sides had needs an explanation"
      fi
    else
      echo "  ($LOCK_VERSIONS not found; compare the locked versions by hand)"
    fi
  fi
  # The versions a side moved to since the merge base that the merge no
  # longer has: taking one side's lock and running uv lock keeps that side's
  # versions, and the other side's own moves disappear without a conflict.
  if [ -x "$LOCK_VERSIONS" ] && git cat-file -e "$BASE:uv.lock" 2>/dev/null; then
    for side in upstream branch; do
      if [ "$side" = upstream ]; then P=$UP; else P=$BR; fi
      git cat-file -e "$P:uv.lock" 2>/dev/null || continue
      DROPPED=$(LC_ALL=C comm -12 \
        <("$LOCK_VERSIONS" "$BASE" "$P" | sed -n 's/^> //p') \
        <("$LOCK_VERSIONS" "$P" "$MERGE_C" | sed -n 's/^< //p'))
      if [ -n "$DROPPED" ]; then
        echo "  ATTENTION  versions the $side side moved to that the merge does not have:"
        printf '%s\n' "$DROPPED" | sed 's/^/    /'
      fi
    done
  fi
fi
if [ -n "$(touched "$UP" pyproject.toml)" ] && [ -n "$(touched "$BR" pyproject.toml)" ]; then
  echo "  ATTENTION  pyproject.toml changed on both sides since the merge base: the merged lock may match neither"
fi
if [ "$LOCK_IN_MERGE" = 1 ]; then
  if [ "$(git rev-parse HEAD)" != "$MERGE_C" ] || [ -n "$(git status --porcelain -- pyproject.toml uv.lock)" ]; then
    echo "  (uv lock --check not run: the merge is not HEAD, or pyproject.toml/uv.lock are modified in the tree)"
  elif ! command -v uv >/dev/null 2>&1; then
    echo "  (uv lock --check not run: uv is not on PATH)"
  else
    CHECK=$(uv lock --check 2>&1)
    RC=$?
    case $RC in
      0) echo "  uv lock --check: ok (consistent with pyproject.toml; not proof that it is the lock you wanted)" ;;
      1) echo "  ATTENTION  uv lock --check: the lock is stale. uv lock (never delete the lock first), then uv sync --locked"
         printf '%s\n' "$CHECK" | tail -2 | sed 's/^/    /' ;;
      *) echo "  uv lock --check could not run (exit $RC), so nothing was measured:"
         printf '%s\n' "$CHECK" | tail -3 | sed 's/^/    /' ;;
    esac
  fi
fi

echo
echo "### the bundle and the frontend sources"
BUNDLE=src/noworkflow/now/vis/static/dist/bundle.js
UP_SRC=$(touched "$UP" src/frontend); BR_SRC=$(touched "$BR" src/frontend)
UP_BUNDLE=$(touched "$UP" "$BUNDLE"); BR_BUNDLE=$(touched "$BR" "$BUNDLE")
state() { echo "sources $([ -n "$1" ] && echo changed || echo unchanged), bundle $([ -n "$2" ] && echo changed || echo unchanged)"; }
echo "  upstream side: $(state "$UP_SRC" "$UP_BUNDLE")"
echo "  branch side:   $(state "$BR_SRC" "$BR_BUNDLE")"
# "rebuild-vis": the skill of that name; its steps are those of the frontend
# job in .github/workflows/ci.yml.
if [ -n "$UP_BUNDLE" ] && [ -n "$BR_BUNDLE" ]; then
  echo "  ATTENTION  both sides changed the bundle: the merged bundle is a line-by-line mix of two builds. rebuild-vis."
elif [ -n "$UP_SRC$UP_BUNDLE" ] && [ -n "$BR_SRC$BR_BUNDLE" ]; then
  echo "  ATTENTION  both sides touched the frontend: the committed bundle does not contain both sides' sources. rebuild-vis."
elif { [ -n "$UP_SRC" ] && [ -z "$UP_BUNDLE" ]; } || { [ -n "$BR_SRC" ] && [ -z "$BR_BUNDLE" ]; }; then
  echo "  ATTENTION  a side changed the sources without rebuilding the bundle. rebuild-vis."
elif { [ -z "$UP_SRC" ] && [ -n "$UP_BUNDLE" ]; } || { [ -z "$BR_SRC" ] && [ -n "$BR_BUNDLE" ]; }; then
  echo "  ATTENTION  a side changed the bundle without changing the sources since the merge base: a stale bundle rebuilt, or an edit no build produces. rebuild-vis tells."
else
  echo "  nothing to rebuild: at most one side touched the frontend, with sources and bundle together"
fi

echo
echo "### new files under static/ brought by the branch side"
# Nothing under static/ is written by hand: dist/ is build output (the
# frontend job compares only bundle.js), external/ and font-awesome-*/ are
# vendored copies that no lock knows. A new file there is kept up to date by
# nobody. The hand-written parts of the vis are src/frontend and
# src/noworkflow/now/vis/templates.
NEW_STATIC=$(git -c core.quotePath=false diff --name-only --diff-filter=A "$UP" "$MERGE_C" -- src/noworkflow/now/vis/static \
  | grep -v -E 'dist/bundle\.js(\.map)?$' || true)
if [ -z "$NEW_STATIC" ]; then
  echo "  none"
else
  while IFS= read -r f; do echo "  ATTENTION  $f"; done <<<"$NEW_STATIC"
fi

echo
echo "### where a semantic conflict may live"
# Pairs of areas that pass separately and only fail together. The script
# says where to look; SKILL.md ("What git does not see") says what to read.
MODELS=src/noworkflow/now/persistence/models
READERS="src/noworkflow/now/cmd/cmd_export src/noworkflow/now/models src/noworkflow/resources/rules.pl src/noworkflow/now/vis src/frontend"
TRANSFORMER=src/noworkflow/now/collection/prov_definition
COLLECTOR=src/noworkflow/now/collection/prov_execution
# What moves a dependency is the lock; pyproject.toml only for a tree older
# than it (a [tool.*] edit moves nothing).
if git cat-file -e "$MERGE_C:uv.lock" 2>/dev/null; then DEPS=uv.lock; else DEPS=pyproject.toml; fi
# The code AGENTS.md lists under "Patches of third-party internals", plus the
# SQLAlchemy models and the pyposast users in prov_definition. Left out:
# py2module.py (never runs on Python 3) and the forty-odd `future` importers.
PATCHED="src/noworkflow/now/collection/prov_execution/execution.py src/noworkflow/now/persistence/content/safeopen.py src/noworkflow/now/ipython src/noworkflow/now/collection/prov_deployment/deployment.py src/noworkflow/now/utils/functions.py src/noworkflow/now/persistence/relational_database.py src/noworkflow/now/persistence/models src/noworkflow/now/collection/prov_definition"
FOUND=0
pair() {  # pair <label> <side A> <paths A> <side B> <paths B>
  local label=$1 a=$2 pa=$3 b=$4 pb=$5
  # shellcheck disable=SC2086
  if [ -n "$(touched "$a" $pa)" ] && [ -n "$(touched "$b" $pb)" ]; then
    echo "  ATTENTION  $label"
    FOUND=1
  fi
}
pair "models changed on the upstream side, their readers (exports, Prolog, vis) on the branch side" "$UP" "$MODELS" "$BR" "$READERS"
pair "models changed on the branch side, their readers (exports, Prolog, vis) on the upstream side" "$BR" "$MODELS" "$UP" "$READERS"
pair "the transformer changed on the upstream side, the collector on the branch side" "$UP" "$TRANSFORMER" "$BR" "$COLLECTOR"
pair "the transformer changed on the branch side, the collector on the upstream side" "$BR" "$TRANSFORMER" "$UP" "$COLLECTOR"
pair "dependencies moved on the upstream side, code written against a library's internals on the branch side" "$UP" "$DEPS" "$BR" "$PATCHED"
pair "dependencies moved on the branch side, code written against a library's internals on the upstream side" "$BR" "$DEPS" "$UP" "$PATCHED"
UP_T=$(touched "$UP" src/noworkflow/tests/__init__.py)
BR_T=$(touched "$BR" src/noworkflow/tests/__init__.py)
if [ -n "$UP_T" ] && [ -n "$BR_T" ]; then
  echo "  ATTENTION  src/noworkflow/tests/__init__.py changed on both sides: the two runners may disagree after the merge"
  FOUND=1
elif [ -n "$UP_T$BR_T" ]; then
  echo "  src/noworkflow/tests/__init__.py changed on one side: the parity of the two runners is part of the closing"
fi
[ "$FOUND" = 0 ] && echo "  none of the known pairs; the suite after the merge is still the measurement"

echo
echo "### the test floor (min-tests)"
# One floor per matrix leg, keyed by os and python. Both sides raising a leg
# by their own delta conflicts on the same line, and the resolution keeps one
# of the two numbers: whichever it keeps, the floor ends below the count. A
# hunk resolved with one side can also leave some legs at the old floor. The
# right number is the count of the suite after the merge.
legs() {  # "os,python floor" for each leg of a workflow at a commit
  git show "$1:$2" 2>/dev/null \
    | sed -nE 's/.*os: *([A-Za-z0-9._-]+).*python: *"?([0-9.]+)"?.*min-tests: *([0-9]+).*/\1,\2 \3/p'
}
leg_floor() { printf '%s\n' "$1" | awk -v k="$2" '$1 == k { print $2; exit }'; }
SEEN=0
RAISED_BOTH=0
for wf in .github/workflows/ci.yml .github/workflows/experimental.yml; do
  LM=$(legs "$MERGE_C" "$wf"); LU=$(legs "$UP" "$wf"); LB=$(legs "$BR" "$wf"); L0=$(legs "$BASE" "$wf")
  [ -z "$LM$LU$LB" ] && continue
  SEEN=1
  BAD=0
  for k in $(printf '%s\n' "$LM" "$LU" "$LB" | awk 'NF { print $1 }' | LC_ALL=C sort -u); do
    FM=$(leg_floor "$LM" "$k"); FU=$(leg_floor "$LU" "$k"); FB=$(leg_floor "$LB" "$k"); F0=$(leg_floor "$L0" "$k")
    if [ -z "$FM" ]; then
      # Missing from the merge: suspect when both sides have the leg, or when
      # a side added it; a side that removed it (a leg promoted) is not.
      if { [ -n "$FU" ] && [ -n "$FB" ]; } || { [ -z "$F0" ] && [ -n "$FU$FB" ]; }; then
        echo "  ATTENTION  $wf, leg $k: the merge has no min-tests (upstream side ${FU:-none}, branch side ${FB:-none})"
        BAD=1
      fi
      continue
    fi
    HIGHEST=$(printf '%s\n' "${FU:-0}" "${FB:-0}" | sort -n | tail -1)
    if [ -n "$F0" ] && [ -n "$FU" ] && [ -n "$FB" ] && [ "$FU" -gt "$F0" ] && [ "$FB" -gt "$F0" ]; then
      echo "  ATTENTION  $wf, leg $k: both sides raised it ($F0 -> $FU and $F0 -> $FB); the merge has $FM, the deltas add up to $((FU + FB - F0))"
      BAD=1
      RAISED_BOTH=1
    elif [ "$FM" -lt "$HIGHEST" ]; then
      echo "  ATTENTION  $wf, leg $k: the merge has $FM, a side had $HIGHEST"
      BAD=1
    fi
  done
  if [ "$BAD" = 0 ]; then
    echo "  $wf: no leg below either side (floors in the merge: $(printf '%s\n' "$LM" | awk 'NF { print $2 }' | sort -un | tr '\n' ' ' | sed 's/ $//'))"
  fi
done
if [ "$RAISED_BOTH" = 1 ]; then
  echo "  (the right floor is the count of the suite after the merge)"
fi
if [ "$SEEN" = 0 ]; then
  echo "  no workflow with min-tests in the merge: a tree older than the CI"
fi
exit 0
