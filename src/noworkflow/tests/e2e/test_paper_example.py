# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The running example of the noWorkflow 2 paper, replayed (#257)

``corpus/paper_example`` is the paper's credit card fraud detection
pipeline as its reproducibility package tags it; ``paper.replay`` runs the
package's ``run_trials.sh`` on it, once per module. Each test checks one
thing the paper shows of that history and names the figure or listing by
its LaTeX label. A failure here means that noWorkflow no longer produces
what the paper shows: triage it before changing anything ("The paper's
running example" in AGENTS.md). The expectation is never edited just to
make the test pass.

Marked ``paper``: the tests need the ``paper`` dependency group
(scikit-learn, imbalanced-learn, pandas), skip without it, and run in the
``paper-example`` job of ci.yml, which the matrix legs leave out. What
depends on noWorkflow's numbering (the ids the queries bind, the
dataflows, the prospective graph) is compared on the reference platform
only (``goldens/REFERENCE``), like the goldens. With ``NOW_PAPER_DATASET``
pointing at the real dataset the same tests run on it, the goldens
excepted.
"""
import ast
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from noworkflow.tests.e2e import golden
from noworkflow.tests.e2e.golden import assert_golden
from noworkflow.tests.e2e.harness import NowProject, runs_this_interpreter
from noworkflow.tests.e2e.normalize import prolog_statements
from noworkflow.tests.e2e.paper import (
    DATASET,
    DATASET_VARIABLE,
    PAPER_CORPUS,
    SCRIPT,
    STEPS,
    apply_patch,
    labelled,
    parse_dot,
    replay,
    run_trials_steps,
    synthetic_dataset,
    trial_sources,
)

pytestmark = pytest.mark.paper

GROUP_MODULES = ("sklearn", "imblearn", "pandas")

# fig:now-history: (sequence key, tag, status, parent tag, command).
HISTORY = [
    (1, "1.1.1", "finished", None, "run credit_card_fraud.py"),
    (2, "1.1.2", "finished", "1.1.1", "run credit_card_fraud.py"),
    (3, "1.1.3", "finished", "1.1.2", "run credit_card_fraud.py"),
    (4, "1.2.1", "finished", "1.1.3", "run credit_card_fraud.py 40"),
    (5, "2.1.1", "finished", "1.2.1", "run credit_card_fraud.py"),
    (6, "2.2.1", "finished", "2.1.1", "run credit_card_fraud.py 40"),
    (7, "3.1.1", "finished", "2.2.1", "run credit_card_fraud.py"),
    (8, "4.1.1", "unfinished", "3.1.1", "run credit_card_fraud.py"),
    (9, "5.1.1", "finished", "2.1.1", "run credit_card_fraud.py"),
    (10, "6.1.1", "finished", "2.1.1", "run credit_card_fraud.py"),
    (11, "7.0.0", "backup", "6.1.1", "restore 5.1.1"),
]
TAGS = [tag for _, tag, _, _, _ in HISTORY]

# The hashes the paper prints: the code hash of 1.1.1 (fig:now-commandquery,
# fig:now-prologfacts) and of 6.1.1 (fig:now-diffcommand), and the code
# block hashes of get_df (fig:now-prologfacts) and get_rus (the queries).
SCRIPT_1_1_1 = "7b37007618e4d03616352063871a0572579126da"
SCRIPT_6_1_1 = "66c7915a0819fc79620f665ceca5c20366ce1ca5"
GET_DF = "b946139b998148a304e93f93d470590398df83d6"
GET_RUS = "4599d2d3fb2519038ccd3c7c9de233aa354b1812"

# fig:now-commandquery: (depth, line, name) of the activations it shows, in
# order; the listing leaves some out ("Some function calls were removed").
COMMANDQUERY_TREE = [
    (0, 1, "__main__"),
    (1, 33, "get_df"),
    (1, 34, "drop"),
    (1, 36, "get_pca"),
    (2, 14, "PCA"),
    (1, 38, "len"),
    (1, 40, "get_rus"),
    (2, 17, "range"),
    (2, 18, "RandomUnderSampler"),
    (2, 18, "RandomUnderSampler"),
    (1, 44, "save_metrics"),
]

# fig:now-sqlquery, verbatim but for the prompt.
SQL_QUERY = """
SELECT b.code_hash, e.repr
        FROM activation a, evaluation e, code_block b, code_component c
        LEFT JOIN tag as t
        ON a.trial_id == t.trial_id AND e.trial_id == t.trial_id AND b.trial_id == t.trial_id AND c.trial_id == t.trial_id
        WHERE t.name = '1.1.1'
        AND a.id = e.id
        AND a.code_block_id = b.id
        AND e.code_component_id = c.id
        AND a.name = 'get_rus'
        AND c.first_char_line = 40;
"""

# fig:now-patternquery, verbatim but for the prompts.
PATTERN_QUERY = """
from noworkflow.patterns import activation, code_block, code_component
from noworkflow.patterns import evaluation, var, trial, tag
from noworkflow.now.persistence import persistence_config
persistence_config.connect_existing(".")
query = (
   tag(trial_id=var.Trial, name="1.1.1")
   & activation(var.Trial, var.E, 'get_rus', code_block_id=var.B)
   & evaluation(var.Trial, var.E, code_component_id=var.C, repr=var.Value)
   & code_component(var.Trial, var.C, first_char_line=40)
   & code_block(var.Trial, var.B, var.Hash)
)
for _, binds in query:
    print(binds)
