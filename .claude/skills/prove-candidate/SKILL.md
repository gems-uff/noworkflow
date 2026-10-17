---
name: prove-candidate
description: Turns a suspected defect into a confirmed, refuted or declaredly plausible finding — a reproduction with a control and one verdict per claim. Use when triaging code-review output, when investigating a reported bug, or before stating in a PR or an issue that something is broken.
---

# Proving a candidate

A suspicion is not a finding. A candidate that goes to the author without
proof spends their time and your credibility; a candidate discarded without
proof leaves a defect in the air. Both mistakes are avoided the same way.

## The escalation, from the cheapest to the most expensive

1. **One command.** For each candidate, ask whether a `grep`, a `uv run python
   -c "..."` or a `now run` in a scratch directory closes the case. Most do,
   and this is where the work happens. `now` is not on the PATH and `uv run`
   only finds it from inside the checkout, so the form that works from a
   scratch directory is

   ```bash
   cd <scratch> && uv run --project <checkout> now run script.py
   ```

   which leaves `.noworkflow/`, `.last_trial` and whatever the script writes
   in the scratch directory, not in the repository.
2. **One agent**, when the command did not close it. What it buys is
   disposable context for the iteration — building a store with the shape the
   candidate needs, reading the source of a dependency, following the AST
   rewriting through a construct — which in your context would stay forever.
   **One is enough:** what separates a finding from a false positive is the
   proof with a control, not the number of opinions about the same lines.

## The three verdicts

- **Confirmed** — a reproduction that fails on the current tree.
- **Plausible** — the mechanism is real and you did not confirm it. Say **what
  would confirm it**: that field is what routes the candidate to a test, to
  `golden-run`, to `python-matrix`, to `rebuild-vis` or to a question to the
  maintainer.
- **Refuted** — the line that makes the defect impossible, or a reproduction
  showing that the alleged failure does not happen.

**Plausible is a confidence dial, not a severity dial.** If you confirmed
everything that was checkable, the verdict is not plausible even if the defect
is small — severity is said in the prose. Downgrading for severity makes the
reader reopen a verification that is already closed.

**One verdict per claim.** A candidate that bundles mechanism, trigger and
consequence needs a verdict on each: "mechanism yes, trigger no, consequence
yes through another door" is a frequent and legitimate answer. A single label
for the bundle hides which part the author has to fix.

## Rules of proof

- **A proof without a control proves nothing.** Show that the scenario without
  the defect behaves differently, and ask: would this script fail the same way
  if the defect did not exist?
- **Confirm that the path is reachable in this tool** — above all for a fix
  that came from outside. Find the call, the option that enables it, the
  condition that guards it, the Python version that takes the branch. The two
  traps of step 1 of `safe-refactor` hold here — an empty search is not
  evidence; execute instead of deducing — and they are not only for upgrades.
  **An instrument on an unreachable path returns "no difference", and that
  reads as "did not regress"**: worse than not measuring, because it costs
  time and produces false assurance. A fix that does not reach this tool is
  refuted, and enters the report as such — with no test and no probe.
- **A claim about a consequence requires an executed sweep, not a read one.**
  A field of the provenance has more readers than the code that writes it:
  the model and its doctest (`src/noworkflow/now/persistence/models/`), `now
  show`, `now diff` (`now/models/diff.py`), each export (`now export prolog
  | prov | dataflow | ast | prospective | ipynb`, in `now/cmd/cmd_export/`,
  with the Prolog rules in `src/noworkflow/resources/rules.pl` and
  `now/models/trial_prolog.py`), `now restore`, and the vis
  (`now/vis/views.py` and `src/frontend/packages/nowvis/src/`). Run each one
  with the two values; the ones that escape whoever only reads are the Prolog
  rule that matches the field by arity, the vis that formats it in
  TypeScript, and the `or` / `if not` over the value.
- **A reproduction that runs the collector in this process inherits what it
  changes.** Inside `now run`, and inside a test that calls
  `collect_provenance`, the four `open`s are wrappers, the builtins carry
  `__noworkflow__`, and a script that raised leaves a finder in
  `sys.meta_path`. `CollectionTestCase.tearDown` undoes it between tests; a
  script of yours does not. A comparison with the original `open`, or a second
  run in the same process, measures the wrapper, not the candidate.
- **Two reproductions that contradict each other: run both before arguing.**
  Usually one fails its own control, or the two measure different scenarios.
  Argument is the instrument for when the experiment cannot be run — here it
  can.
- **Confront the measurement with the field when the two disagree.** A store
  created by the latest version on PyPI (`uvx --from noworkflow==<version>
  now run`, in a scratch directory), a trial the maintainer collected on a
  real project — cheap checks, and the field beats deduction. `AGENTS.md` says
  the same about old stores: do not claim they still open without opening
  one. Between releases the wheel and the tree print the same `now
  --version`, so what tells the two apart is `uv run --project <checkout>
  python -c "import noworkflow; print(noworkflow.__file__)"` — the tree's
  `src/` against a uv cache path.
- **A candidate that only stands on a defect of another file becomes its own
  item.** Do not use someone else's defect to prop up the one at hand.

## Traps when building the scenario in this project

**Read "Reproduction traps" in `AGENTS.md` before building the scenario.** A
reproduction that ignores one of them confirms or refutes the trap, not the
candidate.

Two that belong to the proof rather than to the reproduction:

- **A candidate about an environment attribute is named, never quoted.** The
  store records the whole `os.environ`, the user and the hostname; the report
  says "the `USER` attribute", and the reproduction uses invented values. See
  "Sensitive data" in `AGENTS.md`.
- **The suite's store is in memory and pinned to the `plain` engine.** A
  candidate in the SQLite file, in the content directory or in a git engine
  is reproduced with a real `now run` in a scratch directory, never with a
  test of the suite — the test would pass on both sides.

## What comes out of here

One item per candidate, in the same format whether it serves the review
report, the comment on the PR or the issue: **the verdict**; **how it was
proven** — the command or the test, and the control that goes with it; and,
only for the plausible ones, **what would confirm it** and where that sends
the candidate.

Refuted enters the report like confirmed: whoever raised the candidate needs
to know it fell, and why. And the reproduction of a confirmed one is not
thrown away — it goes clean, with the name and the place of a test of the
project (step 3 of `safe-refactor` says where), named after the property it
guarantees, with no remains of the exploratory script that produced it, and
it is what travels to the author or becomes the coverage of the fix.
