---
name: noworkflow
description: Captures and analyzes the provenance of Python scripts with noWorkflow (the `now` command) — runs a script as a recorded trial, lists, shows and compares trials, traces where a value or an output file came from, exports provenance to Prolog, PROV-N, Graphviz or notebooks, restores earlier versions of the script and its files, and opens the visualization. Use when the user wants to record how a script produced its results, compare two runs of an experiment, find which inputs, files or functions a result depends on, go back to the files of an earlier run, or mentions noWorkflow, `now run`, trials or a `.noworkflow/` directory.
---

# noWorkflow

noWorkflow records the provenance of a Python script without any change to
the script. `now run script.py` executes it and stores a **trial**: the
script and the local modules it imported (with their content), the
arguments, the environment, every function activation with its arguments
and return values, every variable evaluation and its dependencies, and
every file the script opened, with the content before and after. Trials
are kept in a `.noworkflow/` directory, and the other commands read,
compare, export and restore them.

Use it to answer questions like "what changed between yesterday's run and
today's?", "which input files produced this output?", "which values does
this result derive from?" and "give me back the script and data of run 3".

The help of the installed version is the reference: `now -h` and
`now <command> -h`. What follows was checked by running each command; where
a command misbehaves today, the issue number in the noWorkflow repository
says so — check it before telling the user something cannot be done.

## Install and check the installation

```bash
pip install noworkflow             # the collector, the CLI and the vis server
pip install "noworkflow[all]"      # plus IPython, Jupyter, pyswip-alt, matplotlib, numpy
```

Install it **into the same environment as the script's dependencies**:
`now run` executes the script with the interpreter noWorkflow is installed
in, so the script's imports must resolve there. Rendering the `.dot`
graphs needs Graphviz's `dot` program, which is a system package, not a
Python one.

Check:

```bash
now --version          # prints "noWorkflow <version>"
now -h                 # the commands (one is missing from the list: `now import`, #253)
now run -h             # the options of one command
```

A smoke test in a scratch directory:

```bash
mkdir /tmp/now-smoke && cd /tmp/now-smoke
printf 'with open("out.txt", "w") as f:\n    f.write(str(sum(range(10))))\n' > s.py
now run -v s.py        # ends with "[now] the execution of trial <uuid> finished successfully"
now list               # one trial, marked [*]
```

## Where the data lives — and what it contains

- `now run script.py` creates `.noworkflow/` **next to the script**, not in
  the current directory: `db.sqlite` (the relational store) and `content/`
  (a copy of every script, module and file version, by hash). Files the
  script opens by relative path still resolve against the current directory,
  so run it from where the script expects to run.
- Every other command reads `.noworkflow/` in the **current directory**, or
  in `--dir DIR`. Without a store there it prints "there is no provenance
  store in the informed directory" and exits 1.