"""

# fig:now-prologquery.
PROLOG_QUERY = (
    "tag(_, Trial, _, '1.1.1', _), "
    "activation(Trial, E, 'get_rus', _, B), "
    "evaluation(Trial, E, _, C, _, Value, _), "
    "code_component(Trial, C, _, _, _, 40, _, _, _, _), "
    "code_block(Trial, B, Hash, _)"
)
# The ids both queries bind in the paper: E, B and C.
QUERY_IDS = {"E": 57, "B": 57, "C": 253}

# fig:now-prologfacts: the FACT DEFINITION comments it shows, and the facts,
# as the text after the trial id; checkpoints are left out, and so are the
# reprs except that of evaluation 1.
PROLOG_DEFINITIONS = [
    "% FACT DEFINITION: trial(Id, Script, Start, Finish, Command, Path, "
    "Status, ModulesInheritedFromTrialId, ExperimentId, MainId, ParentId, "
    "UserId).",
    "% FACT DEFINITION: code_component(TrialId, Id, Name, Type, Mode, "
    "FirstCharLine, FirstCharColumn, LastCharLine, LastCharColumn, "
    "ContainerId).",
    "% FACT DEFINITION: code_block(TrialId, Id, CodeHash, Docstring).",
    "% FACT DEFINITION: activation(TrialId, Id, Name, StartCheckpoint, "
    "CodeBlockId).",
    "% FACT DEFINITION: evaluation(TrialId, Id, Checkpoint, "
    "CodeComponentId, ActivationId, Repr, MemberContainerId).",
]
PROLOG_CODE_COMPONENTS = [
    "1, 'credit_card_fraud.py', 'script', 'w', 1, 0, 45, 0, nil",
    "2, 'from sklearn.decomposition import PCA', 'import_from', 'n', "
    "1, 0, 1, 37, 1",
    "21, 'get_df', 'function_def', 'w', 9, 0, 10, 58, 1",
    "28, 'return pd.read_csv(''creditcard.csv'', encoding=''utf-8'')', "
    "'return', 'n', 10, 4, 10, 58, 21",
    "30, 'pd.read_csv(''creditcard.csv'', encoding=''utf-8'')', 'call', "
    "'r', 10, 11, 10, 58, 21",
    "185, 'df = get_df()', 'assign', 'n', 33, 0, 33, 13, 1",
    "187, 'df', 'name', 'w', 33, 0, 33, 2, 1",
    "188, 'get_df()', 'call', 'r', 33, 5, 33, 13, 1",
]
PROLOG_CODE_BLOCKS = [
    "1, '{}', ''".format(SCRIPT_1_1_1),
    "21, '{}', ''".format(GET_DF),
]
# activation(_, Id, Name, _, CodeBlockId).
PROLOG_ACTIVATIONS = ["1, '__main__', 1", "10, 'get_df', 21"]
# evaluation(_, Id, _, CodeComponentId, ActivationId, _, MemberContainerId).
PROLOG_EVALUATIONS = ["1, 1, 0, 1", "10, 188, 1, 17", "19, 187, 1, 17"]

# fig:now-fa-diff: `now diff 1.1.1 1.2.1 -fa 57 65 op`, the evaluations of
# get_rus in each trial, and the variables it shows: (name, id in 1.1.1,
# id in 1.2.1).
FUNCTION_DIFF_ARGS = ("diff", "1.1.1", "1.2.1", "-fa", "57", "65", "op")
FUNCTION_DIFF_VARIABLES = [
    ("RandomUnderSampler", 64, 72),
    ("random_seed", 65, 73),
    ("rus", 68, 76),
]

# fig:now-prospective-graph: its edges, (source, target, dashed), by label.
PROSPECTIVE_EDGES = {
    ("Start", "6: import pandas as pd", False),
    ("6: import pandas as pd", "7: import sys", False),
    ("7: import sys", "12: def get_pca()", False),
    ("9: def get_df()",
     "10: return pd.read_csv('creditcard.csv', encoding='utf-8')", False),
    ("10: return pd.read_csv('creditcard.csv', encoding='utf-8')",
     "10: pd.read_csv('creditcard.csv', encoding='utf-8')", False),
    ("12: def get_pca()", "13: pca_components = 3", False),
    ("13: pca_components = 3",
     "14: return PCA(n_components=pca_components)", False),
    ("14: return PCA(n_components=pca_components)",
     "14: PCA(n_components=pca_components)", False),
    ("16: def get_rus(random_seed)", "17: for", False),
    ("17: for", " Variable: i \n i in range(2)", True),
    ("17: for", "18: rus = RandomUnderSampler(random_state=random_seed)",
     False),
    ("18: rus = RandomUnderSampler(random_state=random_seed)",
     "18: RandomUnderSampler(random_state=random_seed)", False),
    ("18: RandomUnderSampler(random_state=random_seed)", "17: for", True),
    ("17: for", "19: return rus", False),
    ("21: def get_ypred(X_train, X_test, y_train)",
     "22: rf = RandomForestClassifier()", False),
    ("22: rf = RandomForestClassifier()", "22: RandomForestClassifier()",
     False),
    ("22: RandomForestClassifier()", "23: rf.fit(X_train, y_train)", False),
    ("23: rf.fit(X_train, y_train)", "24: return rf.predict(X_test)", False),
    ("24: return rf.predict(X_test)", "24: rf.predict(X_test)", False),
    ("26: def save_metrics(y_test, y_pred)",
     "27: roc_metric = roc_auc_score(y_test, y_pred)", False),
    ("27: roc_metric = roc_auc_score(y_test, y_pred)",
     "27: roc_auc_score(y_test, y_pred)", False),
    ("27: roc_auc_score(y_test, y_pred)",
     "28: f1_metric = f1_score(y_test, y_pred)", False),
    ("28: f1_metric = f1_score(y_test, y_pred)",
     "28: f1_score(y_test, y_pred)", False),
    ("28: f1_score(y_test, y_pred)",
     '30: open("out.txt", "w").write("ROC="+str(roc_metric)+"\\nF1="'
     '+str(f1_metric))', False),
    ("33: df = get_df()", "33: get_df()", False),
    ("33: get_df()", "9: def get_df()", True),
    ("33: get_df()", "34: X = df.drop('Class', axis=1)", False),
    ("34: X = df.drop('Class', axis=1)", "34: df.drop('Class', axis=1)",
     False),
    ("34: df.drop('Class', axis=1)", "35: y = df['Class']", False),
    ("35: y = df['Class']", "36: pca = get_pca()", False),
    ("36: pca = get_pca()", "36: get_pca()", False),
    ("36: get_pca()", "12: def get_pca()", True),
    ("36: get_pca()", "37: random_seed = 42", False),
    ("37: random_seed = 42", "38: if", False),
    ("38: if", " Condition:\n  len(sys.argv) > 1", True),
    ("38: if", "38: len(sys.argv)", False),
    ("38: len(sys.argv)", "39: random_seed = int(sys.argv[1])", False),
    ("39: random_seed = int(sys.argv[1])", "39: int(sys.argv[1])", False),
    ("39: int(sys.argv[1])", "40: rus = get_rus(random_seed)", False),
    ("40: rus = get_rus(random_seed)", "40: get_rus(random_seed)", False),
    ("40: get_rus(random_seed)", "16: def get_rus(random_seed)", True),
    ("40: get_rus(random_seed)", "41: X_resampled, y_resampled = "
     "rus.fit_resample(pca.fit_transform(X), y)", False),
    ("41: X_resampled, y_resampled = rus.fit_resample(pca.fit_transform(X), "
     "y)", "41: rus.fit_resample(pca.fit_transform(X), y)", False),
    ("41: rus.fit_resample(pca.fit_transform(X), y)", "42: X_train, X_test, "
     "y_train, y_test = train_test_split(X_resampled, y_resampled, "
     "test_size=0.2, random_state=random_seed)", False),
    ("42: X_train, X_test, y_train, y_test = train_test_split(X_resampled, "
     "y_resampled, test_size=0.2, random_state=random_seed)",
     "42: train_test_split(X_resampled, y_resampled, test_size=0.2, "
     "random_state=random_seed)", False),
    ("42: train_test_split(X_resampled, y_resampled, test_size=0.2, "
     "random_state=random_seed)",
     "43: y_pred = get_ypred(X_train, X_test, y_train)", False),
    ("43: y_pred = get_ypred(X_train, X_test, y_train)",
     "43: get_ypred(X_train, X_test, y_train)", False),
    ("43: get_ypred(X_train, X_test, y_train)",
     "21: def get_ypred(X_train, X_test, y_train)", True),
    ("43: get_ypred(X_train, X_test, y_train)",
     "44: save_metrics(y_test, y_pred)", False),
    ("44: save_metrics(y_test, y_pred)",
     "26: def save_metrics(y_test, y_pred)", True),
    ("44: save_metrics(y_test, y_pred)", "End", False),
}

# fig:queryQ1Result: the activation dataflow of what derived save_metrics in
# 1.2.1. Its clusters, nodes and edges, by label.
Q1_CLUSTERS = {"get_df", "get_pca", "get_rus", "get_ypred"}
Q1_NODES = {
    "creditcard.csv",
    "10 pd.read_csv('creditcard.csv', encoding='utf-8')",
    "33 return",
    "34 df.drop('Class', axis=1)",
    "14 PCA(n_components=pca_components)",
    "36 return",
    "38 len(sys.argv)",
    "39 int(sys.argv[1])",
    "18 RandomUnderSampler(random_state=random_seed)",
    "40 return",
    "41 pca.fit_transform(X)",
    "41 rus.fit_resample(pca.fit_transform(X), y)",
    "42 train_test_split(X_resamp ... random_state=random_seed)",
    "22 RandomForestClassifier()",
    "24 rf.predict(X_test)",
    "43 return",
}
Q1_EDGES = {
    ("10 pd.read_csv('creditcard.csv', encoding='utf-8')", "creditcard.csv",
     True),
    ("33 return", "10 pd.read_csv('creditcard.csv', encoding='utf-8')",
     False),
    ("34 df.drop('Class', axis=1)", "33 return", True),
    ("36 return", "14 PCA(n_components=pca_components)", False),
    ("39 int(sys.argv[1])", "38 len(sys.argv)", True),
    ("18 RandomUnderSampler(random_state=random_seed)", "39 int(sys.argv[1])",
     True),
    ("18 RandomUnderSampler(random_state=random_seed)", "38 len(sys.argv)",
     True),
    ("40 return", "18 RandomUnderSampler(random_state=random_seed)", True),
    ("41 pca.fit_transform(X)", "36 return", True),
    ("41 pca.fit_transform(X)", "34 df.drop('Class', axis=1)", True),
    ("41 rus.fit_resample(pca.fit_transform(X), y)",
     "41 pca.fit_transform(X)", False),
    ("41 rus.fit_resample(pca.fit_transform(X), y)", "40 return", True),
    ("41 rus.fit_resample(pca.fit_transform(X), y)", "33 return", True),
    ("42 train_test_split(X_resamp ... random_state=random_seed)",
     "41 rus.fit_resample(pca.fit_transform(X), y)", True),
    ("42 train_test_split(X_resamp ... random_state=random_seed)",
     "39 int(sys.argv[1])", True),
    ("42 train_test_split(X_resamp ... random_state=random_seed)",
     "38 len(sys.argv)", True),
    ("24 rf.predict(X_test)", "22 RandomForestClassifier()", True),
    ("24 rf.predict(X_test)",
     "42 train_test_split(X_resamp ... random_state=random_seed)", True),
    ("43 return", "24 rf.predict(X_test)", False),
}

# fig:queryQ4Result: the query of Q4, with the date of the replay instead
# of the paper's.
Q4_QUERY = """
SELECT ta.name as trial_tag, t.user_id, t.start, t.finish,
SUBSTRING (c.name, 1,16) AS name
FROM code_component as c
   LEFT JOIN trial as t on c.trial_id = t.id
   LEFT JOIN tag as ta on ta.trial_id = t.id
