# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Replay the case study of the "Beyond Python" section of the noWorkflow 2
paper

The case study (``corpus/beyond_python``; its README says where it comes
from) is the credit card fraud problem of the running example with Python
as the glue: ``fraud_pipeline.py`` prepares the dataset with pandas, then
launches ``Rscript model.R``, ``cc`` on ``metrics.c`` and the compiled
binary. ``run.sh`` turns two patches into a history of three trials, 1.1.1
to 1.1.3, in which only the R script and then the C program change.
``replay`` runs the same sequence with the e2e harness, applying the
patches without a ``patch`` binary and deleting the outputs before each
trial as ``run.sh`` does, on the synthetic dataset that
``synthetic_dataset`` writes, or on the real one when ``NOW_PAPER_DATASET``
names it.
"""

import math
import os
import random
import shlex
import shutil
import subprocess

from .harness import CORPUS
from .paper import DATASET_VARIABLE, apply_patch

CASE_CORPUS = CORPUS / "beyond_python"
SCRIPT = "fraud_pipeline.py"
DATASET = "creditcard.csv"
# The wrapped non-Python code, edited between the trials.
SOURCES = ("model.R", "metrics.c")
# What the pipeline writes: run.sh deletes them before each trial, so that
# every trial creates them (a first access without a hash before).
OUTPUTS = ("pred.csv", "out.txt", "metrics")
# The programs the wrapper launches, as it names them on its command lines.
TOOLS = ("Rscript", "cc")
# What each `now run` may take: pandas under the collector, then R.
RUN_TIMEOUT = 600
# The fourth trial: the same wrapper with model.R run under rdtLite
# (``prov.run``), which writes its PROV-JSON here, next to copies of the
# files the script read and wrote.
RDTLITE_WRAPPER = CASE_CORPUS / "rdtlite" / SCRIPT
PROV_JSON = os.path.join("prov_model", "prov.json")

# The trial history of run.sh, one step per command, in its order.
# test_run_sh_is_the_replayed_sequence parses run.sh and fails when the two
# drift apart (a new tag of the package changes it).
STEPS = (
    ("clean",),
    ("run",),  # 1.1.1
    ("apply", "patch_2_threshold.patch"),
    ("clean",),
    ("run",),  # 1.1.2
    ("apply", "patch_3_accuracy.patch"),
    ("clean",),
    ("run",),  # 1.1.3
)
TRIAL_HISTORY_MARKER = "# --- Trial history"
LISTINGS_MARKER = "# --- Listings"
# The automatic tag of each run of STEPS, in order: the wrapper and the
# command line never change, so only the third number moves.
RUN_TAGS = ("1.1.1", "1.1.2", "1.1.3")


def run_sh_steps(text):
    """The steps of the trial history section of ``run.sh``

    Each command becomes a tuple in the form of ``STEPS``; a comment is
    dropped. An unknown command raises ``ValueError``: the replay would not
    know how to perform it.
    """
    _, found, rest = text.partition(TRIAL_HISTORY_MARKER)
    if not found:
        raise ValueError("run.sh has no {!r} section".format(TRIAL_HISTORY_MARKER))
    history, found, _ = rest.partition(LISTINGS_MARKER)
    if not found:
        raise ValueError("run.sh has no {!r} section".format(LISTINGS_MARKER))
    steps = []
    # The rest of the marker line is a ruler.
    for line in history.splitlines()[1:]:
        for command in line.split(";"):
            words = shlex.split(command, comments=True)
            if not words:
                continue
            if words == ["clean"] or words == ["run"]:
                steps.append((words[0],))
            elif words[0] == "apply" and len(words) == 2:
                steps.append(("apply", words[1]))
            else:
                raise ValueError(
                    "run.sh runs {!r}, which the replay does not know".format(
                        " ".join(words)
                    )
                )
    return tuple(steps)


def synthetic_dataset(seed=1, rows=400):
    """A small ``creditcard.csv`` with the layout of Kaggle's dataset

    The columns are ``Time``, ``V1``-``V28``, ``Amount`` and ``Class``,
    quoted and formatted as in the original. Unlike the dataset of the
    running example (``paper.synthetic_dataset``), whose classes are far
    apart, the classes here **overlap**: ``Class`` is drawn from a logistic
    model of ``V1``, ``V2`` and ``V3`` with noise, so the fitted
    probabilities spread over (0, 1) and the threshold of ``model.R``
    decides a share of the predictions. With separable classes, every
    probability would sit near 0 or 1, and the change of the threshold
    from 0.5 to 0.3 in trial 1.1.2 would change neither ``pred.csv`` nor
    ``out.txt``: the diff the section shows would have nothing to show.
    The generator is deterministic, and ``set.seed(42)`` in ``model.R``
    makes the split and the fit deterministic for a given version of R;
    ``test_the_synthetic_dataset_*`` checks the premise with the trials
    themselves.
    """
    rng = random.Random(seed)
    header = ["Time"] + ["V{}".format(i) for i in range(1, 29)] + ["Amount", "Class"]
    lines = [",".join('"{}"'.format(name) for name in header)]
    time = 0
    for _ in range(rows):
        time += rng.randint(0, 60)
        features = [rng.gauss(0.0, 1.0) for _ in range(28)]
        logit = 1.5 * features[0] - 1.2 * features[1] + 0.8 * features[2]
        probability = 1.0 / (1.0 + math.exp(-(logit + rng.gauss(0.0, 1.0))))
        fraud = 1 if rng.random() < probability else 0
        amount = min(round(rng.expovariate(1 / 80), 2), 1000.0)
        lines.append(
            ",".join(
                ["{:d}".format(time)]
                + ["{:.6f}".format(value) for value in features]
                + ["{:.2f}".format(amount), '"{:d}"'.format(fraud)]
            )
        )
    return "\n".join(lines) + "\n"


def write_dataset(path):
    """Put the dataset of the replay at ``path``: the real one when
    ``NOW_PAPER_DATASET`` names it, the synthetic one otherwise"""
    real = os.environ.get(DATASET_VARIABLE)
    if real:
        shutil.copyfile(real, path)
    else:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(synthetic_dataset())


def tool_directories():
    """The directories of the tools the wrapper launches, or the names of
    the missing ones

    Returns ``(directories, missing)``. The harness runs ``now`` with a
    synthetic PATH of system directories (``harness.clean_env``), and the
    wrapper finds ``Rscript`` and ``cc`` through the child's PATH: a
    replay appends these directories to it.
    """
    directories, missing = [], []
    for tool in TOOLS:
        found = shutil.which(tool)
        if found is None:
            missing.append(tool)
        else:
            directories.append(os.path.dirname(os.path.realpath(found)))
    return list(dict.fromkeys(directories)), missing


def has_rdtlite():
    """Whether the ``Rscript`` on the PATH can load the rdtLite package"""
    rscript = shutil.which("Rscript")
    if rscript is None:
        return False
    completed = subprocess.run(
        [rscript, "-e", 'quit(status = !requireNamespace("rdtLite", quietly = TRUE))'],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=120,
    )
    return completed.returncode == 0


def add_tools_to_path(project, directories):
    """Let the ``now`` of ``project`` and its children find the tools"""
    project.env["PATH"] = os.pathsep.join(
        dict.fromkeys(project.env["PATH"].split(os.pathsep) + list(directories))
    )


def place_sources(project):
    """Copy the baseline wrapper and sources into the project, with the
    dataset"""
    for name in (SCRIPT,) + SOURCES:
        shutil.copyfile(CASE_CORPUS / name, project.path / name)
    write_dataset(project.path / DATASET)


def clean_outputs(directory):
    """Delete the outputs of the pipeline, as the ``clean`` of run.sh"""
    for name in OUTPUTS:
        path = directory / name
        if path.exists():
            path.unlink()


def perform(project, step):
    """Perform one step of ``STEPS`` in ``project``

    Returns the ``Result`` of the ``now run`` a run step ran, ``None``
    for the other steps. The R calls may warn on stderr (``glm``), so a
    run only has to end with 0.
    """
    kind, args = step[0], step[1:]
    if kind == "run":
        return project.run("run", SCRIPT, allow_stderr=True, timeout=RUN_TIMEOUT)
    if kind == "apply":
        apply_patch(project.path, (CASE_CORPUS / args[0]).read_text(encoding="utf-8"))
    elif kind == "clean":
        clean_outputs(project.path)
    else:
        raise ValueError("unknown step {!r}".format(step))
    return None


def replay(project, steps=STEPS):
    """Run the trial history of ``run.sh`` in ``project``

    Returns ``[(step, result)]``, as ``perform`` gives them.
    """
    place_sources(project)
    return [(step, perform(project, step)) for step in steps]
