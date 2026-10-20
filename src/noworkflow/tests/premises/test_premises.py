# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Premises: the facts behind pins, ignores, exclusions and workarounds

A premise test does not check what noWorkflow should do. It pins a fact
that some line of the repository relies on: the SQLAlchemy pin, the
setuptools that ``[project.dependencies]`` leaves out, the e2e tests that
characterize the CLI, the committed ``bundle.js``, the documented
``now vis`` default, the way the suite keeps its store in memory and its
corpus out of collection, the uv-managed Python of the CI legs, the lock
export that ``pip-audit`` reads whole, the warning filter of the suite.
One test per fact, named as the fact; the docstring says why the code
depends on it, and the assert message says what to edit, and under which
issue, when it falls.

Wherever a premise asserts an absence (no warning, no import, no file, no
collected path), a paired control proves that the same instrument does see
the thing when it is there, so the absence cannot pass by accident.

Everything runs in-process under the leak detector, except what can only be
measured from outside: importing the test package in an empty directory and
pytest's own collection, which run in a child process inside ``tmp_path``,
and the committed bundle, which ``git show`` reads from HEAD. Files of the
checkout are located through ``request.config.rootpath`` or
``noworkflow.__file__``, never through the current directory (the session
runs from a scratch directory); the import premises scan the runtime
package, ``tests/`` excluded.
"""
import ast
import functools
import inspect
import io
import os
import re
import shutil
import subprocess
import sys
import warnings
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest
import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.util.deprecations as sa_deprecations

import noworkflow
from noworkflow.now import cmd as now_cmd
from noworkflow.now.cmd import cmd_vis
from noworkflow.now.cmd.cmd_list import List
from noworkflow.now.persistence import persistence_config
from noworkflow.now.persistence.models import Trial
from noworkflow.now.utils.io import print_msg
from noworkflow.tests.e2e.harness import CORPUS, clean_env, same_path, tail
from noworkflow.tests.premises import corpus_spy

PACKAGE = Path(noworkflow.__file__).resolve().parent
# Relative to the repository root (request.config.rootpath).
BUNDLE = Path("src") / "noworkflow" / "now" / "vis" / "static" / "dist" / "bundle.js"
ROOT_CORPUS = Path("src") / "noworkflow" / "tests" / "e2e" / "corpus"
SPY_PLUGIN = "noworkflow.tests.premises.corpus_spy"
# The original, kept before any test replaces it.
VIS_RUN = cmd_vis.run


def _child_env(tmp_path):
    """The harness's synthetic environment, with a home and TMPDIR in tmp_path

    No bytecode is written: the child imports modules of the checkout.
    """
    home, tmp = tmp_path / "home", tmp_path / "tmp"
    home.mkdir(exist_ok=True)
    tmp.mkdir(exist_ok=True)
    env = clean_env(home, tmp, [sys.executable])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _python(args, cwd, env):
    """Run this interpreter with ``args`` in ``cwd``"""
    return subprocess.run(
        [sys.executable] + list(args),
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def _report(result):
    """A child process's outcome, for assertion messages"""
    return "return code {}\n--- stdout ---\n{}\n--- stderr ---\n{}".format(
        result.returncode, tail(result.stdout), tail(result.stderr))


# 1. SQLAlchemy < 2 is still needed ------------------------------------------

MSG_SA_SERIES = (
    "SQLAlchemy {} is installed, but noWorkflow still uses 1.4-only APIs: "
    "Connection.execute(insert, *params) with implicit autocommit in "
    "now/persistence/models/base.py (2.0 rejects the call; without autocommit "
    "every row of a trial would be rolled back), select([...]) in "
    "now/persistence/models/trial.py, activation.py and tag.py, and "
    "session.execute(<plain str>). Restore the SQLAlchemy pin below 2 in "
    "pyproject.toml and run `uv lock` (dependencies skill, #225)."
)
MSG_SA_INSTRUMENT = (
    "Setting sqlalchemy.util.deprecations.SQLALCHEMY_WARN_20 no longer makes "
    "SQLAlchemy emit RemovedIn20Warning for select([...]), so "
    "test_noworkflow_still_calls_sqlalchemy_apis_that_2_0_removed measures "
    "nothing. Find the switch the installed SQLAlchemy uses before trusting "
    "that premise (#225)."
)
MSG_SA_FELL = (
    "Trial.last_trial no longer triggers RemovedIn20Warning in trial.py "
    "(RemovedIn20Warning sites seen: {}). If the migration to the 2.0 API is "
    "complete, `SQLALCHEMY_WARN_20=1 uv run pytest -W "
    "error::sqlalchemy.exc.RemovedIn20Warning` must be green; then relax the "
    "SQLAlchemy pin in pyproject.toml (dependencies skill, #225), update the "
    "SQLAlchemy entry under 'Patches of third-party internals' in AGENTS.md, "
    "remove the Base20DeprecationWarning exception of filterwarnings in "
    "pyproject.toml and its test in this module, and delete the three "
    "SQLAlchemy premises in this module."
)


