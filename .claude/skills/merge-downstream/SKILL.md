---
name: merge-downstream
description: Brings main into an issue branch and checks that it came in whole — including what git cannot see. Use when bringing a branch that fell behind up to date, when auditing a merge someone else made, or before accepting a branch for integration.
---

# Merging main into the branch

Bringing `main` into an issue branch is routine, and because it is routine it
runs on autopilot. Two things go wrong silently: **content of `main` lost in
the resolution of a conflict**, and **an incompatibility that only exists
after the merge**, which git has no way of seeing. Both are detected by
measurement, not by reading.

The script `check_merge.sh`, in this skill's directory, runs the mechanical
checks in one go, from anywhere inside the repository:

```bash
"$(git rev-parse --show-toplevel)"/.claude/skills/merge-downstream/check_merge.sh [merge-commit] [upstream] [upstream-parent]
```

Without arguments it checks `HEAD` against `origin/main`. The third argument
says which parent is the upstream side, and git's rule decides it: **parent 1
is whatever was checked out when the merge was made.** A merge made on the
branch — `git merge origin/main`, or a `git pull` ("Merge branch 'master' of
<url>") — has the upstream side as parent 2, the default. A merge made on
`main` has it as parent 1: pass `1`. That is the shape of the one merge `main`
still accepts — a fork PR that cannot be fast-forwarded, the only case the
repository keeps the merge-commit option for — and of the merges in the
history from before the fast-forward rule ("Merge pull request #N …",
"Merge PR: …"). For a merge that upstream does not contain yet, the script
warns when the choice looks swapped; for one already in `main` the subject
decides, and the remote refs the script prints next to each parent help when
the branch still exists. Its exit
status carries no verdict (0 after a report, 1 when the arguments are
refused); what needs a human is marked `ATTENTION`. It needs git 2.38 or later
(`merge-tree --write-tree`).

What follows explains each check and what to do with the result; the last
section says which parts apply when the merge is someone else's and already
recorded.

## The merge is yours; so is the semantic conflict

**A conflict is not only overlapping text.** The two sides can each be
correct in isolation, overlap nowhere, git complains about nothing — and the
combination is broken. That is a semantic conflict, and it **is born at the
merge**: before it, the defect existed nowhere.

Hence the practical consequence: **whoever merges resolves it, before the
push.** It does not become an item on the list of whoever wrote the code,
because there was no defect in anyone's code. Fix it in a commit of its own,
on top of the merge, with the explanation in the message — the merge stays
verifiable against the automatic merge, and whoever reads it later understands
why that fix appeared out of nowhere. Both commits are the maintainer's, as
`AGENTS.md` says, one after the other: the merge first, then the fix on top
of it once it is recorded. Leave each ready in the tree and ask.

## Before: measure the distance

```bash
git fetch origin
git rev-list --left-right --count origin/main...HEAD   # behind / ahead
git log --oneline HEAD..origin/main                    # what comes in
git diff --numstat HEAD...origin/main                  # in which files
```

Everything against `origin/main` and `HEAD`, never against the local `main`
nor against `origin/<branch>`: `git fetch` does not advance the local `main`,
and a branch that came from a fork has no `origin/<branch>` at all — if the
origin has a namesake, the three commands resolve against the wrong branch
without complaint.

Cross the list of files `main` touched with the list the branch touched. The
intersection is where a real conflict can be — and where to look first
afterwards.

Rehearse before merging, in the order the merge will record:

```bash
git merge-tree --write-tree --name-only HEAD origin/main
```

It reconstructs the merge without touching the working tree. Exit status 0
means no textual conflict at all. With conflicts the status is 1, the first
line is still the tree, then come the conflicted paths and, after a blank
line, git's `CONFLICT` messages; `git show <tree>:<file>` reads the merged
file, markers included. A ref that does not resolve also exits 1, but prints
no tree.

Three kinds of branch need a word before the merge:

- **A branch older than `uv.lock`** has no lock, no root `conftest.py` and no
  pytest configuration on disk. Nothing goes through `uv` on that tree before
  the merge: every `uv run` there re-resolves and writes an untracked
  `uv.lock`, which then aborts the merge ("untracked working tree files would
  be overwritten"), and a `uv sync` there strips pytest from `.venv`. If it
  already happened, `rm uv.lock` before merging; after the merge, `uv sync
  --locked` puts `.venv` back on the lock the merge brought.
- **A Dependabot branch never receives a pushed merge.** What brings it up to
  date is a `@dependabot rebase` comment; `review-pr` says why.
- **A fork branch without `maintainerCanModify`** can be merged locally to
  measure, not pushed: the sync of step 3 of `CONTRIBUTING.md` goes back to
  the author.

The merge itself is `git merge --no-commit origin/main`: git stops before
recording it, so the resolution, the lock and the bundle land in the merge
commit, and that commit is the maintainer's like any other. The conflicts in
two files are **not resolved by hand**: `uv.lock` is re-resolved (below) and
`bundle.js` is rebuilt (`rebuild-vis`, whose steps are those of the
`frontend` job in `.github/workflows/ci.yml`). A resolution typed into either
one produces a file that no tool would produce.

Before asking, compare what is staged with the automatic merge — the same
comparison as the next section, on the index instead of a commit — and show
it with `git status` and `git diff --cached`:

```bash
git diff $(git merge-tree --write-tree HEAD MERGE_HEAD | head -1) $(git write-tree)
```

`check_merge.sh` needs the recorded merge: it runs once the maintainer has
committed it.

## After: what the human typed

**`git diff-tree --cc` does not serve for this.** It shows only the hunks
that match neither parent and leaves out every file equal to one of them, so
the resolution that replaced a file with one side's version — the one that
loses content — never appears in it. And `git show --stat` on a merge commit
is the diff against parent 1, not against both.

What really isolates it is reconstructing the automatic merge and comparing it
with the tree that was recorded:

```bash
AUTO=$(git merge-tree --write-tree <parent1> <parent2> | head -1)
git diff $AUTO <merge>^{tree}
```

Empty diff: nobody typed anything. Non-empty diff: what is left was typed by
someone — the resolution of a conflict, or not — and that is what to read.
When the pair conflicts, the reconstructed tree carries the conflict markers,
so the diff *is* the resolution. Two conflicts escape it:

- **Markers left in a recorded file** show as `<<<<<<<` and `>>>>>>>` lines
  in it, and only reading the file finds them: the reconstruction labels the
  markers with the parents' SHAs and `git merge` with `HEAD` and the ref, so
  the two never compare equal.
- **A binary or modify/delete conflict has no markers**: the reconstruction
  already holds one side's version, and a resolution that kept it leaves the
  diff empty while the other side's change is gone.

The sign of a resolution that **lost** content is a hunk that undoes what a
side had just done in that file — its added lines removed, or its removed
lines brought back — worse still when it lies outside the conflicted region,
which means the whole file was replaced by one of the versions instead of
merged.

Only some files can have lost something by hand: the ones in that diff, the
ones that conflicted, and the names they had before a rename on either side.
A file git merged by itself kept both sides' changes. The script asks the
loss question for those files alone, against each parent — the next section
says how.

## When parent 2 does not look like main

Before accusing the merge, check that the oddity is not this repository's
own integration. In the normal cycle integration is **fast-forward** (step 6
of `CONTRIBUTING.md`): `main` receives no merge, it is advanced over the
branch — and it is the branch that had merged `main` into itself. Each
fast-forward **redirects the first-parent chain of `main`** into that branch,
and what was the top of `main` ends up on the second-parent side.

The consequence misleads: `git log --first-parent main` stops showing commits
that really were the top of `main`. A legitimate merge, made when that commit
was the top, comes to look as if it had merged some arbitrary branch — and
sometimes the commit is even called "Merge branch 'main' into issue_NNN" of
**another** issue, which reinforces the wrong impression.

Two questions settle it, and neither of them is `--first-parent`:

```bash
git merge-base --is-ancestor <parent2> origin/main   # did that ever reach main?
git reflog show --date=iso origin/main               # what the ref pointed at, and when
```

The reflog dates each window, so you can tell whether the merge took the top
of the moment or an already stale one — and how much lag, which is the
information that matters. It only reaches as far back as this clone has seen
`origin/main` move: on a fresh clone it is empty. For an older merge the
script counts instead the commits of upstream that the merge does not have
and that were committed before it — an upper bound on the lag, since every
branch fast-forwarded into `main` after the merge brings commits dated
before it.

To know whether something from the upstream side was lost, look at the net
difference against **that parent** (not against the current top of `main`,
which has moved on), file by file for the candidates of the previous section.
For each file that differs, ask whether the upstream side touched it since
the merge base of the two parents (`git merge-base <parent1> <parent2>`). If
it did not, the difference belongs to the branch and all is well; if it did,
read the hunk. The script asks this for both parents, because a resolution
can also drop what the branch had.

## What git does not see

After green on the textual side, look for the new incompatibility. The places
where it lives in this project:

- **A model and its readers.** A column added or renamed in
  `src/noworkflow/now/persistence/models/` on one side, while the other side
  changed a reader: `now show`, `now diff`, an export in
  `src/noworkflow/now/cmd/cmd_export/`, the Prolog side
  (`src/noworkflow/resources/rules.pl` and `now/models/trial_prolog.py`, which
  match a fact by arity — one attribute more and every rule over that fact
  stops matching, with no error), the vis (`now/vis/views.py` and the
  TypeScript under `src/frontend/`). The executed sweep over the readers of a
  field is in `prove-candidate`; the exports and the vis have no test that
  compares their output, so the sweep is `golden-run` (the same corpus
  through `now` on both versions, the outputs compared).
- **An AST handler and the transformer.** A node handled on the branch in
  `prov_definition/transformer_stmt.py`, `transformer_expr.py` or
  `prov_execution/collector.py`, while `main` refactored the transformer: the
  handler compiles and is never called, and the construct is silently
  recorded less than before. A failing parse is loud (`Skipping
  transformer`); a handler that nobody calls is not. A `CollectionTestCase`
  for the construct, run after the merge, is what tells.
- **A dependency moved under code written against its internals.**
  `AGENTS.md` ("Patches of third-party internals") lists the code that
  depends on the internals of Python or of a library: the `open` wrappers,
  `pkg_resources`, the SQLAlchemy 1.4 API, `pyposast`, the magics. When one
  side moved one of those packages in `uv.lock` and the other side touched
  the code written against it, the two pass separately. The lock diff below
  says which packages moved; for each one that the list names, read its
  changelog between the two locked versions (`safe-refactor`, step 1).
- **`tests/__init__.py` and pytest discovery.** A test class the branch added
  is found by pytest by file name; `run_tests.py` only sees it through the
  import in `src/noworkflow/tests/__init__.py`. When `main` also changed that
  file, the merge may be clean and the two runners disagree: the parity check
  of step 7 of `safe-refactor` after the merge.
- **The test floor.** Both sides added tests and each raised `min-tests` in
  `.github/workflows/ci.yml` and `experimental.yml` by its own delta. The
  lines conflict, the resolution keeps one of the numbers, and the floor ends
  below the count whichever it keeps — which CI never notices, because it
  only fails below the floor. The right number is the count of the suite
  after the merge.
- **The bundle.** `bundle.js` is a build output with tens of thousands of
  lines, and `.gitattributes` gives it `-text` but no `merge` attribute, so
  git merges two builds line by line: the result is a file that no build
  produces, often without a textual conflict. When both sides touched
  `src/frontend/**` or the bundle, or one side touched the sources and not
  the bundle, `rebuild-vis` after the merge. The script's bundle section
  is the decision: a side that brought its sources and its bundle together,
  with the other side touching neither, needs no rebuild.
- **A test from `main` against a model the branch changed.** The two sides
  pass separately — the new test does not know the branch's model, and the
  branch's suite did not have that test — and only the full suite after the
  merge tells. It also holds for a branch that is already up to date: "up to
  date" is a statement about the instant of the measurement, and the test can
  land on `main` after it. There is no version to resynchronize here: decide
  which side is right, the test or the model, and fix the wrong one before the
  merge.

When one of the first three bites, the fix on top of the merge also leaves a
guard, or the merge after this one repeats the search: a test that fails the
next time the other side moves — the arity of a model's Prolog facts against
the arity `rules.pl` uses, a `CollectionTestCase` for the construct the
handler records, a test of the patched behavior. The floor and the bundle
already have theirs in CI.

## `uv.lock`

A textual merge of the lock can produce an incoherent file, and that is the
right worry. But **do not regenerate the lock from scratch.** Deleting it and
running `uv lock` is `uv lock --upgrade` in effect: with no lock there is no
version to prefer, every package goes to the newest its constraints allow, the
diff becomes unreadable and the merge stops being about the branch. `uv lock`
over an existing lock keeps every locked version it can keep and moves only
what the constraints force.

When git left conflict markers in the lock, uv refuses to parse it (`uv lock`
and `uv lock --check` both exit 2 with a TOML error). Take the upstream side
first — `git checkout --theirs uv.lock`, since in `git merge origin/main` run
on the branch "theirs" is `main` — and only then re-resolve. That drops the
versions the branch had moved itself (an `uv lock --upgrade-package` of its
own): `uv lock` keeps `main`'s, and nothing complains. List them before the
merge, and redo those steps after it:

```bash
.claude/skills/dependencies/lock_versions.sh $(git merge-base HEAD origin/main) HEAD   # the > lines: what the branch moved
```

So the check changes nothing it does not have to:

```bash
uv lock --check      # exit 0: the merged lock is what uv would resolve
uv lock              # exit 1 above: re-resolve, keeping every version it can keep
uv sync --locked     # and put .venv on it
```

Then compare the locked versions with the upstream side, with the extractor
that `dependencies` carries — right after the merge `origin/main` is the
upstream parent, and `uv.lock` is the lock on disk, the one `uv lock` just
wrote:

```bash
.claude/skills/dependencies/lock_versions.sh origin/main uv.lock   # from the repository root
```

Relative to `main`, the healthy result of a catch-up merge is **additions
only** (`>`) — the packages the branch introduced or moved, plus their
transitives. Any *different* version of a package the two sides already had
deserves an explanation. Relative to the branch, nothing the branch moved may
disappear: `lock_versions.sh HEAD uv.lock` in the middle of the merge, and the
script's lock section after it, show a version the branch had introduced
that the merge no longer has. The lock resolves separately per Python version
(uv calls each resolution a fork), so a package appears once per locked
version, and a change can show as a fork added or removed.

`uv lock --check` green says the lock is consistent with `pyproject.toml`,
not that it is the lock you wanted: a side that ran `uv lock
--upgrade-package` moved packages the branch never meant to touch, uv keeps
them, and the check still passes. The version diff is what tells.

`pyproject.toml` changed on both sides merges cleanly when the lines differ,
and the lock may then match neither — it does when a side changed
`pyproject.toml` without locking again; `uv lock --check` tells, and `uv lock`
settles it. When the two sides changed the **same** dependency — the branch
bumped it, `main` pinned it — that is a decision, not a resolution: back to
`dependencies`.

## Auditing a merge that is already recorded

Someone else's merge, or one already on `main`, is audited by the script with
the commit and the right third argument, and by reading three sections above:
what the human typed, the parent that does not look like `main`, and what git
does not see. The rehearsal, the `--no-commit`, the lock commands and the
push do not apply. On a merge that is already in `main`, "does the merge
contain everything" reads as lag, not loss.

What still needs a measurement is measured at the merge commit and at each
parent, each in a detached worktree outside the checkout (`git worktree add
--detach <outside>/<name> <commit>`, removed with `git worktree remove
--force`). A tree older than `uv.lock` or than the pytest configuration does
not go through `uv`: its suite is `run_tests.py`, run with the checkout's
interpreter and the worktree's sources first on the path, and its `Ran N
tests` is the count:

```bash
cd <outside>/<name> && PYTHONPATH=src <checkout>/.venv/bin/python run_tests.py
```

The bundle is rebuilt at the merge only when the script's bundle section
says so; the frontend job's steps there, and `git diff --quiet` on
`bundle.js`, say whether the committed bundle matches the merged sources.

## Closing

The full suite from the root (`uv run pytest`), the count against the floor
and, when `tests/__init__.py` is in the merge, the parity between the two
runners — the three are in `safe-refactor`. `uv run ruff check .`. Then the
maintainer pushes, so that CI measures at the tip what the local machine does
not: every supported Python, macOS, the frontend guard, the audits.

With one reservation worth keeping: **a green suite does not prove the
absence of a semantic conflict.** Of the places listed above, the suite
settles the handler (when a test exercises the construct), the parity, the
floor and the test from `main`; it never reaches the readers of a model — the
exports, the Prolog rules, the vis — nor the bundle (`AGENTS.md`, "Blind
spots of the suite"). The suite closes the merge; what looks for the semantic
conflict there are the checks above, `golden-run` when the merge touched
models, exports or commands, and `rebuild-vis` for the bundle.
