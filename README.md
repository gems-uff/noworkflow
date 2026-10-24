noWorkflow
==========

[![CI](https://github.com/gems-uff/noworkflow/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/gems-uff/noworkflow/actions/workflows/ci.yml?query=branch%3Amain)
[![Code coverage](https://qlty.sh/gh/gems-uff/projects/noworkflow/coverage.svg)](https://qlty.sh/gh/gems-uff/projects/noworkflow)
[![PyPI version](https://img.shields.io/pypi/v/noworkflow.svg)](https://pypi.org/project/noworkflow/)
[![Python versions](https://img.shields.io/pypi/pyversions/noworkflow.svg)](https://pypi.org/project/noworkflow/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/gems-uff/noworkflow/blob/main/LICENSE)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](https://github.com/gems-uff/noworkflow/blob/main/CODE_OF_CONDUCT.md)

noWorkflow is a tool designed to automatically trace the provenance of a Python script without requiring changes to the original code, thereby providing users with the creation and analysis of a detailed history of how data was produced and transformed. This history ensures transparency and reliability in scientific experiments and data processes. Developed in Python, noWorkflow can capture the provenance of scripts using software engineering techniques such as abstract syntax tree (AST) analysis, reflection, and profiling to collect provenance without necessitating a version control system or any other external environment. When a script delegates steps to other programs, such as an R script, a compiled binary, or a shell command, noWorkflow also records each launch, the files it exchanged with the script and the program it ran, so the changes to the wrapped non-Python code show up between trials (see [Beyond Python](#beyond-python-wrapped-non-python-code)).

Installing and using noWorkflow is simple and easy. Please check our installation and basic usage guidelines below, and the [tutorial videos at our Wiki page](https://github.com/gems-uff/noworkflow/wiki/Videos).


Team
----

noWorkflow is developed by researchers from Universidade Federal Fluminense (UFF) in Brazil and New York University (NYU) in the USA.

- Leonardo Murta (joined in September 2013)
- Vanessa Braganholo (joined in September 2013)
- Juliana Freire (joined in September 2013)
- João Felipe Pimentel (joined in July 2014)
- Vynicius Pontes (joined in December 2017)
- Ruslan Guerra Marzo (joined in June 2018)
- Eduardo Jandre (joined in April 2019)
- Erick Grilo (joined in June 2019)
- Daniel Toledo (joined in June 2019)
- Henrique Linhares (joined in January 2022)
- Arthur Paiva (joined in March 2023)
- Jessé Lima (joined in September 2023, Summer of Reproducibility)
- Joshua Daniel Talahatu (joined in July 2024, Google Summer of Code)
- Matheus Lobo (joined in June 2025)
- Bruno Sumar Gonçalves (joined in July 2025)
- Felipe Coutinho (joined in March 2026)

Additional contributors
-----------------------

- Ana Caroline Torres de Carvalho (documentation: README and wiki)
- Ben Marwick (documentation fix)
- David Koop (conception of noWorkflow 1.0)
- Fernando Chirigati (conception of noWorkflow 1.0)
- João Pedro Lopez (performance evaluation of noWorkflow)
- [Mirochill](https://github.com/Mirochill) (bug fix: version lookup without pkg_resources)
- Paolo Missier (Versioned-PROV, the model of the PROV export)
- Remi Rampin (documentation fix)
- Saumen Dey, Timothy McPhillips, Khalid Belhajjame and Bertram Ludäscher (integration with YesWorkflow)
- [tnkinobirb](https://github.com/tnkinobirb) (bug fix: dictionary unpacking as an item dependency)
- Vitor Gama Lemos (conception of the prospective provenance graph)

History
------------------

The project started in 2013, when Leonardo Murta and Vanessa Braganholo were visiting professors at New York University (NYU) with Juliana Freire. At that moment, David Koop and Fernando Chirigati also joined the project. They published the initial paper about noWorkflow in IPAW 2014. After going back to their home university, Universidade Federal Fluminense (UFF), Leonardo and Vanessa invited João Felipe Pimentel to join the project in 2014 for his PhD. João, Juliana, Leonardo and Vanessa integrated noWorkflow and IPython and published a paper about it in TaPP 2015. They also worked on provenance versioning and fine-grained provenance collection and published papers in IPAW 2016. During the same time, David, João, Leonardo and Vanessa worked with the YesWorkflow team on an integration between noWorkflow & YesWorkflow and published a demo in IPAW 2016. João Felipe continued that work in his PhD thesis, and the team above continues the research and development on noWorkflow.

[![Contribution Timeline](https://raw.githubusercontent.com/gems-uff/noworkflow/main/history/history.png)](https://github.com/gems-uff/noworkflow/blob/main/history/history.svg)

Publications
------------

* MURTA, L. G. P.; BRAGANHOLO, V.; CHIRIGATI, F. S.; KOOP, D.; FREIRE, J.; [noWorkflow: Capturing and Analyzing Provenance of Scripts.](https://github.com/gems-uff/noworkflow/raw/main/docs/ipaw2014.pdf) In: International Provenance and Annotation Workshop (IPAW), 2014, Cologne, Germany.
* PIMENTEL, J. F. N.; FREIRE, J.; MURTA, L. G. P.; BRAGANHOLO, V.; [Collecting and Analyzing Provenance on Interactive Notebooks: when IPython meets noWorkflow](https://github.com/gems-uff/noworkflow/raw/main/docs/tapp2015.pdf). In: Theory and Practice of Provenance (TaPP), 2015, Edinburgh, Scotland.
* PIMENTEL, J. F.; FREIRE, J.; BRAGANHOLO, V.; MURTA, L. G. P.; [Tracking and Analyzing the Evolution of Provenance from Scripts](https://github.com/gems-uff/noworkflow/raw/main/docs/ipaw2016a.pdf). In: International Provenance and Annotation Workshop (IPAW), 2016, McLean, Virginia.
* PIMENTEL, J. F.; FREIRE, J.; MURTA, L. G. P.; BRAGANHOLO, V.; [Fine-grained Provenance Collection over Scripts Through Program Slicing](https://github.com/gems-uff/noworkflow/raw/main/docs/ipaw2016b.pdf). In: International Provenance and Annotation Workshop (IPAW), 2016, McLean, Virginia.
* PIMENTEL, J. F.; DEY, S.; MCPHILLIPS, T.; BELHAJJAME, K.; KOOP, D.; MURTA, L. G. P.; BRAGANHOLO, V.; LUDÄSCHER B.; [Yin & Yang: Demonstrating Complementary Provenance from noWorkflow & YesWorkflow](https://github.com/gems-uff/noworkflow/raw/main/docs/ipaw2016c.pdf). In: International Provenance and Annotation Workshop (IPAW), 2016, McLean, Virginia.
* PIMENTEL, J. F.; MURTA, L. G. P.; BRAGANHOLO, V.; FREIRE, J.; [noWorkflow: a Tool for Collecting, Analyzing, and Managing Provenance from Python Scripts](https://github.com/gems-uff/noworkflow/raw/main/docs/vldb2017.pdf). In: International Conference on Very Large Data Bases (VLDB), 2017, Munich, Germany.
* PONTES, V.: [Reducing the Storage Overhead of the noWorkflow Content Database by using Git](https://github.com/gems-uff/noworkflow/raw/main/docs/tcc-vynicius.pdf). Final undergraduate Project, Sistemas de Informação, Universidade Federal Fluminense, 2018.
* [OLIVEIRA, E.; Enabling Collaboration in Scientific Experiments. Masters Dissertation, Universidade Federal Fluminense, 2022.](https://github.com/gems-uff/noworkflow/blob/main/docs/Disserta__o___Eduardo_Jandre.pdf)

Citing noWorkflow and long-term availability
--------------------------------------------

If you use noWorkflow in your research, please cite it. [`CITATION.cff`](https://github.com/gems-uff/noworkflow/blob/main/CITATION.cff) has the reference in a machine-readable form, and the "Cite this repository" button on the GitHub page of the repository exports it as BibTeX or APA. It names the VLDB 2017 paper above as the reference to cite.

Every release stays available as a tag of this repository, listed under [Releases](https://github.com/gems-uff/noworkflow/releases), and on the Python Package Index, so the version an article describes can always be installed by its number (e.g., `pip install noworkflow==2.2.0`). Newer versions are published in the same places, and the `main` branch holds the code that will become the next release.

Quick Installation
------------------

To install the latest release of noWorkflow, follow these basic instructions. The "Alternative" procedure below installs the code of the `main` branch instead, which may hold changes that are not released yet.

With Python 3.11 or later, use pip to install noWorkflow:
```
$ pip install noworkflow
```
This installs noWorkflow with everything it needs to collect provenance and to analyze it from the command line, the visualization tool (Flask) included.

The `all` extra adds IPython and Jupyter for the [IPython interface](#ipython-interface), pyswip-alt for Prolog queries from Python, jsonpickle for the `jsonpickle` serialization of values, and matplotlib, NumPy and Cython, which the demonstration projects use:
```
$ pip install "noworkflow[all]"
```
Alternative: install the most up-to-date version of noWorkflow
------------------

If you wish to install the most up-to-date version of noWorkflow, you can clone our repository using Git.

```
$ git clone https://github.com/gems-uff/noworkflow.git
```
If you don't have git, just download the ZIP source code from our repository and decompress the zip file into a folder (named `noworkflow-main`).

The current version is tested with Python 3.11 to 3.15. Go to the folder where you cloned the project (or where you decompressed the files) and then execute the following:

```
$ cd noworkflow
$ pip install ".[all]"
```
This installs noWorkflow and its dependencies on your system. To work on noWorkflow itself, see [CONTRIBUTING.md](https://github.com/gems-uff/noworkflow/blob/main/CONTRIBUTING.md), which sets up a development environment with uv.

Upgrade
-------

To upgrade the version of a previously installed noWorkflow using pip, you should run the following command:

```
$ pip install --upgrade "noworkflow[all]"
```

Basic Usage
-----------

noWorkflow is transparent in the sense that it requires neither changes to the script, nor any laborious configuration. Run
```
$ now --help
```
to learn the usage options.

noWorkflow comes with demonstration projects, and the repository holds a few examples; see [Examples](#examples).

To run noWorkflow you should run:
```
$ now run script.py
```
The *-v* option turns the verbose mode on, so that noWorkflow gives you feedback on the steps taken by the tool. The output, in this case, is similar to what follows.
```
$ now run -v script.py
[now] removing noWorkflow boilerplate
[now] setting up local provenance store
[now] using content engine noworkflow.now.persistence.content.plain_engine.PlainEngine
[now] creating provenance database
[now] collecting deployment provenance
[now]   registering environment attributes
[now] collection definition and execution provenance
[now]   executing the script
[now] the execution of trial 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb finished successfully
```
The line `creating provenance database` appears in the first run of a project only. Each new run produces a different trial that will be stored with a universally unique identifier in the relational database.

Verifying the module dependencies is a time consuming step, and scientists can bypass this step by using the *-b* flag if they know that no library or source code has changed. The current trial then inherits the module dependencies of the previous one.  To see more usage options, run "now run -h".

The collection can also be tuned. The *-d* option limits the depth of the collection, and *-cg* switches from fine-grained to coarse-grained collection, which stops collecting variable assignments, variable dependencies, and loop structures:
```bash
$ now run -d 2 script.py
$ now run -cg script.py
```
The *-e* option controls which evaluation values are collected: *all* (default), *relevant* (only values of activations, arguments, and tagged evaluations), or *none* (no values at all):
```bash
$ now run -e relevant script.py
```
Other options include *-c* to choose which functions are subject to depth computation (*main*, *package*, or *all*), *-r* to choose the serialization method for values (*repr*, *jsonpickle*, *jsonpickle_content*, or *simple*), *-s* and *-S* to set how often partial provenance is saved, *--name* to group or separate trials, *--dir* to set where provenance is stored, and *--message* to attach a message to the trial.

Scripts that launch other programs, such as an R script, a compiled binary or a shell command, are covered in [Beyond Python](#beyond-python-wrapped-non-python-code) below: noWorkflow records each launch, the files it exchanged with the script and the program it ran, and the *--external-tracer* and *--executable-cap* options of `now run` tune what is recorded.

To restore files, run:
```
$ now restore [trial]
```
By default, the restore command will restore the trial script, imported local modules and the first access to files. Use the option *-s* to leave out the script; the option *-l* to leave out modules; and the option *-a* to leave out file accesses. The restore command track the evolution history. By default, subsequent trials are based on the previous Trial. When you restore a Trial, the next Trial will be based on the restored Trial. A program the trial launched (see [Beyond Python](#beyond-python-wrapped-non-python-code)) comes back with the executable bit; no other file mode is recorded, so any other file, a data file or a module that was executable included, comes back with the default mode.

The restore command also provides a *-f path* option. This option can be used to restore a single file. With this command there are extra options: *-t path2* specifies the target of restored file; *-i id* identifies the file. There are 3 possibilities to identify files: by access time, by code hash, or by number of access. Without *-i*, *-f* restores the first version of the file in the trial: its content before the trial first accessed it or, for a file the trial created, the content the trial wrote into it. When the version asked for is one in which the file did not exist, *-t* leaves the target as it is and the command fails. The option *-f* does not affect evolution history. To see more usage options, run "now restore -h".

To execute the git garbage collection in the content database, run:
```
$ now gc
```

Analysis
-----------

To list all trials, just run:
```
$ now list
```
Assuming we run `script.py` twice, edit it, and then restore the first trial with `now restore 1.1.1`, which saves the edited state as a backup trial first, `now list` shows:
```
$ now list
[now] trials available in the provenance store:
  [*]Trial 91f4fdc7-6c36-4c9d-a43a-341eaee9b7fb: run script.py
                                                 with code hash 6a28e58e34bbff0facaf55f80313ab2fd2505a58
                                                 ran from 2026-10-23 19:38:50.234485 to 2026-10-23 19:38:51.672300
                                                 duration: 0:00:01.437815
                                                 Sequence Key: 1
                                                 Tag: 1.1.1 Type: AUTO
  [*]Trial 01482b72-2005-4319-bd57-773291f9f7b1: run script.py
                                                 with code hash 6a28e58e34bbff0facaf55f80313ab2fd2505a58
                                                 ran from 2026-10-23 19:40:18.747749 to 2026-10-23 19:40:19.401719
                                                 duration: 0:00:00.653970
                                                 Sequence Key: 2
                                                 Tag: 1.1.2 Type: AUTO
  [b]Trial 8bf59cf5-cd06-409e-97f6-185063b1cfc3: restore 1.1.1
                                                 with code hash c3aeb4cb9af363b375aec603010dd1b97460f6b1
                                                 ran from 2026-10-23 19:45:36.937565 to 2026-10-23 19:45:37.141808
                                                 duration: 0:00:00.204243
                                                 Sequence Key: 3
                                                 Tag: 2.0.0 Type: AUTO
```
Each symbol between brackets is its respective trial status. They can express if:
```
a trial has not finished: f

a trial has finished: *

a trial is a backup: b
```
To look at details of an specific trial, use:
```
$ now show [trial]
```
This command has several options, such as *-m* to show module dependencies; *-d* to show function definitions; *-e* to show the environment context; *-a* to show function activations; *-p* to show noworkflow parameters; and *-f* to show file accesses.To see more usage options, please run "now show -h".

To compare two trials:
```bash
$ now diff [trial1] [trial2]
```
where *[trial1]* and *[trial2]* are the trial ids to be compared. It has options to compare modules (*-m*), environment (*-e*), file accesses (*-f*). It has also an option to present a brief diff, instead of a full diff (*--brief*). To see more optional arguments, run "now diff -h".

A module, or a program a trial launched, whose code changed between the trials is listed as replaced with its code hash before and after. A file accessed in both trials whose content changed is listed as replaced with its content hashes; when a file is accessed more than once, the accesses are paired by mode and in the order they happened. With *--content*, which needs *-f* (or *-fa*), `now diff` also prints, under each replaced file access, the unified diff of the two versions it keeps in the content database, such as the lines of an R script edited between two trials:
```bash
$ now diff [trial1] [trial2] -f --content
```
A binary file gets one line saying that its content differs, a side where the file did not exist gets a line instead of the whole content of the other, and a diff longer than 200 lines is cut, with a hint to restore a whole version with `now restore`.

The *-fa* option compares two function activations instead of whole trials, taking the database ids of the activations in the same order as the trials:
```bash
$ now diff [trial1] [trial2] -fa 57 65
```
It reports the differences in output, arguments, duration, variables, and file accesses. An optional argument after the ids selects which kinds of variable are shown: leaving it blank shows name, attribute, and access variables; *op* also shows operations; and *all* shows every kind.

The *dataflow* option exports fine-grained provenance data to a graphviz dot representing the dataflow. The *-m* option chooses the graph mode: *activation*, *coarseGrain*, *looplessCoarseGrain*, *fineGrain*, or *all*. Please, run "now export dataflow -h" to get the description of all options.
```bash
$ now export dataflow [trial] -m coarseGrain | dot -Tpng -o dataflow.png
```

Other options control what appears in the graph: *-a* sets how file accesses are shown, *-e* combines evaluation nodes, *-d* limits which user-defined calls appear, *-g* aligns evaluations, *--value-length* and *--name-length* limit the displayed text, and *-T*, *-t*, *-H*, *-hnc*, *-hf*, and *-an* hide or rename specific kinds of node. The *-w* option restricts the graph to everything that derived a given evaluation:
```bash
$ now export dataflow [trial] -m activation -w 18 | dot -Tpng -o wdf.png
```

To export the prospective provenance graph of a trial, which represents the static structure of the script, run:
```bash
$ now export prospective [trial] | dot -Tpng -o prospective.png
```

To export provenance data of a given trial to Prolog facts, so inference queries can be run over the database, run:
```
$ now export prolog [trial]
```
It also exports inference rules by *-r* argument.

To export the collected provenance of a trial to Prov.
```bash
$ now export prov [trial]
```
Each file access of the trial, the files exchanged with the external programs it launched included, is an entity with the file's name, the mode and the content hashes, used by the activation that read the file or generated by the one that wrote it.

The *schema* option presents the SQL schema of noWorkflow:
```bash
$ now schema sql
```
or Prolog schema of noWorkflow:
```bash
$ now schema prolog
```
Adding the *-d* optional argument exports graphic schema to a dot format.

To check a textual history evolution graph of trials, run:
```bash
$ now history
```
The *-s* option shows the history of one script only, and *-e* the trials in one status (*finished*, *unfinished* or *backup*).

The *evaluation* option query evaluation and its dependencies. The *evaluation* command can be used without arguments, and the default option is *display*. The argument shows evaluations that represent executions or accesses to values and expressions in the code, capturing the interaction between variables, functions, objects, and other script elements. 
```bash
$ now evaluation
```
The argument *wdf* identifies and displays dependency relationships between code elements, tracing how data, functions, and variables have been derived from each other.
```bash
$ now evaluation wdf
```

The *export ast* option generates the Abstract Syntax Tree (AST) of the script of a trial. By default, it outputs the AST in its standard format. However, you can specify the output format using the *-j* (*--json*) option for JSON format or the *-d* (*--dot*) option for Graphviz dot format.
```bash
$ now export ast [trial]
$ now export ast [trial] --dot
```

Beyond Python: wrapped non-Python code
--------------------------------------

Scripts often delegate steps to other programs: an R script, a compiled binary, a shell command. noWorkflow records the processes a script starts through `subprocess`, `os.system`, `os.popen` and `os.posix_spawn`, without changes to the script. It does not trace what happens inside the other program. It records the boundary of each launch and what crosses it:

- **The launch.** The call that starts the process (the `subprocess.run`, for example) is an activation of the trial, whose arguments are the command line and whose value carries the exit status.
- **The files it exchanged.** Each file the command line names becomes a file access of that activation, with its content before and after the process, and so do the files the process creates in the project directory. `now diff -f` thus shows that an R script edited between two trials changed, even though the Python did not, and `now diff -f --content` prints the edit. In `now export prov`, each of these files is an entity used or generated by the activation of the launch.
- **The program.** The program the process runs is a dependency of the trial, like an imported module: `now show -m` lists it under the name the command line gives it, with its real path, the hash of the executable (so `now diff -m` shows that a binary was recompiled) and, for interpreters and compilers such as `Rscript`, `python`, `gcc` or `java`, the version they print, which noWorkflow asks for once per trial with `--version`; no other program is ever run to probe it. Through a shell, the programs of the line's commands are recorded, not the shell. A shared library the script loads through `ctypes` by its path is listed the same way.

The mode of each access is inferred from the content of the file before and after the process. A file that has the same content when the process ends was read (`r`); one whose content changed was read and written (`r+`); one that the process removed was read, with no content after. A word of the command line that looks like a path (it has a directory separator, or an extension that is not a number) and names no file yet becomes a write (`w`) when the process leaves a file there. Redirections are taken as declared: `>` writes (`w`), `>>` appends (`a`) and `<` reads (`r`). A file named in an option (`--out=pred.csv`) or in an assignment (`OUT=pred.csv`) counts as named. The files the process creates without naming them are found by listing the project directory when the process starts and when it ends; in a project with more than 20,000 entries the listing is turned off for the trial, with a warning.

An executable larger than 16 MB is not stored, only its hash and its size, so `now restore` cannot put it back; the *--executable-cap* option of `now run` changes that size (`--executable-cap 64M`; bytes, or a *K*, *M* or *G* suffix; `0` stores no executable), and the trial records it with its other arguments. *-b* records neither the programs nor the libraries, and still records the files. `now restore` puts a program of the project that the trial launched back with its executable bit. The *--external-tracer* option selects how much of this is recorded:
```bash
$ now run --external-tracer none script.py    # nothing of the processes
$ now run --external-tracer argv script.py    # the default: the files named on the command lines and the new files of the project
$ now run --external-tracer strace script.py  # also the files the processes open on their own (Linux; not available yet, falls back to argv)
```

[`Examples/glue_pipeline`](https://github.com/gems-uff/noworkflow/tree/main/Examples/glue_pipeline) is a Python script that prepares data with pandas, fits a model in R and computes its metrics in C, with three trials that edit the R script and then the C program. Its README shows what `now diff`, `now show -m` and `now export dataflow` print for them.

What is not recorded:

- **Inside the program.** Its variables, its functions and the files it opens without naming them on its command line are not seen. A provenance tool of the other language, such as rdtLite for R, can record them; the files it writes in the project are then recorded as files the process created.
- **Changes the content does not show.** A file the process modifies without naming it on its command line is not seen, and a file it rewrites with the same content is recorded as a read. Delete the outputs before each trial when that matters.
- **Other ways to start a process.** The children of `os.fork` and `multiprocessing` are not launches and are not recorded, and neither are a process that a launched program starts in turn, a process started from compiled code, and the program that `os.exec` puts in the place of the script, which also leaves the trial unfinished.

Examples
--------

`now demo` copies a demonstration project into the current directory and runs it step by step, printing each command it runs. `now demo 1` builds the history of a weather simulation, with restores between its trials; its scripts plot with matplotlib, which the `demo` extra installs (`pip install "noworkflow[demo]"`). The repository also holds examples to run by hand, in [`Examples/`](https://github.com/gems-uff/noworkflow/tree/main/Examples):

- [`demo_1`](https://github.com/gems-uff/noworkflow/tree/main/Examples/demo_1): the weather simulation of `now demo 1`, run as `now run simulation.py data1.dat data2.dat`.
- [`Fat`](https://github.com/gems-uff/noworkflow/tree/main/Examples/Fat): a recursive factorial, the smallest script to look at activations with `now show -a`.
- [`glue_pipeline`](https://github.com/gems-uff/noworkflow/tree/main/Examples/glue_pipeline): a Python script that launches an R script and a C program (see [Beyond Python](#beyond-python-wrapped-non-python-code)).
- [`usecase_credit_fraud`](https://github.com/gems-uff/noworkflow/tree/main/Examples/usecase_credit_fraud): a credit card fraud detection experiment in Jupyter notebooks, with tagged variables compared across trials.

What a provenance store records
-------------------------------

A provenance store, the `.noworkflow` directory next to the script, records the whole environment of the machine that ran the script: every environment variable (`PATH`, and any token or password kept in one, included), the user name, the hostname, the process id and the release of the operating system. Its content database also keeps a copy of every file the script read or wrote. `now show -e` prints the environment, `now export prolog` writes it as facts, `now vis` serves it, and `now push` sends it to a server with the trials. Look at what a store holds before sharing it, or an export of it, and keep `.noworkflow` out of public repositories.

Visualization Tool
-----------

The visualization tool runs on Flask, which `pip install noworkflow` already installs. The *vis* option starts a visualization tool that allows interactive analysis:
```bash
$ now vis -b
```
The visualization tool shows the evolution history, the trial information, an activation graph. It is also possible to compare different trials in the visualization tool. An activation graph can be changed into a definition graph that visualizes the structure of a trial, showing the hierarchical relationships of code constructs. 

By default, *now vis* runs on *localhost:5000*, which conflicts with a built-in service on MacOS. To avoid that, you can specify a different port using the -p parameter. The example below uses the 5001 port instead of the default 5000.

```bash
$ now vis -p 5001
```
The *--host* option changes the address the server binds to, so the interface can be reached from another machine, *-d* runs the server in debug mode, and *--dir* points to a provenance database in another directory.


Explore this tutorial to master the [Visualization Tool](https://github.com/gems-uff/noworkflow/wiki#visualization-tool)

Collaboration Usage
-----------

noWorkflow can also be used to run collaborative experiments. Scientists with different computers can work on the same experiments without much trouble. To do this they must do push and pull operations to a server.

The server can be a central one or a peer-to-peer connection. To set up a server or connection online the command below must be run

```bash
$ now vis --force true
```

The command line output will show the server address 
```bash
 * Serving Flask app 'noworkflow.now.vis.views'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://localhost:5000
Press CTRL+C to quit
```
In the case above it's http://localhost:5000

To create a new experiment you must open the server address and choose the "Add Experiment" option
![Collab main page](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/collab_main_page.png)

Then you must give the experiment a name, write its description, and choose "Confirm"
![Collab add experiment](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/collab_add_experiment.png)

If the experiment is successfully created you should see a message stating so
![Collab add experiment success](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/collab_add_experiment_success.png)
As you can see in the image above, an id and an url for the experiment will be generated after the experiment is created.
The url is extremely important since it will be used to do the push and pull operations.

To get the experiment on a computer you first need to navigate to the folder where you want the experiment, then execute the pull command. The pull command accepts a --url parameter that must be followed by the experiment's url. For example

```bash
$ now pull --url http://localhost:5000/experiments/958273cc-b90a-4d1c-b617-43bd2dca20de
```

The command will download the experiment's files and provenience in the folder. If there are already any files or trials in the experiment you must execute the command "now restore" with or without a trial id.

To push(or commit) to the server(or peer-to-peer connection) you must run the push command. The push command accepts a --url parameter that must be followed by the experiment's url. For example

```bash
$ now push --url http://localhost:5000/experiments/958273cc-b90a-4d1c-b617-43bd2dca20de
```

You can also add groups to a server by navigating to the "Group Information" tab and choosing the "Add Group" option

![Collab group tab](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/collab_group_tab.png)

Then you should write the group's name and choose "Confirm"
![Collab group add group](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/collab_add_group.png)

If the group is added successfully, you should see a message confirming that the group was created. You should also see the options to add a user to a group or to delete the group
![Collab group success](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/collab_group_success.png)

If the option to add a user is chosen, you must select the user from a list and choose "Confirm".
![Collab group member](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/collab_add_group_member.png)

To delete a group just select "Delete Group", then "OK" on the alert that will appear on the screen
![Collab delete group](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/collab_delete_group.png)

Annotations
-----------------

You can also add annotations to an experiment. To do this you need to access the experiment's url, then go to the "Annotation" tab, and select "Add Annotation"
![Annotation experiment](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/annotation%20experiment.png)

After filling the annotation's information, choose "Confirm"
![Annotation add](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/annotation_add.png)

If the annotation is added, you will see a success message and will be able to download the annotation as seen below
![Annotation success](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/annotation_success.png)

Annotations can also be added to a trial by following the same procedure above. But first, you must select a trial, choose "Manage Annotations"

![Annotation trial](https://raw.githubusercontent.com/gems-uff/noworkflow/main/readme_images/trial_annotations.png)

IPython Interface
-----------------

Another way to run, visualize, and query trials is to use Jupyter notebook with IPython kernel.
To install Jupyter and noworkflow extension, you can run
```bash
$ pip install jupyter
$ pip install noworkflow_labextension
```

Notes: 

- It is possible to run many of the commands below without installing `noworkflow_labextension`. This package enables visualizing trials and history in the notebook.

- This visualization package supports Jupyter Lab and Notebook 7+. The support for older versions of notebook has been dropped.



After installing jupyter (and noWorkflow labextension), go to the project directory and execute:
```bash
$ jupyter notebook
```

It will start a local webserver where you can create notebooks and run python code.

Before loading anything related to noworkflow on a notebook, you must initialize it:
```python
In  [1]: %load_ext noworkflow
    ...: import noworkflow.now.ipython as nip
```
It is equivalent to:
```python
In  [1]: %load_ext noworkflow
    ...: nip = %now_ip
```

After that, you can either run a new trial or load an existing object (*History*, *Trial*, *Diff*).

There are two ways to run a new trial:

1- Load an external file
```python
In  [1]: arg1 = "data1.dat"
         arg2 = "data2.dat"

In  [2]: trial = %now_run simulation.py {arg1} {arg2}
    ...: trial
Out [2]: <Trial "7fb4ca3d-8046-46cf-9c54-54923d2076ba"> # Loads the trial object represented as a graph
```

2- Load the code inside a cell
```python
In  [3]: arg = 4

In  [4]: %%now_run --name new_simularion --interactive
    ...: l = range(arg)
    ...: c = sum(l)
    ...: print(c)
         6
Out [4]: <Trial "01482b72-2005-4319-bd57-773291f9f7b1"> # Loads the trial object represented as a graph

In  [5]: c
Out [5]: 6
```
Both modes supports all the `now run` parameters.

The *--interactive* mode allows the cell to share variables with the notebook.

Loading existing trials, histories and diffs:
```python
In  [6]: trial = nip.Trial("7fb4ca3d-8046-46cf-9c54-54923d2076ba") # Loads trial with Id = 7fb4ca3d-8046-46cf-9c54-54923d2076ba
    ...: trial # Shows trial graph
Out [6]: <Trial 7fb4ca3d-8046-46cf-9c54-54923d2076ba>

In  [7]: history = nip.History() # Loads history
    ...: history # Shows history graph
Out [7]: <History>

In  [8]: diff = nip.Diff("7fb4ca3d-8046-46cf-9c54-54923d2076ba", "01482b72-2005-4319-bd57-773291f9f7b1") # Loads diff between trial 7fb4ca3d-8046-46cf-9c54-54923d2076ba and 01482b72-2005-4319-bd57-773291f9f7b1
    ...: diff # Shows diff graph
Out [8]: <Diff "7fb4ca3d-8046-46cf-9c54-54923d2076ba" "01482b72-2005-4319-bd57-773291f9f7b1">
```

To visualize the dataflow of a trial, it is possible to use the dot attribute of trial objects:
```python
In  [9]: trial.dot
Out [9]: <png image>
```

This command requires an installation of graphviz.


There are attributes on those objects to change the graph visualization, width, height and filter values. Please, check the documentation by running the following code on jupyter notebook:
```python
In  [10]: trial?

In  [11]: history?
```

It is also possible to run prolog queries on IPython notebook. To do so, you will need to install SWI-Prolog with shared libraries and the pyswip module.

You can install pyswip module with the command:
```bash
$ pip install pyswip-alt
```

Check how to install SWI-Prolog with shared libraries at https://github.com/yuce/pyswip/blob/master/INSTALL

To query a specific trial, you can do:
```python
In  [12]: result = trial.query("activation(_, 550, X, _, _, _)")
    ...: next(result) # The result is a generator
Out [12]: {'X': 'range'}
```

To check the existing rules, please do:
```python
In  [13]: %now_schema prolog -t
Out [13]: [...]
```

Finally, it is possible to run the CLI commands inside ipython notebook:
```python
In  [14]: !now export {trial.id}
Out [14]: %
     ...: % FACT: activation(trial_id, id, name, start, finish, caller_activation_id).
     ...: %
     ...: ...
```

To clean Jupyter Notebook using the collected provenance, run:
```bash
$ now clean [trial]
```

Using noWorkflow with an AI agent
---------------------------------

The repository ships a skill, [`skills/noworkflow/SKILL.md`](https://github.com/gems-uff/noworkflow/blob/main/skills/noworkflow/SKILL.md), that teaches an AI coding agent how to run your scripts under noWorkflow and analyze the trials: the commands, where the data lives, research recipes and the known limitations. With Claude Code, install it for all your projects with:

```bash
$ mkdir -p ~/.claude/skills/noworkflow
$ curl -fsSL https://raw.githubusercontent.com/gems-uff/noworkflow/main/skills/noworkflow/SKILL.md -o ~/.claude/skills/noworkflow/SKILL.md
```

or put it in `.claude/skills/noworkflow/` inside one project. Other agents that read skills or instruction files can be pointed at the same file. Then ask in plain language, for example "run simulation.py with noWorkflow and tell me what changed since the last run". Note that a provenance store records the whole environment of the machine (environment variables, user name, hostname): the skill tells the agent to warn you before sharing it.

Contributing
------------

Pull requests for bug fixes and new features are welcome! The contribution cycle (issue first, `issue_NNN` branch, tests, pull request) and the commands to run the suite locally are in [CONTRIBUTING.md](https://github.com/gems-uff/noworkflow/blob/main/CONTRIBUTING.md).
Security problems are reported as public issues; see [SECURITY.md](https://github.com/gems-uff/noworkflow/blob/main/SECURITY.md).

Included Software
-----------------

Parts of the following software were used by noWorkflow directly or in an adapted form:

The Python Debugger  
Copyright (c) 2001-2016 Python Software Foundation.  
All Rights Reserved.  

Acknowledgements
----------------

We would like to thank CNPq, FAPERJ, and the National Science Foundation (CNS-1229185, CNS-1153503, IIS-1142013) for partially supporting this work.

License
-------

noWorkflow is released under the [MIT License](https://github.com/gems-uff/noworkflow/blob/main/LICENSE).
