---
name: dependencies
description: Decides how a dependency is declared in pyproject.toml, judges whether a version pin still has a reason, and carries out an update one package at a time — uv.lock and pip-audit for Python, the npm lock and the bundle for the frontend, the SHA-pinned GitHub Actions. Use when adding a dependency, changing a version constraint, auditing the pins, handling a Dependabot PR, measuring an unreleased pyposast, or planning an update campaign.
---

# Dependencies: declaring and updating

Two different questions, easily confused. **How to declare** is long-term
policy and lives in `pyproject.toml`. **How to update** is an operation and
lives in the arguments of `uv lock` — never in the file.

The rule of the step — one package per step, the target is the latest patch
of the same series, a minor or major bump is a decision and never a side
effect — is in `AGENTS.md` ("Dependencies") and is not repeated here. What
follows is how to apply it with the tools of this repository.

## Where things are

- `[project.dependencies]` in `pyproject.toml`: what `now` imports at
  runtime, every command included — everything reachable from the CLI counts
  as in use (`AGENTS.md`). These ranges go into the wheel verbatim.
- `[project.optional-dependencies]`: the extras (`demo`, `notebook`, `all`)
  are user-facing features; a user installs `noworkflow[notebook]` to get one.
- `[dependency-groups]`: the tools (pytest, ruff, bandit, pip-audit). Never in
  the wheel; CI installs them from the lock.
- `[build-system]`: what builds the wheel. Its setuptools is not the runtime
  setuptools in `[project.dependencies]`; the two move independently.
- `uv.lock`: the exact set that dev and CI install (`uv sync --locked`),
  extras and groups included. It resolves **separately per Python version**
  when the constraints force it (the `resolution-markers` at the top; uv
  calls each resolution a fork, and this skill says Python fork): one package
  can be locked at several versions, one per fork, and the oldest fork is
  bounded by the oldest `requires-python`.
- `src/frontend/package-lock.json`: the JavaScript side, compiled into the
  committed `bundle.js` (part 3).
- `.github/workflows/*.yml`: the pinned actions (part 4), and in `ci.yml` the
  audit steps with the list of ignored advisories, each with its reason and
  the issue that removes it.
- `.github/dependabot.yml`: version updates off, security updates on (part 2).
- `lock_versions.sh`, in this skill's directory: the locked versions of a
  lock, or the difference between two (its header has the usage).

## Part 1 — Declaring in `pyproject.toml`

### The principle

noWorkflow is a **library**: `pip install noworkflow` puts it into the user's
own environment, next to whatever is already there — their Jupyter, their
numpy — and the wheel carries the ranges of `[project.dependencies]` as
written. A constraint there is not for reproducibility; `uv.lock` does that
for dev and CI, and the user never sees it. A constraint in
`[project.dependencies]` is **a policy imposed on every user's environment**:
an `==` forces a downgrade or a conflict in an environment this project does
not control, and a `<=` that stops before the wheels of a newer Python means a
build from source at install time, because wheels are built per Python.

Hence the rule that decides nearly every case:

> **The constraint covers exactly the reason, and the reason is written next
> to it, as a TOML comment.** Without a reason to write, the right line is
> the name alone.

### The forms and what each one says

| form | means |
|---|---|
| the name alone | no policy; the lock decides in dev and CI, the user's resolver on install |
| `>=x.y` | this code calls an API that appeared in x.y; `now` fails at import below it |
| `<x.y` | x.y is a measured break for this code, and the comment says which |
| `>=x.y,<z.w` | both |
| `==x.y.z` | never in `[project.dependencies]`: a frozen version in a library freezes the user's environment |

**A security floor is not declared.** `>=x.y.z` "because of the advisory"
ages silently: when the next fix comes out the floor stays below it and goes
on asserting a coverage that no longer exists, and nobody reviews floors. The
mechanism that does not age is `pip-audit` (part 2), which compares the lock
with the advisory database of the day. In a library the floor also forces
every user's environment to move for a code path that `now` may not even
reach. The advisory is recorded where it lives: in the database, and in the
message of the commit that moved the package.

Both sides of the rule matter. A constraint that exceeds its reason blocks
fixes by accident: an upper bound placed before the release that really
breaks this code refuses, silently, every release in between — patches and
security fixes included. Check that the form is the loosest that still
covers the reason, and that the bound is the **measured** break, not the one
an issue or a changelog announced. And a constraint without a written reason
is the symmetric defect: whoever reviews it in two years cannot tell whether
it can go.

### What goes where

