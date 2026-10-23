"""Credit card fraud detection as a glue pipeline: Python prepares the
data, an R script fits the model and a C program computes the metrics."""
import subprocess
import sys

import pandas as pd


def prepare(dataset, prepared):
    df = pd.read_csv(dataset, encoding="utf-8")
    df.drop(columns=["Time"]).to_csv(prepared, index=False)


def run(*command):
    completed = subprocess.run(command)
    if completed.returncode != 0:
        sys.exit(completed.returncode)


prepare("creditcard.csv", "prepared.csv")
run("Rscript", "-e", 'rdtLite::prov.run("model.R", prov.dir = ".")')
run("cc", "-O2", "-o", "metrics", "metrics.c")
run("./metrics", "pred.csv", "out.txt")