def _removed_in_20_sites(monkeypatch, call):
    """``{(file name, line)}`` of the RemovedIn20Warning that ``call`` emits

    SQLAlchemy 1.4 reads SQLALCHEMY_WARN_20 at import; setting the module
    flag at runtime is how SQLAlchemy's own test suite turns it on.
    """
    removed = getattr(sqlalchemy.exc, "RemovedIn20Warning", None)
    if removed is None or not hasattr(sa_deprecations, "SQLALCHEMY_WARN_20"):
        pytest.fail(MSG_SA_SERIES.format(sqlalchemy.__version__))
    monkeypatch.setattr(sa_deprecations, "SQLALCHEMY_WARN_20", True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        call()
    return sorted({(Path(warning.filename).name, warning.lineno)
                   for warning in caught
                   if issubclass(warning.category, removed)})


def test_installed_sqlalchemy_is_the_1_4_series():
    """The installed SQLAlchemy is a 1.4 release

    noWorkflow stores every trial through APIs that SQLAlchemy 2.0 removed
    (see the message). The pin in pyproject.toml keeps 2.0 out; this checks
    that what is installed obeys it. Not a version check for its own sake:
    the next premise says when the pin may go.
    """
    assert sqlalchemy.__version__.startswith("1.4."), MSG_SA_SERIES.format(
        sqlalchemy.__version__)


def test_sqlalchemy_warn_20_switch_flags_a_legacy_select(monkeypatch):
    """Control: with SQLALCHEMY_WARN_20 on, 1.4 warns about ``select([...])``

    Without it, the premise below could pass because the switch stopped
    working rather than because noWorkflow stopped using removed APIs.
    """
    sites = _removed_in_20_sites(
        monkeypatch, lambda: sqlalchemy.select([sqlalchemy.literal(1)]))
    assert sites, MSG_SA_INSTRUMENT


def test_noworkflow_still_calls_sqlalchemy_apis_that_2_0_removed(monkeypatch):
    """Trial.last_trial still builds a ``select([...])`` that 2.0 removed

    This is the reason for the SQLAlchemy pin (#225): while the models use
    the 1.4 API, a 2.0 install fails on the first query (and the store's
    insert path loses rows). The query runs on the suite's in-memory store
    and writes nothing.
    """
    sites = _removed_in_20_sites(
        monkeypatch,
        lambda: Trial.last_trial(script="premise.py", check=True))
    assert any(name == "trial.py" for name, _ in sites), MSG_SA_FELL.format(
        sites)


# 2. Imports seen by an AST scan of the runtime package ------------------------

# Paths relative to the scanned root, with "/". The test package is not code
# that noWorkflow runs: its scripts (the examples, the e2e corpus) may use
# the syntax of any Python or import anything, and no pin depends on them.
SCAN_EXCLUDE = ("tests",)
MSG_SCAN = (
    "the import premises scan every module of the runtime package (tests/ "
    "excluded), and these do not parse on Python {}: {}. A module of the "
    "package that does not parse is a defect of its own."
)


def _scanned(relative):
    """Whether the import scan reads a module, given its path under the root"""
    return not ("__pycache__" in relative.parts
                or relative.parts[0] in SCAN_EXCLUDE)


def _imported_names(tree):
    """``(module, line)`` of every absolute import, static or dynamic"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                yield node.module, node.lineno
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            name = (func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute)
                    else None)
            first = node.args[0]
            if (name in ("__import__", "import_module")
                    and isinstance(first, ast.Constant)
                    and isinstance(first.value, str)):
                yield first.value, node.lineno


@functools.lru_cache(maxsize=None)
def _import_index(root):
    """``{relative posix path: ((module, line), ...)}`` of the scanned modules

    Every .py under root except SCAN_EXCLUDE.
    """
    root = Path(root)
    index, unparsable = {}, []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if not _scanned(relative):
            continue
        try:
            tree = ast.parse(path.read_bytes(), filename=str(path))
        except SyntaxError as exc:
            unparsable.append("{} ({})".format(relative.as_posix(), exc))
            continue
        index[relative.as_posix()] = tuple(_imported_names(tree))
    assert not unparsable, MSG_SCAN.format(
        sys.version.split()[0], "; ".join(unparsable))
    return index


def _importers(name, root=PACKAGE):
    """``{relative path: [lines]}`` of the modules under root that import name"""
    found = {}
    for relative, imports in _import_index(str(root)).items():
        lines = [line for module, line in imports
                 if module == name or module.startswith(name + ".")]
        if lines:
            found[relative] = lines
    return found


def test_the_import_scanner_finds_every_form_of_import(tmp_path):
    """Control: the scan behind the setuptools premise sees imports

    ``import x``, ``import x.y as z``, ``from x import y`` inside a function,
    ``importlib.import_module("x")`` and ``__import__("x")`` are found;
    relative imports and other names that start with the same letters are
    not. The tree mirrors the package: the top-level ``tests/`` is neither
    read nor parsed (it holds a file that does not parse here), while a
    nested ``tests`` directory is scanned. Without this, "no module imports
    setuptools" could pass because the scanner sees nothing.
    """
    files = {
        "plain.py": "import zipp\n",
        "dotted.py": "import zipp.glob as zglob\n",
        "pkg/inner.py": "def f():\n    from zipp import Path\n",
        "dynamic.py": "import importlib\nimportlib.import_module('zipp')\n",
        "builtin.py": "__import__('zipp')\n",
        "relative.py": "from .zipp import Path\nimport zippy\n",
        "tests/test_scan.py": "import zipp\n",
        "tests/e2e/corpus/script.py": "import zipp\nprint 'not parsed'\n",
        "now/tests/inner.py": "import zipp\n",
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert _importers("zipp", tmp_path) == {
        "builtin.py": [1],
        "dotted.py": [1],
        "dynamic.py": [2],
        "now/tests/inner.py": [1],
        "pkg/inner.py": [2],
        "plain.py": [1],
    }


def test_no_module_imports_setuptools_or_pkg_resources():
    """No module of the package imports setuptools or pkg_resources

    [project.dependencies] does not declare setuptools: utils/functions.py
    reads the package's resources through importlib.resources, and
    prov_deployment/deployment.py looks versions up through
    importlib.metadata (#225). pkg_resources is gone from setuptools 82 on,
    and importing it put setuptools/_vendor on the sys.path of every traced
    script (#419). The dev group installs setuptools for
    tests/test_import_smoke.py only, so the suite would not notice a module
    that starts importing it; a user's environment may have no setuptools.
    The scan reads the source file by file, so it names the module, which a
    look at sys.modules cannot.
    """
    found = dict(_importers("pkg_resources"), **_importers("setuptools"))
    assert not found, (
        "{} import(s) setuptools or pkg_resources, which [project."
        "dependencies] does not declare (#225). Use importlib.resources or "
        "importlib.metadata, or declare setuptools with the reason next to "
        "it.".format(", ".join("{}:{}".format(path, lines)
                               for path, lines in sorted(found.items()))))


# 3. argparse drops unknown arguments ------------------------------------------


def test_unknown_arguments_are_dropped_without_error(monkeypatch):
    """``now list --no-such-flag stray`` runs ``list`` as if they were absent

    now/cmd/__init__.py calls ``parser.parse_known_args()`` and discards the
    leftovers. The e2e tests characterize that (an unknown argument gives
    rc 0) and keep the desired behavior, rc 2, as an xfail(strict) twin
    under #226. Runs in-process with ``List.execute`` replaced: no store.
    """
    seen = []
    monkeypatch.setattr(List, "execute", lambda self, args: seen.append(args))
    monkeypatch.setattr(sys, "argv",
                        ["now", "list", "--no-such-flag", "stray-positional"])
    message = (
        "`now list --no-such-flag stray-positional` no longer runs list: "
        "now/cmd/__init__.py stopped dropping unknown arguments ({}). Flip "
        "the characterization of unknown arguments in "
        "src/noworkflow/tests/e2e/test_cli.py (rc 0) into its _desired twin "
        "(rc 2) by removing that twin's xfail(strict=True) (#226). Check "
        "that `now run script.py --flag` still hands --flag to the script "
        "(argparse.REMAINDER in now/cmd/cmd_run.py), then delete this premise "
        "and its control."
    )
    try:
        result = now_cmd.main()
    except SystemExit as exc:
        pytest.fail(message.format("SystemExit({!r})".format(exc.code)))
    assert result is None and len(seen) == 1, message.format(
        "main() returned {!r}, list ran {} time(s)".format(result, len(seen)))


def test_a_known_option_without_its_value_still_exits_2(monkeypatch, capsys):
    """Control: argparse still rejects a known option given without its value

    Without it, the premise above could pass because ``now`` stopped parsing
    its options at all.
    """
    seen = []
    monkeypatch.setattr(List, "execute", lambda self, args: seen.append(args))
    monkeypatch.setattr(sys, "argv", ["now", "list", "--dir"])
    try:
        now_cmd.main()
    except SystemExit as exc:
        code = exc.code
    else:
        code = None
    error = capsys.readouterr().err
    assert code == 2 and "--dir" in error and not seen, (
        "`now list --dir` (missing value) no longer exits 2 through argparse "
        "(exit code {!r}, list ran {} time(s), stderr {!r}): the premise "
        "test_unknown_arguments_are_dropped_without_error measures nothing "
        "until this is understood (#226).".format(code, len(seen), error))


# 4. The bundle that `now vis` serves ----------------------------------------------


@pytest.fixture(scope="module")
def served_bundle():
    """The bytes of /dist/bundle.js as the vis app serves them

    Through Flask's test client: no server, no socket, no store (the static
    route never touches the provenance store).
    """
    from noworkflow.now.vis.views import app
    response = app.test_client().get("/dist/bundle.js")
    try:
        assert response.status_code == 200, (
            "the vis app answered {} to /dist/bundle.js, which "
            "templates/index.html loads: `now vis` would show a blank "
            "page".format(response.status_code))
        return response.get_data()
    finally:
        response.close()


def _git(root, *args):
    """Run git in ``root``; bytes out, so a blob comes back unchanged"""
    return subprocess.run(
        [shutil.which("git")] + list(args),
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
    )


def _committed_bundle(root):
    """The bytes of bundle.js in the HEAD commit of the checkout, or skip

    ``git show`` prints a blob as stored, without the working-tree filters;
    .gitattributes marks bundle.js ``-text``, so the checkout has the same
    bytes on every system.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not installed: the committed bundle.js is "
                    "unreachable")
    top = _git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or not same_path(
            top.stdout.decode("utf-8", "replace").strip(), root):
        pytest.skip("the rootdir is not the top of a git checkout: the suite "
                    "runs outside the repository")
    if _git(root, "rev-parse", "--verify", "--quiet",
            "HEAD^{commit}").returncode != 0:
        pytest.skip("the checkout has no HEAD commit")
    shown = _git(root, "show", "HEAD:" + BUNDLE.as_posix())
    if shown.returncode != 0:
        pytest.skip("{} is not tracked at HEAD".format(BUNDLE.as_posix()))
    return shown.stdout


def test_now_vis_serves_the_committed_bundle(request, served_bundle):
    """The bundle.js that `now vis` serves is the one committed at HEAD

    The CI ``frontend`` job proves that the committed bundle matches the
    sources; this proves that the installed package serves that bundle.
    Compared with the blob in git, not with a file of the checkout: under an
    editable install the served file is the working-tree file, and a
    comparison with it could never fail. A stale non-editable install and a
    bundle rebuilt but not committed both fail here.
    """
    committed = _committed_bundle(request.config.rootpath)
    same = served_bundle == committed
    assert same, (
        "the bundle served differs from the committed one (stale install, "
        "or rebuilt and not committed): now vis serves {} bytes, HEAD:{} has "
        "{}. Run `uv sync --locked` for a stale install; commit a rebuilt "
        "bundle in the same commit as the src/frontend change that produced "
        "it, as src/frontend/development.md describes.".format(
            len(served_bundle), BUNDLE.as_posix(), len(committed)))


def test_the_served_bundle_labels_durations_in_microseconds(served_bundle):
    """Control: the served bundle contains the label "microseconds"

    The function diff labels durations in microseconds
    (src/frontend/packages/nowvis/src/graph/function_diff.ts). Without this,
    the absence of the misspelling below could pass on an empty or
    unrelated file.
    """
    count = served_bundle.count(b"microseconds")
    assert count > 0, (
        "the served bundle.js does not contain 'microseconds' any more, so "
        "test_the_served_bundle_does_not_say_miliseconds proves nothing. "
        "Find where function_diff.ts labels durations now and point both "
        "tests at that label.")


def test_the_served_bundle_does_not_say_miliseconds(served_bundle):
    """The served bundle never says "miliseconds"

    The misspelled label was fixed by editing the committed bundle (and the
    sources); a rebuild from an old source tree, or an old install, would
    bring it back without any other test noticing.
    """
    count = served_bundle.count(b"miliseconds")
    assert count == 0, (
        "the served bundle.js says 'miliseconds' {} time(s) again (the "
        "function-diff label). Fix "
        "src/frontend/packages/nowvis/src/graph/function_diff.ts and rebuild "
        "the bundle as src/frontend/development.md describes.".format(count))


# 5. `now vis` listens on localhost:5000 by default ---------------------------------

MSG_VIS_DEFAULT = (
    "now vis no longer listens on localhost:5000 by default ({}). "
    "SECURITY.md (the `now vis` server listens on `localhost` by default) "
    "and README.md (localhost:5000, and the push/pull URLs built on it) "
    "describe the old default: update them, or restore the default in "
    "now/cmd/cmd_vis.py (the --host and --port defaults and the run() "
    "signature). A non-loopback default exposes the provenance store, "
    "including the recorded environment, to the network."
)


def _now_vis_run_arguments(monkeypatch, *args):
    """The arguments ``now vis <args>`` would pass to cmd_vis.run

    Parsed by the real ``now`` parser; the store connection and the server
    are replaced, so nothing listens and nothing is opened.
    """
    calls = []

    def fake_run(*call_args, **call_kwargs):
        bound = inspect.signature(VIS_RUN).bind(*call_args, **call_kwargs)
        bound.apply_defaults()
        calls.append(dict(bound.arguments))

    config_class = type(persistence_config)
    monkeypatch.setattr(persistence_config, "content_engine",
                        persistence_config.content_engine)
    monkeypatch.setattr(config_class, "connect",
                        lambda self, path=None: None)
    monkeypatch.setattr(config_class, "connect_existing",
                        lambda self, path=None: None)
    monkeypatch.setattr(cmd_vis, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["now", "vis"] + list(args))
    now_cmd.main()
    assert len(calls) == 1, "now vis called run() {} times".format(len(calls))
    return calls[0]


def test_now_vis_listens_on_localhost_port_5000_by_default(monkeypatch):
    """`now vis` without --host and -p serves on localhost:5000

    SECURITY.md promises that the server listens on localhost by default
    (the store it serves records the whole environment), and README.md
    documents localhost:5000. Checked both through the command line and in
    the defaults of cmd_vis.run.
    """
    called = _now_vis_run_arguments(monkeypatch)
    defaults = {name: parameter.default for name, parameter
                in inspect.signature(VIS_RUN).parameters.items()}
    found = "command line: host={!r} port={!r}; run(): host={!r} port={!r}".format(
        called.get("host"), called.get("port"),
        defaults.get("host"), defaults.get("port"))
    assert (called.get("host"), called.get("port"),
            defaults.get("host"), defaults.get("port")) == (
        "localhost", 5000, "localhost", 5000), MSG_VIS_DEFAULT.format(found)


def test_now_vis_forwards_host_and_port_from_the_command_line(monkeypatch):
    """Control: what the stub receives comes from the command line

    Without it, the premise above could pass because the stub saw constants
    instead of what `now vis` parsed.
    """
    called = _now_vis_run_arguments(monkeypatch, "--host", "127.0.0.1",
                                    "-p", "5001")
    assert (called.get("host"), called.get("port")) == ("127.0.0.1", 5001), (
        "now vis --host 127.0.0.1 -p 5001 reached run() as {!r}: "
        "test_now_vis_listens_on_localhost_port_5000_by_default measures "
        "nothing until _now_vis_run_arguments is fixed".format(called))


# 6. print_msg does not follow sys.stdout ----------------------------------------------


def test_print_msg_does_not_follow_a_swapped_sys_stdout(monkeypatch):
    """print_msg writes to the stdout bound at import, not to sys.stdout

    now/utils/io.py binds ``STDOUT = sys.stdout`` at import and uses it as
    the default of ``file=``, and no caller passes ``file=``: every ``[now]``
    message, errors included, goes to the original stdout. That is why the
    e2e tests read ``[now]`` messages from a subprocess's stdout, and why
    capsys and redirect_stdout cannot see them (#226 moves the errors to
    stderr).
    """
    buffer = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buffer)
    print_msg("premise check: this line goes to the stdout bound at import",
              force=True)
    captured = buffer.getvalue()
    assert captured == "", (
        "print_msg now follows sys.stdout ({!r} landed in the swapped "
        "stream): now/utils/io.py binds the stream at call time. Tests can "
        "read [now] messages with capsys: remove the workarounds that existed "
        "for this (print_msg.__defaults__ patches, subprocess-only checks), "
        "and re-check the e2e assertions about which stream carries [now] "
        "messages; if errors moved to stderr, flip their characterizations "
        "into the _desired twins (#226).".format(captured))


