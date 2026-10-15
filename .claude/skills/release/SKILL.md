---
name: release
description: Cuts a release of noWorkflow from an integrated main — the prerequisites, what ships and the version number, the bump of version.txt, a wheel and an sdist built and inspected from the exact commit, the dry run, the annotated tag, PyPI, the GitHub release, the milestone, and whether the Jupyter extension needs a release of its own. Use when the maintainer decides to release, or to rehearse a release without publishing anything.
---

# Releasing noWorkflow

The sequence that turns an integrated `main` into the version that `pip
install noworkflow` gets. Merge is not release: `review-pr` ends at
integration, and a release is a separate decision of the maintainer, taken
over whatever `main` holds at that moment.

**Who does what.** The agent prepares and verifies; every step that leaves
the machine is the maintainer's, or waits for the maintainer's explicit
go-ahead for that step: the version number, the commit of the bump, the tag
(only an admin creates tags, by the ruleset on tags), the push, the upload to
PyPI (with credentials that never enter the session), the GitHub release,
the writes to the milestone and the issues. **A published version cannot be
taken back:** PyPI never accepts the same file name twice, even after a
deletion, so a mistake found after the upload is a new version. uv, uvx,
`gh`, `git worktree add` and the queries to PyPI and python.org run outside
the sandbox.

## Prerequisites

**Before step 1:**

- **`main` synchronized**: `git fetch origin && git rev-list --left-right
  --count origin/main...main` prints `0 0`.
- **Clean tree: `git status --short` empty.** Anything uncommitted is shown
  to the maintainer before going ahead — what it is, and whether it enters
  this version or the next. That includes what the agent itself wrote during
  the cycle (a note in a skill, a probe script): having mentioned it when it
  was written does not count; the question belongs here, next to the decision
  to release.
- **The release's `Task` issue**, when there is one: each item of its
  checklist done or moved, by the maintainer's decision; what it says the
  version ships is compared with step 1.
- **No open PR in the milestone of the version**, if there is a milestone,
  and its open issues moved to the next one or explained — the maintainer's
  decision.
- **The range is python.org's on the day** (`AGENTS.md`, "Python versions"):

  ```bash
  curl -fsS https://peps.python.org/api/release-cycle.json | python3 -c 'import json, sys; print(*sorted(k for k, v in json.load(sys.stdin).items() if v["status"] == "end-of-life"))'
  ```

  against `requires-python`. A version in the range that reached end of life
  leaves in this release when it is a minor one, through the removal of
  `python-matrix`, committed before the bump; a patch release never removes
  one.
- **Someone who can upload.** Ask the maintainer which PyPI account will
  upload, and look for it among the project's roles:

  ```bash
  python3 -c "import xmlrpc.client; print(xmlrpc.client.ServerProxy('https://pypi.org/pypi').package_roles('noworkflow'))"
  ```

  (the project page answers a script with a JavaScript challenge). When it is
  not there, an owner adds it, or a trusted publisher — which needs a
  publishing workflow in the repository — **before** the tag: otherwise the
  release stops at the upload, with the tag already public.

**Before step 2: `golden-run` against the previous release**, when anything
under `src/noworkflow/now`, `src/noworkflow/patterns` or
`src/noworkflow/resources`, or a runtime dependency's range, changed since it
(`git diff --stat <previous tag>..main -- src/noworkflow/now
src/noworkflow/patterns src/noworkflow/resources pyproject.toml`). Its
store-compatibility check says whether stores of the previous release still
open and record, which is the maintainer's input for the number and goes into
the note.

**Before the tag (step 5), on the bump commit:**

- **CI green at that commit**: every blocking leg, `frontend`,
  `paper-example` and `checks` (the lock, the audits, and a build of the
  package that checks `version.txt` and `bundle.js` are in the wheel). That
  run is the suite on every supported Python; there is nothing to rerun
  locally for it. **Green does not cover two audits**: the npm audit is not a
  gate (read its log: `gh run view --job <checks job> --log | grep
  vulnerabilities`), and pip-audit ignores the advisories listed next to its
  step. Both describe what this release ships — `bundle.js` holds the npm
  side's code, and the runtime pins reach users' environments — so the
  maintainer decides whether the release waits and whether the note says so.
- **The experimental legs, run by hand on that commit** while their workflow
  is suspended, as its header asks before a release: `gh workflow run
  experimental.yml --ref main` once the bump is on `main`; the run's
  `headSha` must be the bump commit (`gh run list --workflow experimental.yml
  --limit 1 --json databaseId,headSha,conclusion`). Its failures are compared
  with the previous run of the same legs (`gh run view <id> --log-failed |
  grep FAILED`); anything new goes to the maintainer before going on.