- `now run --dir DIR` puts the store in `DIR`, but it also breaks the
  imports of modules next to the script (#244); avoid it for scripts that
  import their own modules.
- A store cannot be moved or copied elsewhere: trials record absolute paths.
- The store grows with every trial (a copy of every file version read or
  written). Suggest adding `.noworkflow/` to `.gitignore`.

**The store records sensitive data.** Every trial stores the whole
environment of the process (every environment variable, including any token
or key kept in one, `PATH`, the user name, the hostname, the pid, the OS
release). `now show -e`, `now diff -e`, `now export prolog` (one
`environment` fact per variable), `now export prov`, the vis and
`now push` all expose it. Before you share a store, an export or the output
of these commands — in an issue, a chat, a repository, or by sending it to a
server — tell the user what it contains and let them decide. Do not run
`now show -e` just to look around: its output enters your context. When an
environment attribute matters, read only that one
(`now show -e | grep '^  PYTHONPATH:'`).

## The core flow

### 1. Run: `now run`

```bash
now run script.py arg1 arg2              # noWorkflow options go before the script, its arguments after
now run -v script.py data1.dat           # verbose: the steps and the trial id at the end
now run --message "scale 2.0" script.py data1.dat 2.0
```

The script's own output is printed as usual. Each run is a new trial.

**How the trial ended:** `now run` exits as plain Python would have for the
script: with the code given to `sys.exit`, with 1 after an uncaught
exception, with 0 otherwise. A failed run prints the traceback on stderr
after "the execution finished with an uncaught exception", stores the trial
anyway and leaves it marked `[f]` (unfinished) in `now list`.

Collection options, from the cheapest to the most complete:

| Option | Effect |
|---|---|
| `-cg` | coarse-grained: activations, arguments, returns and file accesses only (no variables, no dependencies) |
| `-e relevant` / `-e none` | collect the values of activations, arguments and tagged evaluations only / no values |
| `-d N` | limit the depth of collected activations: the first call past the limit is recorded as a black box (its arguments and its result), and nothing it does or calls is. The script computes what it computes without noWorkflow. |
| `-b` | reuse the module dependencies of the previous trial (faster; fails without a previous trial) |
| `--executable-cap SIZE` | the size above which the program a process runs (and a `ctypes` library) is stored as its hash only, which `now restore` cannot put back (default `16M`; bytes or a `K`, `M`, `G` suffix; `0` stores none) |
| `-c main\|package\|all` | which functions count for `-d` |
| `-r repr\|jsonpickle\|jsonpickle_content\|simple` | how values are serialized |
| `--external-tracer none\|argv\|strace` | what is recorded of the processes the script starts (`subprocess`, `os.system`, `os.popen`, `os.posix_spawn`). `argv` (default): the files their command lines name, with their content before and after, and the files they create in the project, as file accesses of the call that started the process, and the program each one runs as a module (`now show -m`); `none`: nothing; `strace`: also every file of the project they and their children open, and the programs they run from it (Linux, with strace; falls back to `argv` with a warning where strace cannot trace). With `argv` or `strace`, a launch that writes the PROV-JSON of rdtLite (`prov*/prov.json` in the project, as `Rscript -e 'rdtLite::prov.run("model.R", prov.dir = ".")'` leaves it) also gets, as its file accesses, the files that document names: the R script, the scripts it sourced, and the files it read and wrote |
| `-s MS` / `-S CALLS` | save partial provenance every MS milliseconds / CALLS calls |
| `--name NAME` | the name of the trial's script in the history; separates or groups branches |
| `--message TEXT` | a note stored with the trial (`now show -p` shows it) |

`now debug script.py` is `now run` with `-c package` and partial provenance
saved every second and every call: use it for a script that crashes or
hangs, so the provenance up to the failure is kept.

### 2. List: `now list`

```text
[now] trials available in the provenance store:
  [*]Trial 6270af8d-3979-46c4-8f05-96da37074438: run simulation.py data1.dat data2.dat
                                                 with code hash eded2ea6...
                                                 ran from ... to ...
                                                 duration: 0:00:00.193468
                                                 Sequence Key: 1
                                                 Tag: 1.1.1 Type: AUTO
```

Status: `[*]` finished, `[f]` unfinished (failed or interrupted), `[b]` a
backup trial created by `now restore`.

**Naming a trial**, in every command that takes one: the full id, the
sequence key (`1`, `2`, …) or the tag (`1.1.1`). A prefix of the id names
nothing ("Trial 6270af8d not found" on stderr, exit 1). Without a
trial argument, commands use the last trial. Automatic tags change their
major number when the script's code changes and their minor number when the
command line changes.

### 3. Show one trial: `now show`

```bash
now show 2             # id, sequence key, status, script, code hash, start, finish, duration
now show -f 2          # files read and written, mode, content hash before and after, the call chain that opened each
now show -m 2          # the modules the script imported, the programs its processes ran and the libraries it loaded through ctypes, with path, code hash and version
now show -d 2          # the code blocks (script, functions) with parameters and calls
now show -a 2          # the activation tree: every call with parameters, return value and time
now show -p 2          # the options of the run, the message and the script's argv
now show -e 2          # the environment — sensitive, see above
```

### 4. Compare two trials: `now diff`

```bash
now diff 1 2                 # what changed in the trial itself: times, command, parent
now diff 1 2 -f --brief      # a table of files added, removed and changed
now diff 1 2 -f              # per file: content hashes before and after
now diff 1 2 -f --content    # ... and the unified diff of each changed file
now diff 1 2 -m              # modules added, removed and replaced, with their code hash
now diff 1 2 -a              # the tree edit distance between the two activation trees
now diff 1 2 -t              # hide the timestamps
```

Both trials are required. To compare **one function's activation** in the
two trials (its output, arguments, duration and variables, and the files
read or written by it or below it, by the processes it launched too), `-fa`
takes the two activations' database ids, one per trial (the same trial twice
compares two calls of one run):

```bash
sqlite3 -readonly .noworkflow/db.sqlite "SELECT t.sequence_key, a.id, a.name
  FROM activation a JOIN trial t ON t.id = a.trial_id WHERE a.name = 'run_simulation'"
now diff 1 2 -fa 40 40       # add `op` or `all` after the ids to include more kinds of variable
```

Ids that are not integers or name no function are a usage error (exit
2), and so is `--content` without `-f` or `-fa`, or with `--brief`. Two
accesses to one file in a trial (a write and a read back) are paired with
the accesses of the same mode in the other trial, in the order they
happened; each section lists its blocks by name.

### 5. Export: `now export`

