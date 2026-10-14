---
name: safe-refactor
description: Measures the effect of a change locally, comparing the test suite before and after it. Use when refactoring, updating a dependency, fixing a bug or implementing a feature — whenever "what I changed" has to be separated from "what was already like this".
---

# Safe refactoring (local)

Measures the change instead of trusting it: runs the suite **before**, makes
the change, runs it **after** and compares. It is the same reasoning as
`golden-run`, but with the local suite in place of the `now` command run end
to end — cheaper and faster, and therefore the first resort. Escalate to
`golden-run`, `python-matrix` or `rebuild-vis` when the suite does not reach
what changed.

## Steps

### 1. If the change comes from outside, start with the changelog

In an upgrade of a dependency, **the changelog is what defines where to look**
— not the other way round. Without it you map what you imagine; with it, you
map what changed. That is why it comes before everything: before mapping the
code, before writing a test, before touching any line.

(In a refactoring or a feature there is no changelog: start at step 2.)

Read at the right level: **the migration guide and the release notes**, not
the complete CHANGELOG of each package. What matters are the changes of
behavior and the removals, not the new optional features.

**Look first for the library's migration page, and only fall back to the
changelog if it does not exist.** A large project keeps one, versioned and
written for whoever is upgrading (SQLAlchemy's "What's New" per series, for
example); others keep the same thing in an `UPGRADING.md` or `MIGRATION.md`
in the repository, in an "Upgrade" section of the README or in the body of the
GitHub release. The explicit search is worth it before opening the changelog:
that page brings the **what to do** next to the change, which the changelog
only mentions.

Two cautions when using the guide:

- **It is cumulative.** Skipping versions obliges you to read the guides of
  the intermediate ones too; the one of the target series assumes the previous
  ones were applied.
- **It talks about the library, not about this project.** What it lists as
  "do this" still goes through the directed search below: a good part does
  not apply, and that is precisely what shortens the work.

For each item, do a directed search in the code. Most will not apply, and that
is a result: it shortens the list of what needs to be tested by hand.

**The changelog says the intention; the diff says what changed.** When an item
seems to touch the project, read the diff of the dependency itself before
concluding — `gh api repos/<owner>/<repo>/compare/<old-tag>...<new-tag>`
returns the commits and the patch. The tag names come from `gh api --paginate
repos/<owner>/<repo>/tags --jq '.[].name'` — `--paginate`, because the first
page holds the newest tags only and the series this project pins may be far
down — and they do not always carry a `v`. An entry that announces "we added
X" may be logic that merely **moved**, with no effect on anything; the text
alone does not distinguish the two. When `gh api` does not serve — a package
outside GitHub, a tag that does not match the published version, a filtered
network — what is left is comparing the installed source of the two versions
in uv's cache:

```bash
find "$(uv cache dir)/archive-v0" -maxdepth 2 -iname "<name>-<version>.dist-info"
```

The directory that holds the `.dist-info` is the unpacked wheel. The name on
disk is the wheel's, with `-` turned into `_` (`python_docx-…` for
`python-docx`) and in whatever case the wheel was built with, hence `-iname`.
It is less than the repository diff: a wheel brings only what the package
ships — no tests, often no changelog, never a commit message — and the old
version is only there while the cache keeps it. `uv run --with "<pkg>==<old>"
python -c "import <pkg>"` puts it back without touching the project's
environment.

**Two traps in this step:**

- **An empty search is not evidence.** If you search for a pattern and find
  nothing, confirm that the pattern exists somewhere in the project. Searching
  for `Session.execute` and finding nothing only means something after knowing
  that the project calls `Session` at all.
- **Execute instead of deducing.** Reading the code suggests whether a path is
  reachable; running it proves. A `uv run python -c` of three lines, or a
  five-line script traced in a scratch directory (`cd <scratch> && uv run
  --project <checkout> now run script.py`), settles in seconds what reading
  leaves at "probably not".

Each risk that survives these two checks becomes a **test**, not a note.

The mechanics of the upgrade itself — one package at a time, the version that
was actually resolved in `uv.lock`, the audit gate — are in `dependencies`.

### 2. Map the reach in the code

