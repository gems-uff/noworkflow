#!/usr/bin/env bash
#
# Reproduces the noWorkflow 2 running-example trial history
# (credit card fraud detection pipeline) used throughout the paper.
#
# Requirements (in the EXECUTION environment, e.g. the `noworkflow-analysis` repo):
#   - noWorkflow 2 (provides the `now` command)
#   - Python packages: scikit-learn, imbalanced-learn, pandas
#   - The Kaggle "Credit Card Fraud Detection" dataset as creditcard.csv
#     https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
#
# It runs the whole sequence inside a fresh work directory, so the canonical
# baseline (credit_card_fraud.py) and the patches in this folder stay untouched.
#
# Usage:
#   CCF_DATASET=/path/to/creditcard.csv ./run_trials.sh [workdir]
#
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-$HERE/run}"
DATASET="${CCF_DATASET:-$HERE/creditcard.csv}"

command -v now >/dev/null 2>&1 || { echo "ERROR: noWorkflow 'now' command not found in PATH."; exit 1; }

echo ">> Work directory: $WORK"
rm -rf "$WORK"; mkdir -p "$WORK"
cp "$HERE/credit_card_fraud.py" "$WORK/credit_card_fraud.py"

if [ -f "$DATASET" ]; then
  cp "$DATASET" "$WORK/creditcard.csv"
else
  echo "ERROR: creditcard.csv not found at '$DATASET'."
  echo "       Set CCF_DATASET=/path/to/creditcard.csv or place the file next to this script."
  exit 1
fi

cd "$WORK"
apply() { echo ">> applying $1"; patch -p1 < "$HERE/$1"; }
run()   { echo ">> now run credit_card_fraud.py $*"; now run credit_card_fraud.py "$@"; }

# --- Trial history -----------------------------------------------------------
# (tags follow noWorkflow's X.Y.Z scheme: X=code changed, Y=input changed, Z=same)

run                                    # 1.1.1  baseline: PCA=3, RandomForest, seed 42
run                                    # 1.1.2  re-execution: same code, same input (Z++)
run                                    # 1.1.3  re-execution: same code, same input (Z++)
run 40                                 # 1.2.1  same code, seed 40 (input differs -> Y++)

apply patch_2_pca.patch                # v1 -> v2: PCA 3 -> 10
run                                    # 2.1.1  code changed -> X++
run 40                                 # 2.2.1  same code (v2), seed 40

apply patch_3_gradientboosting.patch   # v2 -> v3: RandomForest -> GradientBoosting
run                                    # 3.1.1

apply patch_4_keyerror.patch           # v3 -> v4: typo df['Clas'] -> raises KeyError
run || echo ">> trial 4.1.1 FAILED as expected (KeyError) -- recorded as a failed (red) trial"

# Branch: discard the failed direction, go back to the good 2.1.1 and try feature scaling.
# NOTE: `now restore 2.1.1` restores credit_card_fraud.py to its v2 content, so
#       patch_5 (generated against v2) applies cleanly afterwards.
echo ">> now restore 2.1.1"; now restore 2.1.1
apply patch_5_scaler.patch             # v2 -> v5: add StandardScaler before PCA
run                                    # 5.1.1  branch with base 2.1.1

# Branch: refactor data loading into a LOCAL MODULE + cache an INTERMEDIATE file.
# (restore 2.1.1 -> v2 content; patch_6 was generated against v2, so it applies cleanly.)
# This trial introduces two new file objects used by the version-model figure:
#   - preprocessing.py (local module -> definition provenance of a local module)
#   - prepared.csv     (intermediate file, written and then read within the trial)
# NOTE: use `-a` (--skip-access) here. The previous trial (5.1.1) SUCCEEDED and wrote
#       out.txt; a plain `now restore` would see out.txt differ from the head trial and
#       create an unwanted backup trial, shifting every later tag by one (6.1.1 -> 7.1.1,
#       backup 7.0.0 -> 8.0.0). Skipping file accesses restores the script without that
#       spurious backup. (The restore after the FAILED 4.1.1 above needs no -a, because
#       that trial crashed before writing out.txt, so there is nothing to back up.)
echo ">> now restore -a 2.1.1"; now restore -a 2.1.1
cp "$HERE/preprocessing.py" preprocessing.py
apply patch_6_localmodule.patch        # v2 -> v6: import local module; write+read prepared.csv
run                                    # 6.1.1  branch with base 2.1.1 (adds preprocessing.py, prepared.csv)

# Optional backup trial (7.0.0): edit the script and restore WITHOUT running it,
# so noWorkflow snapshots the edited content as a backup (yellow) trial.
printf '\n# scratch edit to trigger a backup trial\n' >> credit_card_fraud.py
echo ">> now restore 5.1.1 (creates backup trial 7.0.0 of the edited content)"
now restore 5.1.1

echo
echo ">> Done. Inspect the resulting history with:  now vis   (or: now list)"