- A package that one engine or one command needs and the others do not is a
  candidate for an extra. The bare runtime name is the status quo and stays;
  moving a command's package to an extra is a product decision for an issue,
  and an audit only lists the candidates.
- A module that imports a package no declaration covers — the git content
  engines in `src/noworkflow/now/persistence/content/` import `pygit2` and
  `dulwich`; `persistence/serializers.py` imports `jsonpickle`; the magics
  import IPython, declared only in the extras — is the same kind of product
  decision: an extra, a runtime dependency, or a documented "install it
  yourself". Write the decision in an issue, not in a guess.
- A test-only package in `[project.dependencies]` exists because the tests
  ship inside the wheel (`src/noworkflow/tests`). The reason belongs next to
  it as a comment; it leaves with the tests.
- Dev tools go in `[dependency-groups]`, and their floor is the version whose
  configuration this repository uses (`[tool.ruff]`, `[tool.pytest.ini_options]`).

### Judging a pin that is already there

For every entry of `[project.dependencies]` — bare names included: for a bare
name the questions reduce to whether it is imported, whether only the tests
import it, and whether one command alone needs it — four questions, in this
order:

1. **Who asked for it, and why.** Search every line that mentions the
   package, not the constraint: the exact string finds only the commit that
   last wrote it (the move to `pyproject.toml` copied every pin), and the
   reason lives in the commit that introduced the bound.

   ```bash
   git log -G'<name>' --format='%h %ad %an %s' --date=short -- pyproject.toml setup.py capture/setup.py
   ```

   `-G`, not `-S`: `-S` counts occurrences, so a commit that only edits the
   constraint on its line is not a hit, and that is how bounds are usually
   introduced. Before the move to `src/` the declaration lived in
   `capture/setup.py`, and git does not see the creation of `pyproject.toml`
   as a rename of it, so that path must be in the pathspec. `git show
   <commit> -- <file>` on each hit walks the forms of the constraint back to
   the one that introduced the bound. The message of that commit is the reason of that day; an issue or a
   PR number in it says more (`gh issue view <N>`, `gh pr view <N>`, `gh pr
   diff <N> --name-only`).
2. **Is it imported at all.** By the module, which is not always the
   distribution: `-` becomes `_`, the case may differ (`SQLAlchemy` is
   `sqlalchemy`), and `setuptools` is imported as `pkg_resources`.

   ```bash
   grep -rn --include='*.py' -E '^\s*(import|from) <module>\b' src/noworkflow
   uv tree --locked --universal --invert --package <name>     # who else pulls it in, on every fork
   ```

   Without `--universal`, `uv tree` answers for the fork of the current
   interpreter only and hides the dependants on the older forks. A declared
   package that nothing imports is either a transitive someone pinned by hand
   or a leftover.
3. **What it costs today.**

   ```bash
   uv tree --locked --universal --outdated --depth 1     # "latest": the newest the oldest fork can install
   uv lock --upgrade-package <name> --dry-run            # "No lockfile changes detected": nothing can move
   curl -s https://pypi.org/pypi/<name>/<version>/json | jq -r '.info.requires_python, .urls[].filename'
   ```

   The `latest` of `--outdated` is the newest release every Python of
   `requires-python` can install, not PyPI's newest; the newer forks may land
   higher on an actual update, and the lock diff is what says where. The dry
   run answering "No lockfile changes detected" while `--outdated` shows a
   newer release means the declaration is what blocks it. The PyPI query says,
   for a frozen or capped version, on which Pythons its wheels exist (the
   rest build from source) and which Python a newer release requires.
   `pip-audit` (part 2) says whether the pin keeps a known advisory alive.
4. **The verdict.**
   - **Reason alive, bound measured**: keep it, and write the reason next to
     the pin if it is not there.
   - **Reason alive, bound never measured**: find the first release that
     breaks this code, and bound there, with that release in the comment. A
     module that the newer release dropped is still found in `.venv`, so the
     probe runs from outside the project:

     ```bash
     cd <outside> && uv run --isolated --no-project --python <version> --with "<name>==<candidate>" python -c "import <module>"
     ```

   - **Reason gone** (a Python the project no longer supports, an API this
     code no longer calls): relax to the loosest form that still covers what
     is left, or remove the declaration.
   - **Reason unknown**: an issue, never a silent relaxation.

   A relaxed pin is then an update (part 2), measured by `safe-refactor` with
   the changelog first.

`AGENTS.md` ("Patches of third-party internals") and the comments of the
audit step in `ci.yml` carry the reasons of the known pins **as last
written**. The four questions re-measure them; a reason that fails them is
corrected there, in the step that acts on the pin. The measurements of an
audit go to the issue that will act on them, as a comment.

