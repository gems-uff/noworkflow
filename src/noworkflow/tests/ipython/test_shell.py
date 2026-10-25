# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The in-process shell is sound, and the pollution of IPython's magic table

The fixtures of this package (``conftest.py``, ``support.py``) run every
IPython test of the suite. These tests pin what the others rely on: the
extension's magics are registered, a cell's outcome, output and ``[now]``
messages are read, a failing cell imports nothing a collection's finder
could load, the shell runs in the project with the harness's synthetic
environment (so the ``now`` that ``%now_run`` starts records
``nowtest``), a ``%now_run`` trial is read with SQL, by ``now`` and
through the models, a cell whose process outlives its time limit is
killed, a collection left behind is reported, a magics class defined
while a name is pending in IPython's table is repaired and reported, an
in-process collection defines no magics class, ``real_stores`` closes
every connection, and closing the shell puts the process back as it was:
what the root leak detector watches, the in-memory stores, IPython's
singleton, magic table and magics classes, the threads, the ``atexit``
entries, the environment.

The last tests pin that ``%load_ext noworkflow`` and ``%reload_ext
noworkflow`` leave IPython's table of pending magics as they found it,
so the next magics class of the process can be created (#384). Had a
magics class taken the names, it would stay broken for the rest of the
process, so they run in child Pythons, never in this one.
"""

import atexit
import builtins
import collections
import contextlib
import gc
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import weakref

import pytest
from IPython import get_ipython
from IPython.core import magic as ipython_magic
from IPython.core.interactiveshell import InteractiveShell
from sqlalchemy import event
from sqlalchemy.pool import Pool

from noworkflow.now.ipython import dotmagic
from noworkflow.now.persistence import (
    content,
    persistence_config,
    relational,
    relational_database,
)
from noworkflow.now.persistence.models import MetaModel, Trial
from noworkflow.now.utils import io as now_io
from noworkflow.tests.e2e.harness import USER, NowProject, same_path, tail
from noworkflow.tests.e2e.normalize import Normalizer
from noworkflow.tests.helpers import leaks
from noworkflow.tests.helpers.persistence import connected_to, real_stores

from .support import (
    IPYTHON_BUILTINS,
    LAST_EXCEPTION,
    PROMPTS,
    broken_magics_classes,
    command_line,
    import_models,
    magics_classes,
    names_taken,
    open_shell,
    run_python,
)

LINE_MAGICS = {
    "now_ip",
    "now_ls_magic",
    "now_restore",
    "now_run",
    "now_schema",
    "now_set_default",
}
CELL_MAGICS = {"now_prolog", "now_run", "now_sql"}


class Probe:
    """An object that ``weakref.finalize`` accepts"""


def recording(function, calls):
    """``function`` that also appends its first argument to ``calls``"""

    def record(callback, *args, **kwargs):
        calls.append(callback)
        return function(callback, *args, **kwargs)

    return record


@contextlib.contextmanager
def connections_counted():
    """Count the connections checked out of, and into, the pools of the
    SQLAlchemy engines created inside the block

    The listeners go on each engine ``relational_database.create_engine``
    returns inside, never on the ``Pool`` class: a connection an earlier
    test checked out of an engine of its own and dropped without closing
    goes back to its pool when the garbage collector reaches it, and on
    the class that checkin, with no checkout inside the block, would
    count here (#462). The listeners die with the engines, which
    ``real_stores`` disposes.
    """
    counts = collections.Counter()
    saved_create_engine = relational_database.create_engine

    def checkout(*args):
        counts["out"] += 1

    def checkin(*args):
        counts["in"] += 1

    def create_engine(*args, **kwargs):
        engine = saved_create_engine(*args, **kwargs)
        event.listen(engine, "checkout", checkout)
        event.listen(engine, "checkin", checkin)
        return engine

    relational_database.create_engine = create_engine
    try:
        yield counts
    finally:
        relational_database.create_engine = saved_create_engine


def in_memory_state():
    """The objects of the in-memory stores the suite connects on import"""
    return (
        relational.engine,
        relational._session_map,
        relational.db_path,
        content.content_database_engine,
        persistence_config.should_mock,
        persistence_config.base_path,
        persistence_config.content_engine,
    )


def process_state():
    """What a shell may change for the whole process and must put back

    The leak detector's list is checked with a ``Baseline`` of the test's
    own; this is the rest. The models are imported first, so the
    defaults compare the same classes whether or not a trial was created
    in between (#415).
    """
    import_models()
    return {
        "cwd": os.getcwd(),
        # A digest: the values are this machine's.
        "environ": hashlib.sha256(
            repr(sorted(os.environ.items())).encode()
        ).hexdigest(),
        "tempdir": tempfile.tempdir,
        "persistence": in_memory_state(),
        "ipython": (InteractiveShell.initialized(), get_ipython()),
        "magic table": {
            kind: dict(table) for kind, table in ipython_magic.magics.items()
        },
        "builtins": set(vars(builtins)),
        "prompts and last exception": [
            getattr(sys, name, None) for name in PROMPTS + LAST_EXCEPTION
        ],
        "streams": (sys.stdin, sys.stdout, sys.stderr, sys.excepthook, sys.displayhook),
        "sys.path": list(sys.path),
        "threads": set(threading.enumerate()),
        "dot loaded": dotmagic.LOADED,
        "magics classes that took pending names": broken_magics_classes(),
        "verbose": now_io.verbose,
        "defaults": {
            name: dict(model.DEFAULT) for name, model in MetaModel.__classes__.items()
        },
    }


def test_the_extension_registers_its_magics(shell):
    """``%load_ext noworkflow`` adds the magics of the issue, and ``%%dot``"""
    assert LINE_MAGICS <= shell.magics("line")
    assert CELL_MAGICS | {"dot"} <= shell.magics("cell")


def test_the_bare_shell_has_ipython_magics_only(bare_shell):
    """No noworkflow magic, and IPython's own magics already loaded"""
    names = bare_shell.magics("line") | bare_shell.magics("cell")
    assert not {name for name in names if name.startswith("now_")}
    assert "dot" not in names
    registry = bare_shell.ip.magics_manager.registry
    assert {"ScriptMagics", "ExecutionMagics", "HistoryMagics"} <= set(registry)


def test_a_cell_gives_its_result_and_what_it_printed(bare_shell):
    """``run`` returns success, the last value and the captured stdout"""
    cell = bare_shell.run("x = 6 * 7\nprint('printed', x)\nx")
    assert cell.success, cell.describe()
    assert cell.error is None and cell.error_text == ""
    assert cell.result == 42
    assert "printed 42" in cell.stdout
    assert bare_shell.user_ns["x"] == 42


def test_a_failing_cell_gives_its_exception(bare_shell):
    """The exception IPython caught, its type and message, and the
    traceback IPython printed; the next cell still runs
    """
    cell = bare_shell.run("1 / 0")
    assert not cell.success
    assert cell.error_type == "ZeroDivisionError"
    assert cell.error_text == "ZeroDivisionError: division by zero"
    assert "ZeroDivisionError" in cell.stdout
    syntax = bare_shell.run("def broken(:\n    pass")
    assert syntax.error_type == "SyntaxError", syntax.describe()
    assert bare_shell.ok("1 + 1").result == 2


def test_a_failing_cell_imports_nothing(bare_shell):
    """What IPython imports for its first cell and traceback is loaded when
    the shell starts

    So a collection that leaves its import finder installed (an
    ``--interactive`` cell that raised) never loads IPython's own modules
    through it.
    """
    before = set(sys.modules)
    for code in ("1 / 0", "def broken(:\n    pass", "raise KeyboardInterrupt"):
        assert not bare_shell.run(code).success
    assert sorted(set(sys.modules) - before) == []


def test_a_cell_gives_the_now_messages_apart(bare_shell):
    """``[now]`` lines of this process are in ``messages``, not in stdout"""
    cell = bare_shell.ok(
        "from noworkflow.now.utils.io import print_msg\n"
        "print_msg('forced', True)\n"
        "print_msg('only when verbose')\n"
        "print('printed')"
    )
    assert cell.messages == "[now] forced\n"
    assert cell.stdout == "printed\n"


def test_the_shell_runs_in_the_project_with_the_synthetic_environment(shell):
    """The current directory, the temporary directory, the environment
    and the persistence layer belong to the project while the shell runs

    Compared, never printed: the messages are fixed.
    """
    project = shell.project
    checks = {
        "the current directory is the project": same_path(os.getcwd(), project.path),
        "tempfile writes into the project's tmp": same_path(
            tempfile.gettempdir(), project.tmp
        ),
        "USER and LOGNAME are the synthetic user": os.environ.get("USER")
        == os.environ.get("LOGNAME")
        == USER,
        "HOME is the project's home": same_path(
            os.environ.get("HOME", ""), project.home
        ),
        "IPYTHONDIR is in the project's home": same_path(
            os.environ.get("IPYTHONDIR", ""), project.home / ".ipython"
        ),
        "VIRTUAL_ENV is unset": "VIRTUAL_ENV" not in os.environ,
        "PATH starts with this interpreter's directory": same_path(
            os.environ["PATH"].split(os.pathsep)[0], os.path.dirname(sys.executable)
        ),
        "%%script finds the now of this interpreter": same_path(
            os.path.dirname(shutil.which("now") or ""), os.path.dirname(sys.executable)
        ),
        "get_ipython() is the shell": get_ipython() is shell.ip,
        "the persistence layer is on the project's store": not persistence_config.should_mock
        and same_path(persistence_config.path, project.path)
        and (project.path / ".noworkflow" / "db.sqlite").is_file(),
    }
    failed = [name for name, holds in checks.items() if not holds]
    assert failed == []


def test_now_run_records_a_trial_read_with_sql_and_with_the_models(shell):
    """A ``%%now_run`` cell records its trial in the project's store

    The ``now`` it runs inherits the synthetic environment: both USER
    attributes of the trial are ``nowtest``, and its HOME is the
    project's (compared, never printed). The trial is the one
    ``.last_trial`` names; ``now list`` run as a process sees it while
    the shell is open, and so do the models through ``connected_to``,
    after which the shell's own connection is back.
    """
    project = shell.project
    cell = shell.run("%%now_run --name cellA\nprint('in the cell')")
    assert cell.success, cell.describe()
    assert "in the cell" in cell.stdout, cell.describe()
    trials = project.trials()
    assert [(row["script"], row["status"]) for row in trials] == [("cellA", "finished")]
    trial_id = trials[0]["id"]
    assert shell.last_trial_id() == trial_id

    def attribute(name):
        return [
            row["value"]
            for row in project.query(
                "SELECT value FROM environment_attr WHERE trial_id = ? AND name = ?",
                trial_id,
                name,
            )
        ]

    users = attribute("USER")
    synthetic = len(users) == 2 and all(user == USER for user in users)
    assert synthetic, "{} USER attribute(s), not all {!r}".format(len(users), USER)
    homes = attribute("HOME")
    temporary = len(homes) == 1 and same_path(homes[0], project.home)
    assert temporary, "the HOME attribute is not the project's home"
    listed = trial_id in project.run("list").stdout
    assert listed, "now list does not show the trial"
    engine = relational.engine
    with connected_to(project.path):
        assert [trial.id for trial in relational.session.query(Trial.m)] == [trial_id]
    same_engine = relational.engine is engine
    assert same_engine, "the shell's engine is not back"
    back = same_path(persistence_config.path, project.path)
    assert back, "the shell's connection is not back on the project"
    assert not shell.children.running()


def test_a_cell_over_its_time_limit_has_its_process_killed(shell):
    """A ``%%script`` process still running after the cell's timeout is
    killed, and the test fails instead of hanging
    """
    line = command_line([sys.executable])
    with pytest.raises(pytest.fail.Exception, match="ran longer than 1 s"):
        shell.run("%%script " + line + "\nimport time\ntime.sleep(60)", timeout=1)
    assert shell.children.started and not shell.children.running()


def test_a_collection_left_behind_is_undone_and_reported(project):
    """The four opens, the injected builtins and the finder are undone
    before IPython closes, and reported as a leak once the process is back
    """

    def replaced_open(*args, **kwargs):
        return leaks.safeopen.std_open(*args, **kwargs)

    # What leaks.is_finder recognizes; it finds nothing.
    finder = type(
        "ProbeFinder",
        (),
        {
            "__module__": leaks.FINDER_MODULE,
            "find_spec": staticmethod(lambda *args, **kwargs: None),
        },
    )
    with pytest.raises(pytest.fail.Exception) as failed:
        with open_shell(project, extension=False):
            builtins.open = replaced_open
            builtins.now_tag_cell = print
            sys.meta_path.append(finder)
    message = str(failed.value)
    assert "builtins.open replaced" in message
    assert "names added to builtins: now_tag_cell" in message
    assert "import finder left in sys.meta_path" in message
    assert builtins.open is leaks.safeopen.std_open
    assert "now_tag_cell" not in vars(builtins)
    assert finder not in sys.meta_path
    assert not InteractiveShell.initialized()


def test_a_collection_the_test_undoes_is_not_reported(project):
    """A test that expects the leftovers undoes them, and nothing fails"""
    with open_shell(project, extension=False):
        builtins.now_tag_cell = print
        leaks.undo_collection()
    assert "now_tag_cell" not in vars(builtins)


def test_a_magics_class_defined_after_load_ext_takes_nothing(shell):
    """After ``%load_ext noworkflow`` no name is pending in IPython's table,
    and a magics class decorated then defines only its own magics (#384)"""
    pending = {kind: dict(table) for kind, table in ipython_magic.magics.items()}

    @ipython_magic.magics_class
    class LateMagics(ipython_magic.Magics):
        """Defines no magic of its own"""

    assert pending == {"line": {}, "cell": {}}
    assert names_taken(LateMagics) == []
    assert LateMagics.magics == {"line": {}, "cell": {}}


def test_a_magics_class_defined_while_names_are_pending_is_reported(project):
    """A magics class decorated while a name is pending in IPython's table
    takes it; closing the shell drops it from its table and reports the
    class, so no later test of the process meets it broken

    The name is left pending as ``%load_ext noworkflow`` did until #384: a
    ``line_magic`` marker applied outside a class body.
    """
    with pytest.raises(pytest.fail.Exception) as failed:
        with open_shell(project):

            def pending(self, line):
                """Never defined in the class that takes it"""

            ipython_magic.line_magic("now_pending")(pending)

            @ipython_magic.magics_class
            class LateMagics(ipython_magic.Magics):
                """Takes the name pending in IPython's table"""

            taken = names_taken(LateMagics)
    message = str(failed.value)
    assert taken == ["now_pending"]
    assert "LateMagics took the pending magics now_pending" in message
    assert names_taken(LateMagics) == []
    assert LateMagics not in broken_magics_classes()
    assert not InteractiveShell.initialized()


def test_an_in_process_collection_defines_no_magics_class(argv_kept, shell):
    """What an ``--interactive`` collection imports that defines magics
    classes is imported when the shell starts: the cell defines none, and
    none of the process takes a pending name

    ``Execution.configure`` imports ``IPython.terminal.embed`` (the
    ``now_ipython`` builtin), which defines TerminalMagics and
    EmbeddedMagics; ``warm_up`` imports it first, so that every test sees
    the same process whichever ran an ``--interactive`` cell first.
    """
    warmed = {"IPython.terminal.magics", "IPython.terminal.embed"} <= set(sys.modules)
    assert warmed, "the shell started without IPython.terminal's magics"
    before = set(magics_classes())
    cell = shell.run("%%now_run --name i1 --interactive\nx = 1")
    try:
        defined = sorted(
            cls.__qualname__ for cls in magics_classes() if cls not in before
        )
        broken = [cls.__qualname__ for cls in broken_magics_classes()]
    finally:
        leaks.undo_collection()
    assert cell.success, cell.describe()
    recorded = [(row["script"], row["status"]) for row in shell.project.trials()]
    assert recorded == [("i1", "finished")]
    assert defined == []
    assert broken == []


def test_closing_the_shell_puts_the_process_back(project, tmp_path, monkeypatch):
    """After the shell and the magics, the process is as before

    The leak detector finds nothing, and neither does a comparison of what
    it does not watch: the in-memory stores are the same objects, every
    connection to the project's store is closed, IPython's singleton is
    gone and its magic table as it was, no thread of the shell's runs (the
    event loop of ``%%script``), every ``atexit`` entry registered
    meanwhile is unregistered, and the environment, the builtins, the
    prompts, the streams, ``sys.path``, ``tempfile.tempdir``,
    ``dotmagic.LOADED``, ``utils.io.verbose`` and the defaults of the
    models are as they were.
    """
    # weakref.finalize registers an atexit hook of its own the first time
    # the process uses it, and the event loop of %%script may be that use.
    weakref.finalize(Probe(), lambda: None)
    # What IPython adds is taken back even when an earlier shell left it.
    for name in IPYTHON_BUILTINS:
        monkeypatch.delitem(vars(builtins), name, raising=False)
    registered, unregistered = [], []
    monkeypatch.setattr(atexit, "register", recording(atexit.register, registered))
    monkeypatch.setattr(
        atexit, "unregister", recording(atexit.unregister, unregistered)
    )
    baseline = leaks.Baseline(
        cwd=os.getcwd(), scan_dirs=[os.getcwd()], watched_dirs=[str(tmp_path)]
    )
    snapshot = baseline.snapshot()
    before = process_state()
    with connections_counted() as connections:
        with open_shell(project) as shell:
            shell.ok("%%now_run --name cellA\nprint('in the cell')")
            shell.ok("%now_set_default graph.width=200")
            defaults = MetaModel.__classes__["Trial"].DEFAULT
            assert defaults["graph.width"] == 200
            shell.ok("%now_ls_magic")
            assert threading.active_count() > len(before["threads"])
            assert set(IPYTHON_BUILTINS) <= set(vars(builtins))
            assert connections["out"] > 0
    assert connections["out"] == connections["in"]
    leaked = baseline.check(snapshot)
    assert not leaked, project.normalize("\n".join(leaked))
    after = process_state()
    changed = sorted(key for key in before if after[key] != before[key])
    assert changed == []
    assert registered, "the shell registered no atexit entry"
    left = [callback for callback in registered if callback not in unregistered]
    assert left == []


def test_a_connection_dropped_before_the_shell_is_not_counted(project):
    """A connection an earlier test checked out of an engine of its own and
    dropped without closing goes back to its pool when the garbage
    collector reaches it, while the shell is open here: the count of the
    shell's connections stays balanced (#462)

    Control: a listener on the ``Pool`` class sees that checkin.
    """
    seen = collections.Counter()

    def checkin(*args):
        seen["in"] += 1

    enabled = gc.isenabled()
    gc.disable()
    try:
        with real_stores():
            persistence_config.connect(str(project.path))
            # Only the collector frees a cycle; the connection goes back
            # to its pool (and closes) when it does.
            dropped = [relational.engine.raw_connection()]
            dropped.append(dropped)
            del dropped
        event.listen(Pool, "checkin", checkin)
        with connections_counted() as connections:
            with open_shell(project) as shell:
                shell.ok("%%now_sql\nSELECT id FROM trial")
                gc.collect()
                assert seen["in"] == connections["in"] + 1
        assert connections["out"] > 0
        assert connections["out"] == connections["in"]
    finally:
        if enabled:
            gc.enable()
        if event.contains(Pool, "checkin", checkin):
            event.remove(Pool, "checkin", checkin)


def test_real_stores_creates_a_store_and_closes_what_reconnecting_left(project):
    """Inside ``real_stores`` connecting creates a missing store; at the end
    every connection is closed, also those of the sessions that a second
    connect dropped (as every magic does), and the in-memory stores are back

    Control: before the end, the dropped session still holds a connection.
    """
    before = in_memory_state()
    with connections_counted() as connections:
        with real_stores():
            persistence_config.connect(str(project.path))
            assert relational.session.query(Trial.m).count() == 0
            persistence_config.connect(str(project.path))
            assert relational.session.query(Trial.m).count() == 0
            assert connections["out"] - connections["in"] == 2
        assert connections["out"] == connections["in"]
    assert in_memory_state() == before
    assert (project.path / ".noworkflow" / "db.sqlite").is_file()


def test_two_shells_in_a_row_get_the_extension_each(project):
    """A second shell in the same test is new, with ``%%dot`` again"""
    for _ in range(2):
        with open_shell(project) as shell:
            assert "dot" in shell.magics("cell")
            assert "now_run" in shell.magics("line")


# A child Python that starts a fresh shell, loads the extension unless told
# not to, and runs the cells it is named, in order: each defines a magics
# class the first time, ScriptMagics and HistoryMagics lazily, and the third
# one of the user's own.
POLLUTION = r"""
import json
import sys

from IPython.core import magic
from IPython.core.interactiveshell import InteractiveShell
from traitlets.config import Config

report, ipython_dir, program, extension = sys.argv[1:5]
CELLS = {
    "script": "%%script " + program + "\nprint('script', 'ran')",
    "history": "%history -n -l 1",
    "reload": "%reload_ext noworkflow",
    "own-class": (
        "from IPython.core.magic import Magics, line_magic, magics_class\n"
        "@magics_class\n"
        "class Mine(Magics):\n"
        "    @line_magic\n"
        "    def mine(self, line):\n"
        "        return line\n"
        "get_ipython().register_magics(Mine)\n"),
}
config = Config()
config.HistoryManager.hist_file = ":memory:"
config.InteractiveShell.colors = "nocolor"
shell = InteractiveShell.instance(config=config, ipython_dir=ipython_dir)
loaded = extension == "load" and shell.run_cell(
    "%load_ext noworkflow", store_history=True).success
pending = {kind: sorted(table) for kind, table in magic.magics.items()}
ended = {}
for name in sys.argv[5:]:
    result = shell.run_cell(CELLS[name], store_history=True)
    error = result.error_before_exec or result.error_in_exec
    ended[name] = "ok" if error is None else "{}: {}".format(
        type(error).__name__, error)
with open(report, "w", encoding="utf-8") as handle:
    json.dump({"load_ext": loaded, "pending": pending, "ended": ended},
              handle)
"""
# The cells of the child, and the class each one defines first.
FIRST_CLASSES = {
    "script": "ScriptMagics",
    "history": "HistoryMagics",
    "own-class": "Mine",
}


def run_pollution_child(factory, extension, *cells):
    """What the child Python reports, and what it printed"""
    project = NowProject(factory.mktemp("pollution"))
    report = project.root / "report.json"
    completed = run_python(
        project,
        POLLUTION,
        report,
        project.home / ".ipython",
        command_line([sys.executable]),
        extension,
        *cells,
    )
    normalize = Normalizer([("<PROJECT>", project.path), ("<ROOT>", project.root)])
    assert completed.returncode == 0 and report.exists(), normalize(
        "the child Python failed with return code {}\n{}".format(
            completed.returncode, tail(completed.stderr)
        )
    )
    result = json.loads(report.read_text(encoding="utf-8"))
    result["stdout"] = completed.stdout
    return result


@pytest.fixture(scope="module", params=list(FIRST_CLASSES))
def pollution(request, tmp_path_factory):
    """The child after ``%load_ext noworkflow``, and the cell it ran next"""
    return request.param, run_pollution_child(tmp_path_factory, "load", request.param)


@pytest.fixture(scope="module")
def no_extension(tmp_path_factory):
    """The child without the extension, which runs every cell: the
    control"""
    return run_pollution_child(tmp_path_factory, "skip", *FIRST_CLASSES)


def test_load_ext_leaves_the_next_magics_class_working(pollution, no_extension):
    """After ``%load_ext noworkflow`` IPython's table of pending magics is
    as without the extension (empty), and the next magics class decorated
    in the process works: ScriptMagics (``%%script``, which ``%now_run``
    runs through), HistoryMagics (``%history``) or a user's own class,
    whichever comes first (#384)

    Control: without the extension nothing is pending and the three cells
    run.
    """
    first, child = pollution
    assert no_extension["pending"] == {"line": [], "cell": []}
    assert no_extension["ended"] == dict.fromkeys(FIRST_CLASSES, "ok")
    assert "script ran" in no_extension["stdout"]
    assert child["load_ext"]
    assert child["pending"] == no_extension["pending"]
    ended = child["ended"][first]
    assert ended == "ok", "{} failed: {}".format(first, ended)
    printed = first != "script" or "script ran" in child["stdout"]
    assert printed, "%%script printed nothing"


def test_reload_ext_leaves_the_next_magics_class_working(tmp_path_factory):
    """After ``%load_ext noworkflow`` and ``%reload_ext noworkflow``, the
    magics classes decorated next work: ``%%script``, ``%history`` and a
    user's own class (#384)"""
    child = run_pollution_child(tmp_path_factory, "load", "reload", *FIRST_CLASSES)
    assert child["load_ext"]
    expected = dict.fromkeys(["reload", *FIRST_CLASSES], "ok")
    assert child["ended"] == expected
    assert "script ran" in child["stdout"]
