# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The example scripts of the repository still run on the supported Pythons

``Examples/`` holds the scripts that the README and the tutorials point
users to, and ``tests/weather`` (at the root) and ``resources/demo`` the
scripts that ``now demo`` and older tutorials run. Ruff skips all of them
(``extend-exclude``), and nothing else in the suite compiles them, so a
construct that a new Python removes, or a mode that ``open`` stopped
accepting, would reach the user first.

Every script of ``Examples/`` must compile on this interpreter with warnings
as errors (an invalid escape warns today and is an error in a future
Python) and parse with the grammar of the oldest supported Python, read
from ``requires-python``. The ``open`` modes written as constants in the
three directories are checked with Python's own ``open``, which validates a
mode before it touches the file system. The files are read from the
checkout (``request.config.rootpath``); outside one the tests skip.

The root ``tests/`` is not compiled: ``tests/t1.py`` is Python 2.
"""
import ast
import re
import sys
import tomllib
import warnings

import pytest

from noworkflow.tests.helpers.defects import Defect, known_defects

EXAMPLES = "Examples"
# The directories whose open modes are scanned.
MODE_DIRECTORIES = ("Examples", "tests/weather", "src/noworkflow/resources/demo")
# The scripts of Examples/ today, so that a moved directory cannot leave
# the compile check with nothing to compile.
KNOWN_EXAMPLES = {
    "Examples/Fat/fat.py",
    "Examples/demo_1/simulation.py",
    "Examples/demo_1/simulation_complete.py",
    "Examples/demo_1/simulator.py",
}
# The constant modes that open() rejects today (#208).
RU_REJECTED = {
    ("Examples/demo_1/simulation.py", "rU"),
    ("Examples/demo_1/simulation_complete.py", "rU"),
    ("tests/weather/simulation.py", "rU"),
    ("tests/weather/simulation_complete.py", "rU"),
}
# A statement that each Python version introduced. The control of the
# compile check takes the one of the version right after the floor.
NEWER_SYNTAX = {
    (3, 12): b"type X = int\n",  # PEP 695
    (3, 13): b"def f[T = int](): pass\n",  # PEP 696
    (3, 14): b"try:\n    pass\nexcept A, B:\n    pass\n",  # PEP 758
}
RU_MODE = Defect(
    reason="#208: Examples/demo_1/simulation*.py and "
           "tests/weather/simulation*.py open their input with mode 'rU', "
           "which Python 3.11 removed (ValueError: invalid mode: 'rU')",
    signature="invalid mode: 'rU'",
)


def scripts(root, directory):
    """The ``*.py`` files under ``root/directory``, hidden ones left out"""
    base = root / directory
    return sorted(path for path in base.rglob("*.py")
                  if not any(part.startswith(".")
                             for part in path.relative_to(base).parts))


def relative(root, path):
    return path.relative_to(root).as_posix()


@pytest.fixture
def root(request):
    """The checkout, or skip when the example directories are not there"""
    rootpath = request.config.rootpath
    missing = [directory for directory in MODE_DIRECTORIES
               if not (rootpath / directory).is_dir()]
    if missing:
        pytest.skip("not a checkout: no {}".format(", ".join(missing)))
    return rootpath


def floor_version(root):
    """``(major, minor)`` of the oldest Python that ``requires-python``
    admits"""
    with open(root / "pyproject.toml", "rb") as handle:
        requires = tomllib.load(handle)["project"]["requires-python"]
    match = re.fullmatch(r"\s*>=\s*(\d+)\.(\d+)\s*", requires)
    assert match, "requires-python is not a lower bound: {}".format(requires)
    return int(match.group(1)), int(match.group(2))


def compile_error(source, filename, floor):
    """Why ``source`` does not compile here with warnings as errors, or
    does not parse with the grammar of ``floor``; None when it does both
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            compile(source, filename, "exec", dont_inherit=True)
            ast.parse(source, filename, feature_version=floor)
        except (SyntaxError, Warning) as error:
            return "{}: {}".format(type(error).__name__, error)
    return None


def mode_error(directory, mode):
    """The ``ValueError`` that ``open`` raises for ``mode``, or None

    The file is under a directory that does not exist, so a valid mode
    fails with ``FileNotFoundError`` before anything is created.
    """
    try:
        with open(directory / "missing" / "file", mode):
            pass
    except ValueError as error:
        return str(error)
    except FileNotFoundError:
        return None
    raise AssertionError("opened a file under a missing directory")


