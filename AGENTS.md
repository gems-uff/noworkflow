# noWorkflow — instructions for agents

noWorkflow captures the provenance of Python scripts without changes to the
script: the `now` command runs the script, records what it defined, executed
and read or wrote, and stores everything in a `.noworkflow/` directory next to
it. The package lives under `src/noworkflow/`, the Flask visualization and the
Jupyter extension are built from `src/frontend/`. Versions of Python and of
the dependencies come from `pyproject.toml`, `uv.lock` and
`src/noworkflow/resources/version.txt` — do not reproduce them here.

## Existing documentation

Before writing a procedure, check what already exists:

- `README.md`: installation and the usage of every command.
- `CONTRIBUTING.md`: the contribution cycle (issue, branch, commit, PR).
- `SECURITY.md`: how security problems are reported.
- `src/frontend/development.md`: building the visualization bundle and the
  Jupyter extension.
- The [wiki](https://github.com/gems-uff/noworkflow/wiki): tutorial videos
  and related material.

Point to these pages instead of duplicating them. If something there is out
of date, fix it there.

## Working conventions

- One issue, one `issue_NNN` branch, always based on `main`. The cycle is in
  `CONTRIBUTING.md`.
- **The commit subject starts with `Issue #NNN: `**, with the number of the
  branch's issue. GitHub turns the number into a link, and the subject is what
  appears in the commit list and in `git log --oneline`. After the prefix
  about 60 columns remain: imperative mood, no trailing period, and the why in
  the body. The only commit without the prefix is one a maintainer puts
  directly on `main` for work that belongs to no issue.
- **Reference the issue by the prefix alone, never with `Fixes` or
  `Closes`.** Those words close the issue as soon as the commit reaches `main`,
  and closing is a release decision: the version is the milestone, and the
  issues of a milestone are closed when that version is released.
- **Security work follows the same cycle as everything else.** noWorkflow runs
  on the user's own machine, never as a service, so a public issue does not
  expose anyone. Open the issue, describe the problem plainly, and prove the
  fix with a test named after the property it guarantees (for example
  "rejects a restore target outside the project directory") that is red before
  the fix and green after it. See `SECURITY.md`.
- **Definition of done:** `uv run pytest` green from the repository root;
  the test count at or above the floor in `.github/workflows/ci.yml` and
  `experimental.yml` (`min-tests`), **and the floor goes up in the same PR
  that adds tests**;
  `uv run ruff check .` clean; CI green at the tip of the branch; and, whenever
  `src/frontend` changes, `src/noworkflow/now/vis/static/dist/bundle.js`
  rebuilt and committed in the same commit (the `frontend` job rebuilds it
  and fails on any difference).
- Run the suite from the root. It runs from a scratch directory (see the root
  `conftest.py`), so nothing it writes lands in the checkout; if you ever see
  a `.noworkflow/` or `.last_trial` in the tree, a test leaked, and neither
  is ever committed.
- **Do not commit on your own.** Leave the change in the working tree, show
  the diff and the result of the suite, and wait for whoever drives the
  session. Commit, tag, push and new branches are theirs, also in step-by-step
  work where "one commit per step" seems to authorize committing alone.
- Documentation and comments say **"the maintainer"**, never a person's name:
  the role outlives whoever holds it.
- **Before opening an issue, search the existing ones, closed included:**
  `gh issue list --state all --search "<term>"`, in English and in Portuguese
  (older issues and comments are in both). When a related issue exists, also
  read the commits that mention it (`git log --all --grep="#NNN"`): that is
  where the product decision, the reverted attempt or the partial fix is.
- **An issue is born with its Type set:** `gh issue create --type Bug`, or
  `gh issue edit N --type Feature` afterwards. The three values are `Bug`
  (the tool does badly what it already does), `Feature` (a new capability or a
  requested change of behavior) and `Task` (dependency, infrastructure,
  documentation, refactoring, test). Between Bug and Feature, look at the
  effect on the user, not at the size of the fix: lost provenance, an ignored
  flag, a crash, data exposed to the wrong place are Bugs even when fixing
  them means building what does not exist yet.
- **Type says what the issue is, the milestone says in which version it
  ships, labels say area and resolution.** Labels in use: `collection` (area),
  `question`, `duplicate`, `invalid`, `wontfix` (resolution), `good first
  issue`, and the ones Dependabot sets. Do not create a label for something a
  Type or a milestone already expresses.
- **Do not claim that existing provenance stores still open without opening
  one.** There is no schema migration: a change to the models or to the
  content engines either keeps old `.noworkflow/` directories readable or
  breaks them, and only a real store created by the previous version tells
  which. Write what you measured; the release note and the version number
  follow from it.
- **Everything reachable from the CLI counts as in use.** Do not condition a
  fix on "if anyone uses this command" or "if this flag matters": there is no
  dispensable command, and the question only serves to shrink what gets
  verified.
- **Before keeping a fact in memory, ask: would another agent, on another
  machine, with only `git clone`, get it?** If so, it is a convention and
  lives versioned, here or in the skill it belongs to. Local memory does not
  cross machines: keep in it only what dies with the machine (a local path,
  the sandbox behavior, the state of a session).
- **Do not duplicate in memory what is already versioned.** The two copies
  diverge at the first change, and the one that misleads is the one nobody
  reviews. If the fact is in the repository, the right memory is none.
- **When a command fails because the sandbox blocked it, try again outside
  the sandbox.** That triggers the permission question; the human decides.

## Repository skills

In `.claude/skills/`. Claude Code discovers them by itself, and each one
carries its own description; this index is for humans and for other agents,
in the order of the cycle.

- `review-pr` — takes a pull request from start to finish. **Start here**; it
  points to the others.
- `merge-downstream` — brings `main` into an issue branch and checks that it
  came in whole.
- `dependencies` — declares a dependency in `pyproject.toml`, judges whether
  a pin still has a reason, and carries out an update.
- `prove-candidate` — gives a verdict to a suspected defect: confirmed,
  refuted or plausible.
- `safe-refactor` — measures a change by the local suite, before and after.

### A skill is a procedure, not a logbook

When writing something learned into a skill, the test is: **would a future
run do something different because of this line?** The mechanism and the
consequence pass ("`now` prints the error and may still exit with 0, so check
the output, not the status"). *When* it was measured, in which version, which
issue found it, and that the problem is already fixed do not pass: `git log`
keeps that, and in a skill it only accumulates.

That context has a place to go: **a comment on the issue**. Measurements
before and after, the version where the defect appeared, the path a run used
to reproduce it, the trap that cost time — all useful, and there it stays
next to the work that produced it, within reach of whoever reopens the
subject.

Two practical consequences:

- **Do not stack rounds.** A new note on the same subject **replaces** the old
  one; it does not become a paragraph "already fixed, do not look for it".
  A list of known noise is revised in the round that uses it, and an entry
  that disappeared leaves in the same commit.
- **An example with a version number rots.** Prefer the generic form; when
  the concrete value is necessary, cite the file instead of copying the
  value.

A reusable script is legitimate skill content and lives **in the skill's
directory**, never referenced by the path of a dated capture, which is
disposable.

## Dependencies

One dependency per step, to the latest patch of the same series; **never a
major or minor bump as a side effect** of something else. The runtime set is
in `[project.dependencies]`, the tools in `[dependency-groups]`, and
`uv.lock` is the truth that CI installs with `uv sync --locked`: a change to
`pyproject.toml` without `uv lock` fails `uv lock --check` before anything
else runs. Known advisories that a pin keeps alive are listed, with the reason
and the issue that removes them, next to the `pip-audit` step in
`.github/workflows/ci.yml`; never add one without both. The frontend has its
own lock in `src/frontend/package-lock.json`, and any change there means
rebuilding the bundle. The rest — judging a pin, the versions the lock
resolves per Python version, the audit, the Dependabot PRs, the npm lock and
the pinned actions — is in the `dependencies` skill.

## Blind spots of the suite

The suite imports `noworkflow` and runs the collector in-process, against
in-memory stores. Code it never executes:

- **The `now` command as a process:** argument parsing, exit codes, what goes
  to stdout and stderr, `now run` on a script in a real directory with a real
  `.noworkflow/`. CI has a smoke test (`now run` and `now list` on a
  one-line script) and nothing more.
- **`now vis`:** the Flask routes, the push/pull/experiment endpoints, the
  JavaScript. The `frontend` job only proves that the committed bundle matches
  the sources and that the extension type-checks.
- **Windows and macOS:** the matrix runs on Ubuntu for every Python version;
  macOS runs one version, and Windows is an experimental leg that does not
  block. Path separators and encodings differ there.
- **Syntax per Python version:** the collector rewrites the AST, and each
  Python version adds nodes. A construct the examples do not use is not
  covered, on any version.
- **The exports** (`prolog`, `prov`, `dataflow`, `ast`, `prospective`): no
  test compares their output against a reference.
- **The optional content engines** (`puregit`, `pygit`, `gitdb`,
  `dulwich`): the suite pins the `plain` engine; the others open a git
  repository on connect.
- **Jupyter:** the magics (`%now_run`, `%now_ip`), the kernel in
  `src/noworkflow/kernel/` and the lab extension have no automated test.
- **`push`, `pull`, `demo`, `restore`:** a remote server, the demo projects
  and the files a restore writes are exercised by hand or not at all.
- **Deployment provenance:** what gets recorded about the environment
  (`now show -e`) depends on the machine; no assertion covers it.

When a change touches one of these, run it by hand and write what you ran,
and what came out, in the PR.

## Reproduction traps

- **Inside `now run`, `open` is not `open`.** The collector replaces
  `builtins.open`, `io.open`, `codecs.open` and `os.open` with wrappers
  (`src/noworkflow/now/collection/prov_execution/execution.py`) and nothing
  restores them when the script finishes; a script that compares them with
  the originals, or a test that runs the collector and then opens a file, sees
  the wrappers. The originals are kept in
  `src/noworkflow/now/persistence/content/safeopen.py`.
- **The suite never writes a store to disk.** `noworkflow.tests` connects the
  persistence layer to in-memory stores on import
  (`src/noworkflow/tests/helpers/persistence.py`). A defect in the SQLite
  file, in the content directory or in anything that only exists on disk is
  reproduced with a real `now run` in a scratch directory (`cd <scratch> &&
  uv run --project <checkout> now run script.py`: `now` is not on the PATH,
  and `uv run` only finds it from inside the checkout), never with the suite.
- **Trial ids are UUIDs**, not the integers of older versions. A reproduction
  that passes `1` as a trial id is talking to `sequence_key`, not to the id.
- **A version-specific bug is proven with that version:** `uv run --isolated
  --python 3.8 pytest ...` (uv installs the interpreter; without `--isolated`
  it recreates `.venv` on that version and leaves it there). "It works here"
  on another Python proves nothing.
- **`now` prints an error and may still exit with 0.** Several commands
  report failure through `print_msg` and return normally; check the output,
  not only the status.
- **Two trials of the same script differ by design:** the environment table
  records the whole `os.environ`, the start time, the pid. A diff that shows
  only those is "no change".
- **`now demo` depends on `sys.argv[0]` being the console script:** it calls
  `now` through the shell with that path (`src/noworkflow/now/cmd/cmd_demo.py`).
  Through `python -m noworkflow` or from a test, `sys.argv[0]` is something
  else and the demo cannot run itself.
- **On arm64 Macs greenlet never installs,** because SQLAlchemy's marker does
  not select it there; a SQLAlchemy or greenlet build failure only shows up on
  x86_64, so a green `uv sync` on a maintainer's Mac is not evidence for the
  CI legs.

## Patches of third-party internals

Points where noWorkflow depends on the internals of Python or of a library,
and therefore the first suspects when an upgrade breaks something:

- `src/noworkflow/now/collection/prov_execution/execution.py`: replaces the
  four `open`s with wrappers, injects `__noworkflow__`, `now_tag_cell` and
  `now_tag_variable` into `builtins`, and inserts a finder at the front of
  `sys.meta_path` around the `exec` of the script. The finder is removed only
  on the normal path; a script that raises leaves it installed.
- `src/noworkflow/now/persistence/content/safeopen.py`: keeps the original
  `open`s and restores them in a context manager; also pokes at
  `__builtins__["open"]`, which is a dict or a module depending on who imports
  it.
- `src/noworkflow/now/collection/prov_deployment/py2module.py`: the Python 2
  module finder, written against `imp`. It does not parse as Python 3 and is
  excluded from lint, coverage and SAST; the Python 3 branch of
  `prov_definition/definition.py` never imports it.
- `src/noworkflow/now/ipython/magics/now_run.py`: swaps `sys.argv`,
  `sys.path[0]` and `sys.modules["__main__"]` for the shell's user module
  while the cell runs, and swaps them back by hand.
- `pkg_resources` (`prov_deployment/deployment.py` and `utils/functions.py`):
  the reason for the `setuptools<72` pin; the migration to
  `importlib.metadata` is tracked in the open PR that removes the pin.
- SQLAlchemy 1.4: `relational_database.py` uses the 1.4 declarative and
  session API, and the pin keeps the 2.0 series out.
- `pyposast` is a sibling project (`JoaoFelipe/pyposast`): the AST positions
  that the collector relies on come from it, and a fix there only reaches here
  through a release of that package.
- `future` (`future.utils.viewitems`, `viewvalues`) is still imported in
  about forty modules, including `patterns/` and the tests.

## Sensitive data

A provenance store records the whole environment of the machine that ran the
script: every variable in `os.environ` (`PATH` included), the user name, the
hostname, the pid, the OS release. `now show -e` prints it, `now export
prolog` emits an `environment/3` fact per attribute, and the vis serves it
too. **Never paste a real `now show -e` output, a real
Prolog export, a real `environment.json` or a real `.noworkflow/` into an
issue, a PR, a skill or a golden file.** Reproduce with the test corpus, and
when an environment attribute matters, name it ("the `USER` attribute")
instead of quoting the value. The same goes for a user's store sent with a
bug report: look at it locally and describe what you found.

## Language

Everything versioned is in English: code, comments, docstrings, docs, skills,
issues, PRs, commit messages. Discussion with the maintainer may happen in
Portuguese; what gets written to the repository is translated.

## Python versions

The supported range is `requires-python` in `pyproject.toml`; the versions
that are actually run are the legs of `.github/workflows/ci.yml` (blocking)
and `.github/workflows/experimental.yml` (observed, not blocking). A version
is supported when it has a blocking leg, and a classifier in
`pyproject.toml` is added only then. Locally, `uv run --isolated --python
<version> pytest` runs the suite on any of them without touching `.venv`.
