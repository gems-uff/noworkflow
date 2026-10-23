# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""What a store records about the processes a traced script starts

Each script of ``corpus/processes`` starts a child one way:
``subprocess.run`` with an argument list, ``check_output``, ``Popen`` and
``communicate``, ``run`` with ``shell=True``, ``os.system``, ``os.popen``,
``os.posix_spawn`` waited for with ``os.waitpid`` (POSIX only), and a
``multiprocessing`` process of the fork start method (POSIX only). The
child (``child.py``, or the script's ``work`` for the fork) reads
``child_in.txt`` and writes ``child_out.txt``; the parent reads
``parent_in.txt``, the positive control of the file accesses.
``control.py`` has the same imports and starts nothing. Each script runs
once per module (``now`` as a process, in a store of its own), and the
tests read that store through the models under ``connected_to``,
cross-check a few facts with SQL on its ``db.sqlite`` and check that it
did not change. Every wait is bounded: the calls that take a timeout get
one, the join of the fork and the polls of os.fork() children have a
deadline, and ``child.py`` ends itself after a minute, for the waits that
take none; a child that a change breaks fails the test instead of hanging
it.

A call that starts a process is recorded like any call the collector
does not trace: an activation without a code block, without evaluations,
whose arguments are evaluations of its caller and whose value is a repr.
Since #202 (processes captured through the audit hooks of PEP 578 and a
patch of ``subprocess.Popen``, ``prov_execution/external.py``) the call
that starts the process also carries, as its file accesses, the files the
child's command line names, read with the same hash before and after,
and the files the child creates, written with no content before: here
the child's script, its input and its output. A forked child
(``multiprocessing``) is not a launch and records nothing (#375, #379).
Since #203 the module table holds, besides what a script with the same
imports and no call holds, one row for the program the process runs:
the interpreter, under the name the command line gives it, with its real
path, the hash of its bytes and the version it prints; a fork adds no
such row. Two scripts go
further: ``execv.py`` replaces its own process through ``os.execv``, and
its trial is lost; ``fork_exit.py`` forks children with ``os.fork()``
that leave through ``sys.exit``, and each one stores the trial as well.

Structural assertions only, no goldens: paths, hashes, addresses, pids
and evaluation ids differ per platform and version. The executable's path
(often under the home directory), the module paths and the reprs and
facts that embed them are compared through booleans and counts with fixed
messages, never printed.

Known defects have a characterization of today's behavior and a
``_desired`` twin marked through ``known_defects``, named after the
scenario. They were measured on macOS with Python 3.11 to 3.15 and on
Linux with 3.15 (the reference container); the other Linux versions are
the CI legs.
"""

import ast
import contextlib
import dataclasses
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

import pytest

from noworkflow.now.collection.prov_execution.external import executable_content
from noworkflow.now.persistence.models import Trial
from noworkflow.tests.e2e.harness import (
    NowProject,
    runs_this_interpreter,
    same_path,
    sha1,
)
from noworkflow.tests.e2e.oracle import differences, plain_python, run_both
from noworkflow.tests.helpers.defects import Defect, known_defects
from noworkflow.tests.helpers.persistence import connected_to

POSIX_FORK = pytest.mark.skipif(
    sys.platform == "win32", reason="the fork start method does not exist on Windows"
)
POSIX_SPAWN = pytest.mark.skipif(
    not hasattr(os, "posix_spawn"), reason="os.posix_spawn exists only on POSIX systems"
)
OS_FORK = pytest.mark.skipif(
    not hasattr(os, "fork"), reason="os.fork exists only on POSIX systems"
)
POSIX_EXEC = pytest.mark.skipif(
    os.name == "nt",
    reason="on Windows os.execv starts a new process and ends the caller "
    "instead of replacing its image; not measured there",
)
# What the child of every script writes from what it reads.
CHILD_INPUT = b"child input\n"
CHILD_OUTPUT = b"child:child input\n"
# The words after the executable in the command of the child.
CHILD_WORDS = ["child.py", "child_out.txt", "child_in.txt"]
# The fork's child: the target and its arguments.
FORK_ARGUMENTS = ("child_out.txt", "child_in.txt")

RAISING_CALL_DEPS = Defect(
    "#378: when the evaluation of a call raises, whether "
    "the callee is untraced or a function of the script, Collector._call "
    "(collector.py) calls Collector.collect_exception with no handler, "
    "whose loop pops every DependencyAware of the activation, the one "
    "that holds the func and argument dependencies included; the finally "
    "of _call then skips make_dependencies and "
    "create_argument_dependencies, so the call's evaluation is the "
    "dependent of no row (the bindings of a script function's parameters, "
    "made inside its activation, survive). Separately, since result stays "
    "None in _call, close_activation stores get_value(None), the string "
    "'None', as the call's value (ToDo #77 in "
    "Execution.collect_provenance, execution.py)",
    signature="dependencies {}",
)
FORK_BLOBS = Defect(
    "#379: the open wrappers that Execution.configure "
    "(execution.py) installs survive into a child of os.fork; in the "
    "child, Collector.new_open and Collector.close_activation "
    "(collector.py) put the content of each regular file it opens, and "
    "FileAccessProxy._capture_after puts what it writes; the content "
    "engine writes each blob at once (plain into .noworkflow/content, "
    "puregit as loose objects), while the FileAccess objects that would "
    "name them die with the child at os._exit",
    signature="content blobs that no row references",
)
PREIMPORTED_MODULES = Defect(
    "#380: the finder of prov_deployment/py3module.py, "
    "which Execution.collect_provenance (execution.py) puts in "
    "sys.meta_path around the exec of the script, only sees a module "
    "imported for the first time in the process; one that noWorkflow "
    "itself imported before the script is already in sys.modules and is "
    "never recorded (now/cmd/__init__.py imports SQLAlchemy and every "
    "command: json arrives through SQLAlchemy and cmd_push.py, subprocess "
    "through now/utils/functions.py and cmd_demo.py)",
    signature="no module row for ['json', 'subprocess']",
)
EXEC_LOSES_TRIAL = Defect(
    "#377: run (cmd/cmd_run.py) stores the trial, "
    "'ongoing', and its arguments before Execution.collect_provenance "
    "(prov_execution/execution.py) execs the script, and everything else "
    "after the exec returns: the store_provenance of the deployment, the "
    "definition and the execution (modules, code, evaluations, and "
    "Trial.fast_update with the status, finish and main_id), "
    "Tag.create_automatic_tag, content.commit_content and, in the "
    "finally, Metascript.create_last (.last_trial under --create_last); "
    "os.execv replaces the process image inside the exec, so none of them "
    "runs, and the blobs the definition put stay unreferenced. CPython "
    "raises the os.exec audit event before it replaces the image, where "
    "the trial could be stored (os._exit raises none: test_run.py pins "
    "that case with no twin)",
    signature="status 'ongoing', nothing stored in ['code_component', "
    "'evaluation', 'module', 'tag'], .last_trial written: False",
)
FORK_EPILOGUE = Defect(
    "#375: a child that os.fork() makes in the traced script "
    "leaves the exec of the script in Execution.collect_provenance "
    "(prov_execution/execution.py) through SystemExit, as the parent "
    "would, and runs the rest of run (cmd/cmd_run.py): it stores its own "
    "version of the trial, and Tag.create_automatic_tag adds one more AUTO "
    "tag (Tag.fast_load_auto_tag, persistence/models/tag.py, ignores the "
    "tags of the same trial); the parent stores last, and the INSERT OR "
    "REPLACE of Model.store (persistence/models/base.py) replaces only the "
    "rows whose keys it reaches, so the activations of a child's branch "
    "stay in the trial, over evaluations of the parent with the same ids. "
    "Every child that does not leave through os._exit runs this epilogue",
    signature="3 automatic tags, activations of the children: ['exit', 'exit']",
)


@dataclasses.dataclass(frozen=True)
class Call:
    """A call of a corpus script into something the collector does not
    trace, or into a function of the script

    ``name`` is the activation's (``func.__name__``), ``source`` how the
    call's source text starts (it tells apart ``pipe.read()`` from
    ``source.read()``), ``arguments`` the code component types of its
    argument evaluations, sorted, ``assigned`` the name its value is
    assigned to, and ``value`` whether the repr stored as its value has
    the expected shape.
    """

    name: str
    source: str
    arguments: tuple
    assigned: str
    value: object

    @property
    def func(self):
        """The source text of the callee: the call's, up to ``(``"""
        return self.source[:-1]


