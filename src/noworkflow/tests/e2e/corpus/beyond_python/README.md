# The paper's case study: Beyond Python

The glue pipeline that the "Beyond Python" section of the noWorkflow 2
paper (revision R1) uses as its case study: the same credit card fraud
problem as the running example, with Python as the glue between an R
script and a C program.

- repository: [`dew-uff/noworkflow-analysis`](https://github.com/dew-uff/noworkflow-analysis),
  directory `beyond-python/`
- tag: not tagged yet; **until the package is tagged, this copy is the
  source**, and the tag and its commit are written here when it exists
- license: MIT, as the package

| File | Role |
|---|---|
| `fraud_pipeline.py` | the wrapper, the script of every `now run`: prepares the data with pandas, then launches `Rscript`, `cc` and the compiled binary |
| `model.R` | the logistic regression, in base R; its defaults name the same files as the wrapper's command line |
| `metrics.c` | precision, recall and F1 of the predictions |
| `patch_2_threshold.patch` | the change of trial 1.1.2: the threshold of `model.R`, 0.5 to 0.3 |
| `patch_3_accuracy.patch` | the change of trial 1.1.3: `metrics.c` also writes the accuracy |
| `run.sh` | the sequence of `now run` that builds the history 1.1.1 to 1.1.3, the listings of the section and the final `now restore`; then, when R has rdtLite, the fourth trial in a project of its own and its `now show -f` |
| `strace/model_sourced.R`, `strace/utils.R` | the variant of `model.R` that sources a file named on no command line, for the strace backend (#206) |
| `rdtlite/fraud_pipeline.py` | the wrapper of the fourth trial, which runs `model.R` under rdtLite (`prov.run`), for the PROV-JSON claims (#202, #207) and the fourth trial of `run.sh`; it differs from the wrapper in its Rscript line only |

Not copied: the dataset.

## Three places, one rule

Like the running example (`../paper_example/`), the case study lives in
the paper (what it states noWorkflow records), in the reproducibility
package (the files that rebuild the history) and here (the test that
checks the paper against the tool). A change to the case study, or to what
the paper shows of it, in any of the three is carried to the other two;
see "The paper's running example" in `AGENTS.md`.

`Examples/glue_pipeline/` at the root of the repository ships the seven
files of the table above, the rdtLite wrapper included and the strace
variant left out, to users, with a README of its own. They are byte for byte these, and
`src/noworkflow/tests/test_repository_examples.py` fails when the two
copies differ: a change here is copied there in the same commit.

## How the test uses it

`../../test_beyond_python.py` replays the trial history of `run.sh` with
the harness, through `../../beyond_python.py`, which applies the patches
itself (no `patch` binary) and deletes the outputs before each trial as
`run.sh` does; `test_run_sh_is_the_replayed_sequence` fails when this
`run.sh` and the replay disagree. The listings and the restore of `run.sh`
are run by the tests that check them, not by the replay.

The tests need `Rscript` and `cc` on the PATH and skip without them;
`NOW_RSCRIPT=require` fails instead of skipping (the `paper-example` job
of CI sets it). The three claims of the fourth trial need the rdtLite
package in R (`install.packages("rdtLite")`) and skip without it, in CI
too. The strace variant needs Linux with `strace`, and skips elsewhere
(`NOW_STRACE=require`, which the job also sets, fails it instead). A
claim the tool cannot satisfy yet is a `_desired` twin marked
`xfail(strict=True)` until its issue lands; the module docstring says
which issue turned each one, and none is left.

The Kaggle dataset is not committed. The replay writes a small synthetic
`creditcard.csv` with the same columns (`synthetic_dataset` in
`beyond_python.py` explains why its classes overlap). To replay on the
real file, by hand:

```bash
uv sync --locked --group paper
NOW_PAPER_DATASET=/path/to/creditcard.csv uv run pytest -m paper src/noworkflow/tests/e2e/test_beyond_python.py
```

## A new tag of the package

Copy the files of the new tag over these and over the copy in
`Examples/glue_pipeline/` (keep the bytes: both directories are `-text` in
`.gitattributes`, and the wrapper's SHA-1 is the code hash the paper
prints), write the tag and the commit above, and run the tests. A
red is triaged before anything changes: list each divergence between the
tool and the paper, and let the maintainer decide which side moves. Change
`STEPS` in `beyond_python.py` only when the trial history of `run.sh`
changed.
