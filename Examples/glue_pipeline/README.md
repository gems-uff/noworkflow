# A glue pipeline: Python, R and C

A Python script that delegates two of its steps to other languages, and
what noWorkflow records of them: a credit card fraud detection pipeline,
with Python as the glue between an R script and a C program.

| File | Role |
|---|---|
| `fraud_pipeline.py` | the script that `now run` traces: it prepares the data with pandas, then launches `Rscript`, `cc` and the compiled binary through `subprocess` |
| `model.R` | a logistic regression in base R: reads `prepared.csv`, writes the predictions to `pred.csv` |
| `metrics.c` | precision, recall and F1 of the predictions, written to `out.txt` |
| `patch_2_threshold.patch` | the change of the second trial: the threshold of `model.R`, 0.5 to 0.3 |
| `patch_3_accuracy.patch` | the change of the third trial: `metrics.c` also writes the accuracy |
| `run.sh` | builds the three trials, writes the listings below and restores the first trial |

The Python script never changes. Everything noWorkflow shows between the
trials comes from the code it launches.

## Running it

You need noWorkflow 2.2.0 or later with pandas, R 4 or later (`Rscript`;
base R is enough), a C compiler (`cc`), `patch`, and Graphviz (`dot`) for
the drawing of the dataflow. The dataset is not shipped: download
`creditcard.csv` from Kaggle's
[Credit Card Fraud Detection](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)
and run

```bash
$ CCF_DATASET=/path/to/creditcard.csv ./run.sh
```

`run.sh` copies the three source files into a fresh `run/` directory, so
the files here stay untouched, and runs everything there. Before each
trial it deletes the outputs of the pipeline (`pred.csv`, `out.txt` and
the `metrics` binary), so that each trial writes them anew: a file that a
process rewrites with the same content is recorded as a read.

| Trial | What changed before it |
|---|---|
| 1.1.1 | nothing: the baseline, threshold 0.5 |
| 1.1.2 | `model.R`: threshold 0.3 |
| 1.1.3 | `metrics.c`: it also writes the accuracy |

The tags stay at 1.1.x because the Python script and its command line are
the same in the three trials.

## What noWorkflow shows

The excerpts below come from a run on the Kaggle dataset. Hashes, paths,
versions and clock readings depend on the machine; `...` marks what was
cut.

Each launch is an activation of the script (the `subprocess.run` inside
`run`), and the files its command line names are file accesses of that
activation, with their content before and after the process. Between the
first two trials only `model.R` changed, and `now diff` shows the edit and
its effect on the metrics:

```
$ now diff 1.1.1 1.1.2 -f --content
...
[now] 5 file accesses replaced:
  Name: model.R
    Content hash before changed from a94f91f5... to f3d18e7d...
    Content hash after changed from a94f91f5... to f3d18e7d...
    Timestamp changed from ... to ...
--- model.R (trial 1.1.1)
+++ model.R (trial 1.1.2)
@@ -7,6 +7,6 @@
 test <- sample(nrow(data), floor(0.2 * nrow(data)))
 model <- glm(Class ~ ., data = data[-test, ], family = binomial)
 prob <- predict(model, newdata = data[test, ], type = "response")
-threshold <- 0.5
+threshold <- 0.3
 write.csv(data.frame(Class = data$Class[test], Pred = as.integer(prob > threshold)),
           output, row.names = FALSE)

  Name: out.txt
    Content hash after changed from b8ac6398... to d7f35c36...
    Timestamp changed from ... to ...
--- out.txt (trial 1.1.1, after)
+++ out.txt (trial 1.1.2, after)
@@ -1,3 +1,3 @@
-precision=0.8736
-recall=0.6786
-F1=0.7638
+precision=0.8125
+recall=0.6964
+F1=0.7500

  Name: pred.csv
...
  Name: pred.csv
...
Content changed as shown above for pred.csv
...
```