WHERE t.start LIKE ? AND c.name = (
  SELECT c.name FROM code_component as c
  WHERE c.id IN (
    SELECT e1.code_component_id FROM evaluation as e1
     WHERE e1.id IN (
      SELECT d.dependent_id FROM dependency as d WHERE d.dependency_id IN
        (SELECT e.id FROM evaluation as e WHERE e.repr = '0.2')
      AND d.type = "argument"))
  AND name LIKE "%train_test_split%")
"""

# fig:queryQ5Result, verbatim.
Q5_QUERY = """
SELECT ta.name as trial_tag, ar.value, f.name,
f.mode, f.content_hash_before, f.content_hash_after
FROM file_access as f, activation as ac, argument as ar
LEFT JOIN tag as ta on ta.trial_id = f.trial_id
WHERE ac.id = f.activation_id AND
ar.trial_id = f.trial_id
AND f.trial_id = ac.trial_id
AND (f.mode = "w" OR f.mode = "w+b")
AND f.name NOT LIKE "nul"
AND ar.name = "argv"
AND ar.value LIKE "%'40'%";
"""

# fig:scriptQuery5: the trials with seed 42 that reach f1_score.
Q6_TAGS = ["1.1.1", "1.1.2", "1.1.3", "2.1.1", "3.1.1", "5.1.1", "6.1.1"]

# The full outputs compared with goldens on the reference platform: what
# the paper shows, and the commands around it. `{save_metrics}` is the id
# of the evaluation of save_metrics(...) in 1.2.1. Not `now diff -fa`: it
# prints the id of the access to out.txt, which comes after the reads of
# every installed distribution's entry_points.txt (sklearn's fit_resample
# scans them), so it moves with any change to the lock;
# test_function_diff_of_get_rus_is_fig_now_fa_diff covers the figure.
GOLDEN_CASES = (
    [("list", ("list",)), ("history", ("history",))]
    + [("show-" + tag, ("show", tag)) for tag in TAGS]
    + [
        ("show-1.1.1-a", ("show", "1.1.1", "-a")),
        ("diff-1.1.1-6.1.1-f-brief",
         ("diff", "1.1.1", "6.1.1", "-f", "--brief")),
        ("diff-1.1.1-1.2.1", ("diff", "1.1.1", "1.2.1")),
        ("export-prospective-1.1.1", ("export", "prospective", "1.1.1")),
        ("export-dataflow-1.1.1", ("export", "dataflow", "1.1.1")),
        ("export-dataflow-1.2.1-activation-wdf",
         ("export", "dataflow", "1.2.1", "-m", "activation", "-w",
          "{save_metrics}")),
    ]
)


def diverges(label, detail=""):
    """The message of a failed claim of the paper"""
    return (
        "{}: noWorkflow no longer produces what the paper shows. Triage it "
        "before changing anything (\"The paper's running example\" in "
        "AGENTS.md): either the change regressed, or the paper and its "
        "reproducibility package must follow it. The maintainer decides; "
        "the expectation is never edited just to make this test pass.{}"
    ).format(label, "\n" + detail if detail else "")


def reference_only(what):
    """Skip outside the reference platform: ``what`` depends on
    noWorkflow's numbering or on the Python version"""
    reference = golden.reference_platform()
    if golden.current_platform() != reference:
        pytest.skip("{} is compared on the reference platform ({}) only"
                    .format(what, reference))


def sha1(data):
    return hashlib.sha1(data).hexdigest()


@dataclasses.dataclass
class PaperStore:
    """The project after the replay, and what the extra restores did"""

    project: NowProject
    # The project files right after `now restore <tag>`, for 1.1.1 and
    # 6.1.1, and the number of trials before those restores.
    restored: dict
    trials_before_restores: int

    def trial_id(self, tag):
        return self.project.trial(tag)["id"]

    def evaluation_id(self, tag, name):
        """The evaluation of the code component ``name`` in a trial"""
        rows = self.project.query(
            "SELECT e.id FROM evaluation e JOIN code_component c "
            "ON c.trial_id = e.trial_id AND c.id = e.code_component_id "
            "WHERE e.trial_id = ? AND c.name = ?",
            self.trial_id(tag), name)
        assert len(rows) == 1, "{} in {}: {} evaluations".format(
            name, tag, len(rows))
        return rows[0]["id"]

    def run(self, *args, **kwargs):
        return self.project.run(*args, **kwargs)

    def python(self, *args):
        """Run Python in the project, with the harness environment"""
        if not runs_this_interpreter(self.project.command):
            pytest.skip("NOW_E2E_CMD runs another installation; this test "
                        "imports noworkflow from this interpreter")
        return subprocess.run(
            [sys.executable, *args], cwd=str(self.project.path),
            env=self.project.env, stdin=subprocess.DEVNULL,
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=300,
        )


@pytest.fixture(scope="module")
def paper_store(tmp_path_factory):
    """The trial history of run_trials.sh, built once for the module

    After the replay it restores 1.1.1 and 6.1.1, recording the project
    files, for the restore operation the paper describes, and then 5.1.1
    again: the last command of run_trials.sh, so that the store ends as the
    package leaves it.
    """
    if runs_this_interpreter():
        missing = [name for name in GROUP_MODULES
                   if importlib.util.find_spec(name) is None]
        if missing:
            pytest.skip("needs the `paper` dependency group (uv sync "
                        "--group paper); missing: {}".format(", ".join(
                            missing)))
    project = NowProject(tmp_path_factory.mktemp("paper_example"))
    replay(project)
    count = len(project.trials())
    restored = {}
    for tag in ("1.1.1", "6.1.1"):
        project.run("restore", tag)
        restored[tag] = project.files()
    project.run("restore", "5.1.1")
    return PaperStore(project, restored, count)


