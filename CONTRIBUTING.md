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
7. The maintainer sets the milestone of the issue to the version that will
   ship it. The issue is closed when that version is released.

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
`main`, and closing is decided at the release, through the milestone.

## What a pull request needs

- **A test for every change of behavior.** For a bug, a test that fails on
  `main` and passes on the branch; say so in the PR. For a new command or
  option, a test that runs it.
- **The suite green, and the count not below the floor.** CI fails a leg
  whose test count drops below `min-tests` in `.github/workflows/ci.yml`
  and `experimental.yml`; when you add tests, raise the floor in both, in
  the same PR.
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

## Running locally

The project is managed with [uv](https://docs.astral.sh/uv/). From the
repository root:

```bash
uv sync                      # creates .venv with the locked dependencies
uv run pytest                # the whole suite
uv run ruff check .          # lint
uv run bandit -c pyproject.toml -r src/noworkflow -q -b bandit-baseline.json
uv run now run script.py     # the `now` of the working tree
```

To run the suite on another Python version, uv installs the interpreter
(`--isolated` keeps `.venv` as it is; without it, `uv run --python` recreates
`.venv` on that version):

```bash
for v in 3.8 3.12 3.13 3.14; do uv run --isolated --python "$v" pytest -q || break; done
```

The visualization bundle and the Jupyter extension are built from
`src/frontend` (details in `src/frontend/development.md`):

```bash
cd src/frontend && npm ci && npm run build
```

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
