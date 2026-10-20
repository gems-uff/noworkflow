---
name: rebuild-vis
description: Rebuilds the vis bundle (src/noworkflow/now/vis/static/dist/bundle.js) from src/frontend the way the `frontend` job of CI does, proves that a change reached it and that the bundle about to be committed is what its sources build, smoke-tests what the working tree's `now vis` serves (compared with another version: golden-run), runs the browser tests on the rebuilt bundle, and compares in headless Chrome what the vis draws and does with the base bundle and with the rebuilt one. Use after any change under src/frontend (sources or the npm lock), on a Dependabot npm PR, after a merge that touched the frontend or the bundle, and when a change behind a vis route has to be seen served.
---

# Rebuilding the vis bundle

`now vis` serves `bundle.js` from the installed package, so the bundle is
committed: whoever installs noWorkflow never runs npm. The price is that a
change under `src/frontend` reaches nobody until the bundle is rebuilt and
committed with it, and nothing in the source change forces that. The
`frontend` job of `.github/workflows/ci.yml` is the guard: it rebuilds the
bundle from the sources and fails when the result differs from the
committed file. This skill is how to satisfy it, and how to see the change
working, which the guard never does.

## When it enters

- **A change under `src/frontend/packages/**`** (TypeScript, styles,
  images): rebuild, compare in a browser, and the bundle goes in the same
  commit as the source.
- **A change to the npm lock or a `package.json`** (an update, by
  `dependencies`, part 3): rebuild. A package that only builds (a loader,
  lerna itself) leaves the bundle as it was; one that ships changes it.
  Either outcome is the measurement, and a changed bundle goes through
  "Before and after in a browser".