## Part 2 — Updating

### The step

- **A declared package whose constraint blocks the move**: change the
  declaration first (part 1 decides the form), then the update below.
  Relaxing or removing a declaration **moves no locked version by itself**:
  `uv lock` rewrites only the constraint recorded in the lock and keeps the
  version it had. The move is the `--upgrade-package` that follows.
- **The update**, one package:

  ```bash
  uv lock --upgrade-package <name> --dry-run      # what would move, without writing
  uv lock --upgrade-package '<name><x.y+1'        # the newest of the x.y series
  uv lock --upgrade-package <name>                # the newest the constraints allow
  uv sync --locked                                # put .venv on the new lock
  ```

  The quoted bound is one constraint for the whole lock: it applies to every
  Python fork, and it moves down as well as up. When the forks of the package
  sit on different series (`lock_versions.sh` prints two lines for it), a
  bound at the older fork's series downgrades the newer fork; the dry run
  prints that as `Update <name> vA, vB -> vA` with exit status 0, so read the
  line, not the status, and bound at the newest fork's series. Without a
  bound the move may be a minor or a major on some fork, and that is the
  decision the rule reserves.
- **Check the version that was actually resolved**, in the lock, not in the
  command — against the base, with the lock on disk, before anything is
  committed:

  ```bash
  .claude/skills/dependencies/lock_versions.sh origin/main uv.lock   # from the repository root
  ```

  Only the intended package may move, one line per fork. And **a fix may land
  on one Python fork and not on another**: the last release that supports the
  oldest `requires-python` can predate the fix, so the oldest fork stays
  vulnerable while the newer ones are clean. The per-fork audit below says
  so; then the choice is between an ignored advisory in `ci.yml`, with that
  reason and the issue that removes it, and a decision about the Python
  floor.
- The suite by `safe-refactor` (the changelog of the dependency first, then
  the baseline, then the count). Then `pip-audit`, below. The commit is the
  maintainer's, one per package; when the move is a security fix, the
  advisory id goes in the message.
- **Never regenerate the lock from scratch**: it is `uv lock --upgrade` in
  effect, and the step stops being one package (`merge-downstream` says why).

### `pip-audit` before theorizing

```bash
uv sync --locked      # pip-audit comes from the dev group; --no-sync below keeps uv from touching .venv
uv export --locked --format requirements-txt --no-emit-project --all-groups --all-extras --no-hashes -o requirements-audit.txt
uv run --no-sync pip-audit -r requirements-audit.txt --no-deps --disable-pip --strict --desc on
```

Before arguing that a series "no longer gets security patches", measure. Two
things decide what the audit sees:

- **The extras enter the export only with `--all-extras`.** They are in the
  lock, but without the flag the Jupyter stack, matplotlib and numpy are never
  audited.
- **pip-audit audits only the fork of the interpreter that runs it.** The
  export writes each locked version with its environment marker
  (`; python_full_version < '3.9'`), and pip-audit evaluates the marker on its
  own interpreter and skips, silently, every line whose marker is false. The
  run above audits the Python of `.venv`; the other forks are audited by
  running the tool on a Python inside each, from outside the project:

  ```bash
  cd <outside> && uv run --isolated --no-project --python <version> --with pip-audit \
    pip-audit -r <checkout>/requirements-audit.txt --no-deps --disable-pip --strict
  ```

  once per range of the lock's `resolution-markers` (the top of `uv.lock`),
  not once per leg of the matrix: the matrix skips Pythons the lock still
  resolves for. Lines with a platform marker (Windows-only packages, for
  instance) are skipped the same way on any other platform.

The gate in CI (the audit step of `ci.yml`) audits what its own export and
its own interpreter let it see; compare that with the two points above before
trusting its green. An ignore is added there only with the reason and the
issue that removes it (`AGENTS.md`), and it leaves in the step that removes
the pin; an ignore for an advisory of a fork the gate does not audit records
the decision but changes nothing in the gate. pip-audit prints PYSEC ids and repeats a finding once per alias
description; `--ignore-vuln` also accepts the GHSA ids `ci.yml` lists, so the
way to check the ignore list is to run with it and read "N ignored".
`requirements-audit.txt` in the root is ignored by git.

### Diagnosis: is some pin blocking something?

```bash
uv tree --locked --universal --outdated --depth 1     # the newest the oldest fork can install
uv lock --upgrade-package <name> --dry-run            # "No lockfile changes detected" = the declaration blocks it
```

The difference between the two is what the pins block.

### Probing before a campaign

To know whether a move is viable without committing to it:

```bash
uv run --with "<name>==<version>" pytest -q     # that version layered over .venv, lock untouched
uv lock --upgrade --dry-run                     # the whole move, nothing written
```

`--with` wins over a `==` in `[project.dependencies]`: the overlay is
resolved on its own, so it also probes past a pin. But it is layered over
`.venv`: whatever the overlaid release removed is still found there, so a
probe of "does it still import" runs isolated (part 1, question 4). A real
`uv lock --upgrade` followed by the suite is undone with `git checkout uv.lock
&& uv sync --locked`; the clean tree is the undo, and no branch is created for
a probe.

Red is cheap information: abort. Green is **not** authorization for
everything together: each package, the tools included, goes back to one step
(`AGENTS.md`). The dev group declares only floors, so `uv lock
--upgrade-group dev` takes majors.

### A Dependabot PR is a signal, not the step

Version updates are off (`dependabot.yml` says why); security updates arrive
against `main` for `uv.lock`, `src/frontend/package-lock.json` and the
workflows. A security update proposes the minimum version that contains the
fix, and the lock it writes is the one `uv lock --upgrade-package
'<name>==<version>'` writes: the `==` applies to every Python fork, so the
named package ends at one version where uv kept one per fork, a fork that
already had a newer release goes down to it, and a fork that cannot install it
is re-solved around it — packages the title never names move, downgrades
included. Such a lock **passes `uv lock --check`**. Read the version diff
(`lock_versions.sh origin/main <the PR's head>`), not the title.

What to do with a `uv` one: read the advisory it cites, do the step by hand
(`uv lock --upgrade-package`, the series rule, the suite, the audit) in the
cycle of `AGENTS.md` — a PR with no issue goes where the maintainer decides
(`review-pr`) — and close the Dependabot PR with a comment naming where the
step went. An npm or a GitHub Actions one has no Python forks to collapse: it
is accepted or refused by the series rule through `review-pr`, with the lock
diff read entry by entry (part 3), the bundle rebuilt in the same change for
npm, and the version next to the SHA for Actions (part 4). A Dependabot PR
opened before a workflow existed has no checks until a `@dependabot rebase`
comment; a pushed merge or commit on its branch stops Dependabot from
updating it (`review-pr`).

### The sibling project `pyposast`

The AST positions the collector relies on come from `pyposast`, and a fix
there reaches here only through a release of that package (`AGENTS.md`). To
measure an unreleased commit against the suite:

```bash
uv run --with "pyposast @ git+https://github.com/JoaoFelipe/pyposast@<sha>" pytest -q
```

It builds the package from that commit and layers it over `.venv`. The
version in pyposast's `setup.py` comes from `git describe`, so this works for
any commit a tag reaches; for a commit no tag reaches (a fork, a branch cut
before the first tag) the version is a bare SHA, setuptools rejects it and
the build fails. Then clone the commit outside the checkout and put the clone
first on the path:

```bash
git clone https://github.com/JoaoFelipe/pyposast <outside>/pyposast
git -C <outside>/pyposast checkout <sha>
PYTHONPATH=<outside>/pyposast uv run --no-sync pytest -q
```

`--no-sync` keeps uv from touching `.venv`. The control is the same command
without `PYTHONPATH`, which imports the released one;
`python -c "import pyposast; print(pyposast.__file__)"` says which of the
two is loaded.

A PR that depends on the unreleased fix is **blocked until the release**, and
says so. `[tool.uv.sources]` could point the lock at the commit, but the wheel
carries only `[project.dependencies]`: the fix would exist in CI and on no
user's machine.

## Part 3 — The frontend does not go through uv

The JavaScript dependencies of the vis are not Python dependencies: webpack
compiles them into `src/noworkflow/now/vis/static/dist/bundle.js`, which is
committed and ships in the wheel, so a user never runs npm. The lock is
`src/frontend/package-lock.json`, the workspace is described in
`src/frontend/development.md`, and **any change to that lock is followed by
`rebuild-vis`** (its steps are those of the `frontend` job in `ci.yml`), with
the bundle in the same commit — the `frontend` job rebuilds it and fails on a
difference.

```bash
npm audit --prefix src/frontend --package-lock-only --omit=dev --audit-level=high   # the advisories, from the lock alone
npm ls <name> --prefix src/frontend --package-lock-only                              # who pulls a package in
```

Both read the lock without `node_modules`. `--omit=dev`: only the runtime
dependencies of the packages reach the bundle; the build tools do not ship.
The audit runs in CI's `checks` job; the comment there says why it is not a
gate yet.