```bash
now export prolog 2 > trial2.pl          # Prolog facts; `now schema prolog` documents each predicate
now export prov 2 > trial2.provn         # PROV-N; each file access is an entity of its activation
now export dataflow 2 | dot -Tpng -o dataflow.png
now export prospective 2 | dot -Tsvg -o structure.svg   # the static structure of the script
now export ast -d 2 | dot -Tpng -o ast.png               # the script's AST
now export ipynb 2                       # writes Trial-2.ipynb, a notebook to analyze the trial
now export ipynb history                 # History.ipynb
now export ipynb diff:1:2                # Diff-1-2.ipynb
```

- `export dataflow` modes (`-m`): `activation`, `coarseGrain` (default),
  `looplessCoarseGrain`, `fineGrain`, `all`. `-w ID` keeps only an
  evaluation and what it was derived from, inside the clusters of the
  activations that hold them (the id comes from `now evaluation`, below);
  `-m activation` draws only the activations among them.
  `looplessCoarseGrain` draws a call that a loop repeats once, with
  everything any of its iterations called inside it.
- `export prolog -r` appends inference rules that do not match the facts
  (#249); query the facts directly (recipe below).
- `export ast` fails from Python 3.14 on (#241; on 3.14, `-d` still works).
- `export ipynb` writes into the current directory, even with `--dir`.

### 6. Restore: `now restore`

```bash
now restore 1                                  # script, local modules and files as trial 1 first saw them
now restore 1 -s -l                            # files only: skip the script and the local modules
now restore 1 -f data2.dat -t data2-run1.dat   # one file, to another path, without touching anything else
```

**Restore overwrites working files: tell the user before running it.** It
puts each file back as it was at the trial's **first access** to it — so a
file the trial created (first opened for writing) is **deleted**. When the
working files differ from the last trial, it first records a backup trial
(`[b]`, "Backup Trial <id> created") with the current state, and
`now restore <backup>` undoes the restore. The next `now run` becomes a
child of the restored trial, so the history branches. `-f` restores one
file without creating a backup or changing the history; `-i` picks which
access (timestamp, access number or content hash). Without `-i`, `-f`
restores the file as the trial first had it, or, for a file the trial
created, what the trial wrote into it; a version in which the file did not
exist never deletes a `-t` target. A program the trial launched comes back
executable; any other file comes back with the default mode.

Known defects: a binary local module crashes the restore (#183); `--dir`
from another directory writes into the current one (#245).

### 7. History: `now history`

```text
 *    9b9a7469-... simulation.py 1.1.2
 |
 | b  97c19972-... simulation.py 2.0.0
 | |
 | *  fc39aad1-... simulation.py 1.2.1
 |/
 *    6270af8d-... simulation.py 1.1.1
```

`-s SCRIPT` keeps one script (or one `--name`), `-e finished|unfinished|backup`
one status. On a store with no trials it crashes (#253).

### 8. Visualize: `now vis`

```bash
now vis -p 5001        # serves http://localhost:5001 ; port 5000 clashes with a macOS service
now vis -p 5001 -b     # also opens the browser
```

It is a server that runs until stopped: start it in the background, give
the user the URL, and stop it when they are done. It shows the history,
each trial's activation graph, and a comparison of two trials. It has no
authentication, and any page open in the user's browser can reach it, so
never use `--host` to expose it beyond the machine without the user's
explicit decision.

## Secondary commands

```bash
now evaluation -t 2 -l 49 -c total     # evaluations of trial 2 on line 49 whose code is `total`
now evaluation -t 2 --eid 346 wdf      # everything evaluation 346 was derived from
now schema sql                         # the tables of db.sqlite (also `now schema prolog`, `-d` for dot)
now demo 1                             # creates demo_1/ and runs its trials (`now demo -h` lists the demos)
now demo 1 --steps 0:2                 # only creates the files of the first step
now kernel --user                      # installs the "noWorkflow 3" Jupyter kernel spec
now gc                                 # garbage collection of a git content store
now clean -h                           # notebook trials only: a notebook with just the cells a value depends on
now import --source /abs/path/to/other/project
now push --url http://host:5000/experiments/<id>
now pull --url http://host:5000/experiments/<id>
```

- `now evaluation` filters by `-t` (trial), `-l` (line), `-c` (code), `-v`
  (value), `-m` (mode: `w`, `r`, `d`, `p`), `--eid`, `--aid`; each match
  prints as `- <line> <code> (A<activation> E<evaluation>)`. The `E` number
  is the id for `wdf` and for `now export dataflow -w`.
- `now schema` creates an empty `.noworkflow/` in the current directory
  when there is none (#253).
- `now gc` fails with `TypeError` on the default content store (#224).
- The server side of push and pull is `now vis --force true` in an empty
  directory, whose page creates the experiment and its URL. `now pull` into
  an empty directory creates the store; `now restore` then puts a pulled
  trial's files back.
- `now clean` needs a trial recorded by the noWorkflow Jupyter kernel
  (`now kernel`, then the "noWorkflow 3" kernel in Jupyter); on a script
  or a `%%now_run` trial it says the trial is not a notebook trial.

## Jupyter

```python
%load_ext noworkflow
nip = %now_ip                          # the module noworkflow.now.ipython

trial = %now_run simulation.py data1.dat data2.dat   # records and returns a trial (needs `now` on the PATH of the notebook server)
last = nip.Trial()                     # the last trial; nip.Trial(2) by sequence key, tag or id
history = nip.History()
diff = nip.Diff(1, 2)
```

```python
%%now_sql --result rows
SELECT sequence_key, script, status FROM trial
```

- With the `noworkflow_labextension` package, `trial`, `history` and `diff`
  display as graphs in Jupyter Lab and Notebook 7+.
- `%now_run` and `%%now_run` (the cell's code) return the trial they
  recorded; `%%now_run --interactive` runs the cell in the notebook's
  namespace, so it shares its variables. With `--bg`, or when `now` is
  not found, they return `None`: load the trial with `nip.Trial()` once
  the run ends.
- After `%now_run --dir OTHER`, the notebook is connected to OTHER's store
  (`nip.Trial()`, `%now_sql` and the rest read it) until a `%now_run`
  runs elsewhere; a trial kept from another store then raises a
  `RuntimeError` naming its store instead of reading this one.
- `%%now_sql` fails without `--result` (#314); with it, the variable holds
  the rows.
- `src = %now_restore 1` restores trial 1's files and returns its script.
- `%now_schema sql`, `%now_set_default`, `%now_ls_magic` (lists the
  magics), and `%%now_prolog`, which needs `pyswip-alt` and SWI-Prolog with
  shared libraries.

## Research recipes

**Run a parameter sweep and compare.**

```bash
for s in 0.5 1.0 2.0; do now run --message "scale $s" simulation.py data1.dat data2.dat $s; done
now list
now diff 1 3 -f --brief
```

**Find out why a result changed between two runs.** `now diff A B -f
--brief` says which inputs changed content, and `-f --content` how;
`now diff A B -m` which modules and programs;
`now diff A B` whether the command line changed; then `-fa` on the function
that computes the result shows its arguments and output side by side.

**Trace where a value came from.** Find the evaluation (`now evaluation -t 2
-l <line> -c <name>`), then `now evaluation -t 2 --eid <E> wdf`, or draw it:
`now export dataflow 2 -m fineGrain -w <E> | dot -Tpng -o why.png`.

**Get back the data of an earlier run without touching the working copy.**
`now restore 1 -f data2.dat -t data2-run1.dat`.

**Query the store with SQL**, read-only, with the tables of `now schema sql`:

```bash
sqlite3 -readonly .noworkflow/db.sqlite "SELECT sequence_key, status, command FROM trial"
sqlite3 -readonly .noworkflow/db.sqlite "SELECT t.sequence_key, f.name, f.mode, f.content_hash_before, f.content_hash_after
  FROM file_access f JOIN trial t ON t.id = f.trial_id ORDER BY t.sequence_key"
```

Trial ids are UUIDs; join on `trial.id` and filter by `sequence_key`.

**Query with Prolog** (SWI-Prolog):

```bash
now export prolog 2 > trial2.pl
swipl -q -g "consult('trial2.pl'), forall(access(_, _, N, M, _, H, _, _), (write(N-M-H), nl)), halt"
```

## Limitations

- Exit codes and streams: a failure exits with a non-zero status and is
  reported on stderr (a usage error, 2; a missing store or trial, 1; `now
  run`, the script's own status), except `now push` and `now pull`, which
  print their failure on stdout and exit 0 (#256).
- Interrupting a run with Ctrl-C leaves the trial unfinished, without a
  finish time (#251).
- Only Python is traced inside: of a process the script starts, noWorkflow
  records the call boundary (the command line, the exit status in the
  call's value) and the files named on the command line or created in
  the project, never what happens inside the program. A file the process
  modifies without naming it is not seen, a file it rewrites with the same
  content is recorded as a read, and the children of `os.fork` and
  `multiprocessing` are not recorded at all. The program a process runs
  is a module of the trial, with the hash of the executable (and its
  bytes up to `--executable-cap`, 16 MB by default); it has a
  version only when it is an interpreter or a compiler (`Rscript`,
  `python`, `gcc`, `java`...), which noWorkflow runs once with
  `--version`. Through a shell, the programs of the line's commands are
  recorded, not the shell.
- Fine-grained collection slows the script down considerably; `-cg` or
  `-e relevant` reduce the cost.
- Inside `now run`, `open` and `__builtins__` are not the standard ones: the
  collector replaces the `open` functions (#250) and `__builtins__` is a
  dict (#269). A script that inspects them behaves differently.
- Known defects of specific commands are listed with each command above.