@pytest.fixture
def paper(paper_store):
    """The shared store of the paper example, read-only

    A test that changes the database or the project files fails here: the
    other tests read the history run_trials.sh leaves. The content
    directory is not compared; it only grows when something runs.
    """
    project = paper_store.project
    database = project.store / "db.sqlite"
    before = (sha1(database.read_bytes()), project.files())
    yield paper_store
    after = (sha1(database.read_bytes()), project.files())
    assert after == before, (
        "the test changed the shared store of the paper example")


def golden_dataset_only():
    if os.environ.get(DATASET_VARIABLE):
        pytest.skip("{} is set: the goldens hold the synthetic dataset"
                    .format(DATASET_VARIABLE))


# --- The corpus and the replay ------------------------------------------


def test_run_trials_sh_is_the_replayed_sequence():
    """The replay runs the commands of the package's run_trials.sh, in its
    order: a new tag of the package that changes them fails here"""
    text = (PAPER_CORPUS / "run_trials.sh").read_text(encoding="utf-8")
    assert run_trials_steps(text) == STEPS
    # Control: the parser sees a changed sequence and an unknown command.
    assert run_trials_steps(text + "run 41\n") == STEPS + (("run", "41"),)
    with pytest.raises(ValueError, match="does not know"):
        run_trials_steps(text + "now export prolog\n")


def test_patches_apply_only_where_they_were_made(tmp_path):
    """A patch whose context no longer matches the file raises, instead of
    applying elsewhere the way `patch` would"""
    shutil.copyfile(PAPER_CORPUS / SCRIPT, tmp_path / SCRIPT)
    patch = (PAPER_CORPUS / "patch_2_pca.patch").read_text(encoding="utf-8")
    apply_patch(tmp_path, patch)
    assert "pca_components = 10\n" in (tmp_path / SCRIPT).read_text(
        encoding="utf-8")
    with pytest.raises(ValueError, match="expected"):
        apply_patch(tmp_path, patch)


DATASET_CHECK = r"""
import json, os, runpy, sys, tempfile
cases, dataset = json.load(sys.stdin)
outputs = {}
for tag, files, args in cases:
    with tempfile.TemporaryDirectory() as directory:
        os.chdir(directory)
        for name, text in list(files.items()) + [("creditcard.csv", dataset)]:
            with open(name, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
        found = set()
        for _ in range(3):
            sys.argv = ["credit_card_fraud.py"] + args
            sys.path.insert(0, directory)
            runpy.run_path("credit_card_fraud.py", run_name="__main__")
            sys.path.remove(directory)
            sys.modules.pop("preprocessing", None)
            with open("out.txt", encoding="utf-8") as handle:
                found.add(handle.read())
        os.chdir(os.path.dirname(directory))
    outputs[tag] = sorted(found)
print(json.dumps(outputs))
"""


def test_the_synthetic_dataset_gives_stable_metrics_that_depend_on_pca_and_seed(
        tmp_path):
    """Premise of the replay (see ``paper.synthetic_dataset``): each script
    version, run three times with plain Python, writes the same out.txt;
    1.1.1 and 6.1.1 (3 and 10 PCA components) write different ones, and so
    do 1.2.1 and 5.1.1. Without the first, the goldens would flap; without
    the others, the brief diff of fig:now-diffcommand would have no out.txt
    row and the restore that run_trials.sh makes with -a would back
    nothing up without it. A red here is the dataset or a scikit-learn
    release, not noWorkflow."""
    missing = [name for name in GROUP_MODULES
               if importlib.util.find_spec(name) is None]
    if missing:
        pytest.skip("needs the `paper` dependency group (uv sync --group "
                    "paper)")
    cases = [(tag, files, list(args))
             for tag, files, args, fails in trial_sources() if not fails]
    completed = subprocess.run(
        [sys.executable, "-c", DATASET_CHECK], cwd=str(tmp_path),
        input=json.dumps([cases, synthetic_dataset()]), capture_output=True,
        encoding="utf-8", timeout=600,
    )
    assert completed.returncode == 0, completed.stderr
    outputs = json.loads(completed.stdout)
    unstable = {tag: found for tag, found in outputs.items()
                if len(found) != 1}
    assert not unstable, "out.txt changes from run to run: {}".format(
        unstable)
    assert outputs["1.1.1"] != outputs["6.1.1"]
    assert outputs["1.2.1"] != outputs["5.1.1"]


# --- Section 4: storage, versioning and restore -------------------------


def test_history_has_the_tags_statuses_and_parents_of_the_paper(paper):
    """fig:now-history: eleven trials, the failed 4.1.1, the backup 7.0.0,
    and the two branches from 2.1.1"""
    project = paper.project
    tags = {}
    for trial in project.trials():
        found = [row["name"] for row in project.tags(trial["id"])]
        tags[trial["id"]] = found[0] if len(found) == 1 else found
    history = [
        (trial["sequence_key"], tags[trial["id"]], trial["status"],
         tags.get(trial["parent_id"]), trial["command"])
        for trial in project.trials()
    ]
    assert history == HISTORY, diverges("fig:now-history")
    assert {row["type"] for row in project.query("SELECT type FROM tag")} \
        == {"AUTO"}, diverges("fig:now-history")


def project_accesses(project, trial_id):
    """The accesses of a trial to the project's own files, in order"""
    return project.query(
        "SELECT name, mode, content_hash_before, content_hash_after "
        "FROM file_access WHERE trial_id = ? ORDER BY checkpoint, id",
        trial_id)


def is_project_file(access):
    return not os.path.isabs(access["name"])


def test_versions_of_1_1_1_and_6_1_1_access_the_files_of_the_version_model(
        paper):
    """fig:now-versionmodel: both read the same version of creditcard.csv
    and write out.txt, with different content; only 6.1.1 writes
    prepared.csv, reads that same version back, and imports the local
    module preprocessing.py"""
    project = paper.project
    first, sixth = paper.trial_id("1.1.1"), paper.trial_id("6.1.1")
    accesses = {
        tag: [(access["name"], "w" in access["mode"], access)
              for access in project_accesses(project, trial)
              if is_project_file(access)]
        for tag, trial in (("1.1.1", first), ("6.1.1", sixth))
    }
    shape = {tag: [(name, write) for name, write, _ in found]
             for tag, found in accesses.items()}
    assert shape == {
        "1.1.1": [("creditcard.csv", False), ("out.txt", True)],
        "6.1.1": [("creditcard.csv", False), ("prepared.csv", True),
                  ("prepared.csv", False), ("out.txt", True)],
    }, diverges("fig:now-versionmodel")
    dataset = sha1((project.path / DATASET).read_bytes())
    read_1, write_1 = (access for _, _, access in accesses["1.1.1"])
    read_6, prepared_w, prepared_r, write_6 = (
        access for _, _, access in accesses["6.1.1"])
    assert read_1["content_hash_before"] == read_6["content_hash_before"] \
        == dataset, diverges("fig:now-versionmodel", "creditcard.csv")
    assert prepared_w["content_hash_before"] is None
    assert prepared_w["content_hash_after"] \
        == prepared_r["content_hash_before"], diverges(
            "fig:now-versionmodel", "prepared.csv written and read back")
    assert write_1["content_hash_after"] != write_6["content_hash_after"], \
        diverges("fig:now-versionmodel", "out.txt versions 1 and 2")

    def local_modules(trial):
        return project.query(
            "SELECT m.name, m.path, b.code_hash FROM module m "
            "JOIN code_block b ON b.trial_id = m.trial_id "
            "AND b.id = m.code_block_id "
            "WHERE m.trial_id = ? AND m.name = 'preprocessing'", trial)

    assert local_modules(first) == [], diverges("fig:now-versionmodel")
    modules = local_modules(sixth)
    assert [row["code_hash"] for row in modules] == [
        sha1((PAPER_CORPUS / "preprocessing.py").read_bytes())
    ], diverges("fig:now-versionmodel", "the local module")
    assert os.path.realpath(modules[0]["path"]) == os.path.realpath(
        project.path / "preprocessing.py")