def literal(text):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def matches(pattern):
    return lambda text: re.fullmatch(pattern, text) is not None


def child_done(text):
    """A repr of the child's stdout, ``b'child-done\\n'`` or ``\\r\\n``"""
    value = literal(text)
    return isinstance(value, (bytes, str)) and value.strip() in (
        b"child-done",
        "child-done",
    )


def communicated(text):
    value = literal(text)
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and child_done(repr(value[0]))
        and value[1] is None
    )


def waited(text):
    """The repr of what ``os.waitpid`` returns for a child that exited
    with 0: its pid and the status 0"""
    value = literal(text)
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], int)
        and value[0] > 0
        and value[1] == 0
    )


@dataclasses.dataclass(frozen=True)
class Kind:
    """One way of starting a process: its script, its calls and, among
    them, the call that starts the process (``launch``), which carries
    the child's file accesses since #202; None for the fork, which
    records nothing of its child"""

    script: str
    calls: tuple
    launch: str = None


KINDS = {
    "run": Kind(
        "run.py",
        (
            Call(
                "run",
                "subprocess.run(",
                ("list", "literal", "literal", "literal"),
                "result",
                lambda text: (
                    text.startswith("CompletedProcess(args=[")
                    and text.endswith(
                        ", returncode=0, stdout='child-done\\n', stderr='')"
                    )
                ),
            ),
        ),
        launch="run",
    ),
    "check_output": Kind(
        "check_output.py",
        (
            Call(
                "check_output",
                "subprocess.check_output(",
                ("list", "literal"),
                "output",
                child_done,
            ),
        ),
        launch="check_output",
    ),
    "popen": Kind(
        "popen.py",
        (
            # The repr is taken when Popen returns, before any wait, and
            # Popen.__repr__ cuts it at 80 characters.
            Call(
                "Popen",
                "subprocess.Popen(",
                ("attribute", "list"),
                "process",
                lambda text: (
                    text.startswith("<Popen: returncode: None args: [")
                    and len(text) <= 80
                ),
            ),
            # A tuple unpacked into out and err: no "assign" dependency.
            Call(
                "communicate", "process.communicate(", ("literal",), None, communicated
            ),
        ),
        launch="Popen",
    ),
    "shell": Kind(
        "shell.py",
        (
            Call(
                "run",
                "subprocess.run(",
                ("literal", "literal", "name"),
                "result",
                lambda text: (
                    text.startswith("CompletedProcess(args=")
                    and text.endswith(", returncode=0)")
                ),
            ),
        ),
        launch="run",
    ),
    "system": Kind(
        "system.py",
        (Call("system", "os.system(", ("name",), "status", lambda text: text == "0"),),
        launch="system",
    ),
    "os_popen": Kind(
        "os_popen.py",
        (
            Call(
                "popen",
                "os.popen(",
                ("name",),
                "pipe",
                matches(r"<os\._wrap_close object at 0x[0-9a-fA-F]+>"),
            ),
            Call("read", "pipe.read(", (), "output", child_done),
            Call("close", "pipe.close(", (), "status", lambda text: text == "None"),
        ),
        launch="popen",
    ),
    "posix_spawn": Kind(
        "posix_spawn.py",
        (
            # sys.executable, the argument list and os.environ.
            Call(
                "posix_spawn",
                "os.posix_spawn(",
                ("attribute", "attribute", "list"),
                "pid",
                matches(r"[1-9][0-9]*"),
            ),
            # A tuple unpacked into waited and status: no "assign" dependency.
            Call("waitpid", "os.waitpid(", ("literal", "name"), None, waited),
            Call(
                "waitstatus_to_exitcode",
                "os.waitstatus_to_exitcode(",
                ("name",),
                None,
                lambda text: text == "0",
            ),
        ),
        launch="posix_spawn",
    ),
    "fork": Kind(
        "fork.py",
        (
            Call(
                "get_context",
                "multiprocessing.get_context(",
                ("literal",),
                "context",
                matches(
                    r"<multiprocessing\.context\.ForkContext object at "
                    r"0x[0-9a-fA-F]+>"
                ),
            ),
            # The class of a fork context's Process is ForkProcess.
            Call(
                "ForkProcess",
                "context.Process(",
                ("name", "tuple"),
                "process",
                matches(r"<ForkProcess name='ForkProcess-\d+' parent=\d+ initial>"),
            ),
            Call("start", "process.start(", (), None, lambda text: text == "None"),
            Call(
                "join", "process.join(", ("literal",), None, lambda text: text == "None"
            ),
        ),
    ),
}
# What the launch exchanges with the child, as the store records it: the
# child's script and its input, read, with the same hash before and
# after; its output, written, with no content before.
CHILD_FILES = ("child.py", "child_in.txt", "child_out.txt")
# The kinds whose child is a new interpreter, not a fork of the parent.
NEW_INTERPRETER_KINDS = [
    "run",
    "check_output",
    "popen",
    "shell",
    "system",
    "os_popen",
    pytest.param("posix_spawn", marks=POSIX_SPAWN),
]
ALL_KINDS = NEW_INTERPRETER_KINDS + [pytest.param("fork", marks=POSIX_FORK)]


