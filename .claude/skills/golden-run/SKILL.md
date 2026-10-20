---
name: golden-run
description: Compares noWorkflow before and after a change by running the same corpus through `now` on both versions — the outputs the e2e goldens cover, the behaviors the e2e tests pin, one store read by both versions and a new trial recorded into it (together, the store-compatibility check), and the vis routes each version serves — and reports what differs. Use when a change touches persistence, the models, the commands, the exports, the patterns, the resources or the vis server, when a dependency upgrade changes what the store or the vis server runs on, before a release, and whenever a green suite is not evidence enough.
---

# Golden-run: the same corpus through two versions

Validates a change by running `now` twice — **before** and **after** — over
the same corpus, and comparing what comes out. It reaches what the suite does
not (`AGENTS.md`, "Blind spots of the suite"): two versions compared over one
corpus, the read commands with the flags `read_store.py` runs (its docstring
lists what it does not), a store of the previous version opened and recorded
into by the new code, and the vis routes as they are served.

**The value is in the control:** the same machine, the same Python, the same
versions of the dependencies, the same corpus and the same synthetic
environment; only noWorkflow's code changes. Without that, a difference of
interpreter, of a dependency or of the environment shows up as a difference
of the code, and there is no way to tell them apart.

## When it enters

- `review-pr` routes here a change under `now/persistence`, `now/models`,
  `now/cmd`, `patterns` or `resources`, a change to the vis server
  (`now/vis/**`) after `rebuild-vis`, and a change to the collector that
  changes what is recorded.
- `release` asks for it against the previous release; the
  store-compatibility check (steps 3 and 5) is the maintainer's input for the
  version number.
- `dependencies` sends here an upgrade of what the store or the vis server
  runs on (SQLAlchemy, Flask). An npm update changes only the bundle, which
  step 4 sees as a different sha1: that one goes to `rebuild-vis` and a
  browser.
- `merge-downstream` sends here a merge that touched models, exports or
  commands: the after side is the merge, and the before side each of its
  parents in turn, the declared list being the other side's changes.
- `safe-refactor` escalates here when the suite does not reach the change.

It does not replace the suite: it runs after the suite is green.

## Declare the expected differences first

Before running anything, write down the differences the change should
produce, by the criteria of step 8 of `safe-refactor`: none for a
refactoring or an upgrade, the corrected behavior for a fix, the new
behavior for a feature. For each one, name the command and the flag that
shows it. Against a release, the change is a range of commits:

```bash
git log --oneline <previous tag>..HEAD
git diff <previous tag>..HEAD --stat -- src/noworkflow ':!src/noworkflow/tests' src/frontend pyproject.toml
```

— every file that ships but the tests, the frontend whose effect reaches the
wheel through the bundle, and the dependencies.

The list is also an instrument check: **each declared difference must show
up in the comparison.** One that does not show means the instrument does not
reach it — not that the change has no effect. The goldens cover some flags
of some commands, and a difference outside them passes step 1 without a line
of diff; steps 2 to 5 exist for that.

## Where the round lives

Everything goes **outside the repository**, in a folder per round, created
before anything else:

```bash
R=~/noworkflow-golden/<date>_<version>_<label>
mkdir -p "$R/before" "$R/after" "$R/read" "$R/scripts"
```

- `<date>`: the day of the round (`YYYY-MM-DD`), to sort the folders.
- `<version>`: `git describe --tags --always --dirty` of the after side
  (`<tag>-<n>-g<sha>` between releases), for the folder's name only.
- `<label>`: what is compared (`vs-<previous tag>`, `pr<N>`).

pytest creates the directory `--basetemp` names, never its parents: the
`mkdir` is what lets step 1 run. Inside `R`: `before/` and `after/` (the venv,
the goldens, the stores), `read/` (steps 3 to 5), `scripts/` and `NOTES.md`
(the declared list, the identity of each side, the summary line of every run
and the result of each check). What the after side runs is the commit only
when `git status --short -- src pyproject.toml uv.lock` prints nothing — the
editable `.venv` also imports an untracked module under `src/`, which `git
describe --dirty` ignores: write that output in `NOTES.md`.