def test_restoring_1_1_1_and_6_1_1_does_what_the_restore_operation_describes(
        paper):
    """sec:now-versioning, Restore Operation: restoring 1.1.1 brings back
    its script, removes out.txt (1.1.1 created it) and leaves
    preprocessing.py and prepared.csv (it never accessed them); restoring
    6.1.1 brings back its script and preprocessing.py, removes
    prepared.csv and reverts out.txt to what it was before 6.1.1. Neither
    creates a backup trial. Restored by the ``paper_store`` fixture."""
    project = paper.project
    after_1, after_6 = paper.restored["1.1.1"], paper.restored["6.1.1"]
    dataset = sha1((project.path / DATASET).read_bytes())
    local = sha1((PAPER_CORPUS / "preprocessing.py").read_bytes())
    assert after_1[SCRIPT] == SCRIPT_1_1_1, diverges("sec:now-versioning")
    assert after_1[DATASET] == dataset
    assert "out.txt" not in after_1, diverges(
        "sec:now-versioning", "restoring 1.1.1 removes out.txt")
    assert "preprocessing.py" in after_1 and "prepared.csv" in after_1, \
        diverges("sec:now-versioning", "restoring 1.1.1 keeps the files "
                 "only 6.1.1 accessed")
    out_before_6 = [
        access["content_hash_before"]
        for access in project_accesses(project, paper.trial_id("6.1.1"))
        if access["name"] == "out.txt"
    ][0]
    assert after_6[SCRIPT] == SCRIPT_6_1_1, diverges("sec:now-versioning")
    assert after_6["preprocessing.py"] == local
    assert after_6[DATASET] == dataset
    assert "prepared.csv" not in after_6, diverges(
        "sec:now-versioning", "restoring 6.1.1 removes prepared.csv")
    assert after_6["out.txt"] == out_before_6, diverges(
        "sec:now-versioning", "restoring 6.1.1 reverts out.txt")
    assert len(project.trials()) == paper.trials_before_restores, diverges(
        "sec:now-versioning", "a restore created a backup trial")


def test_code_hashes_are_the_ones_the_paper_prints(paper):
    """fig:now-commandquery, fig:now-diffcommand, fig:now-prologfacts and
    the queries: the code hashes of the scripts of 1.1.1 and 6.1.1 and of
    the code blocks of get_df and get_rus; `now show 1.1.1 -d` prints the
    last one (sec:now-query)"""
    project = paper.project
    assert sha1((PAPER_CORPUS / SCRIPT).read_bytes()) == SCRIPT_1_1_1

    def script_hash(tag):
        return project.query(
            "SELECT b.code_hash FROM trial t JOIN code_block b "
            "ON b.trial_id = t.id AND b.id = t.main_id WHERE t.id = ?",
            paper.trial_id(tag))[0]["code_hash"]

    def function_hash(name):
        return project.query(
            "SELECT b.code_hash FROM code_component c JOIN code_block b "
            "ON b.trial_id = c.trial_id AND b.id = c.id "
            "WHERE c.trial_id = ? AND c.name = ? AND c.type = 'function_def'",
            paper.trial_id("1.1.1"), name)[0]["code_hash"]

    found = {"1.1.1": script_hash("1.1.1"), "6.1.1": script_hash("6.1.1"),
             "get_df": function_hash("get_df"),
             "get_rus": function_hash("get_rus")}
    assert found == {"1.1.1": SCRIPT_1_1_1, "6.1.1": SCRIPT_6_1_1,
                     "get_df": GET_DF, "get_rus": GET_RUS}, diverges(
        "the code hashes")
    lines = [line.strip() for line in
             paper.run("show", "1.1.1", "-d").stdout.splitlines()]
    index = lines.index("Name: get_rus [function_def]")
    assert lines[index + 1] == "Code hash: " + GET_RUS, diverges(
        "sec:now-query", "now show 1.1.1 -d")


# --- Section 3: definition and execution provenance ---------------------


def dependencies(project, trial_id, name, line):
    """``[(type, reference, name, line)]`` of what the evaluations of a
    code component depend on"""
    return sorted(
        (row["type"], bool(row["reference"]), row["name"], row["line"])
        for row in project.query(
            "SELECT d.type, d.reference, c2.name, c2.first_char_line AS line "
            "FROM dependency d "
            "JOIN evaluation e1 ON e1.trial_id = d.trial_id "
            "AND e1.id = d.dependent_id "
            "JOIN code_component c1 ON c1.trial_id = e1.trial_id "
            "AND c1.id = e1.code_component_id "
            "JOIN evaluation e2 ON e2.trial_id = d.trial_id "
            "AND e2.id = d.dependency_id "
            "JOIN code_component c2 ON c2.trial_id = e2.trial_id "
            "AND c2.id = e2.code_component_id "
            "WHERE d.trial_id = ? AND c1.name = ? AND c1.first_char_line = ?",
            trial_id, name, line)
    )


def test_functions_and_dependencies_are_the_ones_the_execution_section_names(
        paper):
    """sec:now-execution: the five functions are defined at lines 9, 12,
    16, 21 and 26 and called at 33, 36, 40, 43 and 44; pca_components
    (line 13) has a reference dependency on 3, and len(sys.argv) > 1 (line
    38) derivation dependencies on len(sys.argv) and 1; random_seed is
    evaluated at lines 37 and 40 in 1.1.1 and also at 39 in 1.2.1, where
    the one at 40 refers to the one at 39 and get_rus derives from
    int(sys.argv[1])"""
    project = paper.project
    first, input_trial = paper.trial_id("1.1.1"), paper.trial_id("1.2.1")
    definitions = {
        row["name"]: row["first_char_line"] for row in project.query(
            "SELECT name, first_char_line FROM code_component "
            "WHERE trial_id = ? AND type = 'function_def'", first)}
    assert definitions == {"get_df": 9, "get_pca": 12, "get_rus": 16,
                           "get_ypred": 21, "save_metrics": 26}, diverges(
        "sec:now-execution", "function definitions")
    calls = {
        name: [row["first_char_line"] for row in project.query(
            "SELECT first_char_line FROM code_component WHERE trial_id = ? "
            "AND type = 'call' AND name LIKE ?", first, name + "(%")]
        for name in definitions
    }
    assert calls == {"get_df": [33], "get_pca": [36], "get_rus": [40],
                     "get_ypred": [43], "save_metrics": [44]}, diverges(
        "sec:now-execution", "function calls")
    assert dependencies(project, first, "pca_components", 13) == [
        ("assign", True, "3", 13)], diverges(
        "sec:now-execution", "reference dependency")
    assert dependencies(project, first, "len(sys.argv) > 1", 38) == [
        ("use", False, "1", 38), ("use", False, "len(sys.argv)", 38)], \
        diverges("sec:now-execution", "derivation dependencies")

    def seed_lines(trial):
        return sorted(row["first_char_line"] for row in project.query(
            "SELECT c.first_char_line FROM evaluation e "
            "JOIN code_component c ON c.trial_id = e.trial_id "
            "AND c.id = e.code_component_id WHERE e.trial_id = ? "
            "AND c.name = 'random_seed' "
            "AND c.first_char_line BETWEEN 37 AND 40",
            trial))

    assert seed_lines(first) == [37, 40], diverges("sec:now-execution")
    assert seed_lines(input_trial) == [37, 39, 40], diverges(
        "sec:now-execution")
    assert ("assignment", True, "random_seed", 39) in dependencies(
        project, input_trial, "random_seed", 40), diverges(
        "sec:now-execution", "random_seed at line 40 refers to line 39")

    def derived_from(tag):
        evaluation = paper.evaluation_id(tag, "get_rus(random_seed)")
        return paper.run("evaluation", "-t", tag, "--eid", evaluation,
                         "wdf").stdout

    assert "WasDerivedFrom: 39 int(sys.argv[1])" in derived_from("1.2.1"), \
        diverges("sec:now-execution", "get_rus derives from int(sys.argv[1])")
    # Control: 1.1.1 did not run line 39.
    assert "int(sys.argv[1])" not in derived_from("1.1.1")


