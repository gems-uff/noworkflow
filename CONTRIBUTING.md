# Contributing to noWorkflow

Is this your first time contributing here? Try one of the
[good first issues](https://github.com/gems-uff/noworkflow/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22good%20first%20issue%22)
to start. But remember to agree on your solution in the issue before starting
to code — see [Before coding](#before-coding-agree-on-the-solution-in-the-issue).

If you want to contribute and **do not belong to the main team**, follow
these steps:

1. Agree on the solution in the issue (see [Before coding](#before-coding-agree-on-the-solution-in-the-issue))
2. Fork the repository
3. Implement and test your code
4. Submit a pull request, with "Allow edits by maintainers" checked

If you **do belong to the main team**, just follow the steps below.

## Before coding: agree on the solution in the issue

An issue usually starts as a pain — a command that fails, provenance that is
missing, output that is confusing — not as a solution. Implementing straight
from it means guessing decisions that nobody has written down yet, and every
wrong guess comes back as rework during the review, when it is most expensive
to change.

So before creating a branch, refine the solution in the issue itself:

1. Write your proposal as a comment: what changes, for whom, and how it
   behaves outside the happy path.
2. For a bug, attach a minimal script and the exact `now` command that shows
   it, with the output you got and the output you expected. For a feature,
   show the expected output: the command line, what `now show`, `now export`
   or the vis would display.
3. List the open questions, especially the product decisions: what happens
   with a trial recorded by an older version, whether an option applies to
   every command or to one, what the user is told afterwards.
4. Start coding only when the maintainer agrees that the requirement is
   closed.

Decisions taken later, during the review, also go back to the issue as a
comment. The specification lives in one place, and the pull request
implements what is written there.

A large issue can be split while it is refined: a part whose solution is
closed can be implemented while the others are still under discussion.

## Branching model

We use one branch per issue. Every issue gets its own branch named after it
(for example, `issue_123`), whether it is a bug fix, a dependency update or a
new feature. All of them are based on `main`.

The `main` branch is the baseline and is always stable: every release is cut
from it, and it is protected, so nobody pushes to it directly.

The lifecycle of a branch is:

1. Once the solution is agreed in the issue, create `issue_NNN` from `main`.
2. Implement, with tests.
3. Merge `main` into `issue_NNN` and run the suite again, so the branch is up
   to date.
4. Open the pull request as a draft, and mark it ready for review when the
   checklist in the template is complete.
5. The maintainer reviews it, following the `review-pr` skill in
   `.claude/skills/`.
6. The maintainer merges `issue_NNN` into `main`. Because of step 3 this is a
   fast-forward. The maintainer then deletes `issue_NNN`, on GitHub and
   locally: it points to a commit `main` already contains, so nothing is
   lost.
7. The maintainer closes the issue, unless something is left to do: `main`
   is the baseline, and an issue integrated there and finished is done. The
   release that ships it is found from the commits, through the
   `Issue #NNN:` prefix.

Steps 5 to 7 are done by the maintainer only.

## Commit messages

Start the subject with `Issue #NNN: `, using the number of the branch's
issue. GitHub turns the number into a link, and the subject is what shows up
in the commit list and in `git log --oneline`. After the prefix, keep the
subject around 60 characters, in the imperative mood and with no trailing
period, and use the body to explain why the change was needed:

```
Issue #183: Restore a single file into the target given by -t

`now restore -f path -t other` wrote the file to its original path and
ignored the target. The option existed since the command was created, but
nothing read it after argument parsing.
```

Reference the issue with the prefix alone. Do not write `Fixes #NNN` or
`Closes #NNN`: GitHub closes the issue as soon as such a commit reaches
`main`, while an issue often takes several commits; the maintainer closes it
once it is integrated and nothing is left to do.

## What a pull request needs

- **A test for every change of behavior.** For a bug, a test that fails on
  `main` and passes on the branch; say so in the PR. For a new command or
  option, a test that runs it.
- **The suite green, and the count not below the floor.** CI fails a leg
  whose test count drops below `min-tests` in `.github/workflows/ci.yml`,
  `pre-release.yml` and, while it exists, `experimental.yml`, or below the floor in
  `flaky.yml`; when you add
  tests, raise the floors in the same PR. The reference leg also counts the
  goldens, which the other legs deselect, so its floor is higher.
- **No new code-scanning alert.** CodeQL analyzes the pull requests to
  `main` opened from a branch of this repository: the Python, the
  JavaScript and TypeScript of `src/frontend` (the vis and the Jupyter
  extension) and the workflows. It runs from the repository settings
  (default setup), so no file in `.github/workflows/` configures it. Its
  `CodeQL` check annotates each alert the PR adds in the lines it changes,
  and fails only when one is of severity error or of security severity high
  or critical: a lower one leaves the check green and still counts here.
  Fix each alert, or, when you believe it is a false positive, say why in
  the PR: a maintainer dismisses it on GitHub with that reason. A pull
  request from a fork gets no `CodeQL` check (default setup skips forks); a
  maintainer runs the analysis for it before integrating.
- **The goldens, when an output changes.** A change to what a command prints
  shows up as a golden mismatch on the reference leg. Record the new
  goldens on the reference platform (see "End-to-end tests and goldens"
  below) and commit them with the change: their diff is the visible
  footprint of the change.
- **The bundle, when the frontend changes.** Any change under `src/frontend`
  comes with `src/noworkflow/now/vis/static/dist/bundle.js` rebuilt in the
  same commit; the `frontend` job rebuilds it and fails on a difference.
- **The docs, when the interface changes.** A new or renamed command or
  option is also changed in `README.md` and, once it exists, in
  `skills/noworkflow/SKILL.md`.
- **No real data.** A provenance store records the whole environment of the
  machine (every environment variable, user name, hostname). Do not paste a
  real `now show -e`, a real Prolog export or a real `.noworkflow/` into the
  PR or the tests; use the test corpus and invented values.

## Development environment

What a new machine needs to work on noWorkflow. `README.md` covers
installing noWorkflow as a user, with `pip`; none of that is needed here.
No version number is copied below: each one is read from the file that
owns it, so this section stays right when the versions move.

### What to install

- **git**, to clone the repository. The suite calls it too: the tests that
  read the committed `bundle.js` and the tracked notebooks skip without it.
- **[uv](https://docs.astral.sh/uv/getting-started/installation/), the
  latest release.** It installs Python, creates `.venv` from `uv.lock` and
  runs every tool. CI installs the latest uv as well (`astral-sh/setup-uv`
  without a version), and an older uv may not know the newest Python
  release: `uv python install` fails with "No download found". Update it
  with `uv self update`, or with the package manager that installed it.
- **Python, through uv.** No system Python is needed: `uv sync` downloads
  the interpreter it is asked for (see "Setting up `.venv`" below). When uv
  has none of its own for a version, it takes a matching Python that another
  manager installed instead of downloading one, while CI runs only the ones
  uv downloads (`UV_MANAGED_PYTHON` in the workflows);
  `--managed-python` does the same locally.
- **Node and npm, only to change `src/frontend`** (the vis and the Jupyter
  extension). Use the major of the `frontend` job, which is the one that
  reproduces the committed `bundle.js`:

  ```bash
  sed -n 's/.*node-version: "\([0-9]*\)".*/\1/p' .github/workflows/ci.yml
  ```

  Any installer that provides that major works (nodejs.org, a version
  manager such as nvm or fnm, a system package manager); npm comes with it.
- **[gh](https://cli.github.com/)**, for the contribution cycle from the
  terminal (issues with their Type, pull requests, CI runs) and for the
  repository skills in `.claude/skills/`, which call it. Authenticate once
  with `gh auth login`. From a fork, the website does the same.

Optional, each for one purpose:

- **A Linux container engine**, to reproduce the CI reference leg: recording
  goldens, and failures that only show on Linux x86_64, such as a SQLAlchemy
  or greenlet build. On macOS, [colima](https://github.com/abiosoft/colima)
  or Docker Desktop, plus Rosetta on Apple silicon, which runs the
  `linux/amd64` image; on Linux, the native Docker engine. colima shares
  only the home directory with its VM by default, so the checkout has to be
  under it: elsewhere, the container sees an empty directory. How to use it
  is in [End-to-end tests and goldens](#end-to-end-tests-and-goldens).
- **graphviz** (the `dot` program), which renders the graphs Jupyter shows
  through the `%%dot` magic (`trial.dot`, for example) and turns the output
  of `now export dataflow` or `now export prospective` into an image. The
  suite runs it in the tests of `run_dot`, of the `%%dot` magic and of the
  diagrams of `%now_schema`, and skips them without it.
- **SWI-Prolog with its shared libraries**, together with `pyswip-alt` (the
  `all` extra), for Prolog queries from Jupyter (`trial.query(...)`). `now
  export prolog` does not need it. The suite only runs the `swipl` program:
  for the Prolog query of the paper's running example, for the comparison
  of each pattern rule with `rules.pl`, and to read Prolog exports back; it
  skips those tests without it. The test of the `%%now_prolog` magic needs
  `pyswip-alt` too, and skips without it. The reference-leg container and the legs
  of the `test` job of CI have it.
- **Google Chrome**, for the tests of the vis in a browser (with the
  `browser` dependency group); they skip without it. The `vis-browser` job
  of CI installs it. See [The vis in a browser](#the-vis-in-a-browser).
- **R (`Rscript`) and a C compiler (`cc`)**, for the tests of the case
  study of the paper's "Beyond Python" section
  (`src/noworkflow/tests/e2e/test_beyond_python.py`, see [The paper's
  running example](#the-papers-running-example)); they skip without them.
  Base R is enough (`r-base-core` on Debian and Ubuntu, `brew install r`
  on macOS); the C compiler is the system's. Two of those tests also need
  the rdtLite package in R (`install.packages("rdtLite")`) and skip
  without it.
- **[issuefinder](https://github.com/gems-uff/issuefinder)**, cloned next to
  the checkout (`../issuefinder`), to search the existing issues before
  opening one: it finds an issue written with other words or in the other
  language, which a keyword search misses. Its README has the setup; the
  environment and the model take about 3 GB.

### Setting up `.venv`

`.venv` runs on the Python of the CI reference leg, the `reference: true`
entry of the `test` matrix in `.github/workflows/ci.yml`. The goldens and the
coverage come from that version, so a local run sees what that leg sees:

```bash
git clone https://github.com/gems-uff/noworkflow.git && cd noworkflow
python=$(sed -n 's/.*python: "\([0-9.]*\)".*reference: true.*/\1/p' .github/workflows/ci.yml)
uv sync --locked --python "$python"    # downloads that Python if missing, creates .venv
uv run pytest                           # the whole suite
```

`--locked` installs exactly what `uv.lock` says, as CI does, and fails
instead of re-resolving when the lock and `pyproject.toml` disagree. Run the
same `uv sync` again when `uv.lock` changes, and when the reference leg moves
to a newer Python. The other supported versions run without touching `.venv`
(see "Running locally").

The extras of `pyproject.toml` stay out of `.venv` unless named: add
`--extra demo` (matplotlib) to run the `slow` tests of `now demo`, which
skip without it (the reference leg of CI and its container sync it), and `--extra notebook` (Jupyter) for the full frontend
build (see "The frontend"). The same goes for the `paper` dependency group:
`--group paper` adds what the tests of the paper's running example need
(see [The paper's running example](#the-papers-running-example)). The
`engines` group is the exception: it never goes into `.venv` (see [The
optional content engines](#the-optional-content-engines)).

## Running locally

From the repository root, with `.venv` set up as above:

```bash
uv run pytest                # the whole suite
uv run pytest -n 4           # the same, in four processes (pytest-xdist)
uv run ruff check .          # lint
uv run ruff format .         # format (CI runs `ruff format --check .`)
uv run bandit -c pyproject.toml -r src/noworkflow -q -b bandit-baseline.json   # SAST
uv run now run script.py     # the `now` of the working tree
```

A site that ruff flags and that is intended gets `# noqa: <code>` on its
line, with the reason on the line above. An import block whose order
matters, such as a package that registers what it imports in that order, goes
between `# isort: off` and `# isort: on`, with the reason above it.

A site that bandit flags and that is intended gets `# nosec Bxxx`, with the
reason on the line above; CI refuses a `# nosec` without the test id, which
would silence every test on its line. A real finding stays in `bandit-baseline.json`,
with its issue, until the commit that fixes it regenerates the file (the
command is next to the bandit step in `.github/workflows/ci.yml`). `-b`
hides every finding of a test in a file that already has one in the
baseline, so CI also compares the findings one by one. The same comparison
locally:

```bash
uv run bandit -c pyproject.toml -r src/noworkflow -q -f json -o "${TMPDIR:-/tmp}/bandit.json"
diff <(jq -r '.results[] | "\(.filename) \(.test_id)"' bandit-baseline.json | sort) \
     <(jq -r '.results[] | "\(.filename) \(.test_id)"' "${TMPDIR:-/tmp}/bandit.json" | sort)
```

The suite runs in a random order (pytest-randomly), a new one on every run,
so a test that depends on what another left behind fails sooner or later
instead of passing by luck. The first lines of the run print the seed, as
does the job summary of each CI leg (`-q` hides it); the same seed replays
the same order:

```bash
uv run pytest --randomly-seed=1234   # the order of that run
uv run pytest -p no:randomly         # file order, to tell order from code
```

About 80% of the suite's time is spent waiting for the `now` processes the
end-to-end tests start, so it runs well in parallel: the Linux legs of CI
use `-n 4`, one worker per vCPU of the runner, about three times faster
than one process. On a laptop, `-n 4` is a good start; more workers than
performance cores gain little, because each test gets slower. Under
pytest-xdist the seed still fixes the order of collection, but not which
worker runs which test after which, so a red that depends on another test
may not come back with the same seed and `-n 4`. Replay it in one process,
with the seed of the run, and then in file order:

```bash
uv run pytest -n 0 --randomly-seed=1234   # one process, the order of that run
```

To run the suite on another Python version, uv installs the interpreter
(`--isolated` keeps `.venv` as it is; without it, `uv run --python` recreates
`.venv` on that version). The loop below runs every version of the Linux legs
in `.github/workflows/ci.yml`, which are the supported ones (see "Python
versions" in `AGENTS.md`):

```bash
for v in $(sed -n 's/.*os: ubuntu-latest, python: "\([0-9.]*\)".*/\1/p' .github/workflows/ci.yml); do
  echo "== Python $v"
  uv run --isolated --locked --python "$v" pytest -q
done
```

Every version runs, even after a red one: which versions fail is the
result. `--locked` installs what `uv.lock` says, as CI does, and fails when
the lock and `pyproject.toml` disagree. The `python-matrix` skill in
`.claude/skills/` has the rest: the reference container, the CI legs, and
what to do when one version fails.

### End-to-end tests and goldens

`src/noworkflow/tests/e2e/` runs `now` as a process on a real store, in a
temporary directory and with a synthetic environment (`harness.py`). A
command, an export or a store on disk is tested there. Outputs that must not
change by accident are compared with golden files under
`src/noworkflow/tests/e2e/goldens/`, after `normalize.py` masks what differs
between two identical runs (trial ids, clock readings, paths, addresses).

Goldens depend on the system and on the Python version, so they are
recorded on one platform, the CI reference leg, named in
`goldens/REFERENCE`; on any other platform they are skipped. To compare or
record them from any machine with Docker (colima or Docker Desktop on
macOS):

```bash
GOLDEN=require .github/reference-leg/run.sh -m golden     # compare, as CI does
GOLDEN=overwrite .github/reference-leg/run.sh -m golden   # record them again
git diff src/noworkflow/tests/e2e/goldens/                 # review the change
```

A new golden is written the first time its test runs, and the test is
skipped; from the next run on it is compared. When the reference leg finds a
mismatch, the `golden-actual` artifact of the CI run holds what it printed.
Never edit a golden by hand: record it again.

After every test, the root `conftest.py` checks that the test left no process
state behind (the collector replaces the `open` functions, adds builtins and
an import finder, and some commands write into the current directory) and
no child process running (a `subprocess.Popen` dropped without waiting, a
`multiprocessing` child not joined, which it kills), and fails it
otherwise; `NOW_LEAK_CHECK=warn uv run pytest` only reports, in the LEAKS
section of the summary. It also replaces this machine's hostname with
`<HOSTNAME>` in every report pytest prints, so that a failure log can be
pasted (`src/noworkflow/tests/helpers/reports.py`).

### The paper's running example

`src/noworkflow/tests/e2e/test_paper_example.py` replays the running example
of the noWorkflow 2 paper (a scikit-learn pipeline, eleven trials) and
checks what the paper shows of it, figure by figure. Its tests are marked
`paper` and need the `paper` dependency group; without it they skip, and the
matrix legs of CI deselect them. The `paper-example` job of `ci.yml` runs
them on the reference platform, with SWI-Prolog for the Prolog query:

```bash
uv sync --locked --group paper                           # scikit-learn, imbalanced-learn, pandas
uv run pytest -m paper                                   # about a minute; the replay runs once
GOLDEN=require .github/reference-leg/run.sh -m paper     # as the job runs it, goldens included
```

Off the reference platform the goldens and the claims that depend on
noWorkflow's numbering skip, as the other goldens do. A plain `uv sync
--locked` removes the group from `.venv` again. A red test of the example is
triaged as "The paper's running example" in `AGENTS.md` says: the change
regressed, or the paper and its package must follow it; the expectation is
never edited to make the test pass. To replay on the real dataset, see the
README in `src/noworkflow/tests/e2e/corpus/paper_example/`.

`src/noworkflow/tests/e2e/test_beyond_python.py` does the same for the
case study of the paper's "Beyond Python" section (a Python wrapper that
launches an R script and a C program, three trials), from
`src/noworkflow/tests/e2e/corpus/beyond_python/`. Its tests carry the same
`paper` mark and run in the same job, which installs R; locally they need
`Rscript` and `cc` on the PATH and skip without them, and
`NOW_RSCRIPT=require` fails instead of skipping, as the job sets. The
claims that wait for #202 to #206 are `_desired` twins marked
`xfail(strict=True)`: see "The paper's running example" in `AGENTS.md`.

### The vis in a browser

`src/noworkflow/tests/browser/` serves a two-trial store with `now vis`
over a real port and drives the bundle it serves in headless Chrome, with
Playwright: the history graph, a trial and its tabs, the diff of two
trials, the dataflow, the prospective graph, the Prolog export, the
database graph and the SQL editor, each through the mouse and the
keyboard. Its tests are marked `browser` and need the `browser` dependency
group and Google Chrome, which Playwright drives in place: it never
downloads browsers of its own. Without either they skip; the matrix legs
of CI deselect them, and the `vis-browser` job of `ci.yml` runs them with
`NOW_BROWSER=require`, which fails a test instead of skipping it:

```bash
uv sync --locked --group browser                          # Playwright
uv run pytest -m browser                                  # about a minute and a half
CHROME=/path/to/chrome NOW_BROWSER=require uv run pytest -m browser
```

`CHROME` names the executable when Chrome is not where Playwright looks
(`channel="chrome"`). Each test starts its own `now vis` on a free port, so
they cannot run where binding a port is refused (inside the Claude Code
sandbox, for one). They run the bundle that `now vis` serves, the working
tree's: after a change under `src/frontend`, rebuild it first ("The
frontend", below). As with the `paper` group, a plain `uv sync --locked`
removes the group from `.venv` again.

### The optional content engines

Besides `plain` and `puregit`, a store can keep its content with dulwich,
pygit2 or gitdb (`--content-engine dulwich`, `sequential_pygit`, `gitdb`).
`src/noworkflow/tests/persistence/test_content_engines.py` runs the same
contract on every engine, and `src/noworkflow/tests/e2e/test_optional_engine_stores.py`
runs `now` on a store of each optional one. Their tests are marked
`engines` and need the `engines` dependency group; without it they skip,
the matrix legs of CI deselect them, and the `engines` job of `ci.yml` runs
them with `NOW_ENGINES=require`, which fails a test instead of skipping it.

Never sync the group into `.venv`: once pygit2 or dulwich imports, every
new store without `--content-engine` takes its engine, and the rest of the
suite, which expects `plain`, fails or hangs. Run the engine tests in an
isolated environment instead, on the Python of the `engines` job (pygit2
has no wheel for the newest one yet):

```bash
python=$(sed -n '/^  engines:/,/^  [a-z]/s/.*python-version: "\([0-9.]*\)".*/\1/p' .github/workflows/ci.yml)
NOW_ENGINES=require uv run --isolated --locked --python "$python" --group engines pytest -m engines
```

### The frontend

The visualization bundle and the Jupyter extension are built from
`src/frontend`, with the Node major given in "What to install" (details in
`src/frontend/development.md`). To rebuild `bundle.js`, which is what the
`frontend` job of CI checks:

```bash
cd src/frontend
npm ci                                                             # node_modules from package-lock.json
npx lerna run build --scope=@noworkflow/nowvis --include-dependencies
git restore ../noworkflow/now/vis/static/dist/bundle.js.map
```

Commit `bundle.js` together with the source change. The build also rewrites
`bundle.js.map`, which is not reproducible: it embeds the absolute path of
the checkout, your home directory included. The last line above discards it;
it is not committed.

The bundle is built by babel, which strips the TypeScript types without
checking them, so the same job also counts the `tsc` errors of the vis and
fails when the count goes above a baseline. After the build above, from the
repository root:

```bash
bash .github/scripts/tsc-baseline.sh "$(sed -n 's/.*tsc-baseline.sh \([0-9]*\).*/\1/p' .github/workflows/ci.yml)"
```

When a change removes errors, lower the number in the `frontend` job of
`.github/workflows/ci.yml` to the new count in the same commit.

The same job lints every package of the workspace (the vis, the shared
packages and the Jupyter extension) with stylelint, prettier and eslint.
The three are declared in `src/frontend/package.json` and configured next
to it (`eslint.config.js`, `.prettierrc.json`, `.stylelintrc.json`). From
`src/frontend`, `npm run lint:check` is what the job runs, and `npm run
lint` fixes what the three can fix; `--workspace=@noworkflow/nowvis` (or
another package) limits either to one package. What the tools cannot fix
is fixed by hand, with the behaviour kept: `===` only where both operands
already have the same type, a conversion written out otherwise.

`npm run build` builds every package, the Jupyter extension included, and
that one calls `jupyter labextension build`. It fails with
`jupyter: command not found` unless Jupyter is in `.venv` (`uv sync --locked
--python "$python" --extra notebook`) and the build runs through uv:
`uv run --no-sync npm run build`.

## Security

Security problems follow the same cycle as any other bug: a public issue
describing the problem, an `issue_NNN` branch, `Issue #NNN:` commits and a
pull request with a test for the property the fix guarantees. noWorkflow runs
on the user's own machine, never as a shared service, so describing the
problem in public does not expose anyone. See `SECURITY.md`.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you agree to uphold it.

## Language

Everything in the repository is in English: code, comments, documentation,
issues, pull requests and commit messages. Older issues and comments may be in
Portuguese; search in both languages before opening a new one.