- **Outside the sandbox, the whole round.** `R` is outside the area the
  sandbox lets a command write to, and uv, pytest and the vis's ports need
  it off too.
- **One script per step.** Each call of the Bash tool starts a new shell, so
  variables and the current directory do not carry over: write each step as
  a `#!/bin/sh` script in `$R/scripts/` that sets `R` and
  `S=.claude/skills/golden-run/read_store.py` and `cd`s into the checkout.
  The scripts are also the record of what ran.
- **What the round found goes to the PR or the issue** ("Reading the
  result"), not to this folder: `R` holds stores with this machine's
  hostname and paths, and nothing in it is read from another machine. Remove
  it once the report is posted.

## The two sides

The after side is usually the working tree, with its `.venv` from
`uv.lock`; with `NOW_E2E_CMD` unset, the harness runs it as `python -m
noworkflow`. The before side is an installation of its own, in a venv on the
**same Python as `.venv`**, with the **dependencies of the after side's
lock**, so that only noWorkflow differs:

```bash
cd <checkout>
uv export -q --locked --no-emit-project --no-hashes --format requirements-txt --no-dev -o "$R/constraints.txt"
uv venv --no-python-downloads --python "$(.venv/bin/python -c 'import platform; print(platform.python_version())')" "$R/before/venv"
uv pip install --no-python-downloads --python "$R/before/venv/bin/python" -c "$R/constraints.txt" noworkflow==<previous>
```

That is a published version. For a commit (the merge-base of a PR, a tag), a
worktree outside the checkout, installed into the same kind of venv:

```bash
git worktree add --detach <outside>/nw-before <ref>
uv pip install --no-python-downloads --python "$R/before/venv/bin/python" -c "$R/constraints.txt" <outside>/nw-before
```

Seconds, with uv's cache warm.

- **When the change is a dependency upgrade**, the constraints come from the
  before side's lock instead (the `uv export` line above, run in a worktree
  of `<base>`): the difference is then the upgrade, which is what is
  measured.
- **`--no-python-downloads`** keeps uv from installing an interpreter, which
  needs the maintainer's go-ahead (`AGENTS.md`).
- **Keep `R` short.** When the path of the venv's interpreter exceeds about
  125 characters, uv writes the console script as a `/bin/sh` trampoline,
  and every trial that `now` records gains `SHLVL` and a second `PWD`: a
  difference in the environment table that is the launcher, not the code.