def run_now(project, *args):
    """``now <args>``, which must succeed, with the output normalized in
    the message: a traceback holds paths of the checkout, of the
    interpreter and of the temporary directory, which may hold the login"""
    result = project.run(*args, expect=None, allow_stderr=True)
    succeeded = result.returncode == 0 and result.stderr == ""
    assert succeeded, project.normalize(str(result))
    return result


def shown(project, outcome):
    """An outcome of ``oracle.run_both`` as an assertion may show it"""
    return project.normalize(str(outcome))


def build_store(factory, script):
    """``corpus/processes`` after ``now run <script>``, in a root of its own

    The run must end normally with nothing on stderr, store one finished
    trial with one automatic tag, and leave the child's output on disk:
    the child ran.
    """
    project = NowProject(factory.mktemp(script.replace(".", "_")))
    project.copy_corpus("processes")
    run_now(project, "run", script)
    trials = project.trials()
    assert [trial["status"] for trial in trials] == ["finished"]
    assert project.tags(trials[0]["id"]) == [{"type": "AUTO", "name": "1.1.1"}]
    return project


@pytest.fixture(scope="module")
def stores(tmp_path_factory):
    """``stores(script)``: the store of ``script``, built once per module

    Read-only: ``reading`` checks that a test leaves it as it was.
    """
    built = {}

    def get(script):
        if script not in built:
            built[script] = build_store(tmp_path_factory, script)
        return built[script]

    return get


@contextlib.contextmanager
def reading(project):
    """The only trial of ``project``, with this process connected to its
    store; the store must be unchanged afterwards"""
    before = project.fingerprint()
    trial_id = project.trials()[0]["id"]
    with connected_to(project.path):
        yield Trial(trial_id)
    assert project.fingerprint() == before, (
        "the test changed the shared store of {}".format(project.root.name)
    )


def call_activation(trial, call):
    """The one activation of ``call`` in ``trial``"""
    found = [
        activation
        for activation in trial.activations
        if activation.name == call.name
        and activation.this_evaluation.code_component.name.startswith(call.source)
    ]
    # A count: pytest would show the list, whose items are Prolog facts.
    count = len(found)
    assert count == 1, "{} activations of {!r}".format(count, call.source)
    return found[0]


def script_activation(trial):
    """The activation of the script itself: ``__main__``, whose code block
    is the trial's main block"""
    found = [
        activation
        for activation in trial.activations
        if activation.name == "__main__" and activation.code_block_id == trial.main_id
    ]
    count = len(found)
    assert count == 1, "{} activations of the script".format(count)
    return found[0]


def dependency_types(evaluation):
    return Counter(
        dependency.type for dependency in evaluation.dependencies_as_dependent
    )


def executables(project, trial_id):
    """The paths a module row must not name: each ``sys.executable`` the
    script evaluated, and the interpreter that ``now`` runs on"""
    paths = {
        literal(row["repr"])
        for row in project.query(
            "SELECT evaluation.repr FROM evaluation JOIN code_component "
            "ON code_component.trial_id = evaluation.trial_id "
            "AND code_component.id = evaluation.code_component_id "
            "WHERE evaluation.trial_id = ? "
            "AND code_component.name = 'sys.executable'",
            trial_id,
        )
    }
    paths.add(plain_python(tuple(project.command)))
    paths.discard(None)
    return paths


def names_the_child(project, modules):
    """Whether a module row names the child's script"""
    return any(
        same_path(module.path, project.path / "child.py") or "child" in module.name
        for module in modules
    )


def masked(project, name):
    """A file name as an assertion may show it: an absolute path names the
    temporary directory, which can hold the login"""
    return project.normalize(name).strip()


def content_blobs(project):
    """The hashes of the blobs of the plain content engine, which keeps
    each blob in a file named after its SHA-1; None for another engine"""
    content = project.store / "content"
    if not content.is_dir():
        return None
    return {
        path.parent.name + path.name for path in content.glob("*/*") if path.is_file()
    }


def unreferenced_blobs(project):
    """The hashes of the content blobs that no row of the store names

    Skips unless the store uses the plain content engine.
    """
    stored = content_blobs(project)
    if stored is None:
        pytest.skip("the store does not use the plain content engine")
    referenced = {
        row["hash"]
        for row in project.query(
            "SELECT code_hash AS hash FROM code_block "
            "UNION SELECT content_hash_before FROM file_access "
            "UNION SELECT content_hash_after FROM file_access "
            "UNION SELECT content_hash FROM graph_cache"
        )
    }
    return stored - referenced