- **A Dependabot npm PR**: never merged as it stands (`dependencies`, "A
  Dependabot PR is a signal, not the step"). On its branch, rebased on
  `main`, rebuild: a package that only builds leaves the bundle as it was;
  one that ships changes it, and the maintainer amends the rebuilt bundle
  into the bot's commit before pushing it back to the PR's branch.
- **A merge where both sides touched the frontend or the bundle, or one side
  changed the sources and not the bundle** (`check_merge.sh` of
  `merge-downstream` says which): rebuild after the merge. A bundle is never
  resolved by hand: git merges two builds line by line into a file that no
  build produces. When one side changed the bundle without its sources, "The
  guard, locally" at the merge says whether the bundle is what the sources
  build.
- **A change behind a route of the vis** (`src/noworkflow/now/vis/**`, or a
  model a route serves, such as the prospective graph): no rebuild; the
  smoke below is what shows it served.

## Before building

**The Node major.** The job pins one (`node-version`), the major measured to
reproduce the committed bundle byte for byte, and nothing else in the
repository pins it. Check yours against it:

```bash
sed -n 's/.*node-version: "\([0-9]*\)".*/\1/p' .github/workflows/ci.yml
node --version
```

Another major may produce a different bundle from untouched sources, and
that diff is the toolchain, not the change. Installing Node, or another
major, is an install on the machine: `AGENTS.md` says to propose it and wait.

**Outside the sandbox, all of it.** Inside the Claude Code sandbox `npm ci`
exits 0 after printing `npm warn tar TAR_ENTRY_ERROR EPERM` for the files it
could not write (those under `.idea/` and `.vscode/` of a few packages), the
lerna build dies after about two minutes with an opaque `lerna ERR! lerna
undefined`, and a `node_modules` created outside cannot be removed from
inside: `npm ci` there fails halfway and leaves it broken. Run npm and lerna
outside, every time; a broken `node_modules` is fixed by an `npm ci` outside.

## The build

```bash
cd src/frontend
npm ci --no-audit --no-fund
npx lerna run build --scope=@noworkflow/nowvis --include-dependencies
npx lerna run build:lib --scope=@noworkflow/labextension
git restore ../noworkflow/now/vis/static/dist/bundle.js.map
cd ../.. && git status --short
bash .github/scripts/tsc-baseline.sh "$(sed -n 's/.*tsc-baseline.sh \([0-9]*\).*/\1/p' .github/workflows/ci.yml)"
```

These are the job's steps, plus the restore: seconds with npm's cache warm,
more when `npm ci` has to fetch a package. The last line is the job's `tsc`
baseline: babel builds the bundle without checking types, so the count of
type errors is checked apart, and it only means something after the build
(without the `lib/` it writes, every `@noworkflow/*` import is one more
error). A change that removes errors lowers the number in the job in the
same commit.

- **`npm ci`, never `npm install`.** `ci` installs exactly what
  `package-lock.json` says and leaves it as it is; `install` may rewrite the
  lock, and a change to the lock is an update, with its own skill.
- **The first build writes the tracked `bundle.js` and `bundle.js.map`**, and
  the ignored `lib/` of the packages it builds. **The second is the job's
  type-check of the Jupyter extension**: it reads that `lib/` (alone it fails
  with `TS2307: Cannot find module '@noworkflow/utils'`) and writes only
  ignored files (the extension's `lib/` and `tsconfig.tsbuildinfo`). The full
  extension build needs Jupyter (`CONTRIBUTING.md`, "The frontend").
- **The rebuilt map is never committed.** Every build rewrites
  `bundle.js.map` with the absolute path of the checkout, home directory
  included; the restore puts the tracked one back, after every build.
- **Whether `bundle.js` changed** is in the build's log: `[emitted]` when
  it did, `[compared for emit]` when it did not — and then webpack does not
  even touch the file, so its modification time proves nothing. The sha1
  does.

## Reading `git status`

After the build, one of three:

- **Nothing**, or only the files of the change under test (an updated lock
  that is not committed yet, for one). The committed bundle already matches
  the sources: the expected result for a package that only builds, and for a
  branch that was rebuilt before. `npm ci` leaves the lock as it found it
  (`git hash-object src/frontend/package-lock.json` is the same before and
  after).
- **`M src/noworkflow/now/vis/static/dist/bundle.js`**, plus the sources of
  the change, plus — when the change added or replaced an image — a new
  hashed file under `static/dist/`. All of it goes into one commit, by the
  maintainer. The guard compares only `bundle.js`, so a new asset the build
  emitted and nobody committed is not caught by CI. Every hashed file the
  bundle names must be tracked:

  ```bash
  for f in $(grep -ohE '[0-9a-f]{20,32}\.(png|svg|gif|jpe?g|woff2?|ttf|eot)' src/noworkflow/now/vis/static/dist/bundle.js | sort -u); do
    git ls-files --error-unmatch "src/noworkflow/now/vis/static/dist/$f" >/dev/null 2>&1 || echo "not tracked: $f"
  done
  ```

  (it prints nothing when they all are; a new one is committed with the
  bundle).
- **Anything else** — a lock or a source the change did not touch, an
  untracked file outside `static/dist/`. The build or npm changed what it
  should not: stop. The usual causes are another Node major, or an `npm
  install` where `npm ci` was meant.

**Until the commit, `uv run pytest` has one failure, by design:**
`test_now_vis_serves_the_committed_bundle` compares what `now vis` serves
with the bundle at `HEAD`, and nothing but the commit changes `HEAD`. It goes
green with the commit; do not "fix" it.

## Prove that the change reached the bundle

A rebuilt bundle is not evidence that it holds the change. The bundle is not
minified, so a string the change introduced — a label, a class name — is
there as written:

```bash
git show HEAD:src/noworkflow/now/vis/static/dist/bundle.js | grep -c '<new string>'   # 0 before
grep -c '<new string>' src/noworkflow/now/vis/static/dist/bundle.js                 # > 0 after
git diff -U0 -- src/noworkflow/now/vis/static/dist/bundle.js                        # the transpiled lines
```

and the string it replaced the other way round. A count that did not move
means the package is not in the build's scope or the module is not imported
by `nowvis`.

## The guard, locally

The job builds and then runs `git diff --quiet` on the bundle: in CI the
index is the commit, so that compares the committed bundle with a fresh
build. Locally, two cases; the pathspecs start with `:/` so that they mean the
same from `src/frontend`, where the build runs, as from the root:

- **A commit that already has its bundle** (a branch under review): on a
  clean tree (`git status --porcelain` prints nothing), build, then

  ```bash
  git diff --quiet HEAD -- :/src/noworkflow/now/vis/static/dist/bundle.js; echo $?
  ```

  1 is the job's red: the sources changed after the bundle was built.
- **A change not committed yet:** the build reads the working tree, so what
  it wrote is what the commit will build only when the commit takes the
  working tree's frontend as it is. `git status --short -- :/src/frontend`
  must list only files of the change, every one of them going into the
  commit — a new module left untracked builds here and fails the job with
  "Module not found". The index is the maintainer's: nothing is staged for
  this.

## Smoke: what `now vis` serves

The guard compares files; nothing in CI serves them, and nothing runs the
JavaScript (`AGENTS.md`, "Blind spots of the suite"). Serve a store of the
test corpus — never a real one, which records the environment of the machine
— and fetch what the vis reads. The e2e harness leaves such a store when
pytest keeps its temporary directories, and `read_store.py` of `golden-run`
serves it and fetches the read routes its docstring lists:

```bash
uv run --no-sync pytest src/noworkflow/tests/e2e/test_show.py -k test_list_shows -p no:cacheprovider --basetemp=<scratch>/bt
uv run --no-sync python .claude/skills/golden-run/read_store.py "$PWD/.venv/bin/now" <scratch>/bt/two_trials0 <scratch>/smoke --vis <port>
cat <scratch>/smoke/raw/vis/dist-bundle.js.txt; shasum src/noworkflow/now/vis/static/dist/bundle.js
cat <scratch>/smoke/raw/vis/assets.txt
```

Off the reference platform that golden test skips after building its store,
which is all this needs. The script runs its CLI commands before serving, so
the smoke takes about a minute. `vis.tsv` lists each route with its status;
the bundle's sha1 is the one the working tree holds; `assets.txt` says, for
each hashed file the bundle names, whether it is served and whether its body
is what its extension says. How the server runs (outside the sandbox, a free
port, `127.0.0.1`), the routes that always fail and what the vis writes
into the store are in `golden-run`, step 4 and "Known noise".

- **A change behind a route** shows as a difference: read the same store
  with the `now` of `main` and with the `now` of the change, each into its own
  OUT, and `diff -r` the two `raw/vis/` (and `raw/`). The `now` of the change
  is the `.venv` of a worktree that holds it; a branch that cannot be synced
  (one older than `uv.lock`) is applied as a diff onto a worktree of `main`.
  `golden-run` does this in full, with its controls.
- **A route the script does not fetch** (its docstring lists them) is
  fetched by hand from a server started as below, with `curl` on
  `127.0.0.1`. `/trials.json` needs its three parameters
  (`?script=*&execution=*&summarize=0`, as the frontend sends them); bare, it
  answers 500.
- **A change to a view, or to a package the bundle ships,** is seen only in
  a browser: the next section.

## In a browser

Two tools run the JavaScript, and they answer different questions.

**The browser tests** (`src/noworkflow/tests/browser/`, marked `browser`;
"The vis in a browser" in `CONTRIBUTING.md`) assert that each view opens
and does what its input asks: a wheel zooms, a drag pans by the distance
dragged, a click selects or folds, a query answers, and nothing reaches the
console. They run in the `vis-browser` job of CI against the committed
bundle. Run them after every rebuild, before the commit, on the rebuilt
bundle the working tree's `now vis` serves:

```bash
uv sync --locked --group browser && uv run pytest -m browser
```

(outside the sandbox: each test binds a port). A red one is a regression of
the vis, or a test to adapt when the change altered that view on purpose,
in the same commit. The selectors and the ways to reach each view live in
`page_helpers.js` next to them, which the comparison below loads too.

**The comparison** shows everything a new bundle changes, including what no
test asserts: a stylesheet, a layout a few pixels off, a class, the exact
scale of a zoom. That is what an update needs, because nobody knows in
advance where a package will change something.

## Before and after in a browser

A green suite, browser tests included, says only that what the tests assert
still holds. For an update of a package the bundle ships (`@lumino/*`, d3,
svg-pan-zoom, `@viz-js/viz`, ace, tau-prolog, webpack and Babel, which
write the bundle) or a change to the sources of the vis,
`compare_vis.mjs`, in this directory, serves the store of the smoke above
and drives the same scenario in headless Chrome with the base bundle, with
the base bundle again (the control) and with the new one, and compares,
step by step, the DOM, the measures of each interaction and the events.
Its docstring has the details; what follows is when to run it and how to
read it.

**When:** every step whose build `[emitted]` the bundle, before the
maintainer commits it, and a source change to a view, whose difference is
then the expected one. Not when the bundle came out as it was: the same
bundle runs the same.

```bash
node .claude/skills/rebuild-vis/compare_vis.mjs <scratch>/bt/two_trials0 <scratch>/vis-compare
```

From the root and outside the sandbox, like the smoke; about two minutes.
By default the base is `bundle.js` at `HEAD` and the new one the working
tree's, which is the case of a rebuild not committed yet; on a branch whose
commit already holds the bundle, `--base` takes the bundle of `main`
(`git show main:src/noworkflow/now/vis/static/dist/bundle.js >
<scratch>/main.js`). The bundle is swapped inside the browser and the tracked
file is never touched. It needs Chrome or Chromium (`--chrome`, or the
`CHROME` variable, when it is not where the script looks) and a Node with a
global WebSocket, 22 or later (the job's major, above, is newer); installing
a browser is an install on the machine.

**The scenario.** In phases, each on a freshly loaded page: the history
graph (wheel zoom, drag); a trial (its graph, wheel zoom, drag, a click
that folds a node, a fold of the information tab), the diff of the two
trials (Shift+click), the drag of a split handle and the close of a tab;
the dataflow (svg-pan-zoom: wheel zoom, a drag that brings a box node into
view, a click that selects it); the prospective graph (its zoom button, a
drag); the Prolog export and a query that tau-prolog answers; the main
tabs, the database graph, a table's tab, the SQL editor (ace: text typed
into it) and a query; the drag of a table. The control's noise is
discounted line by line; the ids that differ between two runs of the same
bundle are masked, the randomness the vis draws ids from is seeded, and
the coordinates of the database graph are masked, because a click or a
drag on a table reheats d3-force's simulation, whose ticks follow the
clock (for the drag, only whether the table moved is compared).

**Reading `report.txt`.** One line per step; `same` (or `same (noise N)`)
in all three columns is the result for a dependency that should change
nothing. Exit 0: no difference beyond the control.

- **`dom DIFF`**: `diff/NN-step.diff` has base against new. A `<style #…>`
  line is a stylesheet a package ships; a `style="… top/left/width …"` is
  layout; a class or an attribute is how a widget renders. For a change to
  the sources, the steps that show the changed view differ and the diff is
  what the change meant; anything else is a finding. For an update, every
  difference is a finding, read against the package's changelog.
- **`measures DIFF`**: an interaction does something else (another
  transform after a wheel, another tab current, a node that no longer
  folds); both sides are printed. `NO NEW SNAPSHOT` with an error on the
  new side: the step could not act with the new bundle (nothing to click,
  a view that never came up), which is a regression unless the change
  removed that view on purpose.
- **`events DIFF`**: a console error, an uncaught exception, a dialog or a
  failed request that the base did not have.
- **`BASE FAILED`, exit 2**: the base bundle did not get through a step,
  so the scenario no longer matches the vis (a selector or a label the
  sources changed). Adapt the scenario with `--runs base`, which runs only
  that bundle and writes `base/steps.json` with where each input went, in
  the same commit as the change to the vis; nothing is concluded from a
  comparison that did not run.

Known noise, the same in every run: `http 404:
/experiments//extendedAnnotation` (the annotation widget asks for the
experiment the history page does not have) and `/favicon.ico`.

The `.dom.txt` files and `server.log` hold the store's synthetic
environment and its paths: read them here; what goes into the PR or the
issue is the report and the description of a difference, as for the smoke.

**What it does not reach:** the write routes (restore, push, pull, the
remotes, experiments, groups, annotations) and their modals; the "generate
prov" tab; the function activation diff; the exclusion of prior provenance
in the dataflow; the downloads; the tooltips; the project page that `/` opens instead of
the history when the store has experiments or no trial; and the Jupyter
extension, which only `build:lib`
type-checks (codemirror and `@jupyterlab/*` are its packages). A change to
one of these is exercised by hand: `uv run --no-sync now vis -p <port>
--dir <scratch>/bt/two_trials0/project` from inside that project, with
`.venv/bin` on the `PATH` (the `/commands/*` routes run a bare `now`
without `--dir`, #356, and answer empty otherwise), open
`http://127.0.0.1:<port>/`, and write in the PR what was done and what came
out. CI does not run the comparison: its result is a list of differences
to read, not a verdict, and every intended change to a view is one.

## Commit

The maintainer commits `bundle.js` with the source change — and any new
asset the build emitted — in the same commit, never the rebuilt map. Show
the diff, the result of the guard, of the browser tests, of the comparison
in a browser and of the suite (with the one failure above, until the
commit); do not commit.

## What a rebuild does not prove

- That the vis works in a browser: the browser tests and the comparison
  above, for the views they reach, and by hand for the rest.
- That the Jupyter extension builds in full: `build:lib` is its type-check;
  `npm run build` with Jupyter in `.venv` is the full build
  (`CONTRIBUTING.md`).
- That the published extension (`noworkflow_labextension`) carries the
  change: it is released separately (`release`).