- **Never `uvx` or `uv run` as `NOW_E2E_CMD`**: each test runs in its own
  temporary home, so each one starts from an empty uv cache, writes the
  download to stderr (which fails the harness's empty-stderr check) and may
  pick another Python.

### Which side is which

```bash
"$R/before/venv/bin/now" -v; "$R/before/venv/bin/python" -c 'import noworkflow; print(noworkflow.__file__)'
.venv/bin/now -v;           .venv/bin/python -c 'import noworkflow; print(noworkflow.__file__)'
```

The module path must point into each side's own installation: the before
venv's `site-packages`, the checkout's `src/`. **`now -v` alone does not tell
the sides apart**: `version.txt` keeps the previous release's number until
the next release bumps it, so between releases the tree and the previous
release print the same version, and then the module path is what tells them
apart. In `NOTES.md` write `$R`, `<checkout>` and `<HOME>` in place of the
absolute paths: the tail is what decides.

The control is checked, not assumed: the same base interpreter (resolved: two
venvs may name it through different links), and the same packages but
noWorkflow. On a sound pair the first line prints nothing and the last prints
nothing but uv's `Using Python ...` line:

```bash
base() { "$1" -c 'import os, sys; print(os.path.realpath(sys.base_prefix))'; }
[ "$(base "$R/before/venv/bin/python")" = "$(base .venv/bin/python)" ] || echo "another interpreter"
uv pip freeze --python "$R/before/venv/bin/python" | grep -v '^noworkflow==' | sort > "$R/before/freeze.txt"
uv pip freeze --python .venv/bin/python | sort | comm -23 "$R/before/freeze.txt" -
```

That checks the installations. What each pytest run executed is checked
after step 2, from the stores the runs leave (`recorded_by`).

## Step 1 — The goldens, through the harness

The e2e harness is the executor (`src/noworkflow/tests/e2e/`): it builds the
stores of each golden test with the synthetic environment and normalizes the
output. `NOW_GOLDEN_DIR` sends the goldens to the round instead of the
repository (and skips the platform check: both sides run on this machine),
and `NOW_E2E_CMD` points the tests at the before side. Every directory is
**absolute**: the root `conftest.py` runs the session from a scratch
directory that it deletes at the end, and a relative path dies with it.

```bash
# the before side, recorded
GOLDEN=overwrite NOW_GOLDEN_DIR="$R/before/goldens" NOW_E2E_CMD="$R/before/venv/bin/now" \
  uv run --no-sync pytest src/noworkflow/tests/e2e -m "golden and not paper" -p no:cacheprovider --basetemp="$R/before/stores"
# the A/A control: the before side again, compared with its own recording
GOLDEN=require NOW_GOLDEN_DIR="$R/before/goldens" NOW_E2E_CMD="$R/before/venv/bin/now" \
  uv run --no-sync pytest src/noworkflow/tests/e2e -m "golden and not paper" -p no:cacheprovider --basetemp="$R/before/stores-aa"
# the after side, compared with the before recording
GOLDEN=require NOW_GOLDEN_DIR="$R/before/goldens" GOLDEN_ACTUAL_DIR="$R/after/actual" \
  uv run --no-sync pytest src/noworkflow/tests/e2e -m "golden and not paper" -p no:cacheprovider --basetemp="$R/after/stores"
```

Under a minute each. A failure of the last run is a difference, with its
unified diff in the output and the after side's text in `$R/after/actual`.
**Exit status 3, or a summary line with neither `passed` nor `failed`, is
the instrument failing**, not a result: read the `INTERNALERROR` lines.

- **`GOLDEN=require` is not optional.** Without it, a golden missing from
  the before recording is written there from the side under test and the
  test is skipped: the baseline silently becomes the thing it should
  measure.
- **Count the files.** Under `NOW_GOLDEN_DIR` the harness does not look for
  orphan goldens: `find "$R/before/goldens" -type f | wc -l` must equal the
  `passed` of the A/A run, and `passed + failed` of the after run (each
  golden either matched or differed; an xfailed test writes none), both read
  in the last line of each run. The summary lines go into `NOTES.md`.
- **`--basetemp` keeps the stores** of every test, built by that side with the
  synthetic environment (`<basetemp>/two_trials0` is the weather corpus after
  two trials); steps 3 to 5 read them. Each run needs its own: pytest wipes a
  `--basetemp` at the start of a session that reuses it.
- **The paper's running example is left out** (`and not paper`): under
  `NOW_E2E_CMD` its fixture does not check that the before side has the
  `paper` group, and without it the replay errors. To include it — the
  richest corpus, worth it when the change touches what is recorded — both
  sides need the group: `uv sync --locked --group paper` for `.venv` (and
  `uv sync --locked` afterwards), and for the before venv `uv export -q
  --locked --only-group paper --no-emit-project --no-hashes --format
  requirements-txt -o "$R/paper.txt"`, then `-r "$R/paper.txt"` on its
  install line.

Then the check that the comparator is not blind: plant a difference in a copy
of the recording and compare **the before side** with it, so that the
planted line is the only difference there is.

```bash
cp -R "$R/before/goldens" "$R/planted"
# change one line of one golden in $R/planted, then:
GOLDEN=require NOW_GOLDEN_DIR="$R/planted" NOW_E2E_CMD="$R/before/venv/bin/now" uv run --no-sync pytest \
  src/noworkflow/tests/e2e -m "golden and not paper" -p no:cacheprovider --basetemp="$R/before/stores-planted"
```

Exactly that golden fails, and its diff shows the planted line. The failure
message suggests recording the goldens again in the reference container:
that is for the repository's goldens, never for a round.

## Step 2 — The behaviors the e2e tests pin, against the before side

The e2e tests also assert behaviors outside the goldens (exit codes, files
written, flags such as `diff -fa`). Run them against the before side:

```bash
NOW_E2E_CMD="$R/before/venv/bin/now" uv run --no-sync pytest src/noworkflow/tests/e2e \
  -m "not golden and not paper" -p no:cacheprovider --basetemp="$R/before/stores-e2e" -ra
```

A few minutes. Each failure is a behavior the tests pin and the before side
does not have. Read it against the declared list:

- **Expected:** a test written to prove a declared difference fails here —
  that is the proof that it distinguishes the two versions. **One that passes
  against the before side does not test the difference.** Tests that pin
  what both versions share pass by design: against a release older than the
  e2e suite, that is most of them.
- **The normalizer's own tests** (`test_normalize.py`) run `now` twice and
  check that the masks equalize the outputs. One that fails here means the
  masks do not cover the before side's format (an unrounded value, for
  instance): read it against the declared list, and expect the golden of
  that command to be fragile on that side.
