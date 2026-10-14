---
name: review-pr
description: Takes a pull request of this repository from start to finish — read the issue and the diff, decide what is ours and what goes back to the author, cover what is missing in tests, measure, run the checks the diff calls for and integrate. Use when asked to "work on PR N", when reviewing a third-party contribution, or when resuming a stalled branch.
---

# Working on a pull request

This skill is the **backbone**: it says *when* each thing enters and *why*. The
*how* is in the skills it points to, and is not repeated here — a step that fits
in one sentence plus a pointer is one sentence plus a pointer.

**Not every PR ends in a release, and merge is not release.** The four legitimate
exits are in step 4; the straight line to integration is one of them, not the
only one. Steps 6 and 7 belong to that line alone and step 8 holds for all four;
step 5 serves both sides — on the straight line it covers the gaps, and when
handing the PR back it turns the reproductions into tests of the project. A
plausible verdict also crosses the line: it sends the PR to `golden-run`,
`python-matrix` or `rebuild-vis` before any exit is closed.

## Where each signal leads

| What appears in the diff or on the branch | What enters |
|---|---|
| `pyproject.toml`, `uv.lock`, `src/frontend/package*.json`, `.github/workflows/**` | `dependencies` |
| A Dependabot PR | `dependencies`; up to date by `@dependabot rebase`, never by a pushed merge (below) |
| `src/frontend/**` or `src/noworkflow/now/vis/**` | `rebuild-vis`, then `golden-run` on the vis |
| `src/noworkflow/now/collection/**`, or an issue that names a Python version | `python-matrix` |
| `src/noworkflow/now/persistence/**`, `src/noworkflow/now/models/**`, `src/noworkflow/now/cmd/**`, `src/noworkflow/patterns/**`, `src/noworkflow/resources/**` | `golden-run` |
| A new or renamed command or option | `README.md` and, once it exists, `skills/noworkflow/SKILL.md`; for `run`, `restore` and `schema`, also a manual probe of the magic that inherits the parser (below) |
| `src/noworkflow/now/ipython/**`, `src/noworkflow/kernel/**` | A blind spot of the suite: a manual probe, recorded in the PR |
| `src/noworkflow/tests/__init__.py`, or tests moved | Parity between the two runners (step 6) |
| Branch behind `main` | `merge-downstream` |
| A suspected defect | `prove-candidate` |
| A PR that depends on an unpublished `pyposast` | `dependencies`: blocked until that release |
| Any change that must be measured | `safe-refactor` |
| Green, measured and integrated | `release`, when the maintainer decides |