# --- Section 5: analysis --------------------------------------------------


ACTIVATION_LINE = re.compile(r"^(?P<indent> +)(?P<line>\d+): (?P<name>\S+) \(")


def activation_tree(stdout):
    """``[(depth, line, name, details)]`` of `now show -a`, where
    ``details`` maps "Parameters" and "Return value" to their first line"""
    tree = []
    for line in stdout.splitlines():
        match = ACTIVATION_LINE.match(line)
        if match:
            depth = (len(match.group("indent")) - 2) // 2
            tree.append((depth, int(match.group("line")), match.group("name"),
                         {}))
        elif tree:
            key, separator, value = line.strip().partition(": ")
            if separator and key in ("Parameters", "Return value") and (
                    key not in tree[-1][3]):
                tree[-1][3][key] = value
    return tree


def children(tree, index):
    """The direct children of ``tree[index]``, as (line, name)"""
    depth = tree[index][0]
    found = []
    for entry in tree[index + 1:]:
        if entry[0] <= depth:
            break
        if entry[0] == depth + 1:
            found.append((entry[1], entry[2]))
    return found


def test_show_a_has_the_activation_tree_of_fig_now_commandquery(paper):
    """fig:now-commandquery: `now show 1.1.1 -a`, its header and the
    activations it shows, in order and nesting, with their parameters and
    return values (the listing leaves some calls out)"""
    stdout = paper.run("show", "1.1.1", "-a").stdout
    lines = stdout.splitlines()
    for expected in ("[now] trial tags:", "  Tag: 1.1.1 Type: AUTO",
                     "[now] trial information:", "  Sequence Key: 1",
                     "  Status: Finished", "  Inherited Id: None",
                     "  Script: credit_card_fraud.py",
                     "  Code hash: " + SCRIPT_1_1_1,
                     "[now] this trial has the following function "
                     "activation tree:"):
        assert expected in lines, diverges("fig:now-commandquery", expected)
    for key in ("Id", "Start", "Finish", "Duration"):
        assert any(line.startswith("  {}: ".format(key)) for line in lines), \
            diverges("fig:now-commandquery", key)
    tree = activation_tree(stdout)
    shown = [(depth, line, name) for depth, line, name, _ in tree]
    position = 0
    for entry in COMMANDQUERY_TREE:
        assert entry in shown[position:], diverges(
            "fig:now-commandquery", "{} missing or out of order".format(entry))
        position = shown.index(entry, position) + 1
    index = {name: shown.index((depth, line, name))
             for depth, line, name in COMMANDQUERY_TREE}
    assert children(tree, index["get_pca"]) == [(14, "PCA")]
    assert children(tree, index["get_rus"]) == [
        (17, "range"), (18, "RandomUnderSampler"), (18, "RandomUnderSampler")
    ], diverges("fig:now-commandquery", "the calls inside get_rus")
    details = {name: tree[position][3] for name, position in index.items()}
    assert details["get_pca"]["Return value"] == "PCA(n_components=3)"
    assert details["PCA"]["Return value"] == "PCA(n_components=3)"
    assert details["len"]["Return value"] == "1"
    assert details["get_rus"] == {
        "Parameters": "random_seed = 42",
        "Return value": "RandomUnderSampler(random_state=42)",
    }, diverges("fig:now-commandquery", "get_rus")
    assert details["range"]["Return value"] == "range(0, 2)"
    assert all(entry[3]["Return value"] == "RandomUnderSampler(random_state=42)"
               for entry in tree if entry[2] == "RandomUnderSampler")
    assert re.fullmatch(r"<module '__main__' from '.*credit_card_fraud\.py'>",
                        details["__main__"]["Return value"]), diverges(
        "fig:now-commandquery", "__main__")
    assert details["save_metrics"]["Parameters"].startswith("y_test = ")


def brief_file_diff(stdout):
    """The columns of the table `now diff -f --brief` prints"""
    lines = stdout.splitlines()
    start = lines.index("[now] Brief file access diff")
    header = [cell.strip() for cell in lines[start + 1].split("|")]
    columns = {name: [] for name in header}
    for line in lines[start + 2:]:
        if "|" not in line:
            break
        for name, cell in zip(header, line.split("|")):
            if cell.strip():
                columns[name].append(cell.strip())
    return columns


def test_brief_file_diff_of_1_1_1_and_6_1_1_is_fig_now_diffcommand(paper):
    """fig:now-diffcommand: `now diff 1.1.1 6.1.1 -f --brief` adds
    prepared.csv (written, then read back) and changes out.txt; the script
    change shows as the code hash in the trial diff above it, with the
    sequence key and the parent (2.1.1)"""
    stdout = paper.run("diff", "1.1.1", "6.1.1", "-f", "--brief").stdout
    assert brief_file_diff(stdout) == {
        "[Additions]": ["(rb) prepared.csv", "(w) prepared.csv (new)"],
        "[Removals]": [],
        "[Changes]": ["(w) out.txt (new)"],
    }, diverges("fig:now-diffcommand", stdout)
    lines = [line.strip() for line in stdout.splitlines()]
    for expected in (
            "Code hash changed from {} to {}".format(SCRIPT_1_1_1,
                                                     SCRIPT_6_1_1),
            "Sequence key changed from 1 to 10",
            "Parent id changed from <None> to {}".format(
                paper.trial_id("2.1.1"))):
        assert expected in lines, diverges("fig:now-diffcommand", expected)


def test_sql_query_of_fig_now_sqlquery_returns_the_get_rus_hash_and_value(
        paper):
    """fig:now-sqlquery, run as printed"""
    assert paper.project.query(SQL_QUERY) == [
        {"code_hash": GET_RUS, "repr": "RandomUnderSampler(random_state=42)"}
    ], diverges("fig:now-sqlquery")


def test_pattern_query_of_fig_now_patternquery_binds_what_the_paper_shows(
        paper):
    """fig:now-patternquery, run as printed: one result, with the get_rus
    hash and value of 1.1.1 (and, on the reference platform, the ids)"""
    completed = paper.python("-c", PATTERN_QUERY)
    assert completed.returncode == 0, completed.stderr
    results = [dict(re.findall(r"(\w+): ('[^']*'|\d+)", line))
               for line in completed.stdout.splitlines() if line.strip()]
    assert len(results) == 1, diverges("fig:now-patternquery",
                                       completed.stdout)
    binds = {name: ast.literal_eval(value)
             for name, value in results[0].items()}
    assert (binds["Hash"], binds["Value"], binds["Trial"]) == (
        GET_RUS, "RandomUnderSampler(random_state=42)",
        paper.trial_id("1.1.1")), diverges("fig:now-patternquery")
    reference_only("the ids the query binds")
    assert {name: binds[name] for name in QUERY_IDS} == QUERY_IDS, diverges(
        "fig:now-patternquery", "ids")