def test_print_follows_a_swapped_sys_stdout(monkeypatch):
    """Control: a plain print does land in the swapped sys.stdout

    Without it, the premise above could pass because the swap itself did
    not take effect under the test runner.
    """
    buffer = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buffer)
    print("premise control")
    captured = buffer.getvalue()
    assert captured == "premise control\n", (
        "a plain print did not reach the swapped sys.stdout ({!r}): "
        "test_print_msg_does_not_follow_a_swapped_sys_stdout measures "
        "nothing".format(captured))


# 7. Importing the test package keeps the store in memory -------------------------------

CONNECT_THEN_MOCK = (
    "from noworkflow.now.persistence import persistence_config as config\n"
    "config.content_engine = 'plain'\n"
    "config.path = '.'\n"
    "config.connect()\n"
    "config.mock()\n"
)


def test_importing_noworkflow_tests_writes_nothing_to_the_cwd(tmp_path):
    """``import noworkflow.tests`` in an empty directory leaves it empty

    tests/__init__.py connects the persistence layer on import
    (connect_in_memory in tests/helpers/persistence.py), before pytest's
    hooks run. Mocking before connecting keeps the store in memory; the
    reverse opened a real .noworkflow/db.sqlite in the current directory,
    shared between runs. A subprocess, because in-process the scratch
    directory of the root conftest.py would hide the leak.
    """
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    result = _python(["-c", "import noworkflow.tests"], cwd,
                     _child_env(tmp_path))
    assert result.returncode == 0, _report(result)
    entries = sorted(path.name for path in cwd.iterdir())
    assert entries == [], (
        "importing noworkflow.tests created {} in an empty directory. "
        "connect_in_memory() (src/noworkflow/tests/helpers/persistence.py) "
        "must pin the plain engine and call mock() before connect(); "
        "otherwise every run opens a real .noworkflow/db.sqlite in the "
        "current directory that persists between runs.".format(entries))


