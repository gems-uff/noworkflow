# Front-end development

This folder contains the source code related to the front-end of nowvis and Jupyter extensions.

It is structured as an npm workspace with all the sub-packages on the `packages` directory.

Currently, it has 5 packages:

- `utils`: helpers for the other packages.
- `history`: history graph definition. Depends on `utils`. 
- `trial`: trial graphs definition. Depends on `utils`.
- `nowvis`: now vis main interface. Depends on `history` and `trial`.
- `labextension`: jupyter lab (and notebook 7+) extension that allows visualizing noworkflow data (e.g. trial graphs). Depends on `history` and `trial`.

What to install first (Node, and the `.venv` some of the commands below run in) is in "Development environment" in [CONTRIBUTING.md](../../CONTRIBUTING.md). Use the Node major of the `frontend` job in `.github/workflows/ci.yml`: it is the one that reproduces the committed `bundle.js`.

## Installing dependencies

In this folder (`src/frontend`), run

```
$ npm ci
```

It installs exactly what `package-lock.json` says, as CI does. NPM workspaces will take care of symlinking all the sub-packages and installing the dependencies.

## Building nowvis

To rebuild the bundle that `now vis` serves, `src/noworkflow/now/vis/static/dist/bundle.js`, run

```
$ npx lerna run build --scope=@noworkflow/nowvis --include-dependencies
$ git restore ../noworkflow/now/vis/static/dist/bundle.js.map
```

`lerna` orchestrates the build order of `nowvis` and of the packages it depends on. This is the build the `frontend` job of CI runs; it fails when the committed `bundle.js` differs from the result, so commit `bundle.js` together with the source change. The build also rewrites `bundle.js.map`, which is not reproducible (it embeds the absolute path of the checkout, home directory included); the second command discards it, and it is not committed.

For developing a package/nowvis, instead of this command, it is advisable to run:

```
$ uv run python watch.py
```

This script constantly monitors changes on the files of the sub-packages and rebuilds `nowvis` and the packages it depends on, in order (the `labextension` is disabled in the script).

## Building the jupyterlab extension

While the jupyter lab extension is part of workspace (and shares the dependencies), the process of installing it in development and monitoring file changes is different. Every command below needs Jupyter, which comes with the `notebook` extra, so they run through uv from a `.venv` that has it (`uv sync --locked --python <reference version> --extra notebook`, see CONTRIBUTING.md).

Start by running a single build of all packages:

```
$ uv run --no-sync npm run build
```

Without Jupyter in `.venv`, this build fails in the `labextension` package with `jupyter: command not found`.

Then, install the labextension Python package in development mode and add it to jupyter lab:

```
$ uv pip install -e "packages/labextension"
$ uv run --no-sync jupyter labextension develop "packages/labextension" --overwrite
```

The package installed this way is not in `uv.lock`, so the next `uv sync` removes it from `.venv`; install it again afterwards.

Finally, rebuild the extension after making changes

```
$ uv run --no-sync npm run build
```

For watching the source directory and rebuilding on file changes, you may run:

```
$ uv run --no-sync npx lerna run watch --scope=@noworkflow/labextension
```

(This watch command has not been tested: it was written when the old extension was ported to the current format.)

## Adding new dependencies

To add a dependency to a sub-package, it is possible to run `npm install` and specify the workspace. For instance, if we decided to add the dependency `d3` to `nowvis`, the command would be:

```
$ npm install d3 --workspace=@noworkflow/nowvis --save
```

Note: nowvis already has d3 as a dependency, but the example is still valid. This command may update the version of d3 within the valid range specified in `package.json`.

The command rewrites `package-lock.json`. Commit the lock together with the rebuilt `bundle.js`; the `dependencies` skill in `.claude/skills/` covers updates and the npm audit.

## Cleaning the environment

If the dependencies become inconsistent (it happened during the move from the old package management to the current one), it is possible to reset everything by running:

```
$ npx lerna clean
$ rm -rf node_modules
```

Then, don't forget to install and build again:
```
$ npm ci
$ npx lerna run build --scope=@noworkflow/nowvis --include-dependencies
```

Note: VSCode typescript server has a problem with these operations, so it is also advisable to press ctrl+shift+P and type "TypeScript: Restart TS Server".
