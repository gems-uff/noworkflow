# Front-end development

This folder contains the source code related to the front-end of nowvis and Jupyter extensions.

It is structured as an npm workspace with all the sub-packages on the `packages` directory.

Currently, it has 4 packages:

- `utils`: helpers for the other packages.
- `history`: history graph definition. Depends on `utils`. 
- `trial`: trial graphs definition. Depends on `utils`.
- `nowvis`: now vis main interface. Depends on `history` and `trial`.
- `labextension`: jupyter lab (and notebook 7+) extension that allows visualizing noworkflow data (e.g. trial graphs). Depends on `history` and `trial`.

## Installing dependencies

On this folder (`npm`), run 

```
$ npm install
```

NPM workspaces will take care of symlinking all the sub-packages and installing the dependencies.

## Building nowvis

For a single build of all packages, run

```
$ npm run build
```

It will invoke `lerna` to orchestrate the build order in each sub-package.

For developping a package/nowvis, instead of this command, it is advisable to run:

```
$ python watch.py
```

This script constantly monitors changes on the files of the sub-packages and rebuilds all the appropriate packages in order.

## Building the jupyterlab extension

While the jupyter lab extension is part of workspace (and shares the dependencies), the process of installing it in development and monitoring file changes is different.

Start by running a single build of all packages:

```
$ npm run build
```

Then, install the labextension Python package in development mode and add it to jupyter lab:

```
$ pip install -e "packages/labextension"
$ jupyter labextension develop "packages/labextension" --overwrite
```

Finally, rebuild the extension after making changes

```
$ npm run build
```

For watching the source directory and rebuilding on file changes, you may run:

```
$ npx lerna run watch --scope=@noworkflow/labextension
```

(I haven't actually tested this watch command, since I just ported the old extension to the new format and it worked on the first try, but it will probably work)

## Adding new dependencies

To add a dependency to a sub-package, it is possible to run `npm install` and specify the workspace. For instance, if we decided to add the dependency `d3` to `nowvis`, the command would be:

```
$ npm install d3 --workspace=@noworkflow/nowvis --save
```

Note: nowvis already has d3 as a dependency, but the example is still valid. This command may update the version of d3 within the valid range specified in `package.json`.

## Cleaning the environment

When I was moving from the old package management to the current one, I had some inconsistencies in the dependencies. I do not know if they will happen again, but it they do, it is possible to reset reverything by running:

```
$ npx lerna clean
$ rm -rf node_modules
```

Then, don't forget to install and build again:
```
$ npm install
$ npm run build
```

Note: VSCode typescript server has a problem with these operations, so it is also advisable to press ctrl+shift+P and type "TypeScript: Restart TS Server".