# --- the call ----------------------------------------------------------------


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_process_call_is_an_opaque_activation(stores, kind):
    """Each call that starts or drives the process is an activation of the
    trial, called by the script, with no code block (the collector's -1 is
    stored as NULL) and no evaluations of its own; the call that starts
    the process carries the child's three file accesses (#202), the
    others none

    The fork records nothing of its child: none of its calls has a file
    access.
    """
    project = stores(KINDS[kind].script)
    with reading(project) as trial:
        script = script_activation(trial)
        for call in KINDS[kind].calls:
            activation = call_activation(trial, call)
            # Booleans and counts: a model's repr is its Prolog fact, which
            # can hold the executable's path, and pytest shows the repr of
            # each model whose attribute an assertion compares.
            in_trial = activation.trial_id == trial.id
            assert in_trial, "{}: an activation of another trial".format(call.source)
            no_block_id = activation.code_block_id is None
            assert no_block_id, "{}: a code block id".format(call.source)
            no_block = activation.code_block is None
            assert no_block, "{}: a code block".format(call.source)
            evaluations = len(list(activation.evaluations))
            assert evaluations == 0, "{}: {} evaluations".format(
                call.source, evaluations
            )
            accesses = len(list(activation.file_accesses))
            expected = len(CHILD_FILES) if call.name == KINDS[kind].launch else 0
            assert accesses == expected, "{}: {} file accesses".format(
                call.source, accesses
            )
            by_script = activation.caller.id == script.id
            assert by_script, "{}: not called by the script".format(call.source)
            evaluation = activation.this_evaluation
            is_call = evaluation.code_component.type == "call"
            assert is_call, "{}: not evaluated by a call".format(call.source)
            in_script = evaluation.activation_id == script.id
            assert in_script, "{}: evaluated outside the script".format(call.source)
            null = project.query(
                "SELECT typeof(code_block_id) AS type FROM activation "
                "WHERE trial_id = ? AND id = ?",
                trial.id,
                activation.id,
            )
            assert null == [{"type": "null"}], call.source


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_process_call_arguments_are_evaluations_of_the_caller(stores, kind):
    """The callee and each argument are evaluations of the script, linked
    to the call once by ``func``, and each argument twice, by
    ``argument`` and by ``dependency``; keyword names are not stored. The
    argument list holds the executable and the child's words, the fork's
    tuple the target's arguments

    #202 left the arguments of these calls as they were: this pins them.
    """
    project = stores(KINDS[kind].script)
    with reading(project) as trial:
        script = script_activation(trial)
        for call in KINDS[kind].calls:
            evaluation = call_activation(trial, call).this_evaluation
            count = len(call.arguments)
            expected = {"func": 1}
            if count:
                expected.update(argument=count, dependency=count)
            # A local: pytest would show the evaluation passed to the call.
            types = dependency_types(evaluation)
            assert types == expected, call.source
            sql = project.query(
                "SELECT type, COUNT(*) AS n FROM dependency "
                "WHERE trial_id = ? AND dependent_id = ? GROUP BY type",
                trial.id,
                evaluation.id,
            )
            assert {row["type"]: row["n"] for row in sql} == expected

            links = defaultdict(list)
            for dependency in evaluation.dependencies_as_dependent:
                links[dependency.type].append(dependency.dependency)
            (func,) = links["func"]
            # Booleans: the callee and the arguments are evaluations.
            attribute = (
                func.code_component.type == "attribute"
                and func.code_component.name == call.func
            )
            assert attribute, "{}: the callee is not {!r}".format(
                call.source, call.func
            )
            arguments = links["argument"]
            assert sorted(
                argument.code_component.type for argument in arguments
            ) == list(call.arguments)
            assert sorted(argument.id for argument in arguments) == sorted(
                dependency.id for dependency in links["dependency"]
            )
            in_script = [argument.activation_id for argument in arguments] == [
                script.id
            ] * count
            assert in_script, "{}: an argument evaluated outside the script".format(
                call.source
            )
            for argument in arguments:
                value = literal(argument.repr)
                if argument.code_component.type == "list":
                    words = isinstance(value, list) and value[1:]
                    assert words == CHILD_WORDS, call.source
                    if runs_this_interpreter():
                        same = same_path(value[0], sys.executable)
                        assert same, "the list does not start with the executable"
                elif argument.code_component.type == "tuple":
                    assert value == FORK_ARGUMENTS


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_process_call_value_is_the_repr_of_its_result(stores, kind):
    """The value of each call is the repr of what it returned, taken when
    it returned: the CompletedProcess, the child's stdout, a Popen still
    without a return code, the exit status, the pipe object, the pid and
    what waitpid returned, the process object before start; it flows to
    the name it is assigned to

    #202 left the values of these calls as they were (the patch of Popen
    replaces its functions, not the objects): this pins them.
    """
    project = stores(KINDS[kind].script)
    with reading(project) as trial:
        for call in KINDS[kind].calls:
            evaluation = call_activation(trial, call).this_evaluation
            # Booleans: the reprs can hold the executable's path.
            shaped = evaluation.repr is not None and call.value(evaluation.repr)
            assert shaped, "the value of {!r} has another shape".format(call.source)
            assigned = [
                dependency.dependent.code_component.name
                for dependency in evaluation.dependencies_as_dependency
                if dependency.type == "assign"
            ]
            assert assigned == ([call.assigned] if call.assigned else []), call.source


