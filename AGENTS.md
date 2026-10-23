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

- `README.md`: installing noWorkflow as a **user** (`pip install`) and the
  usage of every command. It is not how to set up a development
  environment.
- `CONTRIBUTING.md`: the development environment (what to install on a new
  machine, and how to set up `.venv`), the commands to run locally, and the
  contribution cycle (issue, branch, commit, PR).
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
  the body. Two commits go without the prefix: one a maintainer puts directly
  on `main` for work that belongs to no issue, and a Dependabot update a
  maintainer integrates, which keeps the bot's subject (`Bump <package> from
  <a> to <b>`) and gains the PR's number at the end, `(#NNN)`, when the
  maintainer rewrites it.
- **An issue is closed when it is integrated into `main` with nothing left
  to do.** `main` is the baseline and releases are cut from it, so integrated
  and finished is done; an issue delivered in part stays open. Which issues
  a release ships comes from its commits: the `Issue #NNN:` prefixes in
  `git log <previous tag>..main`.
- **Reference the issue by the prefix alone, never with `Fixes` or
  `Closes`.** Those words close the issue as soon as the first such commit
  reaches `main`, while an issue often takes several commits, and whether
  anything is left is the maintainer's call (`gh issue close <N> --reason
  completed`).
- **Security work follows the same cycle as everything else.** noWorkflow runs
  on the user's own machine, never as a service, so a public issue does not
  expose anyone. Open the issue, describe the problem plainly, and prove the
  fix with a test named after the property it guarantees (for example
  "rejects a restore target outside the project directory") that is red before
  the fix and green after it. See `SECURITY.md`.
- **Definition of done:** `uv run pytest` green from the repository root;
  the test count at or above the floor of every leg (`min-tests` in
  `.github/workflows/ci.yml`, `pre-release.yml` and, while it exists,
  `experimental.yml`, the one in
  `flaky.yml` and the ones of the `paper-example`, `vis-browser` and
  `engines` jobs;
  the reference leg also
  counts the goldens, which the other legs deselect), **and the floors go
  up in the same PR that adds tests**;
  `uv run ruff check .` clean; the bandit step of `checks` green, so every
  site bandit flags either carries `# nosec Bxxx` with the reason on the line
  above (intended) or has an issue and its entry in `bandit-baseline.json`
  (real; the entry leaves with the fix), as "Running locally" in
  `CONTRIBUTING.md` says; CI green at the tip of the branch; no new
  CodeQL alert in the PR, or each one fixed or explained there for a
  maintainer to dismiss (the `CodeQL` check, described in "What a pull
  request needs" in `CONTRIBUTING.md`, and read as step 6 of `review-pr`
  says); for a commit that reaches `main` without a PR, no open alert of
  `main` created by its analysis, once that analysis has finished (`gh api
  "repos/gems-uff/noworkflow/code-scanning/alerts?ref=refs/heads/main&state=open&sort=created&direction=desc"`
  lists the newest first); and, whenever
  `src/frontend` changes, `src/noworkflow/now/vis/static/dist/bundle.js`
  rebuilt and committed in the same commit (the `frontend` job rebuilds it
  and fails on any difference). The `bundle.js.map` the build rewrites is
  not committed: it embeds the absolute path of the checkout. The commands
  are in "The frontend" in `CONTRIBUTING.md`.
- Run the suite from the root. It runs from a scratch directory (see the root
  `conftest.py`), so nothing it writes lands in the checkout; if you ever see
  a `.noworkflow/` or `.last_trial` in the tree, a test leaked, and neither
  is ever committed. The leak detector in the same file fails a test that
  leaves such a file, or the collector's process state (the `open`s, the
  builtins, `sys.meta_path`, `sys.argv`, `__main__`, the cwd), or a child
  process it started and never waited for, behind; it kills that child.
  `NOW_LEAK_CHECK=warn` only reports while you investigate.