What this code touches, and **what of it do the tests not execute?** Look for
branches by Python version, by operating system, by content engine (the suite
pins `plain`; the git engines never run in it), a bare `except` that swallows
the failure so the path past it runs on the user's machine but never fails
in a test, code only reached through the `now` command as a process, the
vis, the Jupyter magics and the kernel — the blind spots listed in
`AGENTS.md`. `uv run pytest --cov --cov-report=term-missing` prints, per
module, the lines the suite never reaches (`coverage.xml` and `.coverage`
land in the checkout and are ignored by git). High coverage does not mean
that the path you are about to change is exercised.

### 3. Cover the gaps *before* changing

Write the missing tests **against the current behavior**, and confirm that
they pass on the old code. That order is what makes them a safety net;
written afterwards, they merely describe what you just did.

Where a test lives — this is the one place that says it, and the other skills
point here:

- The behavior of the collector is a method of a `CollectionTestCase`
  (`self.script(...)`, `self.execute()`, the `find_*` and `assert_*` helpers)
  under `src/noworkflow/tests/prov_execution/` or `prov_definition/`.
- A model's behavior is its doctest, in
  `src/noworkflow/now/persistence/models/`.
- A command, an export or a store on disk is a test of the e2e harness under
  `src/noworkflow/tests/e2e/` once it exists; until then it is a `cd
  <scratch> && uv run --project <checkout> now run script.py` recorded in the
  PR with its output, with invented values (`AGENTS.md`, "Sensitive data").
- A method added to an existing class needs nothing else. **A new test class
  is also imported and added to its suite in
  `src/noworkflow/tests/__init__.py`** (and exported by the package's
  `__init__.py`): that is how `run_tests.py` finds it; pytest finds it by the
  file name alone, and the two counts diverge until it is done.

When the path is unreachable in the test environment (a git content engine,
the Jupyter kernel), a test with a double fixing the APIs it depends on is
still worth it — it does not prove the behavior, but it catches signature
drift.

### 4. Check that the test is not empty

Break the code on purpose, confirm that the test fails **on the expected
example and by the expected message**, and undo. It holds for the test you
just wrote and for the one you assume already covers the change. A test that
passes both ways protects nothing. It costs seconds.

Three ways this check lies:

- **Simulating the old version from memory.** In an upgrade, "how it was
  before" is not rebuilt from memory or from the changelog: **the code of the
  previous version is the only valid simulation** — `uv run --with
  "<pkg>==<old>" pytest ...` runs the suite with that version layered over the
  project's environment, and a worktree at the merge-base or at the previous
  tag (`git worktree add <outside>/nw-base <ref>`, where `<outside>` is a
  directory outside the checkout — the session scratchpad, or the checkout's
  parent; inside the checkout it dirties `git status`) does it for a change
  of this repository. Replacing the new method with a hand-written approximation
  produces a version that never existed — and the red it gives "confirms" an
  imaginary old behavior.
- **Unrepresentative sabotage.** Damaging a part the test does not depend on
  proves nothing. If the chosen data does not traverse the altered path — a
  script *without* a file access to test the hash of written files — the
  store is produced and the test passes with the sabotage in place. Build the
  data so that only the complete path produces the expected result: a
  distinctive value typed in the script and checked in the store.
- **Red for the wrong reason.** Counting failures is not enough; read the
  message. An `ImportError`, a `SyntaxError` in the traced script, a
  `pyposast` node the version does not support, and an `open` wrapper leaked
  from the previous test all show up as red and pass for successful sabotage
  — and then you conclude the test protects something it does not even see.

### 5. Baseline

Run the whole suite on the code **without the change** and note three
numbers: tests, failures and duration. The last line of pytest has them —
`N passed, M skipped, K xfailed in Ts` — and the count that matters is passed
+ skipped + xfailed + xpassed, the same the CI compares with `min-tests`.

This is not a formality. Without a baseline, a failure after the change is
ambiguous — it may already have been broken. And if the baseline comes out
red, **fix the environment first**: `uv sync --locked` (the `.venv` may be
behind the lock), `uv lock --check`, and a `.noworkflow/` or `.last_trial`
in the checkout left by a leaked run, which `AGENTS.md` says is never
committed.

A bug that is specific to a Python version is measured on that version, with
the same baseline there: `uv run --isolated --python <version> pytest`.
**`--isolated` is not optional**: without it, `uv run --python <version>`
deletes `.venv` and recreates it on that interpreter, every later `uv run`
in the session runs there without saying so, and `uv sync` keeps it — only
`uv sync --locked --python <original>` brings it back. The loop over the
versions is `python-matrix`.

