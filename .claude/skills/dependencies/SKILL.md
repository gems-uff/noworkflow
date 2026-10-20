---
name: dependencies
description: Decides how a dependency is declared in pyproject.toml, judges whether a version pin still has a reason, and carries out an update — one package at a time, or a campaign that moves the tail in batches by level and the core one package per step — with uv.lock and pip-audit for Python, the npm lock and the bundle for the frontend, the SHA-pinned GitHub Actions. Use when adding a dependency, changing a version constraint, auditing the pins, handling a Dependabot PR, measuring an unreleased pyposast, or planning or running an update campaign (the use points, the patches, the minors, the majors experiment).
---

# Dependencies: declaring and updating

Two different questions, easily confused. **How to declare** is long-term
policy and lives in `pyproject.toml`. **How to update** is an operation and
lives in the arguments of `uv lock` — never in the file.

The rule of the step — one package per step, the target is the latest patch
of the same series, a minor or major bump is a decision and never a side
effect — is in `AGENTS.md` ("Dependencies") and is not repeated here, nor is
its one exception, a campaign, whose procedure is "A campaign" below. What
follows is how to apply them with the tools of this repository.

## Where things are

- `[project.dependencies]` in `pyproject.toml`: what `now` imports at
  runtime, every command included — everything reachable from the CLI counts
  as in use (`AGENTS.md`). These ranges go into the wheel verbatim.
- `[project.optional-dependencies]`: the extras (`demo`, `notebook`, `all`)
  are user-facing features; a user installs `noworkflow[notebook]` to get one.
- `[dependency-groups]`: the tools (pytest, ruff, bandit, pip-audit), in
  `dev`, which `uv sync` installs by default, and what a set of tests needs
  beyond them, in a group of its own (`paper`: the ML stack of the paper's
  running example; `browser`: Playwright, for the tests of the vis in a
  browser), which only the CI job of those tests syncs. Never in the
  wheel; CI installs them from the lock.
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
- `use_points.py`, in this skill's directory: the lines of product code that
  use each third-party package, and how many of them a coverage report
  executed ("A campaign"; its docstring has the usage).

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
  `dulwich`; the magics import IPython, declared only in the extras — is
  the same kind of product decision: an extra, a runtime dependency, or a
  documented "install it yourself". Write the decision in an issue, not in
  a guess.
- A test-only package in `[project.dependencies]` exists because the tests
  ship inside the wheel (`src/noworkflow/tests`). The reason belongs next to
  it as a comment; it leaves with the tests.
- Dev tools go in `[dependency-groups]`, and their floor is the version whose
  configuration this repository uses (`[tool.ruff]`, `[tool.pytest.ini_options]`).