## Steps

### 1. What ships

```bash
git describe --tags --abbrev=0                                       # the previous release's tag
curl -fsS https://pypi.org/pypi/noworkflow/json | python3 -c 'import json, sys; print(json.load(sys.stdin)["info"]["version"])'
git log --oneline <previous tag>..main
git log <previous tag>..main --format=%s | grep -oE '^Issue #[0-9]+' | sort -u
git log <previous tag>..main --format='%h %s' | grep -vE '^[0-9a-f]+ Issue #[0-9]+: '
```

`git describe --tags` also finds a lightweight tag. When its tag is not
PyPI's latest version, the previous release was published without a tag: its
commit is the oldest that wrote its number (`git log --reverse --format=%h
-S'<version>' -- '*resources/version.txt' | head -n 1`; the pattern also
finds the file at its older paths).

The subject prefixes are the issues the release delivers (`AGENTS.md`:
releases find their issues by the prefix). **Never take numbers from the
bodies**: a body cites known defects and later work, and an issue that a body
mentions is not delivered by that commit. The commits without the prefix are
the maintainer's direct work on `main` and the Dependabot updates (`Bump
<package> ... (#N)`); the note describes them in prose, the updates with
their PRs.

Each delivered issue is closed — integrated and finished, closed at
integration — or open with a comment that says what is left. One open
without that comment is settled with the maintainer before the release:
read later, "shipped" and "open" contradict each other. Each delivered issue
is also in the version's milestone, when there is one (`gh issue view <N>
--json milestone`); the maintainer moves the ones that are not, or a closed
issue reads later as shipped in another version.

### 2. The version number

The maintainer's. Propose one, with the reason, and wait:

- **patch** when only fixes ship;
- **at least minor** when a store written by the previous release no longer
  opens or no longer takes a new trial (`golden-run`), when a command or an
  option is removed or renamed or its exit status changes, when a feature
  ships, or when a Python version leaves the supported range (`AGENTS.md`:
  never in a patch release).

### 3. The bump

`src/noworkflow/resources/version.txt` is the only source of the version:
`pyproject.toml` reads it at build time and `now --version` prints it. The
file has no trailing newline:

```bash
printf '%s' '<version>' > src/noworkflow/resources/version.txt
git grep -n -F '<previous version>' -- ':!uv.lock' ':!src/noworkflow/now/vis/static' ':!src/frontend'
```

Each hit that names noWorkflow's version (the placeholder in
`.github/ISSUE_TEMPLATE/bug.yml`, a citation file) changes in the same
commit; a hit that only shares the digits (a pinned version of another
package, a recorded snapshot) stays. The tested Python versions in
`README.md` and the classifiers follow the CI matrix, not the release
(`python-matrix`): at a release, only check that they agree with the
blocking legs of `ci.yml`.

The commit is the maintainer's, directly on `main`: with the prefix of the
release's `Task` issue when there is one, or as the maintainer's commit
without an issue that `AGENTS.md` allows. CI runs on it, and that run is a
prerequisite of the tag.

### 4. Build from the commit, and inspect

Build in a clean worktree at the bump commit, never in the working checkout:
the package data (`resources/**`, `now/vis/static/**`, `now/vis/templates/**`)
ships whatever is on disk under those directories, tracked or not, a
`__pycache__` left by a run of the demo included.

```bash
git worktree add --detach <outside>/nw-release <bump commit>
cd <outside>/nw-release && uv build
```

`uv build` builds the source distribution and then the wheel from it;
**never `uv build --wheel` alone**, which builds from the tree and packs
whatever an old `build/` directory holds. Two builds of the same commit are
not byte-identical: compare contents, never the hashes of the files.

**The wheel**, what `pip install` gets:

```bash
W=dist/noworkflow-<version>-py3-none-any.whl
unzip -Z1 "$W" | grep -cE '__pycache__|\.pyc$|/goldens/|/corpus/|\.noworkflow|\.last_trial'   # 0
unzip -Z1 "$W" | grep -v '\.dist-info/' | sed 's|^|src/|' | sort > <scratch>/wheel.txt
git ls-files src/noworkflow | sort | comm -23 <scratch>/wheel.txt -                         # nothing: every file is tracked
unzip -p "$W" noworkflow/resources/version.txt; echo                                        # the version
unzip -p "$W" noworkflow/now/vis/static/dist/bundle.js | shasum
git show HEAD:src/noworkflow/now/vis/static/dist/bundle.js | shasum                          # the same
unzip -p "$W" 'noworkflow-<version>.dist-info/METADATA' | sed -n '1,/^$/p'
uvx twine check --strict dist/*
```

- **`METADATA`**: the version, `Requires-Python`, the classifiers and the
  `Requires-Dist` lines as `pyproject.toml` declares them. What changed since
  the previous release is in `git diff <previous tag> -- pyproject.toml` (the
  `[project]` table is where `METADATA` comes from) and goes into the note.
  Compared with the previous release's wheel from PyPI (`unzip -Z1` of both,
  without the `.dist-info/` entries, which carry the version in their name,
  then `comm`), a file that disappeared is a regression to explain.
- **Home directories.** The builder's own home must be in no file (or only in
  `bundle.js.map`, when the tracked map was committed from the builder's own
  home):

  ```bash
  rm -rf <scratch>/wheel && unzip -q "$W" -d <scratch>/wheel && grep -rlF "$HOME" <scratch>/wheel
  grep -rhoE '/(Users|home)/[A-Za-z0-9_.-]+' <scratch>/wheel | sort | uniq -c
  ```

  The second lists the user names of every home path in the package. Test
  fixtures and doctests use invented ones, `bundle.js` carries the virtual
  home of Emscripten, and `bundle.js.map` the home of whoever built it last;
  any other name stops the release.
- **The sdist** is uploaded too. The same checks, written out for its layout
  (it also carries `PKG-INFO`, `setup.cfg` and the `egg-info`, which git does
  not track):

  ```bash
  S=dist/noworkflow-<version>.tar.gz
  tar -tzf "$S" | grep -cE '__pycache__|\.pyc$|/goldens/|/corpus/|\.noworkflow|\.last_trial'   # 0
  tar -tzf "$S" | grep -v '/$' | sed 's|^noworkflow-<version>/||' \
    | grep -vE '^(PKG-INFO|setup\.cfg|src/noworkflow\.egg-info/)' | sort > <scratch>/sdist.txt
  git ls-files | sort | comm -23 <scratch>/sdist.txt -                                       # nothing
  rm -rf <scratch>/sdist && mkdir -p <scratch>/sdist && tar -xzf "$S" -C <scratch>/sdist && grep -rlF "$HOME" <scratch>/sdist
  ```
- **The README is the PyPI page.** `twine check` passes relative links and
  images that PyPI cannot resolve. Render it and list them:

  ```bash
  uvx --from 'readme-renderer[md]' python -m readme_renderer README.md -o <scratch>/readme.html
  grep -oE '(src|href)="[^"]*"' <scratch>/readme.html | grep -vE '"(https?:|mailto:|#)'
  ```

  Each one renders broken on PyPI. Compare with the previous release's page;
  whether `README.md` is fixed before the bump is the maintainer's call.

**The working tree's `now -v` proves nothing about the wheel.** Run the wheel
itself on the newest and on the oldest supported Python (the reference leg's
Python and the floor of `requires-python`), each in a scratch directory of
its own so that each `show 1` is its own trial:

```bash
for v in <newest> <floor>; do
  mkdir -p <scratch>/py$v && cd <scratch>/py$v && printf 'print("hello")\n' > hello.py
  uvx --isolated --no-python-downloads --python $v --from <outside>/nw-release/$W now -v
  uvx --isolated --no-python-downloads --python $v --from <outside>/nw-release/$W now run hello.py   # then list and show 1
done
```

`--isolated` keeps an installed `noworkflow` tool out of the way; uv
reinstalls from a wheel whose file changed. Those scratch stores record this
machine's environment: never serve them. For the vis, install the wheel into
a venv of its own and serve a store of the test corpus with it, as
`rebuild-vis` ("Smoke") does:

```bash
uv venv --clear --no-python-downloads <scratch>/wheel-venv && uv pip install --python <scratch>/wheel-venv/bin/python <outside>/nw-release/$W
uv run --no-sync python .claude/skills/golden-run/read_store.py <scratch>/wheel-venv/bin/now <basetemp>/two_trials0 <scratch>/wheel-smoke --vis <port>
```

(from the checkout; `rebuild-vis` says where the store comes from).
`raw/vis/dist-bundle.js.txt` must hold the committed bundle's sha1.

Last, **the dry run of the upload**, before anything is public. It needs no
credentials:

```bash
uv publish --dry-run --check-url https://pypi.org/simple/ <outside>/nw-release/dist/noworkflow-<version>*
```

The verdict: exit 0, and no line `already exists, skipping` (that line means
this very file is already on PyPI). `Local file and index file do not match`
(exit 1) means the version is taken by other files: it needs a new number.
`Trusted publishing failed` is printed when there is no CI token, and is not
the verdict.

### 5. The tag

Annotated, never lightweight, with the version as its message, on the bump
commit; created and pushed by the maintainer:

```bash
git tag -a <version> -m "<version>" <bump commit>
git push origin <version>
```

**A published tag is never moved.** Before the upload, a tag created by
mistake is deleted by the maintainer, locally and on the remote; a clone that
already fetched it keeps the old one until `git fetch --tags --force`, and a
publishing workflow triggered by tags runs again when it is created again.
After the upload, the fix is a new version.

### 6. PyPI

The upload is the maintainer's, of the files inspected in step 4, not a
rebuild, with the token in their own shell (or, when the repository has a
publishing workflow, the tag triggers it and this step is checking its run):

```bash
uv publish <outside>/nw-release/dist/noworkflow-<version>*
```

Then check that the index serves exactly the inspected files, and what users
get from it, by behavior and not by the version string alone (the index may
take a minute to serve a new version):

```bash
curl -fsS https://pypi.org/pypi/noworkflow/<version>/json | python3 -c 'import json, sys; [print(u["digests"]["sha256"], u["filename"]) for u in json.load(sys.stdin)["urls"]]'
shasum -a 256 <outside>/nw-release/dist/noworkflow-<version>*                                  # the same
uvx --refresh --isolated --no-python-downloads --python <floor>  --from noworkflow==<version> now -v
uvx --refresh --isolated --no-python-downloads --python <newest> --from noworkflow==<version> now run hello.py
```

### 7. The GitHub release

```bash
gh release create <version> --verify-tag --title "noWorkflow <version>" --notes-file <scratch>/notes.md
gh release list --limit 3                     # the new one is Latest
```

The note, written for users:

- the highlights, in prose, the work without an issue included;
- the issues delivered (step 1), as links, and the milestone, when there is
  one, as a link;
- compatibility, from `golden-run`: whether stores of the previous release
  open and take new trials, and whether the previous release reads stores
  this one writes; any change of `Requires-Python` or of a dependency's
  range — which release stays the last one for a Python that left;
- what the audits found and the maintainer decided to ship;
- the compare link, `https://github.com/gems-uff/noworkflow/compare/<previous tag>...<version>`.

A security fix has an issue like any other bug, and the note cites the issue.

### 8. The milestone, the release's issue and the extension

- **The milestone of the version**, if there is one: closed, and the next
  one created; what is still open in it moves to the next by the
  maintainer's decision. Releasing closes no issue: that happened at
  integration — except the release's own `Task` issue, which the maintainer
  closes now (`gh issue close <N> --reason completed`).

  ```bash
  gh api repos/gems-uff/noworkflow/milestones --jq '.[] | [.number, .title, .open_issues] | @tsv'
  gh api -X PATCH repos/gems-uff/noworkflow/milestones/<number> -f state=closed
  gh api repos/gems-uff/noworkflow/milestones -f title=<next version>
  ```

- **The Jupyter extension**, `noworkflow_labextension`, is a package of its
  own, with its own version and procedure
  (`src/frontend/packages/labextension/RELEASE.md`). When it, the packages it
  is built from or the npm lock changed since the previous release (`git diff
  --stat <previous tag>..<version> -- src/frontend/packages/labextension
  src/frontend/packages/history src/frontend/packages/trial
  src/frontend/packages/utils src/frontend/package-lock.json`), the
  maintainer opens a `Task` to publish it.

### 9. Close

Remove the worktree (`git worktree remove --force <outside>/nw-release`).
Tell the maintainer what was published and where, and what is left for them.

## Rehearsing a release

Everything that stays on the machine, nothing that leaves it:

```bash
git worktree add --detach <outside>/nw-release main
cd <outside>/nw-release && printf '%s' '<version>' > src/noworkflow/resources/version.txt
```

Check the prerequisites that can be read (none dispatches anything: for the
experimental legs, write what would run and which previous run it would be
compared with). Then steps 1 to 4 in that worktree — `uv build` takes the
bump from the working files — the dry run included, and the note of step 7
drafted in `<scratch>/notes.md` from what step 1 found.

The tag is the maintainer's (`AGENTS.md`), also in a rehearsal. With their
go-ahead, the command is tried in a throwaway clone, so that no tag ever
exists among the checkout's refs:

```bash
git clone --quiet --no-checkout <checkout> <scratch>/nw-tag
git -C <scratch>/nw-tag tag -a <version> -m "<version>" origin/main && git -C <scratch>/nw-tag tag -l <version>
rm -rf <scratch>/nw-tag
git -C <checkout> tag -l <version>                    # empty
```

Remove the worktree at the end; it takes `dist/` and the `egg-info` that the
build left with it.
