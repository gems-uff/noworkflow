# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The Jupyter kernel that ``now kernel`` installs, started as Jupyter does

``now kernel --prefix`` installs the kernelspec in the project's
directory; ``jupyter_client`` starts it from there, in the project, with
the harness's synthetic environment, and sends it cells; the tests then
read the store the kernel wrote. The kernel is a process, as in a
notebook: one trial named ``Jupyter Kernel`` for the whole session, a
``cell`` code component per cell, saved after each cell.

The kernelspec runs ``<python> -m noworkflow.kernel`` with the
interpreter of the ``now`` that installed it, so under ``NOW_E2E_CMD``
these tests start the kernel of that installation: the ``checks`` job of
``ci.yml`` runs them against the wheel it builds (#341), and the suite
against the checkout.

What made the kernel useless, each covered here: the wheel did not ship
``noworkflow.kernel`` (#341); the kernel died on start, because the
options it reads lacked one that ``now run`` had gained (#315); every
cell failed under ipykernel 7, which passes ``cell_meta`` to the
``run_cell`` the kernel overrides; and no cell recorded the files it
opened, because IPython puts an ``open`` of its own in the user namespace
that shadows the builtin the collector wraps. The last three were found
together, behind #315. The paper's Beyond Python section states the rest:
the processes a cell starts are traced while it runs, and a ``%%bash``
cell is recorded as the text of its block and the launch of its
interpreter. ``now clean`` slices a trial of the kernel, the only kind
of trial with cells.
"""

import contextlib
import json
import os
import shutil
import sys

import nbformat
import pytest

from noworkflow.now.cmd import build_parser
from noworkflow.now.cmd.cmd_kernel import KERNEL_NAME
from noworkflow.now.collection.metadata import Metascript
from noworkflow.tests.e2e.harness import runs_this_interpreter, same_path, tail

# Seconds: a cold start imports IPython, ipykernel and noWorkflow.
STARTUP_TIMEOUT = 120
CELL_TIMEOUT = 60
# The options of `now run` that the kernel sets from its own state
# instead of reading them: the script, its arguments and where the store
# goes, or that only the command line has.
NOT_KERNEL_OPTIONS = {"script", "argv", "name", "dir", "create_last", "func"}


class Kernel:
    """A running kernel and the client that talks to it"""

    def __init__(self, client, log):
        self.client = client
        self.log = log

    def run(self, code):
        """Run a cell: its status and what it printed, errors included"""
        output = []

        def hook(message):
            kind, content = message["msg_type"], message["content"]
            if kind == "stream":
                output.append(content["text"])
            elif kind == "error":
                output.append("\n".join(content["traceback"]))

        reply = self.client.execute_interactive(
            code, timeout=CELL_TIMEOUT, output_hook=hook
        )
        return reply["content"]["status"], "".join(output)

    def describe(self):
        """The kernel's stderr, for an assertion message"""
        return "--- kernel stderr ---\n{}".format(
            tail(self.log.read_text(encoding="utf-8", errors="replace"))
        )


@pytest.fixture
def prefix(project):
    """The prefix where ``now kernel`` installed the kernelspec"""
    prefix = project.root / "prefix"
    result = project.run("kernel", "--prefix", prefix)
    assert result.stdout == "Installed kernelspec {}\n".format(KERNEL_NAME), result
    return prefix


@contextlib.contextmanager
def running_kernel(project, prefix):
    """Start the installed kernel in the project, as Jupyter starts it"""
    from jupyter_client.kernelspec import KernelSpecManager
    from jupyter_client.manager import KernelManager

    specs = KernelSpecManager(
        kernel_dirs=[str(prefix / "share" / "jupyter" / "kernels")]
    )
    manager = KernelManager(
        kernel_name=KERNEL_NAME,
        kernel_spec_manager=specs,
        connection_file=str(project.tmp / "connection.json"),
    )
    log = project.tmp / "kernel.log"
    with open(log, "wb") as stderr:
        manager.start_kernel(
            cwd=str(project.path),
            env=dict(project.env),
            stdout=stderr,
            stderr=stderr,
        )
        client = manager.client()
        client.start_channels()
        kernel = Kernel(client, log)
        try:
            try:
                client.wait_for_ready(timeout=STARTUP_TIMEOUT)
            except RuntimeError as error:
                pytest.fail("{}\n{}".format(error, kernel.describe()))
            yield kernel
        finally:
            client.stop_channels()
            manager.shutdown_kernel()


def ran(kernel, code, expected_output):
    """Run a cell that must succeed and print ``expected_output``"""
    status, output = kernel.run(code)
    assert (status, output) == ("ok", expected_output), "{}\n{}".format(
        output, kernel.describe()
    )


def the_trial(project):
    """The one trial of the kernel's session"""
    trials = project.trials()
    assert len(trials) == 1, [trial["script"] for trial in trials]
    return trials[0]


def cells(project, trial_id):
    """The code each cell recorded, in the order the cells ran"""
    rows = project.query(
        "SELECT b.code_hash FROM code_component c JOIN code_block b "
        "ON b.trial_id = c.trial_id AND b.id = c.id "
        "WHERE c.trial_id = ? AND c.type = 'cell' ORDER BY c.id",
        trial_id,
    )
    return [project.content(row["code_hash"]).decode("utf-8") for row in rows]


def accesses(project, trial_id, activation):
    """``(name, mode)`` of the files an activation named ``activation``
    opened, in order"""
    return [
        (row["name"], row["mode"])
        for row in project.query(
            "SELECT f.name, f.mode FROM file_access f JOIN activation a "
            "ON a.trial_id = f.trial_id AND a.id = f.activation_id "
            "WHERE f.trial_id = ? AND a.name = ? ORDER BY f.id",
            trial_id,
            activation,
        )
    ]


def test_the_kernel_reads_every_option_of_now_run(monkeypatch, tmp_path):
    """The kernel collects with the defaults of ``now run``: it gives a
    value to every option that ``now run`` reads, the same value

    Without this, an option added to ``now run`` and read by the
    metascript kills the kernel as it starts (#315: ``coarse_granularity``).
    """
    read = []
    monkeypatch.setattr(
        Metascript, "_read_args", lambda self, args: read.append(args) or self
    )
    Metascript().read_jupyter_args()
    (kernel,) = read
    script = tmp_path / "script.py"
    script.write_text("")
    run = build_parser().parse_args(["run", str(script)])
    expected = {
        option: value
        for option, value in vars(run).items()
        if option not in NOT_KERNEL_OPTIONS
    }
    assert vars(kernel) == expected


def test_now_kernel_installs_a_spec_that_runs_the_kernel(project, prefix):
    """``now kernel --prefix`` installs a kernelspec that runs
    ``noworkflow.kernel`` with the interpreter of that ``now``: this one,
    or under ``NOW_E2E_CMD`` the one next to the installed ``now``"""
    spec = prefix / "share" / "jupyter" / "kernels" / KERNEL_NAME / "kernel.json"
    argv = json.loads(spec.read_text(encoding="utf-8"))["argv"]
    assert argv[1:] == ["-m", "noworkflow.kernel", "-f", "{connection_file}"]
    if runs_this_interpreter(project.command):
        assert same_path(argv[0], sys.executable)
    else:
        assert same_path(os.path.dirname(argv[0]), os.path.dirname(project.command[0]))


# Two cells: the second calls the function the first defines and reads
# the file it writes.
DEFINE = (
    "def double(text):\n"
    "    return text * 2\n"
    "\n"
    "with open('data.txt', 'w') as handle:\n"
    "    handle.write('ab')\n"
)
USE = "with open('data.txt') as handle:\n    print(double(handle.read()))\n"


def test_the_kernel_records_each_cell(project, prefix):
    """The kernel starts, runs each cell as plain IPython would, and
    records the session as one finished trial: each cell's code, the
    calls of a function one cell defines and another calls, and the
    files the cells write and read"""
    define, use = DEFINE, USE
    with running_kernel(project, prefix) as kernel:
        ran(kernel, define, "")
        ran(kernel, use, "abab\n")
    trial = the_trial(project)
    assert trial["script"] == "Jupyter Kernel"
    assert trial["status"] == "finished"
    assert cells(project, trial["id"]) == [define, use]
    assert project.query(
        "SELECT COUNT(*) AS n FROM activation WHERE trial_id = ? AND name = 'double'",
        trial["id"],
    ) == [{"n": 1}]
    assert accesses(project, trial["id"], "open") == [
        ("data.txt", "w"),
        ("data.txt", "r"),
    ]


def test_a_cell_records_the_processes_it_starts(project, prefix):
    """A process a cell starts is recorded as a launch while the cell
    runs: the file it creates is an access of the call that started it,
    and the program it runs is a module row"""
    cell = (
        "import subprocess, sys\n"
        "subprocess.run([sys.executable, '-c', "
        "\"open('child_out.txt', 'w').write('child')\"], check=True)\n"
        "print(open('child_out.txt').read())\n"
    )
    with running_kernel(project, prefix) as kernel:
        ran(kernel, cell, "child\n")
    trial = the_trial(project)
    assert accesses(project, trial["id"], "run") == [("child_out.txt", "w")]
    programs = project.query(
        "SELECT version FROM module WHERE trial_id = ? AND version LIKE 'Python %'",
        trial["id"],
    )
    assert len(programs) == 1, programs


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("bash") is None,
    reason="needs bash; on Windows the bash of System32 is WSL's launcher",
)
def test_a_bash_cell_is_recorded_as_a_launch_of_bash(project, prefix):
    """A ``%%bash`` cell is recorded as the text of its block, in the form
    IPython runs it, and as the launch of ``bash``, with the file the
    script writes and the version ``bash`` prints"""
    with running_kernel(project, prefix) as kernel:
        ran(kernel, "%%bash\necho hi > bash_out.txt\n", "")
    trial = the_trial(project)
    assert cells(project, trial["id"]) == [
        "get_ipython().run_cell_magic('bash', '', 'echo hi > bash_out.txt\\n')\n"
    ]
    assert accesses(project, trial["id"], "run_cell_magic") == [("bash_out.txt", "w")]
    versions = project.query(
        "SELECT version FROM module WHERE trial_id = ? AND name = 'bash'",
        trial["id"],
    )
    assert len(versions) == 1 and versions[0]["version"], versions


def test_now_clean_slices_a_trial_of_the_kernel(project, prefix):
    """``now clean`` on a trial of the kernel writes the notebook of the
    cells a cell depends on: the last cell needs the function of the
    first, and nothing of the one between them, so its slice holds the
    first and the last, in order"""
    with running_kernel(project, prefix) as kernel:
        ran(kernel, DEFINE, "")
        ran(kernel, "unrelated = 1\n", "")
        ran(kernel, USE, "abab\n")
    trial = the_trial(project)
    result = project.run("clean", trial["id"], "-n", "3", "-o", "clean.ipynb")
    assert result.stdout == "Created clean notebook: clean.ipynb\n", result
    notebook = nbformat.read(str(project.path / "clean.ipynb"), as_version=4)
    assert [(cell.cell_type, cell.source) for cell in notebook.cells] == [
        ("code", DEFINE.rstrip("\n")),
        ("code", USE.rstrip("\n")),
    ]