# --- the files ---------------------------------------------------------------


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_child_file_accesses_are_recorded_with_the_launch(stores, kind):
    """The parent's read of ``parent_in.txt``, by the script's ``open``,
    with the SHA-1 of its content before and after, is apart from the
    launch; the launch carries the child's files, named as its command
    line names them: ``child.py`` and ``child_in.txt`` read, with the
    same hash before and after, and ``child_out.txt`` written, with no
    content before and the child's output after (#202). The child of the
    fork, which is not a launch, leaves no row: its files are out of
    scope (#375, #379).
    """
    project = stores(KINDS[kind].script)
    assert (project.path / "child_out.txt").read_bytes() == CHILD_OUTPUT
    parent_input = sha1((project.path / "parent_in.txt").read_bytes())
    launch = KINDS[kind].launch
    with reading(project) as trial:
        trial_id = trial.id
        script = script_activation(trial)
        accesses = {
            masked(project, access.name): access for access in trial.file_accesses
        }
        expected = ["parent_in.txt"] + (list(CHILD_FILES) if launch else [])
        assert sorted(accesses) == sorted(expected)
        access = accesses["parent_in.txt"]
        # Booleans: a file access's repr is its Prolog fact, which holds
        # the absolute name of the file.
        read = access.mode == "r"
        assert read, "the access is not a read"
        by_open = (
            access.activation.name == "open"
            and access.activation.caller.id == script.id
        )
        assert by_open, "the access is not made by an open of the script"
        hashed = (
            access.content_hash_before == parent_input
            and access.content_hash_after == parent_input
        )
        assert hashed, "the hashes are not those of parent_in.txt"
        calls = {call_activation(trial, call).id for call in KINDS[kind].calls}
        apart = access.activation_id not in calls
        assert apart, "the access belongs to a call that starts a process"
        if launch:
            launcher = call_activation(
                trial, next(call for call in KINDS[kind].calls if call.name == launch)
            )
            for name in CHILD_FILES:
                by_launch = accesses[name].activation_id == launcher.id
                assert by_launch, "{} is not an access of the launch".format(name)
            hashes = {
                name: (
                    accesses[name].mode,
                    accesses[name].content_hash_before,
                    accesses[name].content_hash_after,
                )
                for name in CHILD_FILES
            }
            child = sha1((project.path / "child.py").read_bytes())
            assert hashes == {
                "child.py": ("r", child, child),
                "child_in.txt": ("r", sha1(CHILD_INPUT), sha1(CHILD_INPUT)),
                "child_out.txt": ("w", None, sha1(CHILD_OUTPUT)),
            }
    rows = project.query(
        "SELECT name, mode FROM file_access WHERE trial_id = ? ORDER BY id",
        trial_id,
    )
    assert [(masked(project, row["name"]), row["mode"]) for row in rows] == [
        ("parent_in.txt", "r")
    ] + (
        [("child.py", "r"), ("child_in.txt", "r"), ("child_out.txt", "w")]
        if launch
        else []
    )


# --- the modules -------------------------------------------------------------


@pytest.mark.parametrize("kind", NEW_INTERPRETER_KINDS)
def test_process_call_adds_the_interpreter_as_a_module(stores, kind):
    """A script that starts a process records the modules of the control,
    which has the same imports and starts nothing, plus one row for the
    program the process runs (#203): the interpreter that the script's
    ``sys.executable`` names, under the name the command line gives it,
    with its real path, the version it prints and, as code, its bytes or,
    above ``EXECUTABLE_CAP`` (the interpreters of uv are larger on some
    systems), the placeholder with their SHA-1; no row names the child's
    script. Through a shell (``shell``, ``system``, ``os_popen``) the row
    is the program of the command, not the shell."""
    with reading(stores("control.py")) as control:
        expected = sorted(module.name for module in control.modules)
    project = stores(KINDS[kind].script)
    with reading(project) as trial:
        modules = list(trial.modules)
        paths = executables(project, trial.id)
        assert paths, "the script evaluated no sys.executable"
        programs = [
            module
            for module in modules
            if any(same_path(module.path, path) for path in paths)
        ]
        assert len(programs) == 1, "{} module rows name the executable".format(
            len(programs)
        )
        (program,) = programs
        others = sorted(module.name for module in modules if module is not program)
        assert others == expected
        names = {os.path.basename(path) for path in paths}
        assert program.name in names, "the row is named {!r}".format(program.name)
        assert (program.version or "").startswith("Python "), program.version
        # A boolean: pytest would show the modules passed to the call,
        # whose Prolog facts hold their paths.
        child = names_the_child(project, modules)
        assert not child, "a module row names the child"
        real = os.path.realpath(program.path)
    (row,) = project.query(
        "SELECT b.code_hash FROM module m JOIN code_block b "
        "ON b.trial_id = m.trial_id AND b.id = m.code_block_id "
        "WHERE m.trial_id = ? AND m.name = ?",
        trial.id,
        program.name,
    )
    code = executable_content(real)
    assert row["code_hash"] == sha1(code)
    stored = project.content(row["code_hash"]) == code
    assert stored, "the content store does not hold the code of the executable"


# What multiprocessing.spawn imports, which `python -m noworkflow` has
# already imported before the script and the `now` console script has not.
SPAWN_IMPORTS = {"runpy"}
# The C modules that the sources of multiprocessing import on POSIX
# (Lib/multiprocessing, 3.11 to 3.15). The fork's join with a timeout
# loads _multiprocessing through multiprocessing.connection, and where
# popen_fork imports the resource tracker (gh-146313) the start loads
# _posixshmem. python-build-standalone, the interpreters of uv and of the
# CI legs, builds them into the interpreter, and a built-in module gets
# no row; python.org, Homebrew, distribution and pyenv builds ship them as
# files in lib-dynload, which get one (measured: a pyenv 3.12.0 records
# _multiprocessing).
MULTIPROCESSING_C = {"_multiprocessing", "_posixshmem", "_posixsubprocess"}


@POSIX_FORK
def test_fork_adds_only_multiprocessing_modules(stores):
    """Beyond the control's modules, a fork records only modules of the
    implementation of multiprocessing that ``start`` and ``join`` import
    on demand, ``multiprocessing.popen_fork`` among them: submodules of
    multiprocessing, the C modules it loads and what multiprocessing.spawn
    imports; no row names the executable or a child's script

    The set depends on the version (``resource_tracker`` and ``spawn``
    where popen_fork imports the resource tracker), on the build of the
    interpreter (the C modules) and on how ``now`` starts (``runpy`` under
    the console script), so only what it is made of is pinned.
    A fork is not a launch: the program it runs is the interpreter
    already running, and #203 adds no row for it.
    """
    with reading(stores("control.py")) as control:
        expected = {module.name for module in control.modules}
    project = stores("fork.py")
    with reading(project) as trial:
        modules = list(trial.modules)
        added = {module.name for module in modules} - expected
        assert "multiprocessing.popen_fork" in added
        foreign = sorted(
            name
            for name in added - SPAWN_IMPORTS - MULTIPROCESSING_C
            if not name.startswith("multiprocessing.")
        )
        assert foreign == []
        paths = executables(project, trial.id)
        named = any(
            same_path(module.path, path) for module in modules for path in paths
        )
        assert not named, "a module row names the executable"
        # A boolean: pytest would show the modules passed to the call,
        # whose Prolog facts hold their paths.
        child = names_the_child(project, modules)
        assert not child, "a module row names the child"