`pred.csv` appears twice because the R script writes it and the binary
reads it; the two accesses are paired by mode, and the diff of the
predictions is printed once. On the Kaggle dataset it shows the nine
predictions the new threshold changed, among some 57,000 rows, each as one
row removed and one added, with three rows of context; a diff longer than
200 lines would be cut, with a hint to write a whole version with `now
restore`.

The programs the script launches are dependencies of the trial, like the
modules it imports. `now show -m` lists them with their real path, the
hash of the executable and, for interpreters and compilers, the version
they print:

```
$ now show 1.1.3 -m
...
  Name: Rscript
    Version: Rscript (R) version 4.6.1 (2026-06-24)
    Path: /opt/homebrew/Cellar/r/4.6.1_1/bin/Rscript
    Code hash: 754025de...

  Name: cc
    Version: Apple clang version 21.0.0 (clang-2100.3.34.2)
    Path: /usr/bin/cc
    Code hash: af706f26...

  Name: metrics
    Version: None
    Path: /path/to/glue_pipeline/run/metrics
    Code hash: 9ba7b242...
...
```

Between the second and the third trial only `metrics.c` changed. The
binary compiled from it is the one module replaced, and its accesses show
the new source and the new output:

```
$ now diff 1.1.2 1.1.3 -f -m
...
[now] 1 modules replaced:
  Name: metrics
    Code hash changed from fa0bce89... to 9ba7b242...
...
[now] 3 file accesses replaced:
  Name: metrics
    Content hash after changed from fa0bce89... to 9ba7b242...
    Timestamp changed from ... to ...

  Name: metrics.c
    Content hash before changed from 6360d632... to 3a9c0353...
    Content hash after changed from 6360d632... to 3a9c0353...
    Timestamp changed from ... to ...

  Name: out.txt
    Content hash after changed from d7f35c36... to 89a8be23...
    Timestamp changed from ... to ...
```

With `--content` the same diff also prints the line added to `metrics.c`,
the new `accuracy=0.9991` line of `out.txt`, and one line saying that the
binary content of `metrics` differs.

In the dataflow, each launch is a node linked to the files it read and
wrote, so `prepared.csv` connects the pandas step of the script to the R
step, and `pred.csv` connects the R step to the binary:

```
$ now export dataflow 1.1.3 -m activation
...
        label = "run";
        e_48 [label="15 subprocess.run(command)" ...];
        a_3 [label="model.R" ...];
        a_5 [label="pred.csv" ...];
...
    a_2 -> e_33 [style="dashed"];
    e_48 -> a_3 [style="dashed"];
    e_48 -> a_2 [style="dashed"];
    a_5 -> e_48 [style="dashed"];
...
```

`run.sh` writes the whole graph to `run/listings/`, as a dot file and as a
PDF. It ends with `now restore 1.1.1`, which puts `model.R` and
`metrics.c` back as the first trial read them and removes the outputs
that the trials created. It reports that `metrics`, `out.txt` and
`pred.csv` changed since the last trial and, before touching them, saves
the current state of the project as the backup trial 2.0.0.
`now restore 1.1.3 -f metrics` brings back the binary of the third
trial, executable.

## What is not seen

noWorkflow records the boundary of each launch, not what happens inside
the R script or the binary: no R variable, no C function. A file that a
launched program reads or writes without naming it on its command line
(a file that `model.R` sources, for example) is not recorded. See "Beyond
Python: wrapped non-Python code" in the
[README](https://github.com/gems-uff/noworkflow#beyond-python-wrapped-non-python-code)
of noWorkflow.

## The same files elsewhere

These files are, byte for byte, the case study that the tests of
noWorkflow replay, in `src/noworkflow/tests/e2e/corpus/beyond_python/`;
`src/noworkflow/tests/test_repository_examples.py` fails when the two
copies differ, and `src/noworkflow/tests/e2e/test_beyond_python.py` fails
when an excerpt above no longer matches what `now` prints for the replay,
hashes, versions, paths and metric values aside.