def constant_modes(source, filename):
    """``[(line, mode)]`` of the ``open`` and ``io.open`` calls whose mode
    is a string constant, positional or ``mode=``"""
    found = []
    for node in ast.walk(ast.parse(source, filename)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_open = (isinstance(func, ast.Name) and func.id == "open") or (
            isinstance(func, ast.Attribute) and func.attr == "open"
            and isinstance(func.value, ast.Name) and func.value.id == "io")
        if not is_open:
            continue
        modes = [node.args[1]] if len(node.args) > 1 else []
        modes += [keyword.value for keyword in node.keywords
                  if keyword.arg == "mode"]
        for mode in modes:
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
                found.append((node.lineno, mode.value))
    return found


def rejected_modes(root, scratch):
    """``(modes found, {(path, mode): [messages]})`` of the constant modes
    in ``MODE_DIRECTORIES`` that ``open`` rejects"""
    found = 0
    rejected = {}
    for directory in MODE_DIRECTORIES:
        for path in scripts(root, directory):
            name = relative(root, path)
            for line, mode in constant_modes(path.read_bytes(), name):
                found += 1
                error = mode_error(scratch, mode)
                if error is not None:
                    rejected.setdefault((name, mode), []).append(
                        "{}:{}: {}".format(name, line, error))
    return found, rejected


def test_every_example_compiles_and_parses_at_the_floor_grammar(root):
    """Every script of ``Examples/`` compiles on this Python with warnings
    as errors and parses with the grammar of the oldest supported Python
    """
    floor = floor_version(root)
    paths = scripts(root, EXAMPLES)
    names = {relative(root, path) for path in paths}
    assert KNOWN_EXAMPLES <= names
    failures = {}
    for path in paths:
        error = compile_error(path.read_bytes(), relative(root, path), floor)
        if error is not None:
            failures[relative(root, path)] = error
    assert failures == {}


def test_the_compile_check_rejects_newer_syntax_and_invalid_escapes(root):
    """Control: the check rejects, at the floor grammar, a statement that
    the next Python introduced, which that Python's grammar accepts, and an
    invalid escape; it accepts plain code
    """
    floor = floor_version(root)
    newer = (floor[0], floor[1] + 1)
    assert newer in NEWER_SYNTAX, (
        "NEWER_SYNTAX needs a statement that Python {}.{} introduced"
        .format(*newer))
    source = NEWER_SYNTAX[newer]
    assert compile_error(b"x = 1\n", "plain.py", floor) is None
    assert compile_error(source, "newer.py", floor) is not None
    if sys.version_info[:2] >= newer:
        # Not vacuous: this Python compiles the statement, so the floor's
        # grammar is what rejects it.
        assert compile_error(source, "newer.py", newer) is None
    assert compile_error(b'x = "\\d"\n', "escape.py", floor) is not None


def test_the_open_mode_check_tells_valid_from_invalid_modes(tmp_path):
    """Control: ``open`` rejects ``rU``, ``U``, ``rbU`` and ``q`` with
    ``ValueError`` and accepts the usual modes, creating nothing
    """
    assert [mode for mode in ("rU", "U", "rbU", "q")
            if mode_error(tmp_path, mode) is None] == []
    assert [mode for mode in ("r", "w", "x", "a+", "rb", "r+b")
            if mode_error(tmp_path, mode) is not None] == []
    assert list(tmp_path.iterdir()) == []


def test_example_scripts_open_modes(root, tmp_path):
    """The only constant ``open`` modes that Python rejects in the example
    scripts are the four ``'rU'`` of ``Examples/demo_1`` and the root
    ``tests/weather``

    Characterization of #208.
    """
    found, rejected = rejected_modes(root, tmp_path)
    # Not vacuous: the scripts open files with constant modes.
    assert found > len(RU_REJECTED)
    assert set(rejected) == RU_REJECTED, rejected


@known_defects(RU_MODE)
def test_example_scripts_open_modes_desired(root, tmp_path):
    """Every constant ``open`` mode of the example scripts is one that
    Python accepts
    """
    _, rejected = rejected_modes(root, tmp_path)
    messages = [message for found in rejected.values() for message in found]
    assert messages == [], "\n".join(messages)
