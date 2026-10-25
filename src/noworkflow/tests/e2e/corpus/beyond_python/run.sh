#!/usr/bin/env bash
#
# Reproduces the trial history of the "Beyond Python" case study of the
# noWorkflow 2 paper: a Python wrapper (fraud_pipeline.py) that prepares the
# credit card fraud dataset with pandas, fits a logistic regression in an R
# script (model.R) and computes the metrics with a C program (metrics.c);
# three trials, with model.R and then metrics.c edited between them, and,
# when R has the rdtLite package, a fourth trial in a project of its own
# with model.R run under rdtLite.
#
# Requirements (in the EXECUTION environment):
#   - noWorkflow 2.2.0 (provides the `now` command)
#   - Python package: pandas
#   - R 4 or later (`Rscript`), a C compiler (`cc`) and Graphviz (`dot`)
#   - optional, for the fourth trial: the rdtLite package in R
#     (`Rscript -e 'install.packages("rdtLite")'`)
#   - The Kaggle "Credit Card Fraud Detection" dataset as creditcard.csv
#     https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
#
# It runs the whole sequence inside a fresh work directory, so the baseline
# files and the patches in this folder stay untouched. Every output of the
# pipeline (pred.csv, out.txt, the metrics binary) is deleted before each
# trial, so that each trial writes them anew.
#
# Usage:
#   CCF_DATASET=/path/to/creditcard.csv ./run.sh [workdir]
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-$HERE/run}"
DATASET="${CCF_DATASET:-$HERE/creditcard.csv}"

for tool in now Rscript cc dot; do
  command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: '$tool' not found in PATH."; exit 1; }
done

echo ">> Work directory: $WORK"
rm -rf "$WORK"; mkdir -p "$WORK"
cp "$HERE/fraud_pipeline.py" "$HERE/model.R" "$HERE/metrics.c" "$WORK/"

if [ -f "$DATASET" ]; then
  cp "$DATASET" "$WORK/creditcard.csv"
else
  echo "ERROR: creditcard.csv not found at '$DATASET'."
  echo "       Set CCF_DATASET=/path/to/creditcard.csv or place the file next to this script."
  exit 1
fi

cd "$WORK"
apply() { echo ">> applying $1"; patch -p1 < "$HERE/$1"; }
clean() { rm -f pred.csv out.txt metrics; }
run()   { echo ">> now run fraud_pipeline.py"; now run fraud_pipeline.py; }

# --- Trial history -----------------------------------------------------------
# (the Python and the command line never change, so the tags are 1.1.x:
# noWorkflow sees the edits of model.R and metrics.c through the launches)

clean; run                             # 1.1.1  baseline: threshold 0.5
apply patch_2_threshold.patch          # model.R: threshold 0.5 -> 0.3
clean; run                             # 1.1.2  same Python, the R script changed
apply patch_3_accuracy.patch           # metrics.c: writes the accuracy too
clean; run                             # 1.1.3  same Python, the C program recompiled

# --- Listings (the figures of the section) -----------------------------------
mkdir -p listings
now show 1.1.1 -f                      > listings/show-1.1.1-f.txt
now diff 1.1.1 1.1.2 -f --content      > listings/diff-1.1.1-1.1.2-f-content.txt
now diff 1.1.2 1.1.3 -f -m             > listings/diff-1.1.2-1.1.3-f-m.txt
now export dataflow 1.1.3 -m activation > listings/dataflow-1.1.3-activation.dot
dot -Tpdf listings/dataflow-1.1.3-activation.dot -o listings/dataflow-1.1.3-activation.pdf

# --- Restore -----------------------------------------------------------------
# Back to the baseline: model.R and metrics.c as 1.1.1 read them, and the
# outputs 1.1.1 created removed.
now restore 1.1.1

# --- Fourth trial: model.R under rdtLite -------------------------------------
# The baseline in a project of its own, rdtlite/, with the wrapper of
# rdtlite/fraud_pipeline.py, which runs model.R through rdtLite's prov.run
# (its only difference). rdtLite writes prov_model/prov.json; noWorkflow
# reads it and records the files the R script read and wrote, and the
# script itself, as file accesses of the Rscript launch.
if Rscript -e 'quit(status = !requireNamespace("rdtLite", quietly = TRUE))' >/dev/null 2>&1; then
  mkdir -p rdtlite
  cp "$HERE/rdtlite/fraud_pipeline.py" "$HERE/model.R" "$HERE/metrics.c" creditcard.csv rdtlite/
  (cd rdtlite && run)                    # 1.1.1 of rdtlite/
  (cd rdtlite && now show 1.1.1 -f)      > listings/show-rdtlite-1.1.1-f.txt
else
  echo ">> rdtLite is not installed in R: the fourth trial is skipped"
fi