- **Unexpected:** a failure the list does not explain is a difference to
  investigate with `prove-candidate`.
- **Not evidence:** the tests that use `console_now` or branch on
  `runs_this_interpreter` never exercise `NOW_E2E_CMD`, or check only the
  shape of the output under it (`grep -n "console_now\|runs_this_interpreter"
  src/noworkflow/tests/e2e/test_*.py`); some skip, saying why in the `-ra`
  lines. Their result says nothing about the before side.

**What each run executed.** A `NOW_E2E_CMD` misspelled or pointing at the
wrong `now` passes every check above with the tree running in place of the
before side, and step 2 would then read the declared tests as not testing the
difference. The stores each run left record the `PATH` the harness gave
`now`, whose first entry is the directory of the command that ran; the query
reads the two trials the run recorded, so it still holds after step 5 adds
one of the other side:

```bash
recorded_by() { sqlite3 -readonly "$1/project/.noworkflow/db.sqlite" \
  "SELECT DISTINCT substr(value, 1, instr(value, ':') - 1) FROM environment_attr
   WHERE name = 'PATH' AND trial_id IN (SELECT id FROM trial ORDER BY sequence_key LIMIT 2)"; }
for s in stores stores-aa stores-planted stores-e2e; do
  [ "$(recorded_by "$R/before/$s/two_trials0")" = "$R/before/venv/bin" ] && echo "$s: ok" || echo "$s: WRONG SIDE"
done
[ "$(recorded_by "$R/after/stores/two_trials0")" = "$PWD/.venv/bin" ] && echo "after: ok" || echo "after: WRONG SIDE"
```

It compares without printing the paths. A run marked `WRONG SIDE` is
discarded and run again.

## Step 3 — The same store, read by both versions

The goldens normalize each side's own stores. The stronger comparison reads
**one store with both versions**: the trial ids, the clocks and the paths are
then the same, nothing needs masking, and whatever differs is how each
version reads and prints the same data. A store written by the previous
version and read by the new one is also the **store-compatibility check**:
`AGENTS.md` forbids claiming that old stores still open without opening one.