def test_prolog_query_of_fig_now_prologquery_binds_what_the_paper_shows(
        paper, tmp_path):
    """fig:now-prologquery, run with SWI-Prolog on `now export prolog
    1.1.1` (skipped without `swipl` on the PATH)"""
    swipl = shutil.which("swipl")
    if swipl is None:
        pytest.skip("SWI-Prolog (swipl) is not on the PATH")
    facts = tmp_path / "facts.pl"
    facts.write_text(paper.run("export", "prolog", "1.1.1").stdout,
                     encoding="utf-8")
    goal = ("forall(({}), format('~w|~w|~w|~w|~w|~w~n', "
            "[Trial, E, B, C, Value, Hash]))".format(PROLOG_QUERY))
    completed = subprocess.run(
        [swipl, "-q", "-g", goal, "-t", "halt", str(facts)],
        stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8",
        errors="replace", timeout=300,
    )
    assert completed.returncode == 0, completed.stderr
    results = [line.split("|") for line in completed.stdout.splitlines()
               if line.strip()]
    assert len(results) == 1, diverges("fig:now-prologquery",
                                       completed.stdout)
    trial, e, b, c, value, code_hash = results[0]
    assert (trial, value, code_hash) == (
        paper.trial_id("1.1.1"), "RandomUnderSampler(random_state=42)",
        GET_RUS), diverges("fig:now-prologquery")
    reference_only("the ids the query binds")
    assert {"E": int(e), "B": int(b), "C": int(c)} == QUERY_IDS, diverges(
        "fig:now-prologquery", "ids")


def prolog_facts(text):
    """``{predicate: {id: arguments}}`` of a Prolog export, and its comment
    lines. ``trial`` facts are keyed by their first argument and keep all of
    them; the others, whose first argument is the trial id, by the second,
    and keep the arguments after the trial id."""
    facts, comments = {}, []
    for kind, statement in prolog_statements(text):
        if kind == "comment":
            comments.append(statement.rstrip("\n"))
            continue
        if kind != "clause" or statement.startswith(":-"):
            continue
        name, _, body = statement.strip().partition("(")
        arguments = split_arguments(body[:-2])
        if name == "trial":
            facts.setdefault(name, {})[arguments[0]] = arguments
        else:
            facts.setdefault(name, {})[arguments[1]] = arguments[1:]
    return facts, comments


def split_arguments(body):
    """The arguments of a fact, split at the commas outside quoted atoms"""
    arguments, current, quoted, index = [], [], False, 0
    while index < len(body):
        char = body[index]
        if quoted and char == "'" and body[index + 1:index + 2] == "'":
            current.append("''")
            index += 2
            continue
        if char == "'":
            quoted = not quoted
        if char == "," and not quoted:
            arguments.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    arguments.append("".join(current).strip())
    return arguments


def test_prolog_export_has_the_facts_of_fig_now_prologfacts(paper):
    """fig:now-prologfacts: the FACT DEFINITION comments and, on the
    reference platform, every fact it shows of 1.1.1. The ids of the script
    (1), of the code block of get_df (21) and of the call to read_csv (30)
    are also those fig:now-transformedcreditcard uses"""
    facts, comments = prolog_facts(
        paper.run("export", "prolog", "1.1.1").stdout)
    for definition in PROLOG_DEFINITIONS:
        assert definition in comments, diverges("fig:now-prologfacts",
                                                definition)
    trial = facts["trial"][repr(paper.trial_id("1.1.1")).replace('"', "'")]
    # trial(Id, Script, Start, Finish, Command, Path, Status,
    # ModulesInheritedFromTrialId, ExperimentId, MainId, ParentId, UserId).
    assert [trial[i] for i in (1, 4, 6, 7, 8, 9, 10)] == [
        "'credit_card_fraud.py'", "'run credit_card_fraud.py'", "'finished'",
        "nil", "nil", "1", "nil"], diverges("fig:now-prologfacts", "trial")
    reference_only("the ids of the facts")

    def shown(predicate, ids, keep=None):
        found = []
        for key in ids:
            arguments = facts[predicate][key]
            if keep is not None:
                arguments = [arguments[i] for i in keep]
            found.append(", ".join(arguments))
        return found

    def ids(expected):
        return [line.split(",")[0] for line in expected]

    assert shown("code_component", ids(PROLOG_CODE_COMPONENTS)) \
        == PROLOG_CODE_COMPONENTS, diverges("fig:now-prologfacts")
    assert shown("code_block", ids(PROLOG_CODE_BLOCKS)) \
        == PROLOG_CODE_BLOCKS, diverges("fig:now-prologfacts")
    assert shown("activation", ids(PROLOG_ACTIVATIONS), (0, 1, 3)) \
        == PROLOG_ACTIVATIONS, diverges("fig:now-prologfacts")
    assert shown("evaluation", ids(PROLOG_EVALUATIONS), (0, 2, 3, 5)) \
        == PROLOG_EVALUATIONS, diverges("fig:now-prologfacts")
    assert re.fullmatch(
        r"'<module ''__main__'' from ''.*credit_card_fraud\.py''>'",
        facts["evaluation"]["1"][4]), diverges("fig:now-prologfacts")


def function_diff_variables(stdout):
    """``[(sign, variable dict)]`` of the variable lines of `now diff -fa`"""
    found = []
    for line in stdout.splitlines():
        if line[:3] in ("- {", "+ {"):
            found.append((line[0], ast.literal_eval(line[2:])))
    return found


def test_function_diff_of_get_rus_is_fig_now_fa_diff(paper):
    """fig:now-fa-diff: `now diff 1.1.1 1.2.1 -fa 57 65 op` compares the
    two calls of get_rus: output, argument and the variables it shows,
    with the evaluation ids of the figure, and no file access changed"""
    reference_only("the evaluation ids of the function diff")
    assert paper.evaluation_id("1.1.1", "get_rus(random_seed)") == 57
    assert paper.evaluation_id("1.2.1", "get_rus(random_seed)") == 65
    stdout = paper.run(*FUNCTION_DIFF_ARGS).stdout
    lines = [line.rstrip() for line in stdout.splitlines()]
    for expected in (
            "  Sequence key changed from 1 to 4",
            "  Command changed from run credit_card_fraud.py to run "
            "credit_card_fraud.py 40",
            "  Parent id changed from <None> to {}".format(
                paper.trial_id("1.1.3")),
            "[now] Function output", "[now] The output changed:",
            "- RandomUnderSampler(random_state=42)",
            "+ RandomUnderSampler(random_state=40)",
            "[now] The arguments changed:", "- ['42']", "+ ['40']",
            "[now] The duration changed:", "[now] The variables changed:",
            "[now] 0 file accesses added:", "[now] 0 file accesses removed:",
            "[now] 0 file accesses replaced:"):
        assert expected in lines, diverges("fig:now-fa-diff", expected)
    variables = function_diff_variables(stdout)
    pairs = {}
    for name, before, after in FUNCTION_DIFF_VARIABLES:
        old = [v for sign, v in variables
               if sign == "-" and v["evaluation_id"] == before]
        new = [v for sign, v in variables
               if sign == "+" and v["evaluation_id"] == after]
        assert [v["name"] for v in old + new] == [name, name], diverges(
            "fig:now-fa-diff", "{} {} -> {}".format(name, before, after))
        pairs[name] = (old[0]["value"], new[0]["value"])
    assert pairs["random_seed"] == ("42", "40"), diverges("fig:now-fa-diff")
    assert pairs["rus"] == ("RandomUnderSampler(random_state=42)",
                            "RandomUnderSampler(random_state=40)")


def test_prospective_graph_is_fig_now_prospective_graph(paper):
    """fig:now-prospective-graph: `now export prospective 1.1.1` has the
    edges of the figure, and no other."""
    reference_only("the prospective graph")
    _, edges = labelled(paper.run("export", "prospective", "1.1.1").stdout)
    assert edges == PROSPECTIVE_EDGES, diverges(
        "fig:now-prospective-graph",
        "missing: {}\nextra: {}".format(sorted(PROSPECTIVE_EDGES - edges),
                                        sorted(edges - PROSPECTIVE_EDGES)))