The step is one package, but npm does not move one entry. A direct
dependency of a workspace package is changed in its `package.json` (`npm
install <name>@<version> --workspace=@noworkflow/<package>`, from
`src/frontend`); a transitive moves with `npm update <name> --prefix
src/frontend --package-lock-only`, which also moves whatever the new version
requires and whatever its ranges let move under it — tens of lock entries for
one package. Read the lock diff entry by entry (`git diff
src/frontend/package-lock.json`), and remember that **a caret range admits
minors**. An `overrides` entry in `src/frontend/package.json` forces one
package's version wherever it appears, even outside its dependants' ranges,
but the forced version still brings what it requires: read the lock diff the
same way, and write the reason in the commit message (JSON has no comments).
`npm audit fix` is a campaign, not a step.

Three things no lock knows, and all three reach the user:

- the vendored copies under `src/noworkflow/now/vis/static/` (`external/`,
  `font-awesome-4.7.0/`), served as they are;
- a copy vendored inside a workspace package (a file under
  `src/frontend/packages/<package>/style/` imported by its sources), which
  webpack embeds in the bundle under its own banner;
- what webpack pulled from npm into the bundle, under names the lock does
  not show.

retire.js reads all three, the copies by file name and the bundle by content:

```bash
npx --yes retire --path src/noworkflow/now/vis/static --severity high
```

It lists every finding; `--severity` only sets the level from which the exit
status is non-zero. A finding inside the bundle is either an npm dependency —
`npm ls` names who pulls it in, and it moves through the lock — or a vendored
copy, when `npm ls` comes back empty: `git grep -il '<name> v<version>' --
src/frontend/packages` finds the file (retire prints the name in lower case,
the banner usually capitalizes it), and it is replaced by hand, then
`rebuild-vis`. A finding in `static/` is replaced or removed by hand.

## Part 4 — GitHub Actions

Third-party actions are pinned by full commit SHA with the version in a
comment (`# vX.Y.Z`); GitHub's own `actions/*` by major. The step:

```bash
gh api repos/<owner>/<repo>/releases/latest --jq .tag_name        # the newest release
gh api repos/<owner>/<repo>/releases/tags/<tag> --jq .body        # what changed
gh api repos/<owner>/<repo>/commits/<tag> --jq .sha               # the commit the tag points to, annotated or not
```

The series rule holds: `releases/latest` is the newest, not necessarily the
same series; `gh api --paginate repos/<owner>/<repo>/tags --jq '.[].name'`
lists the tags, and the newest patch of the pinned series is the target. A
new major of an `actions/*` is a decision like any other. The same action
appears in several workflows (`ci.yml`, `experimental.yml`, `flaky.yml`):
one step moves all of them, to the same SHA. `setup-uv` installs the
`required-version` of `[tool.uv]` when there is one, and the newest uv
otherwise, unless `version:` is given; that uv is the one to compare with
`uv --version` locally when `uv lock --check` disagrees between the two.

## Part 5 — What a green suite does not prove

The suite imports `noworkflow` and runs in-process against in-memory stores
(`AGENTS.md`, "Blind spots of the suite"). After an update, what stays out of
its reach:

- **The git content engines.** The suite pins `plain`; `pygit2`, `dulwich`
  and the engines over them never run in it. A hand probe with a real `now
  run` on that engine, recorded in the PR.
- **The vis.** An npm update only shows in a browser. `rebuild-vis` proves the
  bundle builds; `golden-run` (the same corpus through `now` on both
  versions, the outputs compared) proves the pages; the `frontend` job proves
  only that the committed bundle matches the sources.
- **SQLAlchemy.** The ORM runs against in-memory SQLite in every test, so the
  mapped models are exercised; the file on disk and a store written by the
  previous version only through a real `now run` — `golden-run`, whose
  store-compatibility check opens the old store with the new code.
- **`pyposast`.** The collector exercises it on every test, but only on the
  syntax the examples use and on the Python of the run: `python-matrix` (the
  suite on each Python of the matrix, `uv run --isolated --python <version>
  pytest`).
- **The Jupyter stack** (`ipykernel`, the `notebook` extra), `requests`
  (push and pull) and the Flask routes: no automated test; a hand probe,
  recorded in the PR.
- **`setuptools`.** `pkg_resources` is imported when `now` starts, so the
  suite proves it imports on the version of the lock; the wheel is built by
  the `[build-system]` setuptools, which is another version — `uv build` in
  the `checks` job is what proves the build.
- **The other Python forks of the lock.** The local suite runs on one fork;
  the matrix runs the others, and the oldest leg is the one where a fix may
  be missing.
