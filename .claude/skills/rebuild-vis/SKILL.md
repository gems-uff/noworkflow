---
name: rebuild-vis
description: Rebuilds the vis bundle (src/noworkflow/now/vis/static/dist/bundle.js) from src/frontend the way the `frontend` job of CI does, proves that a change reached it and that the bundle about to be committed is what its sources build, and smoke-tests what the working tree's `now vis` serves (compared with another version: golden-run). Use after any change under src/frontend (sources or the npm lock), on a Dependabot npm PR, after a merge that touched the frontend or the bundle, and when a change behind a vis route has to be seen served.
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
  images): rebuild, and the bundle goes in the same commit as the source.
- **A change to the npm lock or a `package.json`** (an update, by
  `dependencies`, part 3): rebuild. A package that only builds (a loader,
  lerna itself) leaves the bundle as it was; one that ships changes it.
  Either outcome is the measurement.
- **A Dependabot npm PR**: the same, on its branch. When the bundle did not
  change, there is nothing to push: the PR is green as it is. When it did,
  the maintainer pushes it to that branch as the last step before merging,
  after a `@dependabot rebase` has brought the branch up to date: once
  someone else's commit is on the branch, Dependabot stops rebasing it, and
  `@dependabot recreate` overwrites that commit (`review-pr`).
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
```

These are the job's steps, plus the restore: seconds with npm's cache warm,
more when `npm ci` has to fetch a package.

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
- **A change to a view** is seen only in a browser: from the checkout and
  outside the sandbox, `uv run --no-sync now vis -p <port> --dir
  <scratch>/bt/two_trials0/project` (`now` is not on the PATH), open
  `http://127.0.0.1:<port>/`, exercise the view the change touched, and write
  in the PR what was done and what came out. There is no automated test of
  the JavaScript. Stop the server afterwards.

## Commit

The maintainer commits `bundle.js` with the source change — and any new
asset the build emitted — in the same commit, never the rebuilt map. Show
the diff, the result of the guard and of the suite (with the one failure
above, until the commit); do not commit.

## What a rebuild does not prove

- That the vis works in a browser: the smoke above, by hand.
- That the Jupyter extension builds in full: `build:lib` is its type-check;
  `npm run build` with Jupyter in `.venv` is the full build
  (`CONTRIBUTING.md`).
- That the published extension (`noworkflow_labextension`) carries the
  change: it is released separately (`release`).
