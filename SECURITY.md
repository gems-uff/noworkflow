# Security policy

## Reporting a problem

Open a [public issue of type Bug](https://github.com/gems-uff/noworkflow/issues/new?template=bug.yml)
describing the problem: what you ran, what happened, and what you expected.
Security problems follow the same cycle as any other bug here, and there is
no private channel.

noWorkflow runs on the user's own machine, on the user's own scripts, and
never as a shared service: the `now vis` server listens on `localhost` by
default and serves the provenance store of the directory it was started in.
Describing a problem in public therefore does not expose anyone, and the
discussion in the issue is what gets the fix agreed and tested.

Do not paste the output of `now show -e`, a Prolog export or a `.noworkflow/`
directory from a real project into the issue: the provenance store records
the whole environment of the machine, including every environment variable,
the user name and the hostname. Reproduce the problem with a minimal script
and invented values.

## What is in scope

- The `now` command and everything it records, restores or exports.
- The `now vis` server and the pages it serves.
- The Jupyter magics, kernel and extension.
- The published package on PyPI and the files it installs.

## Supported versions

Fixes go to `main` and ship in the next release; older releases are not
patched. Keep the latest version installed (`pip install --upgrade
noworkflow`).