@POSIX_FORK
def test_fork_target_runs_without_an_activation(stores):
    """The target that the forked child runs, ``work``, has no activation:
    what the child does is not in the store, whose activations of the
    process are the parent's calls

    Characterization: #202 records launches, not forks, and left this
    as it was; a change that records the forked child updates this test
    deliberately.
    """
    project = stores("fork.py")
    assert (project.path / "child_out.txt").read_bytes() == CHILD_OUTPUT
    with reading(project) as trial:
        names = [activation.name for activation in trial.activations]
        assert "work" not in names
        assert names.count("ForkProcess") == 1


@pytest.mark.parametrize("kind", NEW_INTERPRETER_KINDS)
def test_process_call_leaves_no_unreferenced_content(stores, kind):
    """A child that is a new interpreter writes nothing into the parent's
    content store: every blob is named by a code block or a file access
    (the control of the fork's case, #379)"""
    assert unreferenced_blobs(stores(KINDS[kind].script)) == set()


# --- known defects -----------------------------------------------------------


# The calls of raising_calls.py that raise, and those that return.
RAISING_CALLS = (
    Call("run", "subprocess.run(", ("list", "literal", "literal"), None, None),
    Call("int", 'int("x", 10)', ("literal", "literal"), None, None),
    Call("boom", "boom(", ("literal", "name"), None, None),
)
RETURNING_INT = Call("int", 'int("7", 10)', ("literal", "literal"), None, None)
RETURNING_FUNCTION = Call("fine", "fine(", ("literal", "name"), None, None)


def parameter_bindings(activation):
    """The dependency types of each parameter of a script function's
    activation, by parameter name"""
    return {
        evaluation.code_component.name: sorted(
            dependency.type for dependency in evaluation.dependencies_as_dependent
        )
        for evaluation in activation.evaluations
        if evaluation.code_component.type == "param"
    }


def test_call_that_raises(stores):
    """A call whose evaluation raises, ``subprocess.run(check=True)`` of a
    child that exits with 3, ``int("x", 10)`` or ``boom(number, 2)``, a
    function of the script, keeps its activation, but its evaluation is
    the dependent of no row, and its value is stored as the string
    ``'None'``; the parameters of ``boom`` keep their bindings. The same
    calls returning, ``int("7", 10)`` and ``fine(number, 2)``, have their
    func and arguments. The launch that raised is recorded all the same:
    the run call carries the child's three files (#202)

    Characterization of #378, a defect of the collector, not
    of subprocess; the value ``'None'`` has a cause of its own (the twin
    does not state it).
    """
    project = stores("raising_calls.py")
    with reading(project) as trial:
        for call in RAISING_CALLS:
            activation = call_activation(trial, call)
            evaluation = activation.this_evaluation
            traced = activation.code_block_id is not None
            assert traced == (call.name == "boom"), "{}: a code block: {}".format(
                call.source, traced
            )
            names = sorted(masked(project, a.name) for a in activation.file_accesses)
            expected = list(CHILD_FILES) if call.name == "run" else []
            assert names == expected, call.source
            # Counts and booleans: an evaluation's repr is its Prolog
            # fact, and a value can hold the executable's path.
            dependencies = len(list(evaluation.dependencies_as_dependent))
            assert dependencies == 0, "{}: {} dependencies".format(
                call.source, dependencies
            )
            is_none = evaluation.repr == "None"
            assert is_none, "{}: the value is not 'None'".format(call.source)
            stored = project.query(
                "SELECT quote(repr) AS repr FROM evaluation "
                "WHERE trial_id = ? AND id = ?",
                trial.id,
                evaluation.id,
            )
            stored_none = stored == [{"repr": "'None'"}]
            assert stored_none, "{}: the stored value is not 'None'".format(call.source)
        # Locals and booleans: pytest would show the models.
        bindings = parameter_bindings(call_activation(trial, RAISING_CALLS[-1]))
        assert bindings == {"first": ["argument"], "second": ["argument"]}
        evaluation = call_activation(trial, RETURNING_INT).this_evaluation
        types = dependency_types(evaluation)
        assert types == {"func": 1, "argument": 2, "dependency": 2}
        returned = evaluation.repr == "7"
        assert returned, "{}: the value is not '7'".format(RETURNING_INT.source)
        evaluation = call_activation(trial, RETURNING_FUNCTION).this_evaluation
        types = dependency_types(evaluation)
        assert types == {"func": 1, "argument": 2, "use": 1}
        returned = evaluation.repr == "3"
        assert returned, "{}: the value is not '3'".format(RETURNING_FUNCTION.source)


@known_defects(RAISING_CALL_DEPS)
def test_call_that_raises_desired(stores):
    """A call that raises keeps its func and its arguments, as the same
    call does when it returns"""
    project = stores("raising_calls.py")
    with reading(project) as trial:
        for call in RAISING_CALLS:
            types = dependency_types(call_activation(trial, call).this_evaluation)
            kept = types["func"] == 1 and types["argument"] == len(call.arguments)
            assert kept, "{}: dependencies {}".format(
                call.source, dict(sorted(types.items()))
            )


# What the fork's child opened: its input and its output. It opens os.devnull
# too, which is not a regular file, so the wrapper does not read it (#371).
FORK_CHILD_BLOBS = {sha1(data) for data in (CHILD_INPUT, CHILD_OUTPUT)}