def test_connecting_before_mocking_creates_a_store_in_the_cwd(tmp_path):
    """Control: the old order (connect, then mock) does create .noworkflow

    Without it, the premise above could pass because the check cannot see
    a store being created.
    """
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    result = _python(["-c", CONNECT_THEN_MOCK], cwd, _child_env(tmp_path))
    assert result.returncode == 0, _report(result)
    store = cwd / ".noworkflow" / "db.sqlite"
    assert store.is_file(), (
        "connecting before mocking no longer creates .noworkflow/db.sqlite "
        "(the directory holds {}): "
        "test_importing_noworkflow_tests_writes_nothing_to_the_cwd measures "
        "nothing until its control creates a store again".format(
            sorted(path.name for path in cwd.iterdir())))


# 8. No corpus file reaches collection ------------------------------------------------

MSG_CORPUS = (
    "pytest reached corpus scripts during collection:\n  {}\nThe scripts "
    "under src/noworkflow/tests/e2e/corpus are traced by `now run` in a "
    "subprocess and must never be imported by pytest: --doctest-modules "
    "imports every .py under testpaths, executing it. Check "
    "collect_ignore_glob in the root conftest.py "
    "(src/noworkflow/tests/e2e/corpus/**), and rename any corpus script "
    "that matches test_*.py or *_test.py."
)