- **Installing software on the machine needs the human's go-ahead.** That
  covers uv, a Python interpreter, Node, a container engine, Rosetta, a
  system package. uv counts too when it downloads an interpreter that is
  missing, which `uv sync --python`, `uv run --python` and `uv python
  install` do (`uv python list --only-installed` shows what is there).
  Filling `.venv` from `uv.lock` (`uv sync --locked`) or `node_modules`
  from the npm lock (`npm ci`) stays inside the checkout and is not an
  install on the machine. To prepare an environment, check first what is
  installed, and at which version, against "Development environment" in
  `CONTRIBUTING.md`; then propose the commands, what each one costs (disk,
  memory, a background VM) and what it unlocks, and wait. Never settle for a
  worse workaround (a CI round trip instead of a local container, a check
  left unrun) without saying that an install would avoid it.
- **Do not commit on your own.** Leave the change in the working tree, show
  the diff and the result of the suite, and wait for whoever drives the
  session. Commit, tag, push and new branches are theirs, also in step-by-step
  work where "one commit per step" seems to authorize committing alone.
- Documentation and comments say **"the maintainer"**, never a person's name:
  the role outlives whoever holds it.
- **Before opening an issue, search the existing ones, closed included,**
  with [issuefinder](https://github.com/gems-uff/issuefinder) over the draft
  of the new one: `uv run --project ../issuefinder issuefinder query -f
  <draft>` from the checkout. It matches by meaning across English and
  Portuguese (older issues and comments are in both) and by exact tokens (an
  error message, a name, a path), and it syncs the issues before answering.
  It lives in a sibling directory of the checkout; when it is missing, clone
  it there (`gh repo clone gems-uff/issuefinder ../issuefinder`). Its
  environment and its model (about 3 GB) land outside the checkout, so
  setting it up is an install and needs the human's go-ahead; until then,
  search with `gh issue list --state all --search "<term>"`, in both
  languages. When a related issue exists, also read the commits that mention
  it (`git log --all --grep="#NNN"`): that is where the product decision, the
  reverted attempt or the partial fix is.
- **An issue is born with its Type set:** `gh issue create --type Bug`, or
  `gh issue edit N --type Feature` afterwards. The three values are `Bug`
  (the tool does badly what it already does), `Feature` (a new capability or a
  requested change of behavior) and `Task` (dependency, infrastructure,
  documentation, refactoring, test). Between Bug and Feature, look at the
  effect on the user, not at the size of the fix: lost provenance, an ignored
  flag, a crash, data exposed to the wrong place are Bugs even when fixing
  them means building what does not exist yet.
- **Type says what the issue is, the milestone (when there is one) says
  which version the work is aimed at, labels say area and resolution.** Labels in use: `collection` (area),
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
  this machine's sandbox settings, the state of a session).
- **Do not duplicate in memory what is already versioned.** The two copies
  diverge at the first change, and the one that misleads is the one nobody
  reviews. If the fact is in the repository, the right memory is none.
- **When a command fails because the sandbox blocked it, try again outside
  the sandbox.** That triggers the permission question; the human decides.
- **Three failed attempts at the same goal: stop, explain, recommend.** When
  the same goal fails three times in a row (a test or a CI leg that stays
  red, a command that keeps failing, a change the human rejects), do not
  start a fourth variation. Stop and tell the human what was tried, why each
  attempt failed, and what to change for the next one: a stronger model
  among those available (Sonnet → Opus → Fable), a higher reasoning effort,
  or ultracode on (or off, when the fan-out is what keeps failing). When the
  cause is not the model (a missing tool, the sandbox, the network, an
  ambiguous requirement), say that instead: a stronger model would fail the
  same way. Switching is the human's decision.

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
- `golden-run` — runs the same corpus through `now` on two versions and
  compares what they print, what they record and what the vis serves.
- `python-matrix` — runs the suite on every supported Python and keeps the
  CI matrix in step with python.org.
- `rebuild-vis` — rebuilds the vis bundle from `src/frontend`, proves that
  the committed bundle matches its sources, and smoke-tests `now vis`.
- `release` — cuts a version from an integrated `main`: the bump, the wheel,
  the tag, PyPI and the GitHub release.

### A skill is a procedure, not a logbook

When writing something learned into a skill, the test is: **would a future
run do something different because of this line?** The mechanism and the
consequence pass ("inside `now run`, `open` is the collector's wrapper, so a
test that runs the collector and then opens a file sees the wrapper"). *When*
it was measured, in which version, which
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
major or minor bump as a side effect** of something else. The exception is a
campaign: the tail (transitives, tools, what the build compares byte for
byte) moves in one batch per level with a hard ceiling, bisected when red,
while the core still moves one package per step; the procedure is "A
campaign" in the `dependencies` skill. The runtime set is
in `[project.dependencies]`, the tools in `[dependency-groups]` (with
`paper`, what the tests of the paper's running example import,
`browser`, what the tests of the vis in a browser import, and `engines`,
the optional content engines), and
`uv.lock` is the truth that CI installs with `uv sync --locked`: a change to
`pyproject.toml` without `uv lock` fails `uv lock --check` before anything
else runs. Known advisories that a pin keeps alive are listed, with the reason
and the issue that removes them, next to the `pip-audit` step in
`.github/workflows/ci.yml`; never add one without both. The frontend has its
own lock in `src/frontend/package-lock.json`, and any change there means
rebuilding the bundle. **A Dependabot PR is never merged as it stands:**
`main` is the baseline, and only what a maintainer tested reaches it. The PR
is its own record and needs no issue. A maintainer turns its branch into the
commit that will land — rebased on `main`, the bundle rebuilt in the same
commit for npm, the lock redone for uv — pushes it to the PR's branch so that
CI tests that exact commit, and with CI green fast-forwards `main` and pushes.
The rest — judging a pin, the versions the lock
resolves per Python version, the audit, the Dependabot PRs, the npm lock and
the pinned actions — is in the `dependencies` skill.

## Blind spots of the suite

Most of the suite imports `noworkflow` and runs the collector in-process,
against in-memory stores; the end-to-end tests (`src/noworkflow/tests/e2e/`)
run `now` as a process on a real store in a temporary directory. What
neither executes:

- **Commands the e2e tests do not run:** `vis` (the server; its routes run
  in process, see below), `push`, `pull`, `kernel`, `debug`, `evaluation`
  (its query options run through `clean`), and `demo` outside the reference
  leg (see below). For the commands they do run, only the flags their tests
  name are covered.
- **`now vis`:** the write routes (experiments, groups, annotations,
  remotes, the collaboration import and the files it receives) and push
  and pull against them (#256), in the server and in the JavaScript; the
  views the browser tests do not open (below). The read routes,
  `/db/query` included, run in process through Flask's test client
  (`src/noworkflow/tests/vis/`) on stores that `now run` builds in a
  temporary directory; the rows only push and pull create are added through
  the models or in SQL. There the `/commands/*` routes that start `now` run
  with `subprocess.run` replaced, so only the argv they build and how they
  answer are checked. The JavaScript and the server as a process run only
  in the `vis-browser` job of `ci.yml` (`src/noworkflow/tests/browser/`,
  marked `browser`, deselected on every other leg): `now vis` on a real
  port and the committed bundle in headless Chrome, through the history,
  a trial, the diff, the dataflow and the Prolog export (the only places
  where a `/commands/*` route runs a real `now`), the prospective graph,
  the database graph and the SQL editor. What those tests do not open (the
  modals of restore, push, pull and the remotes, the "generate prov" tab,
  the function activation diff, the exclusion of prior provenance, the
  downloads, the tooltips, the project page) runs nowhere. A PDF out of
  `flow.pdf` is checked only where Graphviz's `dot` is on the PATH, which
  the Linux and macOS legs install and the Windows legs do not, and
  `prospective.dot` is drawn for a handful of scripts. The `frontend` job proves that the committed bundle matches the
  sources, that the extension type-checks, that every frontend package
  lints clean (stylelint, prettier, eslint) and that the count of `tsc`
  errors of the vis does not grow. By hand, `golden-run` (step 4) and the
  smoke of `rebuild-vis` fetch the routes `read_store.py` lists from a
  corpus store, and `compare_vis.mjs` of `rebuild-vis` shows everything a
  new bundle changes against a base one, CSS and layout included, which
  the tests do not assert.
- **Windows and macOS:** a push runs the matrix on Ubuntu only, for every
  Python version. macOS and Windows run every version in `pre-release.yml`,
  by hand before a release. Path separators, encodings, processes and the
  shell differ there: a change that touches them runs `pre-release.yml` on
  its branch before it reaches `main`. The Windows legs keep the projects
  on Python's drive, so a project on another drive than the modules it
  imports (#294) runs nowhere.
- **Syntax per Python version:** the collector rewrites the AST, and each
  Python version adds nodes. The syntax corpus of the e2e tests
  (`corpus/syntax/`, `test_syntax_corpus.py`) traces one script per
  construct on every leg, and its marks are the map of what the collector
  cannot handle yet; a construct outside it and outside the examples is not
  covered, on any version.
- **What the oracle compares:** `test_oracle.py` runs each script of
  `corpus/oracle/` with plain Python and with `now run`, under the
  harness's synthetic UTF-8 environment and with the flags its cases name;
  an encoding the legacy locale chooses, another flag of `now run` or a
  construct no script uses is compared nowhere. Its process scripts compare
  what the children of a traced script print and write, never what the
  store records about them; the ones that need `os.fork`, `preexec_fn` or
  `os.posix_spawn` skip on Windows, and spawn and forkserver (#325, #334)
  run nowhere.
- **External processes and compiled code:** `test_external_processes.py`
  pins what the store records when a traced script starts a process (the
  call, and since #202 the files the child's command line names and the
  files it creates, as accesses of the call), and
  `test_compiled_modules.py` how an extension module of the standard
  library and a library loaded through `ctypes` are recorded (`_dbm` on
  POSIX, `winsound` on Windows, which only `pre-release.yml` runs), and,
  since #203, the program a launch runs (the interpreter, under the name
  the command line gives it) as a module row. What the external
  process tracer (`prov_execution/external.py`) does on Windows, where
  `subprocess` hands the audit hook one command-line string,
  `os.spawn*` is a launch and `shutil.which` resolves a program with the
  extensions of `PATHEXT`, runs only in `pre-release.yml`; the version
  probe runs on `python` in the suite and on `Rscript` and `cc` only in
  `test_beyond_python.py`; a child of
  `os.fork` or `multiprocessing` is not a launch and is tested as not
  recorded; the `strace` backend has no test anywhere until #206
  installs `strace` on a leg; and the kernel's own use of the tracer
  (around each cell, `kernel/shell.py`) runs nowhere, like the rest of
  the kernel. The leak detector sees the children of the pytest process
  only, never what a `now` run as a process leaves behind.
- **The exports off the reference leg:** goldens compare `prolog`, `prov`,
  `dataflow` and `prospective` on the reference leg only (Linux, the newest
  blocking Python); on every other leg nothing compares their output.
  `export ast` fails from Python 3.14 on (#241), so no golden compares it,
  and only a structural test checks it on 3.11 to 3.13.
- **The paper's running example off the reference platform:** the
  `paper-example` job replays it on Linux with the reference leg's Python
  only; the claims that depend on noWorkflow's numbering, and its goldens,
  are skipped anywhere else, and no other leg runs it at all. The same
  goes for the case study of the "Beyond Python" section
  (`test_beyond_python.py`), the only tests that run R and a C compiler:
  the job and the reference container install `r-base-core`, every other
  leg deselects `paper`, and a maintainer's machine without `Rscript`
  skips them. Its strace variant runs nowhere until #206 installs
  `strace` on a leg, and its two claims under rdtLite run only where the
  rdtLite package is installed in R, which no leg does.
- **The optional content engines** (`dulwich`, `pygit`, `gitdb`): only the
  `engines` job of `ci.yml` installs them (the `engines` group) and runs
  the tests marked `engines`, the contract tests of
  `src/noworkflow/tests/persistence/` on each of them and
  `e2e/test_optional_engine_stores.py`, on Linux with Python 3.14 alone
  (pygit2 has no wheel for 3.15 yet); no other Python and no other system
  runs them. The rest of the suite never runs with them installed: a new
  store without `--content-engine` would take one of theirs, and the
  in-process suite pins `plain`. The `pygit` name selects the distributed
  engine, which runs nowhere, and neither do the other process-based
  wrappers of `parallel.py` (#334); the tests run `sequential_pygit`.
- **`rules.pl` without SWI-Prolog:** the patterns tests compare each rule
  with its `rules.pl` twin over `now export prolog -r`, and the Prolog-fact
  tests read exports back, only where `swipl` is on the PATH; they skip
  elsewhere. In CI the legs of the `test` job and the `paper-example` job
  install it, and so do the Linux and macOS legs of `pre-release.yml`; its
  Windows legs do not.
- **Jupyter:** the magics run in an in-process IPython shell
  (`src/noworkflow/tests/ipython/`), never under a kernel: the kernel in
  `src/noworkflow/kernel/` is only imported (#315), so `now clean` never
  meets a notebook trial, and the lab extension has no automated test:
  only the type-check and the lint of the `frontend` job reach it, so an update of
  its packages (codemirror, `@jupyterlab/*`) is measured by nothing else.
  `%%dot` and the diagrams of `%now_schema` skip where
  Graphviz's `dot` is missing (the Windows legs of `pre-release.yml`),
  `%%now_prolog` without `pyswip`, which no
  leg installs, and the tagging helpers that import pandas where the
  `paper` group is not synced (it is in the reference container only).
- **`push`, `pull`, `demo`:** a remote server and the demo projects are
  exercised by hand or not at all; the exception is `demo 1` (marked `slow`),
  which the reference leg runs because it syncs the `demo` extra
  (matplotlib), and which skips on every other leg and on `uv sync --locked`
  alone.
- **Deployment provenance:** what gets recorded about the environment
  (`now show -e`) depends on the machine; the e2e tests assert only the
  names of a few attributes and the synthetic user, never the values.
- **What bandit does not see:** it reads the Python of `src/noworkflow`
  without the tests and the demo scripts (`[tool.bandit]` in
  `pyproject.toml`), and it resolves names within one file only, so a
  name imported from another module escapes it: the graph cache's
  `pickle.loads` (`models/graphs/structures.py`) takes `pickle` from
  `utils/cross_version.py`, and the B403 entries of that module are its
  only trace. A program named in a variable argv escapes B607 (the bare
  `now` of the vis routes), and no check flags a `subprocess` call without
  a timeout. The frontend and the workflows are CodeQL's.

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
- **The module table holds only modules imported for the first time.** A
  module already in `sys.modules` when the script starts never reaches the
  import finder, and `now` loads more than eight hundred before it (json
  through SQLAlchemy, subprocess through `utils/functions.py`), more or
  fewer by how it starts and by the interpreter's build (#380). A test of
  the module table imports a module measured absent at the top of a traced
  script, such as `_dbm`. Besides them, the table holds the program each
  launch runs and each library `ctypes` loads by a path (#203), named as
  the script names them; a program of the project is then a local module,
  which `now restore` puts back like an imported one.
- **A child of `os.fork()` in a traced script runs `now`'s epilogue** when
  it leaves through `sys.exit` or by returning: it stores the trial again,
  prints `[now]` lines and exits 0 (#375). A corpus script ends its forked
  children with `os._exit`, unless that is its subject, and bounds every
  wait on them.
- **The in-process suite never writes a store to disk.** `noworkflow.tests`
  connects the persistence layer to in-memory stores on import
  (`src/noworkflow/tests/helpers/persistence.py`). A defect in the SQLite
  file, in the content directory or in anything that only exists on disk is
  reproduced with an e2e test (`NowProject` in
  `src/noworkflow/tests/e2e/harness.py` runs `now` in `tmp_path` with a
  synthetic environment), or by hand with a real `now run` in a scratch
  directory (`cd <scratch> && uv run --project <checkout> now run
  script.py`: `now` is not on the PATH, and `uv run` only finds it from
  inside the checkout). In-process code that reads a store (the models, the
  patterns, the vis views) runs against a real one under the
  `connected_two_trials` fixture or `connected_to(path)`, which put the
  in-memory stores back afterwards.
- **`now run` writes the store next to the script** (or in `--dir`), not in
  the cwd, while the files the script opens by relative path resolve against
  the cwd. A store cannot be moved either: trials record absolute paths
  (`trial.path`, `module.path`), which a copy keeps pointing at the original
  directory. Build each store where it is used.
- **Automatic tags count the whole store:** the major goes up for every new
  code hash of any script, and the command line, flags included, decides
  the minor. An assertion on a tag needs a fresh store.
- **`python -m pytest` is not `uv run pytest`:** under `-m`,
  `sys.modules['__main__']` is pytest's own, and the two tests in
  `prov_execution/test_script.py` that assert its repr fail.
- **Every run of the suite has its own order** (pytest-randomly). A red that
  a rerun does not repeat may be the order, not the code: the header line
  `Using --randomly-seed=N` (absent under `-q`) and `--randomly-seed=N`
  replay it, `-p no:randomly` runs in file order. A test red under some
  seed depends on another test; the fix is that pair, never a fixed order
  for the suite. Under pytest-xdist (`-n 4`, as the CI legs run) the seed
  fixes the collection, not which worker runs what after what: replay a
  red that the seed does not repeat with `-n 0` and the seed.
- **Trial ids are UUIDs**, not the integers of older versions. A reproduction
  that passes `1` as a trial id is talking to `sequence_key`, not to the id.
- **A version-specific bug is proven with that version:** `uv run --isolated
  --locked --no-python-downloads --python <version> pytest ...` (without the
  flag uv downloads a missing interpreter, which is an install; without
  `--isolated` it recreates `.venv` on that version and leaves it there). "It
  works here" on another Python proves nothing.
- **`now` exits with a non-zero status when it fails, and reports the
  failure on stderr:** a usage error is argparse's (2); a failure a command
  foresaw is a `RuntimeError` that `main` reports (1); `now run` exits with
  the status plain Python would have given the script (the code of
  `sys.exit`, 1 after an uncaught exception), once the trial is stored;
  `now restore` exits with 1 when a file it was asked for was not
  restored. The exceptions are `push` and `pull`, which still print their
  failure (`Exporting trials failed`, `Error pushing`) on stdout and return
  normally (#256). Everything else `now` prints, the `-v` progress lines
  and the section headers of `show`, `list` and `diff` included, stays on
  stdout.
- **Two trials of the same script differ by design:** the environment table
  records the whole `os.environ`, the start time, the pid. A diff that shows
  only those is "no change". `src/noworkflow/tests/e2e/normalize.py` masks
  what differs between two identical runs; anything it leaves is a real
  difference, with one known exception: on Python 3.11 the order of the
  blocks `now diff` prints can change from run to run (#248: it iterates
  sets whose hash includes `None`, which is address-based before 3.12).
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
  `sys.meta_path` around the `exec` of the script, and removes it in a
  `finally`, whichever way the script leaves.
- `src/noworkflow/now/collection/prov_execution/external.py`: installs an
  audit hook (`sys.addaudithook`, which no process can remove: it stays
  inert when no collection traces) that reads the `subprocess.Popen`,
  `os.system`, `os.posix_spawn`, `os.spawn`, `os.exec` and `ctypes.dlopen`
  events as CPython raises them, with the arguments each one carries
  (the version probe of a program starts a process from inside the hook,
  under `suspended()` and `use_safe_open()`, before the user's launch is
  bound); and, around
  the `exec` of the script (and around each cell in the kernel), replaces
  `subprocess.Popen.__init__`, `wait` and `poll` with wrappers that bind a
  launch to its `Popen` and see its end through `returncode`, which is
  where `run`, `check_output`, `communicate` and `with Popen` meet. The
  class is not replaced, and the originals come back in the same
  `finally` as the finder.
- `src/noworkflow/now/persistence/content/safeopen.py`: keeps the original
  `open`s and restores them in a context manager; also pokes at
  `__builtins__["open"]`, which is a dict or a module depending on who imports
  it.
- `src/noworkflow/now/ipython/magics/now_run.py`: swaps `sys.argv`,
  `sys.path[0]` and `sys.modules["__main__"]` for the shell's user module
  while the cell runs, and swaps them back by hand.
- `importlib.metadata` (`prov_deployment/deployment.py`): `get_version`
  looks a module's distribution up from inside the import finder, while the
  script runs. Before 3.15 a distribution whose metadata has no version
  gives `None` instead of raising, PEP 503 folds the dots of a module name
  into `-`, and the lookup asks every finder in `sys.meta_path`, the
  script's own included (#417). Whatever reading metadata imports
  (`importlib.metadata._adapters`, `email.policy`...) must already be in
  `sys.modules` when the script starts, or it gets a module row as the
  script's: `load_metadata_modules` reads noWorkflow's own metadata on
  import for that, instead of relying on another import of `now` to bring
  them (`test_the_version_lookup_records_no_module_of_its_own`).
- SQLAlchemy 1.4: `relational_database.py` uses the 1.4 declarative and
  session API, and the pin keeps the 2.0 series out.
- `pyposast` is a sibling project (`JoaoFelipe/pyposast`): the AST positions
  that the collector relies on come from it, and a fix there only reaches here
  through a release of that package.
- `future` (`future.utils.viewitems`, `viewvalues`) is still imported in
  about forty modules, including `patterns/` and the tests.

## The paper's running example

The noWorkflow 2 paper uses a credit card fraud detection pipeline as its
running example. The example lives in three places, each with its own
purpose:

1. **The paper**, which states what noWorkflow records for it: the script,
   the trial history, the output of `now show` and `now diff`, the queries
   and their results, the graphs. Its source is kept by the authors, outside
   this organization.
2. **The reproducibility package**,
   [`dew-uff/noworkflow-analysis`](https://github.com/dew-uff/noworkflow-analysis),
   which the paper cites by tag: the script, the patches and the
   `run_trials.sh` that rebuild the trial history.
3. **The tests of this repository**:
   `src/noworkflow/tests/e2e/test_paper_example.py` replays that sequence
   on the copy in `src/noworkflow/tests/e2e/corpus/paper_example/` (its
   README names the tag) and checks what the paper shows, one test per
   figure or listing, in the `paper-example` job of `ci.yml`, so that a
   change here cannot contradict the paper without a red build.

A change to the example, or to what the paper shows of it, in any of the
three is carried to the other two. When the test of the example turns red,
the maintainer decides whether the change regressed or the paper and the
package must follow it; the expectation is never edited just to make the
test pass. When the package gets a new tag, the copy in the tests follows in
the same commit.

The case study of the paper's "Beyond Python" section is a second example
in the same three places: a Python wrapper that launches an R script and a
C program, in `beyond-python/` of the package and in
`src/noworkflow/tests/e2e/corpus/beyond_python/` here, replayed by
`src/noworkflow/tests/e2e/test_beyond_python.py` (#459) in the same job.
Its tests need `Rscript` and `cc` and skip without them (the job sets
`NOW_RSCRIPT=require`). The claims that only #204 to #207 and #461 can
satisfy are `_desired` twins, `xfail(strict=True)` through
`known_defects` with the signature of today's failure; the issue that
makes one pass removes the mark in its own commit, and the issue that
changes how one fails rewrites its signature. The map is the module's
docstring.

## Sensitive data

A provenance store records the whole environment of the machine that ran the
script: every variable in `os.environ` (`PATH` included), the user name, the
hostname, the pid, the OS release. `now show -e` prints it, `now export
prolog` emits an `environment/3` fact per attribute, and the vis serves it
too. **Never paste a real `now show -e` output, a real
Prolog export, a real `environment.json` or a real `.noworkflow/` into an
issue, a PR, a skill or a golden file.** Reproduce with the test corpus, and
when an environment attribute matters, name it ("the `USER` attribute")
instead of quoting the value. The e2e harness runs `now` with a synthetic
environment (user `nowtest`, a temporary home), the Prolog goldens drop the
`environment` predicate, and `test_normalize.py` fails if a golden or a
tracked notebook contains an environment fact, a home directory or the
hostname. The same goes for a user's store sent with a
bug report: look at it locally and describe what you found. A failing
test's report gets pasted too: the root `conftest.py` replaces this
machine's hostname with `<HOSTNAME>` in every report pytest prints
(`src/noworkflow/tests/helpers/reports.py` lists what it cannot reach),
and a test still never puts a store's environment or user id in an
assertion message or a test id.

## Language

Everything versioned is in English: code, comments, docstrings, docs, skills,
issues, PRs, commit messages. Discussion with the maintainer may happen in
Portuguese; what gets written to the repository is translated.

## Python versions

The supported range is `requires-python` in `pyproject.toml`; the versions
that are actually run are the legs of `.github/workflows/ci.yml` (blocking,
on every push), of `.github/workflows/pre-release.yml` (by hand, before a
release) and, from the next Python's first beta to its promotion, of
`.github/workflows/experimental.yml` (observed, not blocking). A version
is supported when it has a blocking leg, and a classifier in
`pyproject.toml` is added only then. Locally, `uv run --isolated --locked
--no-python-downloads --python <version> pytest` runs the suite on any of
them without touching `.venv`.

The rule that decides the range and the matrix (the record of the decision,
with the measurements behind it, is issue #237):

- **Range:** the versions python.org maintains on the day of the release
  (bugfix or security, see <https://devguide.python.org/versions/>). A
  version that reaches end of life leaves in the next minor release, never
  in a patch release. `requires-python`, the classifiers and the CI matrix
  change in the same commit.
- **Matrix:** on every push, Linux runs every supported minor, blocking,
  with four pytest-xdist workers per leg. Before a release, `pre-release.yml`
  runs Linux, macOS and Windows on every supported minor, by hand. The next
  Python runs on Linux as an experimental leg from its first beta (May), in
  an `experimental.yml` that exists only while such a leg does, and is
  promoted when the suite passes on it, with the October release as the
  target. The record of the move of macOS out of the push, with the
  measurements behind it, is issue #426; of Windows into
  `pre-release.yml`, #374.
- **Reference leg** (coverage, goldens, `flaky.yml`, and the Python of the
  `checks` and `paper-example` jobs): Linux on the newest blocking version.
  It moves when a new version is promoted, and the goldens are regenerated
  in the same step:
  `src/noworkflow/tests/e2e/goldens/REFERENCE` names the platform they were
  recorded on, and `.github/reference-leg/run.sh` reads the Python from
  `ci.yml`. The
  diff of that regeneration is what the new Python changes in noWorkflow's
  output; a line it does not explain is a defect.
- **Runner images:** the `-latest` labels, which GitHub moves to the newest
  generally available image.

Why macOS and Windows only before a release: defects specific to a system
(paths, encodings, the file system) rarely depend on the Python version, and
in 99 runs of `ci.yml` with macOS on every push no Python version failed
alone and macOS failed alone once, while its legs, on a 3-core runner where
workers barely help, set the pace of every push (#426); a Windows leg,
serial, takes about forty minutes (#374). On Windows the versions also read
files differently: from 3.15 UTF-8 mode is on by default (PEP 686), so an
`open()` without `encoding=` reads the locale encoding (usually cp1252)
before 3.15 and UTF-8 from it.

Why every minor on Linux: the ends cover the middle only while no code
branches on a middle version and no dependency resolves differently there
(the forks in `resolution-markers` of `uv.lock`), and nothing would say when
that stops being true. Linux legs cost nothing on a public repository.