- A heavy package that only some tests import goes in a group of its own,
  not in `dev`, so that every matrix leg does not install it: the tests
  skip without it, carry a marker the matrix deselects, and a CI job syncs
  the group (`uv sync --locked --group <name>`). Its packages are audited
  like the rest (the export takes `--all-groups`).

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
   `sqlalchemy`), and the name may be another (`pyswip-alt` is `pyswip`).

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
  vulnerable while the newer ones are clean. The audit below says so; then
  the choice is between an ignored advisory in `ci.yml`, with that
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
uv export --locked --format pylock.toml --no-emit-project --all-groups --all-extras -o <outside>/audit/pylock.toml
uv run --no-sync pip-audit --locked <outside>/audit --strict --desc on
```

`<outside>` is any directory outside the checkout (the export creates it);
`--locked` reads `pylock.toml` and `pylock.*.toml` in the directory given.
Before arguing that a series "no longer gets security patches", measure. Two
things decide what the audit sees:

- **The extras enter the export only with `--all-extras`.** They are in the
  lock, but without the flag the Jupyter stack, matplotlib and numpy are never
  audited.
- **The format of the export decides which Python forks are audited.** A
  requirements export writes each locked version with its environment
  marker (`; python_full_version < '<version>'`), and `pip-audit -r`
  evaluates the marker on its own interpreter and skips, silently, every
  line whose marker is false: it audits the fork of the Python that runs
  it, on its platform, and nothing else. A `pylock.toml` is read entry by
  entry, no marker evaluated, so `--locked` audits every version of every
  fork and platform, whatever the interpreter. A finding names the package
  and the version; `lock_versions.sh` (or the `marker` of that entry in the
  export) says which fork holds it.

The gate in CI (the audit step of `ci.yml`) runs these commands. An ignore
is added there only with the reason and the issue that removes it
(`AGENTS.md`), and it leaves in the step that removes the pin. pip-audit
prints PYSEC ids and repeats a finding once per alias description;
`--ignore-vuln` also accepts the GHSA ids `ci.yml` lists, so the way to
check the ignore list is to run with it and read "N ignored".

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
everything together: what goes in as a batch, and what goes one package per
step, is the regime of a campaign (below). The dev group declares only
floors, so `uv lock --upgrade-group dev` takes majors.

### A campaign

A campaign brings both locks up to date at once: before a stretch of work
that should start from current dependencies, or when the audits and the
Dependabot alerts pile up. One issue (a Task) holds it, each step is a
session that ends with a results comment there, and the steps go in this
order: the use points, the patches, the minors, the majors.

**The regime.** The rule of the step (`AGENTS.md`) holds for the core; the
tail moves in batches.

- **Core:** a package the code is built on — its use points are spread over
  many modules, or the suite reaches few of them, or its minors carry
  documented migrations. One package per step, to the newest minor of its
  series, with every changelog between the locked version and the target
  (and the upgrade guide) read first. The step is split at a minor whose
  changelog announces a migration — an API removed, a configuration that
  changes, a new packaging — and that minor is a step of its own.
- **Tail:** everything else — a transitive this code never names, a dev
  tool, a build tool whose product is compared byte for byte (Babel and the
  loaders: the bundle is the proof). One batch per level, all the patches
  and then all the minors, with a hard ceiling (below), the lock diff read
  entry by entry, and bisection only when the batch goes red.
- **A major** is never in a batch: the majors are an experiment first
  (below), and each one that goes in is a step of its own.

Which package is core is measured in the first step and written in the
campaign's issue. A framework the code is built on stays core from one
campaign to the next: SQLAlchemy, Flask, IPython and pyposast on the Python
side; webpack, typescript, `@lumino/widgets`, `@jupyterlab/*`, codemirror
and d3 on the npm side.

**1. The use points.** Line coverage of noWorkflow says nothing about a
dependency; what matters is whether the suite executes the lines that use
it. `use_points.py`, in this directory, counts per package the lines of
product code that load a name the package bound, and how many of them a
coverage report executed (its docstring has what it does not count):

```bash
uv run pytest -n 4 --cov --cov-report=json:<outside>/coverage.json
uv run --no-sync python .claude/skills/dependencies/use_points.py src/noworkflow --exclude src/noworkflow/tests src/noworkflow/resources/demo --coverage <outside>/coverage.json --detail <module> ...
```

A use point the suite never reaches is where an update breaks without a
red: it names the hand probe of part 5 that the step owes, and where a
characterization test should go before a core package moves. A transitive
has no use point of its own: `uv tree --locked --universal --invert
--package <name>` names the package through which it reaches this code,
whose points are the ones that verify it. On the npm side no JavaScript
runs in the suite but the browser tests, so the measure is static: the
import sites of each package (`git grep -n "from ['\"]<name>" --
src/frontend/packages`) and the view, or the build output, that proves it.

**2. The inventory, by level.**

```bash
uv tree --locked --universal --outdated     # every locked package with a newer release, at any depth
uv lock --upgrade --dry-run                 # what the constraints let move: the "Update" lines
npm outdated --prefix src/frontend          # per workspace: current, wanted (the range), latest
```

A dry run that answers "Lockfile changes detected" without any `Update`
line only reorders the `resolution-markers` and moves no version
(`lock_versions.sh` against the base confirms it). In `npm outdated`,
"wanted" is the newest the range admits and "latest" the newest release;
the level of each move is read from the versions, and a "latest" beyond
"wanted" means changing a range, which is a decision.

**3. A batch at one level.** Neither tool has a level flag. In uv, one bound
per package, all in one call — `'<name><x.y+1'` keeps a patch batch in the
series, `'<name><x+1'` a minor batch in the major, and the fork rule of "The
step" above applies to each bound:

```bash
uv lock --upgrade-package '<a><bound>' --upgrade-package '<b><bound>' ...
.claude/skills/dependencies/lock_versions.sh origin/main uv.lock
```

In npm, part 3, "A batch at one level". The batch's commit lists every entry
that moved. A lock diff with a package outside the level (a minor in a patch
batch) is a red batch: that package's bound was missing.

**4. A red batch is bisected** (delta debugging): from the base lock, redo
the batch with the first half of its names; the half that stays red is
halved again, until one package explains it. That package leaves the batch
and becomes a step of its own, under the core regime; the rest of the batch
goes in.

**5. Every step**, batch or package: the suite before and after with the
same seed (`safe-refactor`), the counts against the floors, `ruff`, `uv
lock --check`, both audits; `rebuild-vis` for any change to the npm lock,
with the browser tests on the rebuilt bundle and, when it changed,
`compare_vis.mjs` against the previous step's bundle, every difference read
against the changelog; the two checks of part 3 that no job of CI makes;
`golden-run` when a core Python package moves; and the hand probes of part 5
for the use points the suite does not reach. One commit per batch and one
per core package, each message listing every entry that moved and what was
read and measured. Each step builds on the commit of the previous one (the
comparison in a browser takes `HEAD` as its base), and the series goes
through a `ci-NNN` branch before `main`.

**6. The majors: an experiment first,** on throwaway worktrees of `main`,
never on the checkout: one for Python and one for npm, so that a probe's
build never meets the suite running in the other (`git worktree add
--detach <scratch>/<name> main`, then, in each, `uv sync --locked` with the
groups of the checkout's `.venv`). Nothing of it is integrated as it
stands; it ends in a report.

- **Python:** relax the pin in the worktree's `pyproject.toml`, `uv lock
  --upgrade-package <name>`, and the suite with the base's seed; group the
  failures by the deepest exception line of each one in a JUnit report
  (`--junitxml=<file>`). When one signature covers nearly everything, it is
  a first layer that hides the rest: fix it on the throwaway tree, run
  again, and repeat until what is left is either expected (a premise that
  asserts the old series) or a real cost. Each layer and its fix go to the
  report (the Mikado method: the goal on a throwaway tree, the
  prerequisites recorded, back to the base). When the old series can warn
  about what the new one removes, run the suite on the base with those
  warnings on and a `pytest_warning_recorded` hook that writes each one's
  file and line: the distinct sites are the surface of the migration on the
  paths the suite executes. Last, steps 3 to 5 of `golden-run`, with the
  worktree's `now` as the after side: whether a store of the old series
  still opens is measured, never assumed (`AGENTS.md`).
- **npm:** one major per probe, each from a fresh `npm ci` of the base lock:
  its range to `^<latest>` in the `package.json` that declares it, `npm
  install`, then the bundle build, the extension's `build:lib`, the `tsc`
  count and the two checks of part 3. For a bundle that built and changed,
  the browser tests with that bundle in the worktree's `static/dist/`, and
  `compare_vis.mjs --new <the probe's bundle>` from the checkout. Read the
  `engines` and `peerDependencies` of the new release first (`npm view
  <name>@<version> engines peerDependencies`): another package's peer range
  that excludes it is a prerequisite found without building.

The report goes to the campaign's issue: per major, what broke, what it
would cost and what comes first. A major that came out green and read
becomes a step of its own; one that needs a migration becomes an issue of
its own, with its prerequisites in the body.

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

**No Dependabot PR is merged as it stands** (`AGENTS.md`, "Dependencies":
`main` is the baseline). Its commit was never tested against today's
`main`, a `uv` one collapses the forks, and an npm one does not rebuild the
bundle. The PR is its own record, and needs no issue: a maintainer turns its
branch into the commit that will land, and integrates it.

1. Read the advisory it cites, and decide by the series rule.
2. `gh pr checkout <N>`, then `git rebase origin/main` when `main` moved.
3. Make the bot's commit the one that will land (`git commit --amend`, one
   commit per package):
   - **`uv`**: redo the lock by hand — `git checkout origin/main -- uv.lock`,
     then `uv lock --upgrade-package <name>` under the series rule — and read
     its diff (`lock_versions.sh`). The lock Dependabot wrote collapses the
     forks (above).
   - **npm**: read the lock diff entry by entry (part 3), and rebuild the
     bundle (`rebuild-vis`): when it changes, it goes into the same commit;
     when the package only builds, it does not change.
   - **GitHub Actions**: the SHA with its `# vX.Y.Z` comment, in every
     workflow that uses the action (part 4); usually nothing to change.

   The subject stays the bot's (`Bump <package> from <a> to <b>`) and gains
   the PR's number at the end, `(#N)`, as `AGENTS.md` allows for this
   commit.
4. The suite and the audit locally, then `git push --force-with-lease` to the
   PR's branch: CI tests the exact commit that will land. Once anyone but
   Dependabot has pushed there, Dependabot stops rebasing the PR; never
   comment `@dependabot recreate` afterwards, which discards that push.
5. With CI green, a maintainer fast-forwards `main` to it and pushes
   (`review-pr`, step 7). GitHub marks the PR as merged once its commit is on
   `main`; if it does not, close it with a comment naming the commit. The
   alert closes by itself once Dependabot rescans the default branch, a few
   minutes after the push.

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
The audit is a gate in CI's `checks` job, at `high` and on the runtime
dependencies only; the build tools' advisories are read with the same
command without `--omit=dev`, and wait for a campaign.

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
`npm audit fix` is neither a step nor a batch (below).

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

### A batch at one level

npm has no flag that keeps an update inside a series, and a caret range
admits minors. What works, from `src/frontend`, with every `package.json`
range as it was at the end:

- **Within the ranges:** `npm update <name>... --package-lock-only` moves
  the named packages, and what they require, as far as the ranges admit.
  Naming only the packages whose move is a patch ("wanted" against
  "current" in `npm outdated`) makes the patch batch.
- **A direct dependency held below its range:** set its range to `~x.y.z`
  for the `npm update`, put the original range back, and run `npm install
  --package-lock-only`: the lock records the original range and keeps the
  version just resolved, which that range admits.
- **A transitive held below what its dependants admit:** a temporary entry
  with the bound in the root `devDependencies`, removed the same way.

Two commands look like they bound and do not: `npm install
<name>@<version> --no-save --package-lock-only` leaves the lock as it was,
and `npm update <transitive>` takes the newest its dependants' ranges admit,
whatever the level. `npm audit fix` is not a batch either: to escape an
exact pin it downgrades the package that holds it, and it moves core
packages along with the tail. Read its `--dry-run` as a list of fixes, and
make the batch with `npm update`.

An `overrides` entry nested under one dependant (`"<dependant>":
{"<name>": "~x.y.z"}`) forces the version only below that dependant, where a
top-level one would also move, or downgrade, every other copy of the
package. It leaves when a release of the dependant requires that version on
its own, and the commit that adds it says so.

### Two checks no job of CI makes

- **The bundle holds no path of the machine.** A package whose build reads
  `import.meta.url` gets, from webpack, the `file://` URL of the module on
  the machine that builds, and the committed bundle carries the path of the
  checkout, home directory included; the `frontend` job fails only after the
  push, when the path is already in the history. `rebuild-vis` ("Reading
  `git status`") checks it after every build. A package that starts doing
  it is held below that release, or the build resolves its CommonJS entry,
  which does not read `import.meta`: a `resolve.alias` of `"<name>$"` to
  `require.resolve("<name>")` in `webpack.config.js`, plus a
  `resolve.fallback` set to `false` for each Node module that entry
  requires (the build names them, "Can't resolve '<module>'").
- **The Jupyter extension builds in full** when webpack, the extension's
  builder or another of its build dependencies moves. The `frontend` job
  only type-checks it (`build:lib`); the production build runs the bundler
  through the builder, with plugins of its own (`rebuild-vis`, "What a
  rebuild does not prove", has the command). The build is deterministic, so
  its output is compared file by file with the base's; its `package.json`
  is the extension's own, and differs only by the ranges the step changed.

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
appears in several workflows (`ci.yml`, `pre-release.yml`, `flaky.yml`, and
`experimental.yml` while it exists):
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
- **The vis.** An npm update only shows in a browser. The browser tests
  (the `vis-browser` job) assert that each view still opens and answers its
  input; `rebuild-vis` runs them on the rebuilt bundle and, when it changed,
  compares in headless Chrome what the vis draws and does with the bundle
  of `HEAD` and with the rebuilt one ("Before and after in a browser"),
  which shows what no test asserts; a view neither reaches is exercised by
  hand. The `frontend` job proves only that the committed bundle matches
  the sources.
- **SQLAlchemy.** The ORM runs against in-memory SQLite in every test, so the
  mapped models are exercised; the file on disk and a store written by the
  previous version only through a real `now run` — `golden-run`, whose
  store-compatibility check opens the old store with the new code.
- **`pyposast`.** The collector exercises it on every test, but only on the
  syntax the examples use and on the Python of the run: `python-matrix` (the
  suite on each Python of the matrix, `uv run --isolated --locked
  --no-python-downloads --python <version> pytest`).
- **Flask** serves the vis: `golden-run`, step 4, serves a store with each
  version and compares the routes `read_store.py` fetches (its docstring
  lists them); the others, among them the ones that write (push, pull, the
  experiments), stay a hand probe.
- **The Jupyter stack** (`ipykernel`, the `notebook` extra) and `requests`
  (push and pull): no automated test; a hand probe, recorded in the PR.
- **`setuptools`.** No module of `noworkflow` imports it (a premise in
  `tests/premises` holds that); the `dev` group's copy serves only
  `test_import_smoke.py`, and the wheel is built by the `[build-system]`
  setuptools, which is another version — `uv build` in the `checks` job is
  what proves the build.
- **The other Python forks of the lock.** The local suite runs on one fork;
  the matrix runs the others, and the oldest leg is the one where a fix may
  be missing.
