# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Run ``now`` as a process on a real store (pytest plugin)

Registered through ``pytest_plugins`` in the root ``conftest.py``. Every test
gets a project directory under ``tmp_path``, a temporary home and a
synthetic environment, so that what the store records (the environment, the
user, the paths) is the same on every machine except for what
``normalize`` masks.

``NOW_E2E_CMD`` replaces the command, for running the same tests against
another installation (the golden-run compares two versions of noWorkflow
this way); point it at an installed ``now``, not at ``uvx``/``uv run``,
which would start from an empty cache in each test's temporary home.
"""
import contextlib
import dataclasses
import hashlib
import os
import shlex
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from .normalize import Normalizer

E2E_DIR = Path(__file__).resolve().parent
CORPUS = E2E_DIR / "corpus"

# Environment variables kept from the parent: coverage of the child
# (``COVERAGE_PROCESS_CONFIG``, set by ``[tool.coverage.run] patch``) and the
# environment a ``NOW_E2E_CMD`` based on uv may need.
PRESERVE_PREFIXES = ("COVERAGE_", "COV_CORE_")
PRESERVE = ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")
# Windows cannot start Python without SYSTEMROOT (sockets fail), and
# ``shell=True`` needs COMSPEC.
WINDOWS_KEEP = ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "PATHEXT", "COMSPEC",
                "PROGRAMDATA")
# Never forwarded, on purpose: PYTHONWARNINGS, PYTHONWARNDEFAULTENCODING
# (set by the Windows experimental legs) and PYTHONDEVMODE print warnings
# on stderr, PYTHONPATH and PYTHONSTARTUP change what runs, FORCE_COLOR
# colors argparse and tracebacks, LANG and LC_* change the recorded
# environment.
USER = "nowtest"
# Directories and files of a project that are not the user's files.
NOT_PROJECT_FILES = (".noworkflow", ".last_trial", "__pycache__")


def now_command():
    """The command that runs ``now``: NOW_E2E_CMD, or this interpreter

    The executable is resolved here, in the parent: on Windows the child's
    PATH is not used to find it.
    """
    custom = os.environ.get("NOW_E2E_CMD")
    if not custom:
        return [sys.executable, "-m", "noworkflow"]
    parts = shlex.split(custom, posix=os.name != "nt")
    if os.name == "nt":
        # Non-POSIX shlex keeps the quotes that protect a path with spaces.
        parts = [part[1:-1] if len(part) > 1 and part[0] == part[-1] == '"'
                 else part for part in parts]
    # Absolute: the child runs in the project directory.
    parts[0] = os.path.abspath(shutil.which(parts[0]) or parts[0])
    return parts


def runs_this_interpreter(command=None):
    """Whether ``now`` runs on the interpreter that runs the tests

    False under a ``NOW_E2E_CMD`` that points at another installation, where
    what this process can import or which version it is says nothing about
    the child.
    """
    return list(command or NOW_CMD)[:3] == [sys.executable, "-m", "noworkflow"]


NOW_CMD = now_command()


def clean_env(home, tmp, command=None):
    """The environment of every ``now`` the harness runs

    Built from scratch: the store records the whole environment, and a
    developer's variables would reach it, change the stderr (warnings) or
    change the output (COLUMNS, colors, the hash seed). ``PATH`` is
    synthetic: the directory of the command (never resolved: ``.venv/bin``
    holds ``now``, the interpreter's real directory does not), the system
    directories that ``platform`` and ``sh`` need, and git's.
    """
    command = command or NOW_CMD
    path = [os.path.dirname(command[0])]
    if os.name == "nt":
        root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        path += [os.path.join(root, "System32"), root]
    else:
        path += ["/usr/bin", "/bin", "/usr/local/bin"]
    git = shutil.which("git")
    if git:
        path.append(os.path.dirname(git))
    home, tmp = str(home), str(tmp)
    env = {
        "PATH": os.pathsep.join(dict.fromkeys(path)),
        "HOME": home,
        "USERPROFILE": home,
        # getpass.getuser() reads LOGNAME first and falls back to the
        # password database, which would record the real login.
        "USER": USER,
        "LOGNAME": USER,
        "USERNAME": USER,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        # The order of `now diff` blocks and of DOT attributes in `now export
        # dataflow` comes from sets of strings.
        "PYTHONHASHSEED": "0",
        # argparse wraps the help at the terminal width.
        "COLUMNS": "100",
        "NO_COLOR": "1",
        "PYTHON_COLORS": "0",
        "TMPDIR": tmp,
        "TEMP": tmp,
        "TMP": tmp,
    }
    if os.name == "nt":
        env.update({key: os.environ[key] for key in WINDOWS_KEEP
                    if key in os.environ})
        env["APPDATA"] = os.path.join(home, "AppData", "Roaming")
        env["LOCALAPPDATA"] = os.path.join(home, "AppData", "Local")
    for key, value in os.environ.items():
        if key.startswith(PRESERVE_PREFIXES) or key in PRESERVE:
            env[key] = value
    return env


@dataclasses.dataclass
class Result:
    """What a ``now`` invocation returned"""

    args: list
    returncode: int
    stdout: str
    stderr: str

    def __str__(self):
        return (
            "$ now {}\nreturn code: {}\n--- stdout ---\n{}\n--- stderr ---\n{}"
            .format(" ".join(self.args), self.returncode,
                    tail(self.stdout), tail(self.stderr))
        )


def last_line(text):
    """The last non-blank line of an output, without trailing spaces"""
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def same_path(stored, expected):
    """Whether a path noWorkflow stored names ``expected``

    noWorkflow stores real paths (on macOS the temporary directories are
    symlinks: /var -> /private/var); Windows compares paths without case.
    """
    return (os.path.normcase(os.path.realpath(str(stored)))
            == os.path.normcase(os.path.realpath(str(expected))))


def tail(text, lines=40):
    """The last lines of a long output, for assertion messages"""
    parts = text.splitlines()
    if len(parts) <= lines:
        return text
    return "[... {} lines ...]\n".format(len(parts) - lines) + "\n".join(
        parts[-lines:])


class NowProject:
    """A project directory, its store and the ``now`` that runs on it"""

    def __init__(self, root, command=None):
        root = Path(root)
        self.root = root
        self.path = root / "project"
        self.home = root / "home"
        self.tmp = root / "tmp"
        for directory in (self.path, self.home, self.tmp):
            directory.mkdir(parents=True, exist_ok=True)
        self.command = list(command or NOW_CMD)
        self.env = clean_env(self.home, self.tmp, self.command)
        self.normalize = Normalizer([
            ("<PROJECT>", self.path),
            ("<HOME>", self.home),
            ("<TMP>", self.tmp),
            ("<ROOT>", self.root),
        ])

    @property
    def store(self):
        return self.path / ".noworkflow"

    def run(self, *args, expect=0, allow_stderr=False, cwd=None, timeout=120):
        """Run ``now <args>`` in the project and check its outcome

        ``expect`` is the return code (``None`` accepts any); stderr must be
        empty unless ``allow_stderr``. The output is decoded as UTF-8 with
        universal newlines.
        """
        args = [str(arg) for arg in args]
        completed = subprocess.run(
            self.command + args,
            cwd=str(cwd or self.path),
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        result = Result(args, completed.returncode, completed.stdout,
                        completed.stderr)
        if expect is not None:
            assert result.returncode == expect, (
                "expected return code {}\n{}".format(expect, result))
        if not allow_stderr:
            assert result.stderr == "", "expected an empty stderr\n{}".format(
                result)
        return result

    def copy_corpus(self, name):
        """Copy ``corpus/<name>`` into the project, keeping the file modes"""
        shutil.copytree(
            CORPUS / name, self.path, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    def write(self, name, text):
        """Write a project file with LF line ends on every system"""
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    @contextlib.contextmanager
    def db(self):
        """A read-only connection to the store's SQLite file

        Closed on exit: an open handle keeps Windows from removing
        ``tmp_path`` and can make the next ``now`` find the database locked.
        """
        path = self.store / "db.sqlite"
        assert path.exists(), "no provenance store in {}".format(self.path)
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def query(self, sql, *params):
        """Rows of a query on the store, as dicts"""
        with self.db() as connection:
            return [dict(row) for row in connection.execute(sql, params)]

    def trials(self):
        """Every trial, in the order they ran"""
        return self.query("SELECT * FROM trial ORDER BY sequence_key")

    def trial(self, ref):
        """The trial a reference names: its id, a tag or its sequence key"""
        rows = self.query(
            "SELECT DISTINCT trial.* FROM trial "
            "LEFT JOIN tag ON tag.trial_id = trial.id "
            "WHERE trial.id = ? OR tag.name = ? OR trial.sequence_key = ?",
            str(ref), str(ref), str(ref),
        )
        assert len(rows) == 1, "trial {!r}: {} matches".format(ref, len(rows))
        return rows[0]

    def tags(self, trial_id):
        return self.query(
            "SELECT type, name FROM tag WHERE trial_id = ? ORDER BY id",
            trial_id)

    def count(self, table, trial_id):
        """Rows of ``table`` that belong to a trial"""
        tables = {row["name"] for row in self.query(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert table in tables, "no table {!r} in the store".format(table)
        return self.query(
            'SELECT COUNT(*) AS n FROM "{}" WHERE trial_id = ?'.format(table),
            trial_id)[0]["n"]

    def content(self, content_hash):
        """The bytes the plain content engine stored under a hash

        A new store uses a git engine when pygit2 or dulwich is importable
        (``persistence/content_database.py``); ``uv.lock`` has neither, but a
        ``NOW_E2E_CMD`` installation may.
        """
        path = self.store / "content" / content_hash[:2] / content_hash[2:]
        if not path.exists() and not (self.store / "content").is_dir():
            pytest.skip("the store does not use the plain content engine")
        return path.read_bytes()

    def files(self):
        """``{path: sha1}`` of the project files, the store excluded

        Paths use ``/`` on every system, so the result compares across
        systems; the hash is the one noWorkflow records.
        """
        result = {}
        for path in sorted(self.path.rglob("*")):
            relative = path.relative_to(self.path)
            if any(part in NOT_PROJECT_FILES for part in relative.parts):
                continue
            if path.is_file():
                result[relative.as_posix()] = sha1(path.read_bytes())
        return result

    def fingerprint(self):
        """Hashes of the store and of the project, to detect a change"""
        store = {}
        for path in sorted(self.store.rglob("*")):
            if path.is_file():
                store[path.relative_to(self.store).as_posix()] = sha1(
                    path.read_bytes())
        return store, self.files()


def sha1(data):
    return hashlib.sha1(data).hexdigest()


# `now export ast` fails on recent Pythons (models/ast/trial_ast.py). From
# 3.14, ast.parse() validates the tree that noWorkflow rebuilds from the
# store, whose statements have no lineno: the text and -j forms fail. From
# 3.15, AST constructors reject unknown keywords and the rebuild calls
# ast.Module(name=...): every form fails, before reaching ast.parse().
EXPORT_AST_PY314 = (
    "#241: from Python 3.14 ast.parse() validates the tree "
    "rebuilt by models/ast/trial_ast.py, whose statements have no lineno "
    "(TypeError: required field \"lineno\" missing from stmt)"
)
EXPORT_AST_PY315 = (
    "#241: from Python 3.15 AST constructors reject unknown "
    "keywords, and models/ast/trial_ast.py builds ast.Module(name=...) "
    "(also ast.Yield(ctx=...))"
)
EXPORT_AST_FORMS = {"text": (), "json": ("-j",), "dot": ("-d",)}


def export_ast_failure(form, version=None):
    """Why ``now export ast`` fails in ``form`` on a Python version, or None

    ``form`` is a key of EXPORT_AST_FORMS; ``version`` defaults to this
    interpreter's ``(major, minor)``.
    """
    version = tuple(version or sys.version_info[:2])
    if version >= (3, 15):
        return EXPORT_AST_PY315
    if version >= (3, 14) and form != "dot":
        return EXPORT_AST_PY314
    return None


# Trial 2 changes the last row of data2.dat, so `now diff` has content.
WEATHER_ARGS = ("run", "simulation.py", "data1.dat", "data2.dat")
WEATHER_DATA2_TRIAL2 = "2.0:0.1\n1.5:0.3\n0.5:0.0\n4.0:2.0\n"


def build_weather(project, trials=1):
    """Copy the weather corpus and run it ``trials`` times (1 or 2)"""
    project.copy_corpus("weather")
    project.run(*WEATHER_ARGS)
    if trials > 1:
        project.write("data2.dat", WEATHER_DATA2_TRIAL2)
        project.run(*WEATHER_ARGS)
    return project


@pytest.fixture
def project(tmp_path):
    """An empty project with its own home, temporary directory and env"""
    return NowProject(tmp_path)


@pytest.fixture
def weather_project(project):
    """The weather corpus after one ``now run``, in this test's project"""
    return build_weather(project)


@pytest.fixture(scope="session")
def _two_trial_store(tmp_path_factory):
    return build_weather(NowProject(tmp_path_factory.mktemp("two_trials")),
                         trials=2)


@pytest.fixture
def two_trial_project(_two_trial_store):
    """The weather corpus after two runs, shared by the tests: read-only

    Built once per session, because a store cannot be copied (it records
    absolute paths). A test that changes the store or the project files
    fails here; build your own with ``build_weather(project, trials=2)``.
    Besides ``run`` and ``restore``, commands that build a trial's graphs
    write to the store: ``now diff -a`` and ``-d`` cache trees there.
    """
    before = _two_trial_store.fingerprint()
    yield _two_trial_store
    assert _two_trial_store.fingerprint() == before, (
        "the test changed the shared two-trial store or its project files; "
        "use build_weather(project, trials=2) for a store of its own")


@pytest.fixture(scope="session")
def console_now():
    """The ``now`` console script next to this interpreter, or skip

    ``now demo`` re-runs ``sys.argv[0]`` through the shell, so it only
    works through the console script, never through ``python -m``.
    """
    found = shutil.which("now", path=os.path.dirname(sys.executable))
    if not found:
        pytest.skip("the `now` console script is not installed next to "
                    "{}".format(sys.executable))
    return [found]