def connected(text, source, target):
    """Whether a node labelled ``source`` and one labelled ``target`` are
    linked by a path of edges, in any direction. By node id: labels repeat
    (the two iterations of the loop in get_rus)."""
    nodes, edges, _ = parse_dot(text)
    neighbors = {}
    for start, end, _ in edges:
        neighbors.setdefault(start, set()).add(end)
        neighbors.setdefault(end, set()).add(start)

    def labelled_as(label):
        return {node for node, attrs in nodes.items()
                if attrs.get("label") == label}

    sources, targets = labelled_as(source), labelled_as(target)
    assert sources and targets, "no node {!r} or {!r}".format(source, target)
    seen, stack = set(sources), list(sources)
    while stack:
        for node in neighbors.get(stack.pop(), ()):
            if node not in seen:
                seen.add(node)
                stack.append(node)
    return bool(seen & targets)


def test_dataflow_of_1_1_1_is_fig_now_dataflow(paper):
    """fig:now-dataflow: `now export dataflow 1.1.1` (coarseGrain) has a
    cluster per function, the two files, and the function nodes the figure
    shows; random_seed (line 37) is not connected to len(sys.argv) > 1
    (line 38), and nothing mentions int(sys.argv[1]), because line 39 did
    not run."""
    reference_only("the dataflow")
    text = paper.run("export", "dataflow", "1.1.1").stdout
    _, _, clusters = parse_dot(text)
    labels, _ = labelled(text)
    assert {label for label, _ in clusters.values()} == {
        "get_df", "get_pca", "get_rus", "get_ypred", "save_metrics"}, \
        diverges("fig:now-dataflow")
    for label in ("creditcard.csv", "out.txt", "9 get_df", "-1 len",
                  "-1 open", "37 random_seed", "38 len(sys.argv) > 1"):
        assert label in labels, diverges("fig:now-dataflow", label)
    assert not any("int(sys.argv[1])" in label for label in labels), \
        diverges("fig:now-dataflow", "int(sys.argv[1]) in 1.1.1")
    assert not connected(text, "37 random_seed", "38 len(sys.argv) > 1"), \
        diverges("fig:now-dataflow", "random_seed reaches the condition")
    # Control: in 1.2.1 line 39 ran, and it links the seed to the condition.
    text_1_2_1 = paper.run("export", "dataflow", "1.2.1").stdout
    assert connected(text_1_2_1, "39 random_seed", "38 len(sys.argv) > 1")


# --- Section 7: the First Provenance Challenge --------------------------


def test_q1_dataflow_of_save_metrics_in_1_2_1_is_fig_query_q1_result(paper):
    """Q1, fig:queryQ1Result: the activation dataflow of what derived
    save_metrics in 1.2.1 (`now export dataflow 1.2.1 -m activation -w
    <id>`, what `now vis` runs) has the clusters, nodes and edges of the
    figure: the functions get_df, get_pca, get_rus and get_ypred, back to
    creditcard.csv. Through `now evaluation`, the same id needs `-t 1.2.1`:
    without it the command reads the last trial, the backup 7.0.0."""
    evaluation = paper.evaluation_id("1.2.1", "save_metrics(y_test, y_pred)")
    derived = paper.run("evaluation", "-t", "1.2.1", "--eid", evaluation,
                        "wdf").stdout
    for name in ("get_df", "get_pca", "get_rus", "get_ypred"):
        assert re.search(r"WasDerivedFrom: \d+ {} \(".format(name), derived), \
            diverges("Q1", name)
    reference_only("the dataflow")
    text = paper.run("export", "dataflow", "1.2.1", "-m", "activation", "-w",
                     evaluation).stdout
    _, _, clusters = parse_dot(text)
    labels, edges = labelled(text)
    assert Q1_CLUSTERS <= {label for label, _ in clusters.values()}, \
        diverges("fig:queryQ1Result", "clusters")
    assert Q1_NODES <= set(labels), diverges(
        "fig:queryQ1Result", "missing nodes: {}".format(
            sorted(Q1_NODES - set(labels))))
    assert Q1_EDGES <= edges, diverges(
        "fig:queryQ1Result", "missing edges: {}".format(
            sorted(Q1_EDGES - edges)))


def test_q4_query_lists_every_trial_that_defines_train_test_split_with_0_2(
        paper):
    """Q4, fig:queryQ4Result: the ten trials 1.1.1 to 6.1.1, and not the
    backup 7.0.0. 4.1.1 is listed because the query matches the code, not
    the calls: 4.1.1 failed at line 35 and never called
    train_test_split."""
    project = paper.project
    days = {trial["start"][:10] for trial in project.trials()}
    if len(days) > 1:
        pytest.skip("the replay crossed midnight: {}".format(sorted(days)))
    rows = project.query(Q4_QUERY, "{} %".format(days.pop()))
    # The query has no ORDER BY.
    assert sorted(row["trial_tag"] for row in rows) == TAGS[:-1], diverges(
        "fig:queryQ4Result")
    assert {row["name"] for row in rows} == {"train_test_split"}
    failed = paper.trial_id("4.1.1")
    assert project.query(
        "SELECT e.id FROM evaluation e JOIN code_component c "
        "ON c.trial_id = e.trial_id AND c.id = e.code_component_id "
        "WHERE e.trial_id = ? AND c.name LIKE 'train_test_split(%'",
        failed) == []


def test_q5_query_lists_the_outputs_of_the_trials_run_with_40(paper):
    """Q5, fig:queryQ5Result, run as printed: out.txt, written by 1.2.1 and
    2.2.1, the two trials whose argument is 40"""
    rows = paper.project.query(Q5_QUERY)
    assert sorted((row["trial_tag"], row["value"], row["name"], row["mode"])
                  for row in rows) == [
        ("1.2.1", "['credit_card_fraud.py', '40']", "out.txt", "w"),
        ("2.2.1", "['credit_card_fraud.py', '40']", "out.txt", "w"),
    ], diverges("fig:queryQ5Result")


def test_q6_script_finds_the_trials_with_seed_42_that_reach_f1_score(paper):
    """Q6, fig:scriptQuery5: provenance_challenge_6_with_noworkflow.py from
    the package prints the f1_score of every trial run with 42 that
    reaches it: not 1.2.1 and 2.2.1 (seed 40) nor 4.1.1 (failed)"""
    completed = paper.python(
        str(PAPER_CORPUS / "provenance_challenge_6_with_noworkflow.py"))
    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    tags = re.findall(r"^Trial tag:  (\S+)$", completed.stdout, re.M)
    assert tags == Q6_TAGS, diverges("fig:scriptQuery5", completed.stdout)
    assert len(lines) == 2 * len(Q6_TAGS)
    assert all(line.startswith("Output of f1_score:  ")
               for line in lines[1::2]), diverges("fig:scriptQuery5")


def top_level_calls(paper, tag):
    return [(line, name) for depth, line, name, _ in activation_tree(
        paper.run("show", tag, "-a").stdout) if depth == 1]


def test_q7_trial_1_2_1_calls_int_before_get_rus(paper):
    """Q7, fig:commandDiffTrial: 1.2.1 calls int (line 39) right before
    get_rus, and 1.1.1 does not call it"""
    calls = top_level_calls(paper, "1.2.1")
    index = calls.index((40, "get_rus"))
    assert calls[index - 1] == (39, "int"), diverges("fig:commandDiffTrial")
    assert (39, "int") not in top_level_calls(paper, "1.1.1")


# --- Goldens ------------------------------------------------------------


@pytest.mark.golden
@pytest.mark.parametrize(
    "name, args", GOLDEN_CASES, ids=[name for name, _ in GOLDEN_CASES])
def test_paper_example_outputs_match_goldens(request, paper, name, args):
    """The full output of the commands the paper shows and of the commands
    around them, normalized. Not in the paper's form: its listings are
    edited, and one of them holds the recording machine's home directory"""
    golden_dataset_only()
    values = {"save_metrics": paper.evaluation_id(
        "1.2.1", "save_metrics(y_test, y_pred)")}
    args = [arg.format(**values) for arg in args]
    result = paper.run(*args)
    assert_golden(request, name, paper.project.normalize(result.stdout))