@POSIX_FORK
def test_fork_child_content_blobs(stores):
    """The forked child writes into the parent's content store the content
    of its input and of its output, which no row names: exactly these two

    Characterization of #379. #202 records launches, not forks, and
    left this as it was.
    """
    project = stores("fork.py")
    assert (project.path / "child_in.txt").read_bytes() == CHILD_INPUT
    orphans = unreferenced_blobs(project)
    missing = len(FORK_CHILD_BLOBS - orphans)
    others = len(orphans - FORK_CHILD_BLOBS)
    assert orphans == FORK_CHILD_BLOBS, (
        "{} of the child's blobs are not orphans, {} other orphans".format(
            missing, others
        )
    )


@POSIX_FORK
@known_defects(FORK_BLOBS)
def test_fork_child_content_blobs_desired(stores):
    """Every blob of the content store is named by a row of the store"""
    orphans = unreferenced_blobs(stores("fork.py"))
    assert not orphans, "{} content blobs that no row references".format(len(orphans))


# The modules of preimported.py. json and subprocess are imported by
# noWorkflow itself before any script: now/cmd/__init__.py imports
# SQLAlchemy, which imports json, and every command, and cmd_push.py
# imports json and utils/functions.py and cmd_demo.py subprocess at module
# level, so that holds on every leg and every interpreter build. tabnanny
# is a pure-Python tool of the standard library on every supported version
# and system, and nothing that
# `now run` imports before the script imports it (measured at the top of a
# script under `now run` on 3.11 to 3.15; colorsys, which looked as good,
# is imported before the script by prompt_toolkit, a dependency of
# IPython). The script prints the precondition, which the fixture asserts.
PREIMPORTED = ["json", "subprocess"]
NOT_PREIMPORTED = "tabnanny"


@pytest.fixture(scope="module")
def preimported(tmp_path_factory):
    """The module names that ``preimported.py`` records, once its
    precondition holds: noWorkflow imported json and subprocess before the
    script, and not tabnanny"""
    project = NowProject(tmp_path_factory.mktemp("preimported"))
    project.copy_corpus("processes")
    result = run_now(project, "run", "preimported.py")
    unchanged = result.stdout.splitlines() == [repr(PREIMPORTED)]
    assert unchanged, (
        "the modules noWorkflow imports before the script changed:\n{}".format(
            project.normalize(result.stdout)
        )
    )
    with reading(project) as trial:
        return {module.name for module in trial.modules}


def test_modules_imported_before_the_script(preimported):
    """A module that noWorkflow imported before the script, json or
    subprocess, has no module row when the script imports it; one that it
    did not, tabnanny, has one

    Characterization of #380. preimported.py starts no
    process and loads no library through ctypes: #203 leaves this test
    alone unless its module recording also covers what is already in
    sys.modules.
    """
    assert NOT_PREIMPORTED in preimported
    assert sorted(name for name in PREIMPORTED if name in preimported) == []


@known_defects(PREIMPORTED_MODULES)
def test_modules_imported_before_the_script_desired(preimported):
    """Every module the script imports has a module row, whoever imported
    it first"""
    assert NOT_PREIMPORTED in preimported
    missing = [name for name in PREIMPORTED if name not in preimported]
    assert not missing, "no module row for {}".format(missing)


