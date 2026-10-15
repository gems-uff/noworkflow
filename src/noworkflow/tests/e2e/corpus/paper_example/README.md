# The paper's running example

The credit card fraud detection pipeline that the noWorkflow 2 paper uses
as its running example, copied byte for byte from its reproducibility
package:

- repository: [`dew-uff/noworkflow-analysis`](https://github.com/dew-uff/noworkflow-analysis)
- tag: `is-2026-submission`, commit `61d7436f9b4d1ee669f7d648a28a40a76710f8e3`
- license: MIT, `LICENSE` in this directory

| File | Role |
|---|---|
| `credit_card_fraud.py` | the baseline script, trial 1.1.1 (the paper's figure `code:creditcardfraudTrial1`) |
| `patch_2_pca.patch` … `patch_6_localmodule.patch` | the code changes of trials 2.1.1, 3.1.1, 4.1.1, 5.1.1 and 6.1.1 |
| `preprocessing.py` | the local module that trial 6.1.1 introduces |
| `run_trials.sh` | the sequence of `now run` and `now restore` that builds the history from 1.1.1 to 7.0.0 |
| `provenance_challenge_6_with_noworkflow.py` | the script that answers query Q6 of the First Provenance Challenge |

Not copied: the MLflow and manual PROV variants of the script (the paper's
effort comparison, which runs no noWorkflow), and the dataset.

## Three places, one rule

The example lives in the paper (what it states noWorkflow records), in the
reproducibility package (the files that rebuild the history) and here (the
test that checks the paper against the tool). A change to the example, or to
what the paper shows of it, in any of the three is carried to the other two;
see "The paper's running example" in `AGENTS.md`.

## How the test uses it

`../../test_paper_example.py` replays `run_trials.sh` with the harness,
through `../../paper.py`, which applies the patches itself (no `patch`
binary), and checks what the paper shows of the history, one test per figure
or listing. `test_run_trials_sh_is_the_replayed_sequence` fails when this
`run_trials.sh` and the replay disagree.

The Kaggle dataset (*Credit Card Fraud Detection*, 284,807 rows) is not
committed. The replay writes a small synthetic `creditcard.csv` with the
same columns (`synthetic_dataset` in `paper.py` explains how it keeps the
metrics stable and dependent on the code, as the real data is). To replay
on the real file, by hand:

```bash
uv sync --locked --group paper
NOW_PAPER_DATASET=/path/to/creditcard.csv uv run pytest -m paper
```

The goldens are skipped then; everything else runs, on a larger and slower
store.

## A new tag of the package

Copy the files of the new tag over these (keep the bytes: the directory is
`-text` in `.gitattributes`, and the script's SHA-1 is the code hash the
paper prints), update the tag and the commit above, and run the tests. A
red is triaged before anything changes: list each divergence between the
tool and the paper, and let the maintainer decide which side moves. Change
`STEPS` in `paper.py` only when `run_trials.sh` changed.
