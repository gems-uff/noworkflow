---
name: python-matrix
description: Runs the suite on every Python version of the CI matrix — locally with uv, on Linux x86_64 in the reference container, on the CI legs and on the experimental Windows legs — checks that the collector still handles a construct on each version, triages a failure that shows on one leg only, and keeps the matrix in step with python.org (the experimental leg of the next version, its promotion with the move of the reference leg and its goldens, the removal of the version that reached end of life). Use when a change touches the collector or the AST rewriting, when an issue names a Python version, when one leg is red and the others green, and when python.org releases or retires a version.
---

# The suite on every supported Python

`.venv` runs one Python, the reference leg's. Users run noWorkflow inside
their own interpreter, anywhere in the supported range, and between two
versions more changes than the version string:

- **The AST.** Each version adds nodes, and the collector rewrites the AST of
  the traced script (`prov_definition/`, `prov_execution/`) through
  `pyposast`. A construct that neither the syntax corpus of the e2e tests
  nor the examples use is covered on no version (`AGENTS.md`, "Blind spots
  of the suite").
- **The standard library.** On Windows, `ntpath.isabs` stopped taking a
  rooted path without a drive as absolute; from 3.15, UTF-8 mode is on by
  default (PEP 686), so an `open()` without `encoding=` reads differently at
  the two ends of the range.
- **The dependencies.** `uv.lock` resolves separately per Python fork (the
  `resolution-markers` at its top), so a package may be locked at two
  versions on two legs (`dependencies`), and a new interpreter may find no
  wheel for a package and build it from source.
- **The interpreter build.** Two builds of the same version can differ in
  what they compile in; a test that depends on such a module may skip on one
  and run on the other. CI runs only uv's (python-build-standalone); a local
  interpreter from another manager is another build.

The rule that decides the range and the matrix is "Python versions" in
`AGENTS.md`; this skill is how to apply it. Everything here runs outside the
sandbox: inside it uv cannot lock its cache (`Could not acquire lock ...
Operation not permitted`) and every version fails before pytest starts, and
`gh` cannot reach GitHub.

## Locally, on each version

The loop of `CONTRIBUTING.md` ("Running locally"), with what an agent adds:
no download of an interpreter, one log per version, and the reference
version left to `.venv` (`uv run pytest`):

```bash
uv python list --only-installed
legs=$(sed -n '/reference: true/!s/.*os: ubuntu-latest, python: "\([0-9.]*\)".*/\1/p' .github/workflows/ci.yml)
[ "$(echo "$legs" | wc -w | tr -d ' ')" -eq "$(( $(grep -cE 'os: *"?ubuntu-latest' .github/workflows/ci.yml) - 1 ))" ] \
  || echo "the sed missed a Linux leg: fix it before reading any result"
seed=$RANDOM; echo "seed $seed"
for v in $(echo "$legs"); do
  echo "$v: $(uv python find --no-python-downloads "$v")"
  uv run --isolated --locked --no-python-downloads --python "$v" pytest -q -p no:cacheprovider --randomly-seed=$seed > "<scratch>/py$v.log" 2>&1
  echo "$v: exit $? — $(tail -n 1 "<scratch>/py$v.log")"
done
```

Each version takes minutes, one after the other; an agent runs the loop in
the background and waits for it. `$(echo "$legs")` is there for zsh, which
does not split a plain `$legs` into words. One seed for every version (`-q`
hides the one pytest-randomly picks): a red on one version only is then
that version, not an order the others never ran.

- **The sed reads one leg per line.** It finds the `- { os: ..., python:
  "...", ... }` form of `ci.yml`, as `CONTRIBUTING.md`,
  `.github/reference-leg/run.sh`, `test_normalize.py` and the
  `check_merge.sh` of `merge-downstream` do. A leg written over several
  lines, with its keys in another order or with a quoted value is silently
  left out; the count check above says so.
- **A version that is not installed is an install.** `uv run --python`
  downloads a missing interpreter on its own; `--no-python-downloads` makes
  it fail instead, and the download waits for the maintainer's go-ahead
  (`AGENTS.md`). `uv python find` shows which interpreter will run — it may
  be one from another manager, at another patch level than CI's.
  `--managed-python` (on `uv python find` and `uv run`) refuses it, as CI
  does; where only another manager's build is installed, CI's build is an
  install.
- **`--isolated` is not optional**: without it `uv run --python` recreates
  `.venv` on that version (`safe-refactor`, step 5). **`--locked`** makes a
  `uv.lock` that disagrees with `pyproject.toml` fail, as CI's `uv sync
  --locked` does; without it the isolated run re-resolves in memory and
  measures a set that CI never installs.
- **Every version runs**, even after a red one: which versions fail is the
  measurement.
- **The count.** Compare the total, passed + failed + skipped + xfailed +
  xpassed. CI's count (the same without the failures: the one `min-tests`
  floors and `safe-refactor` uses) drops by the failures of a red version,
  and the total does not. Locally nothing is deselected: the goldens skip off
  the reference platform, and most `paper` tests skip without their group
  while a few pass, so on a green version the total is CI's count plus what
  CI reports as deselected; `-m "not golden and not paper"` gives CI's
  number for a non-reference leg. Between versions the total stays the same
  and only the split moves; a total that changes is a test that disappeared.
- **One version, one test:** `uv run --isolated --locked --no-python-downloads
  --python <v> pytest -p no:cacheprovider <node id>`. A bug specific to a
  version is proven on that version (`AGENTS.md`, "Reproduction traps").

### A green count does not prove the grammar

The collector reports a construct it cannot handle in ways a passing log
never shows. A `SyntaxError` from `pyposast` becomes `Syntax error on file
... Skipping transformer.`, which is printed only under `now run -v`, and the
script then runs without its definition provenance; pytest drops what a
passing test prints anyway. Any other exception inside `pyposast` prints a
traceback, the script does not run at all, and `now run` still exits 0. A
test that does not inspect what was recorded passes in both cases.

To check a construct on a version, trace a short script that uses it, from a
scratch directory:

```bash
cd <scratch> && uv run --isolated --locked --no-python-downloads --python <v> --project <checkout> now run -v <script>.py
```

The script's own output must be there, with neither `Skipping transformer`
nor a traceback, and `now show -d` (same prefix) lists its definitions.

The syntax corpus does this for each construct it holds, on every leg:
`src/noworkflow/tests/e2e/corpus/syntax/` has one script per construct,
and `test_syntax_corpus.py` runs each one twice, once against plain Python
(the comparator of `oracle.py`) and once under `now run -v`, where the
transformer must have run (no `Skipping transformer`, the construct's code
components on its lines, evaluations recorded). A construct missing there
is checked by hand as above; one that fails becomes a `Bug`, a script in
the corpus and an entry in its `CASES`, marked on the versions where it
fails. That range is measured, never guessed: the module run with
`--runxfail` on each version (the loop of the previous section, with the
module's path) shows every case without its marks, and `strict` turns a
mark on a version where the case passes into a failure.

## Off this machine: the container, the legs, Windows

- **The reference platform** (Linux x86_64 on the reference version) is a
  container: `.github/reference-leg/run.sh [pytest arguments]` builds the
  image with the Python of the `reference: true` leg and runs pytest there
  (the goldens take about ten minutes under emulation). It is where goldens
  are compared and recorded, and where a package built from source on x86_64
  only fails. It needs a container engine (`CONTRIBUTING.md`, "What to
  install"), which is an install: when there is none, using a CI run instead
  is the worse workaround, and the report says that the install would avoid
  it (`AGENTS.md`). colima and Docker Desktop keep a VM running; stopping it
  is the maintainer's call.
- **The image ages.** It is built once per Python version and reused as it
  is, uv and the CPython patch included, while CI takes the newest of both.
  Before recording goldens, and whenever CI's `Using CPython` line shows a
  newer patch than the image, pull for `linux/amd64` every image the `FROM`
  and `COPY --from` lines of `.github/reference-leg/Dockerfile` name, and
  remove the tag; the next `run.sh` builds it again:

  ```bash
  for i in $(sed -nE 's/^FROM (--platform=[^ ]+ )?([^ ]+).*/\2/p; s/^COPY --from=([^ ]+).*/\1/p' .github/reference-leg/Dockerfile); do
    docker pull --platform linux/amd64 "$i"
  done
  docker image rm noworkflow-reference:<v>
  ```
- **The CI legs**: a push runs `ci.yml` on any branch; `gh workflow run
  ci.yml --ref <branch>` runs it again without one. **Windows** is in
  `experimental.yml`, which runs only by hand while its header says it is
  suspended: `gh workflow run experimental.yml --ref <branch>`. On a branch
  other than `main`, a dispatch cancels the run still going (the workflows'
  concurrency group); on `main` it queues behind it. Either way, wait for it
  first.

```bash
gh run list --workflow <file> --branch <branch> --limit 1 --json databaseId,headSha,status,conclusion
gh run watch <id> --exit-status
gh run view <id> --json jobs --jq '.jobs[] | [.name, .conclusion] | @tsv'
gh run view <id> --log | awk -F'\t' '$2 ~ /^Run (tests|the paper example)$/ && $3 ~ / in [0-9.]+s( \([0-9:]+\))? =+$/ {sub(/^[^ ]+ /, "", $3); print $1 ": " $3}'
gh run view <id> --log | grep 'Using CPython'
```

- **Check `headSha`** against `git rev-parse <branch>`: right after a push or
  a dispatch the newest run may still be the previous one, and the newest run
  of a suspended workflow can be many commits old.
- **Decide by the text.** `gh run watch --exit-status` on a finished run
  answers at once with the run's verdict; `gh pr checks` exits non-zero
  while a check is pending, not only when one failed (`review-pr`, step 6).
- **The summary line of each leg** comes from the log, one call for every
  leg (the `awk` above): the job summary that `pytest-summary.sh` writes is
  not readable through the API.
- **Which interpreter each leg ran.** The three workflows set
  `UV_MANAGED_PYTHON` at the top, so every leg runs python-build-standalone,
  the build of the reference container and of uv on a maintainer's machine,
  and no leg changes when GitHub updates an image. A `Using CPython` line
  without `interpreter at:` is a download; one with a path of the image
  after it (`/usr/bin`, `/usr/local/bin`, `/opt/homebrew`, the hosted tool
  cache) means a job lost the setting. A new workflow that installs uv
  sets it too.

## Reading a failure that shows on one leg

A red on one leg **is not necessarily a bug**. Three categories, and the
difference matters:

1. **A test that assumes one version.** The AST of the version that wrote it,
   a rooted POSIX path in a fixture, the locale encoding. The test is wrong,
   not the tool: it asserts what the tool never promised on that version.
   Fix the test.
2. **A real defect that the reference version hid.** An AST node the
   transformer does not handle, a path that only breaks on Windows, a
   package locked at another version on that Python fork. A `Bug` issue
   (with the `collection` label when it is in the collector), and a test that
   fails on that version.
3. **An artifact of the environment.** A `pyposast` release that does not
   parse the new grammar yet (a fix there reaches this repository only
   through a release: `dependencies`), a pre-release interpreter, a package
   with no wheel for that interpreter built from source, an interpreter build
   that lacks a module, a uv too old to know the version. Not a verdict on
   the change.

Suspect the third first: it is the easiest to cause without noticing and the
one that produces the most misleading diagnosis. Then compare with the same
leg on `main` (`gh run list --workflow <file> --branch main --limit 1`)
before charging the red to the change.

## Following python.org

The supported versions and their end-of-life dates are at
<https://devguide.python.org/versions/>; the release schedule of the next
version is its PEP. The decision that set the rule, with the measurements
behind it, is the issue that `AGENTS.md` cites. Against the matrix:

```bash
curl -fsS https://peps.python.org/api/release-cycle.json | python3 -c '
import json, re, sys
cycle = json.load(sys.stdin)
legs = set(re.findall(r"os: ubuntu-latest, python: .([0-9.]+).", open(".github/workflows/ci.yml").read()))
for v in sorted(cycle, key=lambda v: tuple(map(int, v.split(".")))):
    if cycle[v]["status"] != "end-of-life" or v in legs:
        print(v, cycle[v]["status"], cycle[v]["end_of_life"], "leg" if v in legs else "no leg")
'
```

A version with a leg and the status `end-of-life` leaves at the next minor
release (the `release` skill checks it). The next version's status turns from
`feature` to `prerelease` at its first beta: the moment for its experimental
leg.

Each of the three moves below is one commit, by the maintainer:
`requires-python`, the classifiers and the matrix change together. What each
one touches:

| What | Where | Moves with |
|---|---|---|
| Supported range | `requires-python` and the classifiers in `pyproject.toml` | the floor; the classifiers with every blocking leg |
| Lint target | ruff's `target-version` in `pyproject.toml` | the floor |
| Linux legs | the `test` matrix of `ci.yml` (and the comment over the floor) | every supported minor |
| Reference leg | `reference: true` and its `min-tests` in `ci.yml`; the Python of the `checks` and `paper-example` jobs, their step names and the label of the paper example's summary; `flaky.yml` (setup and reproduction line) | the newest blocking version |
| macOS legs | `ci.yml` | the floor and the newest |
| Windows legs, next version | `experimental.yml` (its header and `on:` as well) | the floor and the newest; the next version's leg |
| Goldens | `src/noworkflow/tests/e2e/goldens/` and `goldens/REFERENCE` | the reference leg |
| User docs | `README.md` (the minimum version and the tested range); `Examples/*/README.md` and the bug template, when they name a version out of the range | the range |
| Agent docs | sentences that name a version in `AGENTS.md`, `CONTRIBUTING.md` and `.claude/skills/` (`git grep -n -F '<version>' -- AGENTS.md CONTRIBUTING.md .claude/skills`) | when the versions they name leave |
| Jupyter extension | `requires-python` and the classifiers in `src/frontend/packages/labextension/pyproject.toml` | the range, unless the maintainer gives it one of its own |
| Lock | `uv.lock` (`uv lock`) | `requires-python` only |

`CONTRIBUTING.md` and `.github/reference-leg/run.sh` read the versions from
`ci.yml` and move by themselves; `test_normalize.py` fails when
`goldens/REFERENCE` disagrees with the reference leg. After each move, `git
grep -n -F '<old version>' -- .github` lists what the table missed (read each
hit: a package pinned at the same digits is not a Python version).

### The next version's pre-releases: an experimental leg

From its first beta, the next version runs on Linux in `experimental.yml`:

- uv must know the pre-release: `uv python list --only-downloads <next>`
  lists it. The request `"<next>"` (the minor alone) selects the newest
  pre-release while there is no final; `<next>.0` and `>=<next>` do not.
  `setup-uv` hands `python-version` to uv as `UV_PYTHON`, as it is, so the
  leg is `python: "<next>"`. CI installs the newest uv, which may know a
  newer pre-release than the local one.
- The leg gets the `min-tests` of the other non-reference legs.
- When the workflow is suspended and its header names this leg as the moment
  to resume, the same commit puts `push:` and `pull_request:` back under
  `on:` and rewrites the header paragraph that explains the suspension.
- The heaviest compiled dependencies are in the `paper` group, which only
  the reference platform syncs: they meet the new version on promotion day.
  Whether the pre-release leg also syncs that group and runs `-m paper` is
  the maintainer's call.
- Locally the pre-release is an install: ask before it.
- The grammar the version adds (the syntax PEPs of its "What's New") enters
  the syntax corpus as scripts gated by that version (`min_py`), measured
  on the pre-release like every other case.
- What fails is triaged by the categories above. On a pre-release the third
  is the usual one: `pyposast` and the grammar first, and every package
  without a wheel for that interpreter builds from source (those with C or
  Rust extensions among them).

### When the suite passes on it: the promotion

The target is the October release of the version. In one commit:

- `ci.yml`: the version enters the `test` matrix on Linux as the new
  reference (`reference: true`, with the reference leg's `min-tests`); the
  previous reference becomes a plain leg with the `min-tests` of the others;
  the newest macOS leg moves to it; the Python of `checks` and of
  `paper-example` moves with the reference, with every other mention of it
  (`git grep -n -F '<old reference>' -- .github`).
- `experimental.yml`: the pre-release leg leaves; the newest Windows leg
  moves to the new version. If `push:` came back only for the pre-release leg
  and the reason for the suspension still holds, suspend it again, and update
  any version its header names. `flaky.yml`: the reference Python.
- `pyproject.toml`: the classifier. `README.md`: the tested range.
- The goldens, recorded again in the container **after** `ci.yml` changed
  (the script reads the version from it) and **after** `goldens/REFERENCE`
  names the new platform. Nothing writes that file, and while it names the
  old platform `GOLDEN=overwrite` fails every golden without writing any:

  ```bash
  printf 'linux <new>\n' > src/noworkflow/tests/e2e/goldens/REFERENCE
  GOLDEN=overwrite .github/reference-leg/run.sh -m golden
  git diff --stat src/noworkflow/tests/e2e/goldens/
  ```

  `-m golden` includes the goldens of the paper's running example: the
  container syncs the `paper` group. That diff is what the new Python
  changes in noWorkflow's output (the standard library's paths in the Prolog
  export, at least), and it is read line by line: a line it does not explain
  is a defect, not a golden to accept.
- `uv lock --check`: adding a version at the top does not change
  `requires-python`, so the lock does not move.

Afterwards each developer moves `.venv` to the new reference (`uv sync
--locked --python <new>`, `CONTRIBUTING.md`); when `<new>` is not installed,
that downloads it, which for an agent waits for the maintainer's go-ahead.

### At the first minor release after a version's end of life: the removal

Never in a patch release. In one commit:

- `pyproject.toml`: the floor of `requires-python`, the classifier, ruff's
  `target-version`.
- `ci.yml`: the Linux floor leg leaves, the macOS floor moves to the new
  floor, and the comment over the floor follows; `experimental.yml`: the same
  for Windows.
- `uv.lock`: `uv lock`, nothing upgraded. The forks below the new floor
  leave; `lock_versions.sh` of `dependencies` shows that nothing else moved.
- `README.md`, the documents the table lists that name the removed version,
  and the release note: which release stays the last one for it (pip on that
  version keeps resolving to that release).

The code that exists only for the removed version, the tests that branch on
it included, leaves in steps of its own, measured like any refactoring
(`safe-refactor`).

## What the matrix does not cover

- The middle versions on macOS and Windows, and Windows as a blocking leg.
- The goldens and the paper's running example off the reference platform.
- A construct outside the syntax corpus and the examples, on any version:
  the AST is exercised only where a test runs a script that contains it ("A
  green count does not prove the grammar").
- The extras (`demo`, `notebook`): the legs sync the lock without them.