def test_the_version_lookup_records_no_module_of_its_own(tmp_path):
    """get_version (prov_deployment/deployment.py) reads a distribution's
    metadata from inside the import finder, while the script runs; what
    that reading imports for the first time (importlib.metadata._adapters,
    email.policy) must not get a module row as if the script had imported
    it. The oracle is the same script under plain Python, which prints the
    modules its import of idna brings."""
    project = NowProject(tmp_path)
    project.copy_corpus("processes")
    python = plain_python(project.command)
    if python is None:
        pytest.skip("no plain interpreter next to {}".format(project.command))
    plain = subprocess.run(
        [python, "metadata_lookup.py"],
        cwd=str(project.path),
        env=project.env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert plain.returncode == 0, plain.stderr
    imported = set(ast.literal_eval(plain.stdout.strip()))
    run_now(project, "run", "metadata_lookup.py")
    with reading(project) as trial:
        recorded = {module.name for module in trial.modules}
    assert "idna" in recorded, (
        "precondition: noWorkflow imported idna before the script, so it "
        "has no module row (#380) and its version is never looked up"
    )
    assert sorted(recorded - imported) == []


# What an exec loses: the rows that run (cmd/cmd_run.py) stores after the
# script, and those the desired twin expects back.
LOST_TABLES = (
    "environment_attr",
    "module",
    "code_component",
    "code_block",
    "evaluation",
    "activation",
    "file_access",
    "tag",
)
KEPT_TABLES = ("code_component", "evaluation", "module", "tag")


def what_was_kept(project):
    """``(status, lost, last)`` of the only trial of ``project``: its
    status, the tables of ``KEPT_TABLES`` with no row of it, and whether
    ``.last_trial`` was written"""
    (trial,) = project.trials()
    lost = [table for table in KEPT_TABLES if project.count(table, trial["id"]) == 0]
    return (trial["status"], lost, (project.path / ".last_trial").exists())


@pytest.fixture(scope="module")
def replaced(tmp_path_factory):
    """``{label: (project, plain, traced)}``: ``execv.py`` run by Python
    and by ``now run --create_last``, each from a fresh copy of the corpus,
    as the control (no argument) and with the exec (``exec``), each in a
    project of its own whose store the traced run left"""
    runs = {}
    for label, args in (("control", ()), ("exec", ("exec",))):
        project = NowProject(tmp_path_factory.mktemp("execv_" + label))
        plain, traced = run_both(
            project, "processes", "execv.py", *args, flags=("--create_last",)
        )
        runs[label] = (project, plain, traced)
    return runs


@POSIX_EXEC
def test_script_that_replaces_itself_through_exec(replaced):
    """A script that replaces its process through ``os.execv`` behaves as
    under plain Python (the exit status, 3, and the output are the new
    image's), but its trial keeps only what ``now`` stored before the
    script: ongoing, with no finish and no main block, its arguments and
    nothing else, no ``.last_trial`` under ``--create_last``, and the
    blobs of its code with no row naming them; the same script without the
    exec (the control) is stored whole, its local module included

    Characterization of #377. #202 records the processes a script starts
    through audit hooks, and CPython raises ``os.exec`` before it replaces
    the image, but the tracer stores nothing there (it only closes its
    pending launches in memory, by the decision recorded in #202): this
    stays as it was.
    """
    # The outcomes reach the messages through normalize: a traceback holds
    # paths of the checkout, of the interpreter and of the project.
    for label, (project, plain, traced) in replaced.items():
        found = differences(plain, traced)
        assert not found, "{}: {}".format(label, project.normalize("\n".join(found)))

    control, _, _ = replaced["control"]
    # What the twin asks of the exec holds for the control.
    assert what_was_kept(control) == ("finished", [], True)
    (trial,) = control.trials()
    assert [
        row["name"]
        for row in control.query(
            "SELECT name FROM module WHERE trial_id = ?", trial["id"]
        )
    ] == ["square"]

    project, _, traced = replaced["exec"]
    replaced_image = traced.returncode == 3 and traced.stdout.splitlines() == [
        "before exec 9",
        "child-done",
    ]
    assert replaced_image, shown(project, traced)
    assert (project.path / "child_out.txt").read_bytes() == CHILD_OUTPUT
    (trial,) = project.trials()
    assert trial["status"] == "ongoing"
    assert trial["finish"] is None
    assert trial["main_id"] is None
    assert project.count("argument", trial["id"]) > 0
    stored = {table: project.count(table, trial["id"]) for table in LOST_TABLES}
    assert stored == dict.fromkeys(LOST_TABLES, 0)
    assert what_was_kept(project) == ("ongoing", list(KEPT_TABLES), False)
    blobs = content_blobs(project)
    if blobs is not None:
        for name in ("execv.py", "square.py"):
            kept = sha1((project.path / name).read_bytes()) in blobs
            assert kept, "no blob of {}".format(name)


@POSIX_EXEC
@known_defects(EXEC_LOSES_TRIAL)
def test_script_that_replaces_itself_through_exec_desired(replaced):
    """The trial of a script that replaces its process through
    ``os.execv`` is stored up to the exec: no longer ongoing, with its
    code, its evaluations, its local module and its automatic tag, and
    ``--create_last`` writes ``.last_trial``"""
    status, lost, last = what_was_kept(replaced["exec"][0])
    assert status != "ongoing" and not lost and last, (
        "status {!r}, nothing stored in {}, .last_trial written: {}".format(
            status, lost, last
        )
    )


@pytest.fixture(scope="module")
def forked_exits(tmp_path_factory):
    """``(project, plain, traced)``: ``fork_exit.py`` run by Python, then
    by ``now run``, whose store the project keeps"""
    project = NowProject(tmp_path_factory.mktemp("fork_exit"))
    plain, traced = run_both(project, "processes", "fork_exit.py")
    return project, plain, traced


def children_rows(project, trial_id):
    """The automatic tags of the trial and the names of the activations of
    ``exit``, which only a child's branch calls"""
    tags = [tag for tag in project.tags(trial_id) if tag["type"] == "AUTO"]
    exits = [
        row["name"]
        for row in project.query(
            "SELECT name FROM activation WHERE trial_id = ? AND name = 'exit' "
            "ORDER BY id",
            trial_id,
        )
    ]
    return tags, exits


@OS_FORK
def test_forked_children_that_leave_through_sys_exit(forked_exits):
    """Children of os.fork() that leave through ``sys.exit`` store the
    trial too: one more automatic tag each, and the activation of their
    ``sys.exit`` call stays in the trial over an evaluation of the parent
    with the same id (which one depends on the numbering; never the
    child's call, which the parent does not evaluate); the child that
    leaves through ``os._exit`` leaves nothing. The children exit with 0,
    3 and 3 under plain Python and under ``now``, where the second one also
    prints the epilogue's line on stderr

    Characterization of #375 on the store; the oracle case
    ``fork_child_exit_status`` pins the output. #202 records launches,
    not forks, and left this as it was.
    """
    project, plain, traced = forked_exits
    # The outcomes reach the messages through normalize: a traceback holds
    # paths of the checkout, of the interpreter and of the project.
    exited = plain.returncode == 0 and plain.stderr == ""
    assert exited, shown(project, plain)
    printed = plain.stdout == "exit codes [0, 3, 3]\n"
    assert printed, shown(project, plain)
    exited = traced.returncode == 0 and traced.stdout == "exit codes [0, 3, 3]\n"
    assert exited, shown(project, traced)
    printed = traced.stderr.splitlines() == [
        "[now] the execution exited via sys.exit(). Exit status: 3",
    ]
    assert printed, shown(project, traced)
    (trial,) = project.trials()
    assert trial["status"] == "finished"
    tags, exits = children_rows(project, trial["id"])
    assert tags == [{"type": "AUTO", "name": "1.1.1"}] * 3
    assert exits == ["exit", "exit"]
    # The source text of the evaluation that has the id of each activation
    # of exit, the parent's: the child's own row, the call sys.exit(code),
    # was replaced.
    shared = [
        row["name"]
        for row in project.query(
            "SELECT code_component.name FROM activation "
            "JOIN evaluation ON evaluation.trial_id = activation.trial_id "
            "AND evaluation.id = activation.id "
            "JOIN code_component ON code_component.trial_id = evaluation.trial_id "
            "AND code_component.id = evaluation.code_component_id "
            "WHERE activation.trial_id = ? AND activation.name = 'exit'",
            trial["id"],
        )
    ]
    assert len(shared) == len(exits) and "sys.exit(code)" not in shared, shared
    controls = project.query(
        "SELECT id FROM activation WHERE trial_id = ? AND name = '_exit'", trial["id"]
    )
    assert controls == []


@OS_FORK
@known_defects(FORK_EPILOGUE)
def test_forked_children_that_leave_through_sys_exit_desired(forked_exits):
    """The trial of a script whose forked children leave through
    ``sys.exit`` is the parent's alone: one automatic tag, and no
    activation that only a child's branch calls"""
    project, _, _ = forked_exits
    (trial,) = project.trials()
    tags, exits = children_rows(project, trial["id"])
    assert len(tags) == 1 and not exits, (
        "{} automatic tags, activations of the children: {}".format(len(tags), exits)
    )
