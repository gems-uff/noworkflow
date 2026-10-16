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
   fast-forward.
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
  whose test count drops below `min-tests` in `.github/workflows/ci.yml`
  and `experimental.yml`, or below the floor in `flaky.yml`; when you add
  tests, raise the floors in the same PR. The reference leg also counts the
  goldens, which the other legs deselect, so its floor is higher.
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
  the interpreter it is asked for (see "Setting up `.venv`" below).
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
  suite does not need it.
- **SWI-Prolog with its shared libraries**, together with `pyswip-alt` (the
  `all` extra), for Prolog queries from Jupyter (`trial.query(...)`). `now
  export prolog` does not need it. The suite only runs the `swipl` program,
  for the Prolog query of the paper's running example, and skips that test
  without it. The reference-leg container has it.

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
(see [The paper's running example](#the-papers-running-example)).

## Running locally

From the repository root, with `.venv` set up as above:

```bash
uv run pytest                # the whole suite
uv run ruff check .          # lint
uv run bandit -c pyproject.toml -r src/noworkflow -q -b bandit-baseline.json
uv run now run script.py     # the `now` of the working tree
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
fails it otherwise; `NOW_LEAK_CHECK=warn uv run pytest` only reports, in the
LEAKS section of the summary.

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