def _spy_lines(output):
    return [line for line in output.splitlines()
            if line.startswith(corpus_spy.MARKER + " ")]


def test_the_corpus_spy_recognizes_a_path_under_the_corpus():
    """Control: the spy's matcher flags paths inside the corpus, and only those

    Checked on paths that need not exist, in both path flavours.
    """
    inside = [
        CORPUS / "nested" / "test_fake.py",
        PurePosixPath("src/noworkflow/tests/e2e/corpus/weather/simulation.py"),
        PureWindowsPath(r"C:\work\src\noworkflow\tests\e2e\corpus\fake.py"),
    ]
    outside = [
        CORPUS,
        CORPUS.parent / "harness.py",
        PurePosixPath("src/noworkflow/tests/examples/corpus/fake.py"),
        PurePosixPath("src/noworkflow/tests/e2e/corpus_like/fake.py"),
    ]
    assert [corpus_spy.is_corpus_path(path) for path in inside] == [True] * 3
    assert [corpus_spy.is_corpus_path(path) for path in outside] == [False] * 4
    assert corpus_spy.is_e2e_path(CORPUS.parent / "harness.py")


CORPUS_SCRIPT = (
    "from pathlib import Path\n"
    "Path(__file__).with_name('imported.txt').write_text('imported')\n"
)


