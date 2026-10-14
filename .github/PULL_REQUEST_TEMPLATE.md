<!--
Keep the PR as a draft until every box below is checked. Do not write
"Fixes #NNN" or "Closes #NNN": the issue is closed at the release, through
the milestone. See CONTRIBUTING.md.
-->

## Issue

Issue #NNN (the solution was agreed there before coding).

## What changes

<!-- What the branch does and why, in a few lines. For a bug, which test
fails on `main` and passes here. For a new or changed command or option, the
output the user sees. -->

## Checklist

- [ ] The branch is `issue_NNN`, based on `main`, and `main` was merged into it before this PR
- [ ] Every commit subject starts with `Issue #NNN: `, imperative, no trailing period
- [ ] A test covers the change of behavior (for a bug: it fails on `main`)
- [ ] `uv run pytest` is green from the repository root, and `min-tests` in `.github/workflows/ci.yml` and `experimental.yml` was raised if tests were added
- [ ] `uv run ruff check .` is clean
- [ ] `src/frontend` unchanged, or `bundle.js` rebuilt and committed in the same commit
- [ ] `README.md` (and `skills/noworkflow/SKILL.md`, once it exists) updated if a command or option changed
- [ ] No real provenance data: no `now show -e` output, Prolog export or `.noworkflow/` from a real project