### 6. Change in small steps

One step, one suite, one commit — by the maintainer. If something breaks, the
commit points to the cause. For dependencies, the rules are in
`dependencies` — in particular the one of checking the version that was
actually resolved in `uv.lock`.

### 7. Compare, and compare the number of tests

Do not look only at "0 failed". **Compare the count with the baseline's.** A
green suite with fewer tests means tests disappeared — a module that no
longer matches `python_files`, a doctest that left a docstring, a
`parameterized` list that lost an entry. It vanishes with the same effect as
a regression, and without an alarm. CI fails a leg below `min-tests`; locally,
the baseline is the floor, and tests added raise `min-tests` in
`.github/workflows/ci.yml` and in `experimental.yml` in the same PR.

**A skip does not lower the count**: skipped is part of it, so a test that
starts skipping keeps the total and only shows in the split between passed
and skipped and in the `-ra` lines. Compare the three numbers of the last
line with the baseline's, not their sum alone.

When `src/noworkflow/tests/__init__.py` changed, compare the two runners as
well: `uv run python run_tests.py` prints `Ran N tests`, and N must equal
pytest's count. An import dropped there shrinks only the suite that
`run_tests.py` builds by hand — pytest collects by file name and does not
read those imports — so a difference between the two is what tells.

### 8. Interpret according to the nature of the change

Here the criterion changes, and you are the one who decides:

- **Refactoring** — the behavior should be identical, so *any* difference is a
  defect. No difference is the expected result.
- **Bug fix** — the expected difference is exactly the corrected behavior. Any
  other is a regression.
- **Feature** — the expected difference is the new behavior, and the old code
  should go on the same.

In the three cases, **declare before running which differences you expect**
— in a refactoring the list is empty, and writing it empty is already the
declaration. A characterization test that turns `XPASS(strict)` is a
difference like any other: it goes on the list beforehand, or it is a
surprise to explain. Without that list made in advance, it is easy to look at
an unexpected difference and rationalize it as intentional.

## Running the suite in practice

- **From the repository root**: `uv run pytest`. From a subdirectory
  the `testpaths` of `pyproject.toml` do not apply, the doctests of the models
  and of the utils are not collected, and the count is not comparable.
- Inside the sandbox, uv's cache is not writable and every `uv run` dies
  before pytest starts. With the `.venv` already in sync (`uv sync --locked`,
  outside the sandbox if it has to be), `UV_CACHE_DIR=<scratchpad>/uv uv run
  --no-sync pytest` runs the suite inside it; the same prefix serves
  `run_tests.py` and `now`.
- `-x` stops at the first failure, `-k <expression>` selects by name (the
  doctests of the models too), and a node id
  (`src/noworkflow/tests/prov_execution/test_stmt_execution.py::TestStmtExecution::test_name`)
  runs one test. `-ra` is already in the configuration, so the skips come
  with their reason; `-q` shortens the output of an interactive run.
- **In the background, do not buffer.** `... | tail -N` **hides everything
  until the end** — `tail` only prints when the pipe closes, so the output
  file stays empty the whole run and there is no way to follow it or to see
  where it got stuck. Redirect the output to a file in the session scratchpad
  and read it as it grows, and run with `-v`: it is the only verbosity that
  writes one line per test, flushed as each one finishes; with `-q` or the
  default the file holds dots, and a stuck run cannot be located.
- A run far beyond the baseline's duration is stuck, not slow: the last test
  name in the output file says where. Kill it and look there.
- After the run, `ls -d .noworkflow .last_trial` in the checkout: both are
  gitignored, so `git status` is blind to them, and either one present means
  a test leaked — it is the test that is fixed, not the file that is removed
  by hand.

## When the suite is not enough

Escalate when the change touches what the local tests structurally do not
reach — the list is "Blind spots of the suite" in `AGENTS.md`:

- `golden-run` for the `now` command as a process, the stores written to
  disk, the exports and the vis served: the same corpus on both versions, and
  the normalized output compared.
- `python-matrix` for a construct that the AST of one version has and another
  does not, and for path separators and encodings on Windows and macOS.
- `rebuild-vis` for anything under `src/frontend`.
- The rest of that list is probed by hand, and what you ran and what came out
  goes into the PR.