Two rows need a word more. **A Dependabot PR has no issue and must not
receive a pushed merge**: Dependabot stops updating a PR that received
commits from someone else, and `@dependabot recreate` wipes them; what brings
it up to date is a `@dependabot rebase` comment, by the maintainer, and what
the maintainer pushes (a rebuilt bundle, for an npm bump) survives `rebase`
only. What decides whether the bump is accepted is the series rule of
`AGENTS.md` ("Dependencies"): a patch of the same series goes in, a minor or
major bump is a decision for the maintainer, never a side effect. With no
issue, where the milestone goes (`gh pr edit <N> --milestone`, or a `Task`
issue) is the maintainer's call. **A new option of `now run`, `now
restore` or `now schema` is also a new option of `%now_run`, `%now_restore` or
`%now_schema`**: the magics in `src/noworkflow/now/ipython/magics/` inherit
the command's parser, so the diff never touches `now/ipython/**` and the
blind-spot row does not fire; probe the magic by hand in an IPython shell and
record it in the PR.

## 1. Reconnaissance

`gh pr checkout` switches branches: with a modification of yours in a file the
PR touches, git refuses the whole switch, so start with a clean tree. If there
is uncommitted work there, **stop and ask the maintainer** before switching: by
`AGENTS.md` it is the maintainer who commits, and an uncommitted change has no
reflog to come back from. On an older branch, what only `main`'s `.gitignore`
ignores (the files the audit and the build generate) shows up as untracked:
that is nobody's work.

`--force` is not optional: without it, on a PR that was force-pushed, the
fast-forward that gh runs inside fails and the local branch stays at the old
head, and you spend the whole cycle measuring a stale branch. `--force`
resets the local branch to the PR's head — check first that no commit of
yours is there.

```bash
gh pr view <N> --json title,body,state,headRefName,baseRefName,mergeable,commits,statusCheckRollup,isCrossRepository,maintainerCanModify,closingIssuesReferences
git fetch --all --prune
gh pr checkout <N> --force                  # everything from here on reads the tree
git log --oneline origin/main..HEAD         # what the PR brings
git log --oneline HEAD..origin/main         # what is missing from main
```

The second list empty is what you want. If it is not, `merge-downstream` before
any measurement: a stale base measures the lag, not the PR.

`closingIssuesReferences` lists the issues the merge would close. Anything
there goes against the milestone rule of `AGENTS.md`: ask the author to drop
the `Fixes`/`Closes`. A body that names the issue without a closing keyword
does not appear there, and needs nothing.

**"Everything from here on reads the tree" includes this skill and the tools.**
A branch that predates `uv.lock`, the root `conftest.py`, the pytest
configuration or `.claude/skills/` no longer has them on disk after the
checkout: the skills this one points to are read from `main` (`git show
origin/main:.claude/skills/<name>/SKILL.md`), and **nothing goes through `uv`
on that tree — `/code-review` included — until `merge-downstream` has brought
the lock in.** On a tree without `uv.lock`, every `uv run` re-resolves, writes
an untracked `uv.lock`, syncs `.venv` to a set without pytest, and the
untracked lock then aborts the catch-up merge. If it already happened: `rm
uv.lock` before the merge, `uv sync --locked` after it. Meanwhile the probes
and the reproductions run on a worktree of `main` (step 3).

A PR from a fork brings the branch in the author's remote: `maintainerCanModify`
above says whether the maintainer can push there the reproduction that step 3
prepares, and whether a catch-up merge can be pushed at all. Without it, the
reproduction only reaches the author as a comment, `merge-downstream` serves
only to measure, and the sync of step 3 of `CONTRIBUTING.md` goes back to the
author with the rest of the round (step 4).

**Read the issue and its comments, not only the title**, and also those of the
related and closed issues — in English and in Portuguese, the way `AGENTS.md`
prescribes (`gh issue list --state all --search`, `git log --all
--grep="#NNN"`). That is where the product decision already taken, the reverted
attempt and what was already verified live; without it, it is easy to treat as
new a part that was already settled, or to reopen a closed discussion.

Fire `/code-review max <N>` and follow step 2 while it runs — the PR number
also gives it the author's comments.

- **`max`, not less:** below `xhigh` it may fall into a single-pass variant,
  without the final sweep for gaps, and `max` is the ceiling.
- **Never `--comment` nor `--fix`.** The first publishes on the PR; the second
  applies to the tree outside the checkpoints, and `/rewind` does not undo it.
- It does not verify what it returns, and the end of the list is usually a
  floor of findings, not discovery. Who triages is step 3.
- **It measures: it runs the suite.** Overlapping with the measurement of step
  6 contaminates the round — a failure shows up as a regression of the PR and
  is two runs sharing the machine. Wait for it to finish before measuring, or
  measure before firing it.
- **It cleans the tree when it closes, and does not distinguish whose file it
  is.** An untracked file that appeared during the round disappears — the
  reproduction you just wrote included, without warning: you only find out
  when you run the test. Write it in the session scratchpad and copy it into
  `src/noworkflow/tests/` when it is time to run.
- **"Finished" may not be the end.** The completion notice arrives even with a
  background sweep of its still alive: it comes back, sends an addendum — and
  cleans the tree again. Check that it is `completed` before treating the list
  as closed.

## 2. Read the diff

**Say first what kind of PR this is** and declare the expected differences
before running any measurement. The criteria are in step 8 of `safe-refactor`
— bug fix, feature and refactoring — and **an upgrade is read as a
refactoring**: no difference is expected from it either.

**Read the diff yourself, and note your own candidates** — do not delegate
this to `/code-review`. It crosses files and confronts the diff with the
written conventions, but it does not leave the repository: four classes of
candidate **only come out of your reading**, because they depend on what the
repository does not keep:

- **The effect on existing provenance stores.** `AGENTS.md` says why it cannot
  be claimed without opening a store created by the previous version; the
  store-compatibility check of `golden-run` is the instrument. The same
  question for the data already recorded: a field whose meaning changes is
  read by `now show`, by every export and by the vis, over trials that were
  collected before the change.
- **The coverage the issue asked for**, not the one that exists: the machine
  only complains about a missing test as a nit, and does not know what the
  issue promised.
- **A product decision**, including about the request you yourself made to the
  author. It is not a finding, it is judgement, and retracting in public is
  part of the job.
- **What the merge will run into** — which test on `main` stops passing
  against the new model, which export or Prolog rule stops matching a model
  that the branch changed, which handler the transformer refactoring on `main`
  no longer calls. The two sides pass green separately, and only the full
  suite after the merge tells; the detail is in `merge-downstream`. It also
  holds with the branch up to date, so do not wait for the routing of step 1
  to look. `git merge-tree --write-tree origin/main HEAD` shows the conflicts,
  and `git show <tree>:<file>` the merged file, without touching the tree.

When the PR touches `pyproject.toml` or `uv.lock`, what decides the review is
what changed **in the dependency**, not what the author wrote: the notes of
step 1 of `safe-refactor` apply. What is specific to the review is checking
**the author's adjustment against the library's migration guide** — a
migration instruction comes in prose, and it is the item that goes unnoticed
and only breaks on the user's machine.

The checklist of the PR template is what the author claims; step 6 is where
each box is verified.

## 3. Triage the candidates

Yours and those of `/code-review`, all through `prove-candidate`: the
escalation, the three verdicts and the rules of proof are there.

What is specific to a PR review is **where the "before" is: at the
merge-base, not on `main`** — a stale branch would measure the PR plus what
`main` moved. A worktree outside the checkout — `<outside>` is the session
scratchpad, or the checkout's parent:

```bash
base=$(git merge-base origin/main HEAD)
git worktree add <outside>/nw-base "$base"
cd <outside>/nw-base && uv sync && uv run pytest   # run_tests.py at an old base (below)
```

**The merge-base may predate the pytest configuration and the lock**: a
`pyproject.toml` without `[tool.pytest.ini_options]` and no `uv.lock`. There,
`uv sync` resolves fresh and installs no pytest (`uv run pytest` fails to
spawn), and `uv run --with pytest pytest` would collect without the doctests
and without the scratch directory, so its count is not comparable. The runner
at such a commit is `uv run python run_tests.py`, and its `Ran N tests` is
comparable with pytest's count here (the parity of step 6).

It is also how you find out that **a candidate already held before the PR**:
it is not a regression, and the message to the author changes from "you broke
it" to "this got worse here — fix it now or does it become an issue?".

The merge-base worktree is for when the **environment** differs — a PR that touches
`pyproject.toml`, a different lock. When only the code changed, the cheaper
**and more precise** control is `git checkout "$base" -- <file>` and run
again: it isolates the hunk, not the whole commit, and skips `uv sync`. The
tree is clean after the checkout of step 1, so `git checkout HEAD -- <file>`
puts it back without losing anything.

**When the branch predates the lock, the probes run on a worktree of
`main`.** Until `merge-downstream`, nothing on the PR's tree goes through
`uv` (step 1), and the merge-base has no pytest. A worktree of `origin/main`
synced from the lock takes the PR's files one by one:

```bash
git worktree add --detach <outside>/nw-main origin/main
cd <outside>/nw-main && uv sync --locked
git checkout <branch> -- <file>                    # a file main did not change
git diff "$base" <branch> -- <file> | git apply    # only the PR's hunk, for one it did
git diff --stat "$base" origin/main -- <files>     # what main changed since the base
```

It stands for the "before" only for the files that the last command shows
unchanged; say so in the report. Bringing the whole file of one that `main`
changed undoes `main` in the measurement. `--detach` matters: a worktree on
the `main` branch stops the checkout from switching back to `main`.

Create either worktree **outside** the repository and remove it with `git
worktree remove --force` when step 6 closes (`--force` because `uv sync`
leaves `.venv/`, and at an old base also `uv.lock`, untracked there; `git
worktree prune` if the directory is already gone): inside the checkout it
breaks the clean-tree precondition of `release`, and forgotten it accumulates
one per PR — `release` checks `git status`, never `git worktree list`.

## 4. Whose fix is it?

It is the central decision of the skill, and it has four exits.

**We take it over, and carry on** when the PR is mostly adequate: the
author's fixes attack the cause, what is missing is **additive** (a test
nobody wrote, coverage of a new path) and there is no product decision in
dispute. Commenting on the PR in that case only postpones by days work that is
already done in the tree.

**Comment on the PR and hand it back** when there is rework: the fix treats
the symptom instead of the cause, the number of adjustments would rewrite the
author's commits, or context is missing that only the author has.

**Stop and ask the maintainer** when the doubt is about the product, not the
code.

**Do not go ahead** when the PR contradicts a decision already taken,
duplicates a closed issue, or is stale to the point that the merge costs more
than redoing it. It comes out of the reading of step 1, and it is the most
valuable conclusion a review produces — the one that avoids the whole rest of
the cycle. Closing a third party's PR is the maintainer's decision: bring the
reason and what supports it.

**When handing back, convert the PR to a draft** (`gh pr ready --undo <N>`).
A PR marked ready for review is how the author signals that the checklist is
complete, and it is by that mark that the maintainer finds the queue; a PR
handed back that stays ready comes back to the queue as if nothing had
happened. Who marks it ready again is the author, when the round is done.

**When handing back, send the reproductions along — not only the prose.**
Those of step 3 already assert the correct behavior and fail while the defect
exists, and on the author's branch they would leave the suite red until the
fix. That is more useful than a description, and it is not an accusation: the
reproduction **is the specification of the fix**, and it is worth saying so in
the comment. Commit and push belong to the maintainer — leave the reproduction
ready in the tree and ask. On a branch of this repository the maintainer
pushes it; on a fork, only if `maintainerCanModify` allows.

Two conditions. The reproduction goes clean, with the name and the place of a
test of the project, with no remains of the exploratory script that produced
it. And **feedback in one round**: gather everything — confirmed, refuted,
what is not a regression and what stayed open — instead of commenting finding
by finding, which makes the author chase a moving target.

**A vulnerability the PR itself introduces is discussed in it**, because the
defect is born at the merge. One found in passing, already on `main`, becomes
its own issue like any other bug: noWorkflow runs on the user's own machine,
and `AGENTS.md` has the cycle.

Two things that do **not** justify handing back, and become a written note: a
deviation from the commit-message convention, and an adjacent finding outside
the PR's scope — that one becomes its own issue (search the existing ones
first, closed included, in both languages).

## 5. Cover the gaps

The new coverage comes after step 4, because only there you know where it
goes. Handing the PR back does **not** throw it away: on a branch of this
repository it travels with the reproductions, in the same commit, and the
author receives both. On a fork without `maintainerCanModify` only the prose
arrives — then writing it before the decision is wasted work. The
reproductions of step 3 are another thing — those already exist, and they are
what travels; when handing back, this is where they take the form of a test
of the project, by the rules below.

**The commit goes red, and the message says so.** A reproduction that travels
leaves the branch's CI red until the fix — it is the design, not a new break.
Without that sentence in the body of the commit, the next round reads the red
as a regression and goes fixing the test.

**Measure what the PR's own coverage reaches before writing yours.** Revert
each part of the change and run the tests the PR adds: the part whose
reversal brings down no test is not covered — and it is where the regression
passes without the suite noticing. In a four-part PR, three may come without a
single test, with the suite closing green.

What the change touches and the suite does not execute becomes a test, by
`safe-refactor` — including the check that the test is not empty. Where the
test lives, and what a new test class needs so that both runners find it, is
in step 3 of `safe-refactor`. Tests added raise `min-tests` in
`.github/workflows/ci.yml` and in `experimental.yml` in the same PR. What not
even the suite reaches goes to `golden-run`, `python-matrix` or `rebuild-vis`
by the table, and the blind spots that none of them covers (`AGENTS.md`) are
probed by hand and recorded in the PR.

A review inverts the order of `safe-refactor`: the change **already exists**,
so the test cannot be written against the old code. The way out is to write it
against the new behavior and prove the red **by simulating the previous
version** — with its code, never with a hand-written approximation. The
cheapest control is the file-level one of step 3: `git checkout "$base" --
<file>`, run the new test and see it red, `git checkout HEAD -- <file>`. The
worktree of step 3 when the environment differs; `uv run --with
"<pkg>==<old>" pytest` for a dependency.

**The reproduction must also go green when the defect leaves.** Today's red
proves it reaches the defect; only the control proves it is satisfiable —
disable the culprit line and check that it passes. Without that, an assertion
travels that no fix satisfies, and the author loses the round trying: an
output compared character by character, a UUID typed in, an order that the
store does not guarantee, an environment attribute that only exists on your
machine.

**A reproduction from a previous round is suspect again.** Run the old ones
before reading the new diff, and for each one that passed ask *why* it
passed: was the defect fixed, or did the fix open a path that returns before
reaching the point being measured? A precondition guard, an early `return`
on an empty store and a condition on the Python version leave the test green
without touching what it guarded. The test is the usual one: disable the line
of the fix and check that the test falls. One that passed for the wrong
reason is rewritten — and with it the comment that described the defect in
the present tense, otherwise the next round reads the description as if the
defect were still there.

## 6. Measure

The full suite by `safe-refactor`, compared with the baseline. When the diff
touches `src/noworkflow/tests/__init__.py` or moves tests, also the **parity
between the two runners**: `uv run python run_tests.py` prints `Ran N tests`,
and pytest's passed + skipped + xfailed + xpassed must be the same N — a test
that one runner collects and the other does not is a test that only runs on
one machine. When the two differ, pytest is the reference (it is what CI
runs), and the usual cause is a new test class that was not added to the
suites in `tests/__init__.py` (step 3 of `safe-refactor`).

Check also the CI at the tip of the branch: it runs what the local machine
does not — every supported Python, macOS, the frontend guard, lint, SAST, the
audits — and it is the measurement that reaches the blind spots `AGENTS.md`
lists.

**`gh pr checks <N>` exits non-zero while a check is pending, when one
failed, and when the branch has no checks at all** (a PR older than the
workflow), so treating a non-zero exit as a transient error to swallow makes
the waiting loop spin silently, and the silence is indistinguishable from
"still running". Pending *is* the state, not a failure to query it: decide by
the text of the output, never by the exit status. The status the ruleset
requires is `ci-ok`; the `test-experimental (...)` legs come from
`experimental.yml` and are not required — a red there is compared with the
same leg on `main` (`gh run list --workflow experimental.yml --branch main
--limit 1`) before being charged to the PR. A PR from a fork has no `coverage`
job, by the guard in `ci.yml`; that is not a failure either.

Then what the table routes: `dependencies` for the lock and the workflows,
`python-matrix` when the collector changed, `rebuild-vis` and `golden-run`
for the vis, `golden-run` for persistence, models, commands, patterns and
resources. A green suite says nothing about any of them.

## 7. Integrate

Before this, all of it has to be true: the full suite green on the branch, the
checks the table routed done, `main` synchronized, working tree clean, CI
green at the tip, and the second list of step 1 empty — otherwise
`merge-downstream` and measure again. The worktrees of step 3 are removed.
Your part of this step ends with that list, checked; the integration itself
is the maintainer's, and these are the commands they run:

```bash
git checkout main && git pull --ff-only
git merge --ff-only <branch>                # fails if the branch is behind
git push origin main
```

Then the issue gets its milestone (`gh issue edit <issue> --milestone
<version>`) and stays **open**: the version is the milestone, and the issues
of a milestone close when that version is released. The integration leaves a
pending item for the release when persistence, exports or commands changed:
the store-compatibility check of `golden-run` decides the version number.

## 8. Close the trail

Each thing learned has a place, and the criterion is the one of `AGENTS.md`,
in the section "A skill is a procedure, not a logbook": the mechanism goes to
the skill, the measurements and the path of the round go to a comment on the
issue.

One obligation before considering the PR closed: **a conclusion of yours that
fell to new evidence is corrected where it was written.** If it became a commit
message not yet pushed, ask the maintainer to rewrite the commit — the test
may survive with another framing, the wrong justification cannot become
history.