`read_store.py`, in this skill's directory, runs a fixed list of read-only
commands — `list`, `history`, `show` with each flag but `-e`, `diff` with
each flag but `-e`, `-a` and `-d`, `-fa` on every function that runs once in
each trial, every export but `ipynb`, `schema` in each form — with one
installation over one store root, in the harness's environment. Its
docstring lists what it writes, what it leaves out and why:

```bash
uv run --no-sync python $S "$R/before/venv/bin/now" "$R/before/stores/two_trials0" "$R/read/before-on-before"
uv run --no-sync python $S "$PWD/.venv/bin/now"    "$R/before/stores/two_trials0" "$R/read/after-on-before"
uv run --no-sync python $S "$R/before/venv/bin/now" "$R/after/stores/two_trials0"  "$R/read/before-on-after"
uv run --no-sync python $S "$PWD/.venv/bin/now"    "$R/after/stores/two_trials0"  "$R/read/after-on-after"
diff -r "$R/read/before-on-before/raw" "$R/read/after-on-before/raw"
diff -r "$R/read/before-on-after/raw"  "$R/read/after-on-after/raw"
diff "$R/read/before-on-before/summary.tsv" "$R/read/after-on-before/summary.tsv"   # upgrade
diff "$R/read/before-on-after/summary.tsv"  "$R/read/after-on-after/summary.tsv"    # forward
```

Under a minute per reader.

- **Compare `raw/`.** The store is the same on both sides, so the raw
  outputs are comparable as they are, and nothing a mask would hide (the
  format of a timestamp, a duration) escapes the comparison. The harness
  decodes with universal newlines, so a change of line ends never reaches
  `raw/`; compare the bytes of that command (`now ... | od -c`) when line
  ends matter.
- **The compatibility verdict is the difference between the `summary.tsv` of
  each pair**, not a return code alone. A store `now` cannot read makes it
  print `[now] invalid noWorkflow database` on stderr and exit 1; the script
  flags it (`invalid-db`), and also a `traceback` and a trial reference that
  found nothing (`not-found`). **Upgrade:** a flag that
  the after side gets on the before store and the before side does not
  breaks existing stores. **Forward:** a flag that the before side gets on
  the after store and the after side does not means the previous release
  cannot read the new stores — a release note, not a break.
- **A command flagged on both sides compared nothing**: like a skipped
  golden, it goes into `NOTES.md` as not compared, with its last stderr line
  (the last column of `summary.tsv`; its traceback differs only in the
  paths, `src/` against `site-packages`).
- **`store.txt`** describes each store before the commands: the schema, the
  rows per table and the names of the environment attributes. The two stores
  were built from the same corpus by each side, so
  `diff "$R/read/before-on-before/store.txt" "$R/read/after-on-after/store.txt"`
  is what the change does to what is recorded. A schema difference that the
  readers do not flag is a release note; with flags, or with step 5 failing,
  it breaks existing stores.
- **The script reports when the store changed while it was read**, and
  writes the store's fingerprint at each stage to `fingerprint.txt`: a reader
  that does not start where the previous one ended did not see the same
  store.
- **What is not compared here**: the commands that write (`restore`,
  `export ipynb`, `gc`, `import`), which step 2's tests pin, and the options
  the docstring lists as not run. When the change reaches one of them, run it
  by hand on stores each side built (a store cannot be moved: `AGENTS.md`),
  and say so in the report.

A diff to attach comes from `masked/` (the e2e normalizer, the reader's
installation and the environment left out): `raw/` holds the hostname and
the paths of this machine.

## Step 4 — The vis, served by each version

`--vis PORT` makes `read_store.py` also serve the store with that version,
fetch the routes its docstring lists (among them the bundle's sha1, every
asset the bundle names, each trial's graphs and the function diff of each
`-fa` pair) and stop the server. Serve the before store with each version in
turn; serving the after store is the forward direction, worth it when that
matters:

```bash
uv run --no-sync python $S "$R/before/venv/bin/now" "$R/before/stores/two_trials0" "$R/read/before-vis" --vis <port>
uv run --no-sync python $S "$PWD/.venv/bin/now"    "$R/before/stores/two_trials0" "$R/read/after-vis"  --vis <port>
diff -r "$R/read/before-vis/raw/vis" "$R/read/after-vis/raw/vis"
diff -r -x vis "$R/read/before-on-before/raw" "$R/read/before-vis/raw"     # the reader's A/A
```

- **Outside the sandbox**: inside it, binding a port is refused and so is a
  connection to `127.0.0.1`.
- **The port**: one that nothing listens on (`lsof -nP -iTCP:<port>
  -sTCP:LISTEN` prints nothing; the script refuses one that answers on
  `127.0.0.1`). On macOS, AirPlay holds 5000 (the vis's default) and 7000,
  and a browser sent to `localhost:5000` reaches it and gets 403 even while a
  vis started by hand listens on `127.0.0.1:5000`.
- **The index's status is part of the result**: a version whose index fails
  on the other version's store answers 500 there, and `vis.tsv` says so.
- **The bundle** is written as its sha1: each side serves the bundle of its
  own version, which is the vis's identity check. `raw/vis/assets.txt` says,
  for each hashed file the bundle names, whether the server returns it and
  whether its body is what its extension says.
- **The environment routes** are reduced to the attribute names.
- **The vis writes into the store**: every graph route stores a cache, so the
  second reader starts from another fingerprint, as the script reports. The
  routes are fetched with cache 0 — each one recomputes — so the second
  version's graphs are its own and the pair stays comparable. Run step 3
  before this one.
- **The reader's A/A**: `--vis` runs step 3's commands first, so its `raw/`
  must equal the earlier read of the same store by the same version. A line
  that differs varies between two reads, and step 3 cannot attribute it to
  the version.

## Step 5 — The upgrade path

Reading is half of compatibility: the first thing a user does after
upgrading is `now run` in an old project. Last, because it adds a trial to
the before store:

```bash
uv run --no-sync python $S "$PWD/.venv/bin/now" "$R/before/stores/two_trials0" "$R/read/after-run" \
  --run "simulation.py data1.dat data2.dat"
```

It passes when the run prints no flag and the trial count went up by one
(`run: ... trials N -> N+1`). A version that cannot record into an old
project prints `invalid noWorkflow database`, exits 1 and records nothing,
even when every read of step 3 passed.

## The instrument, not only the system

A broken comparator also returns "no difference", and that is the same
result as "nothing changed". None of these is optional:

- **Identity.** Each side is the code it claims, on the same interpreter
  with the same packages ("Which side is which"), and each run executed the
  side it claims (`recorded_by`, after step 2). When both print the same
  version, the module path settles it.
- **A/A.** The before side compared with its own recording passes whole
  (step 1), and the same version reading the same store twice prints the same
  (step 4). If not, something varies between two identical runs on this
  machine, and every A/B difference is suspect until it is understood — a
  gap of `normalize.py`, fixed through an issue of its own, or a known
  ordering ("Known noise").
- **Planted difference.** The comparator of step 1 flags the line planted in
  a copy of the recording. The flags of steps 3 and 5 are planted too: copy a
  store root (nothing from the copy is compared, so a copy is fine here),
  break its schema (`sqlite3 <copy>/project/.noworkflow/db.sqlite 'ALTER
  TABLE tag RENAME TO tag_planted'`) and read it with the after side: every
  command but `schema` is flagged `invalid-db`.
- **The same set on both sides.** A golden that one side did not produce
  (a skip, an xfail, an error), or a command flagged on both sides, is not a
  match: it is "not compared". The `-ra` lines and `summary.tsv` say why, and
  what was not compared goes into the report.
- **Every declared difference shows up.** If one does not, the instrument
  does not reach it: run the command that shows it (step 3 covers the read
  commands; anything else by hand) before concluding anything.

What the normalizer masks by design is in `Normalizer.__call__` of
`normalize.py`: trial ids, clocks, checkpoints, durations, addresses and the
volatile environment values, paths, the hostname, the Python and noWorkflow
versions. A change aimed at one of those fields — how a duration is printed,
the format of a timestamp — is invisible in the goldens of the command that
prints it, and visible in step 3's raw outputs. When the change also alters
an equality (a rounding that makes two durations equal), it may surface in
another command's golden — `now diff` drops a "changed" line — which then
looks unrelated to the change.

## Reading the result

- A difference in the declared list is the change working.
- One outside it goes through `prove-candidate`: a defect of the change, or
  a defect of the previous version that the change fixed without saying so
  (then the list was incomplete, and the PR says so).
- An upgrade flag (step 3) or a failed upgrade run (step 5): the change breaks
  existing stores. It is not for the round to accept: it goes to the
  maintainer, and to the release note. A forward flag (the previous release
  cannot read new stores) goes to the release note.

What goes to the PR (or to the issue, for a release): the declared list, the
identity of each side (paths written with `<HOME>`), the summary lines of
every run, the result of each instrument check, what was not compared and
why, and the masked diffs — never the stores, the raw outputs, `vis.log` or
anything from the environment. Before posting, both of these print nothing:

```bash
grep -rlF "$HOME" "$R"/read/*/masked
grep -rliF "$(hostname -s)" "$R"/read/*/masked
```

## Known noise

Differences that are not the change:

- `GET /trials/<id>/flow.pdf` answers 500 where Graphviz's `dot` is not on
  the PATH (`KeyError: 'application/pdf'`).
- `now export ast` fails on recent Pythons, in some forms or in all
  (`export_ast_failure` in `harness.py` says which, #241). Its goldens are
  xfail there on both sides, so the AST export is compared only on an older
  Python (below).
- Every hashed image the bundle names is served as JavaScript text, not as
  an image (`BAD magic` in `raw/vis/assets.txt`, on both sides, #263).
- On 3.11 the order of the blocks `now diff` prints can change from run to
  run (`AGENTS.md`, "Reproduction traps"): a `diff` golden or a `diff` output
  whose only change is a block that moved is noise there. Run the A/A
  several times on 3.11 before trusting it.
- Where `now export ast -d` works (before 3.15), it names its nodes after
  `id()` of the AST node: two reads of the same store differ in `raw/` and
  agree in `masked/`.

**The list is checked at every round and corrected there.** An entry that
stopped happening leaves in the same commit; noise that appeared enters with
its cause. An entry that changes between the sides is a signal, not noise.

## On another Python

The round runs on `.venv`'s Python by default. A change that concerns a
construct of one version, or the AST export, runs the round on that version:
both sides then become venvs on it (`uv venv --no-python-downloads --python
<v>`; the after side installed from the checkout, `uv pip install ... -e
<checkout>`), both are given through `NOW_E2E_CMD`, and pytest itself runs on
that Python — `uv run --isolated --locked --no-python-downloads --python <v>
pytest ...` — because the normalizer masks the version of the interpreter
that runs the tests. A `<v>` that `uv python list --only-installed` does not
list is an install: ask first.

## When the after side is not the working tree

A PR checked out by `review-pr` is the working tree, and its merge-base is
the before commit. When the after side cannot run the harness — a branch
older than `src/noworkflow/tests/e2e/` — the instrument comes from a worktree
of `main`, and both sides are installations given through `NOW_E2E_CMD`.
The instrument is always one checkout for both sides: a probe changed in the
middle of a round measures the probe.

## Closing

The script stops its own servers; check that no `now vis` is left
(`lsof -nP -iTCP:<port> -sTCP:LISTEN`). Remove the worktrees (`git worktree
remove --force`). Post the report, what was not compared included, where the
change is discussed; then `R` can go.