def test_the_corpus_spy_reports_corpus_paths_and_keeps_them_unimported(
        tmp_path):
    """Control: in a child pytest, the spy reports the corpus paths it is shown

    A synthetic tree with ``--doctest-modules`` and no ignore glob: the
    corpus script and the corpus subdirectory are reported, and the script,
    which writes a file when imported, is never imported. Without this, the
    premise below could pass because the spy's report never reaches the
    output.
    """
    tree = tmp_path / "tree"
    e2e = tree / "src" / "noworkflow" / "tests" / "e2e"
    corpus = e2e / "corpus"
    (corpus / "weather").mkdir(parents=True)
    (e2e / "harness.txt").write_text("not a test\n", encoding="utf-8")
    (corpus / "script.py").write_text(CORPUS_SCRIPT, encoding="utf-8")
    (corpus / "weather" / "data1.dat").write_text("1.0:0.5\n",
                                                  encoding="utf-8")
    ini = tree / "pytest.ini"
    ini.write_text("[pytest]\naddopts = --doctest-modules\n",
                   encoding="utf-8")
    result = _python(
        ["-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "-p", SPY_PLUGIN, "-c", str(ini), "--rootdir", str(tree), str(tree)],
        tree, _child_env(tmp_path))
    lines = _spy_lines(result.stdout)
    expected = sorted(
        "{} reached src/noworkflow/tests/e2e/corpus/{}".format(
            corpus_spy.MARKER, name)
        for name in ("script.py", "weather"))
    assert lines and sorted(lines[:-1]) == expected, _report(result)
    assert re.fullmatch(r"\S+ done files=\d+ e2e=1 corpus=2", lines[-1]), (
        _report(result))
    assert not (corpus / "imported.txt").exists(), (
        "the spy let pytest import a corpus script\n" + _report(result))


def test_no_corpus_file_reaches_collection(request, tmp_path):
    """pytest never collects (and so never imports) a corpus script

    The scripts under e2e/corpus are what the e2e tests trace with `now
    run` in a subprocess. With ``--doctest-modules``, any .py that pytest
    collects is imported, which runs the script at collection time in the
    test process; ``collect_ignore_glob`` in the root conftest.py keeps
    them out. Measured from outside, by a child ``pytest --collect-only``
    with the repository's configuration and the corpus spy plugin: in a
    partial run, this session's own items would prove nothing. The child's
    return code is not asserted: a collection error elsewhere in the suite
    is reported by the suite itself, and the spy still sees the whole walk.
    """
    root = request.config.rootpath
    if not (root / "conftest.py").is_file() or not (root / ROOT_CORPUS).is_dir():
        pytest.skip("the suite runs outside the checkout")
    result = _python(
        ["-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "-p", SPY_PLUGIN],
        root, _child_env(tmp_path))
    lines = _spy_lines(result.stdout)
    done = [line for line in lines if " done " in line]
    assert done, (
        "the corpus spy never wrote its summary: the child `pytest "
        "--collect-only` did not get to the end of its session, so this "
        "premise measured nothing\n" + _report(result))
    reached = [line for line in lines if " reached " in line]
    reached += [line for line in result.stdout.splitlines()
                if "::" in line and "e2e/corpus/" in line.split("::")[0]]
    assert not reached, MSG_CORPUS.format("\n  ".join(reached))
    e2e = int(re.search(r"\be2e=(\d+)", done[-1]).group(1))
    assert e2e > 0, (
        "the corpus spy saw no file next to the corpus ({}): the walk never "
        "reached src/noworkflow/tests/e2e, so an empty report proves nothing. "
        "Check testpaths in pyproject.toml.".format(done[-1]))


def _module_file(module):
    try:
        return getattr(module, "__file__", None)
    except Exception:
        return None


def test_no_corpus_item_or_module_in_this_session(request):
    """In-process complement: no item of this session and no loaded module
    comes from the corpus

    Cheap, and meaningful in a full run, where the session holds every
    item; in a partial run it only covers what was collected, which is why
    the child-process test above is the premise. A module imported by a
    traced script is removed by the leak detector after its test, so one
    left here was imported by collection.
    """
    corpus = os.path.normcase(os.path.realpath(CORPUS)) + os.sep
    items = [item.nodeid for item in request.session.items
             if corpus_spy.is_corpus_path(item.path)]
    modules = []
    for name, module in list(sys.modules.items()):
        filename = _module_file(module)
        if filename and os.path.normcase(
                os.path.realpath(filename)).startswith(corpus):
            modules.append("module {} ({})".format(name, filename))
    assert not items and not modules, MSG_CORPUS.format(
        "\n  ".join(items + sorted(modules)))


# 9. The CI legs run the Python that uv downloads ------------------------------

WORKFLOWS = Path(".github") / "workflows"


def _top_level_env(text):
    """The ``KEY: value`` lines of a workflow's top-level ``env:`` block"""
    env, inside = {}, False
    for line in text.splitlines():
        if re.fullmatch(r"env:\s*", line):
            inside = True
        elif inside and line.strip() and not line.lstrip().startswith("#"):
            if not line.startswith(" "):
                inside = False
            else:
                key, _, value = line.strip().partition(":")
                env[key] = value.split("#")[0].strip().strip("'\"")
    return env


def test_every_workflow_that_installs_uv_requires_uv_managed_python(request):
    """Each workflow that runs setup-uv sets ``UV_MANAGED_PYTHON`` at the top

    Without it, uv takes a matching Python of the runner image before it
    downloads one, so which build a leg runs depends on the image and
    changes with it. The comments over the setup steps, the "Which
    interpreter each leg ran" check of the python-matrix skill and the
    parity with the reference container (.github/reference-leg/) rely on
    every job running python-build-standalone.
    """
    directory = request.config.rootpath / WORKFLOWS
    if not directory.is_dir():
        pytest.skip("{} is not here: the suite runs outside the checkout".format(
            WORKFLOWS.as_posix()))
    workflows = {path.name: path.read_text(encoding="utf-8")
                 for path in sorted(directory.glob("*.y*ml"))}
    with_uv = [name for name, text in workflows.items()
               if "astral-sh/setup-uv@" in text]
    assert "ci.yml" in with_uv, (
        "ci.yml no longer runs astral-sh/setup-uv: this premise looks for "
        "the workflows that install uv by that action. Point it at what "
        "installs uv now.")
    missing = [name for name in with_uv
               if _top_level_env(workflows[name]).get("UV_MANAGED_PYTHON") != "1"]
    assert not missing, (
        "{} run(s) astral-sh/setup-uv without UV_MANAGED_PYTHON: \"1\" in the "
        "top-level env: of the workflow, so a leg may run the runner image's "
        "Python instead of the one uv downloads. Add it, with the pointer to "
        "the comment in ci.yml (#264).".format(", ".join(missing)))


# 10. pip-audit reads a pylock.toml without its markers ------------------------

# One entry per kind of marker: none, one that holds on any Python 3, one
# that holds on no Python 3, one that holds on no platform.
AUDITED = (
    ("first", "1.0", None),
    ("second", "2.0", "python_version >= '3'"),
    ("third", "3.0", "python_version < '3'"),
    ("fourth", "4.0", "sys_platform == 'no-such-platform'"),
)
MSG_PYLOCK = (
    "pip-audit --locked collected {} from a pylock.toml whose entries are {}. "
    "The 'Audit Python dependencies' step of .github/workflows/ci.yml relies "
    "on --locked reading every entry, its marker not evaluated, so that the "
    "versions uv.lock keeps for other Python forks and platforms are audited "
    "too. Find how the installed pip-audit audits every fork, rewrite that "
    "step and its comment, and the pip-audit section of the dependencies "
    "skill (#225)."
)
MSG_REQUIREMENTS = (
    "pip-audit -r collected {} from a requirements file whose lines are {}, "
    "with the markers that hold on no Python 3 and on no platform. It used "
    "to skip them: if it no longer does, test_pip_audit_reads_every_entry_"
    "of_a_pylock no longer shows what the audit step of ci.yml gains from "
    "the pylock export; rewrite this control."
)


def _collected(source):
    """``{(name, version)}`` of what a pip-audit dependency source collects"""
    return {(dep.name, str(dep.version)) for dep in source.collect()}


def test_pip_audit_reads_every_entry_of_a_pylock(tmp_path):
    """``pip-audit --locked`` audits every entry of a PEP 751 lock

    The audit step of ci.yml exports uv.lock as a pylock.toml and audits
    it with ``--locked``. uv.lock keeps some packages at one version per
    Python fork, and some only on one platform, each entry with its
    environment marker; the step audits them all from one Linux runner on
    one Python because pip-audit reads the entries without evaluating their
    markers. Offline: collecting the dependencies queries nothing.
    """
    from pip_audit._dependency_source import PyLockSource

    lines = ['lock-version = "1.0"', 'created-by = "test"', ""]
    for name, version, marker in AUDITED:
        lines += ["[[packages]]", 'name = "{}"'.format(name),
                  'version = "{}"'.format(version)]
        if marker:
            lines.append('marker = "{}"'.format(marker))
        lines.append("")
    pylock = tmp_path / "pylock.toml"
    pylock.write_text("\n".join(lines), encoding="utf-8")
    expected = {(name, version) for name, version, _ in AUDITED}
    found = _collected(PyLockSource([pylock]))
    assert found == expected, MSG_PYLOCK.format(sorted(found), sorted(expected))


def test_pip_audit_skips_requirements_whose_marker_is_false(tmp_path):
    """Control: ``pip-audit -r`` skips the lines whose marker is false here

    The same entries as a requirements export, the form the audit step used
    before: only the lines whose marker holds on this interpreter are
    collected, so a requirements audit sees one fork. Without this, the
    premise above could pass on entries that every form of audit reads.
    """
    from pip_audit._dependency_source import RequirementSource

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("".join(
        "{}=={}{}\n".format(name, version,
                            " ; " + marker if marker else "")
        for name, version, marker in AUDITED), encoding="utf-8")
    found = _collected(RequirementSource(
        [requirements], no_deps=True, disable_pip=True))
    assert found == {("first", "1.0"), ("second", "2.0")}, (
        MSG_REQUIREMENTS.format(sorted(found), [
            line for line in requirements.read_text(
                encoding="utf-8").splitlines()]))


# 11. The warning filter of the suite ---------------------------------------------

MSG_WARNING_FILTER = (
    "A DeprecationWarning attributed to a noworkflow module no longer fails "
    "the test: filterwarnings in pyproject.toml must start with "
    "error::DeprecationWarning:noworkflow (#221)."
)
MSG_SA_EXCEPTION = (
    "SQLAlchemy's warning about the 2.0 API, attributed to a noworkflow "
    "module, was {}. While the SQLAlchemy pin keeps 1.4, filterwarnings in "
    "pyproject.toml lists default::sqlalchemy.exc.Base20DeprecationWarning "
    "after the error:: entry, so that SQLAlchemy's once-per-process warning "
    "does not fail whichever test reaches the first 1.4-only API (#221)."
)


def test_a_deprecation_that_noworkflow_triggers_fails_the_test():
    """A DeprecationWarning attributed to a noworkflow module is an error

    filterwarnings in pyproject.toml turns it into an exception, so the test
    whose code path reaches a deprecated API fails instead of adding a line
    to the warnings summary that nobody reads.
    """
    try:
        warnings.warn_explicit("probe", DeprecationWarning, "probe.py", 1,
                               module="noworkflow.probe")
    except DeprecationWarning as error:
        assert str(error) == "probe"
    else:
        pytest.fail(MSG_WARNING_FILTER)


def test_sqlalchemy_2_0_warnings_stay_warnings():
    """Control: SQLAlchemy's warnings about its 2.0 API stay warnings

    SQLAlchemy 1.4 emits one Base20DeprecationWarning per process, at the
    first use of an API that 2.0 removed, attributed to the module that
    used it: one of noWorkflow's, while the pin of premise 1 holds. The
    exception that follows the error entry keeps it a warning; without it
    the first such query of each process would fail its test.
    """
    with warnings.catch_warnings(record=True) as caught:
        try:
            warnings.warn_explicit(
                "probe", sqlalchemy.exc.MovedIn20Warning, "probe.py", 1,
                module="noworkflow.probe")
        except sqlalchemy.exc.MovedIn20Warning:
            pytest.fail(MSG_SA_EXCEPTION.format("raised"))
    categories = [warning.category for warning in caught]
    assert categories == [sqlalchemy.exc.MovedIn20Warning], (
        MSG_SA_EXCEPTION.format("not recorded: {}".format(categories)))
