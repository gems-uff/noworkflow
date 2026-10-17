# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Compare a normalized output with a stored golden file (pytest plugin)

``assert_golden(request, name, actual)`` compares ``actual`` with
``goldens/<module>/<test>/<name>.txt``. The goldens depend on the system and
on the Python version (module paths, the AST, argparse), so they belong to
one platform, the CI reference leg, written in ``goldens/REFERENCE``.

The ``GOLDEN`` environment variable selects the mode:

- unset: compare. A missing baseline is written and the test is skipped,
  so the next run compares (the first run of a new golden).
- ``overwrite`` (or ``--update-goldens``): write every baseline and pass;
  review the result with ``git diff``.
- ``require``: compare, and fail on a missing baseline. The reference leg
  runs with it, so a golden that nobody recorded cannot pass as a skip.

On any other platform the goldens are skipped, and ``require`` or
``overwrite`` fail with the command that runs them on the reference
platform. ``NOW_GOLDEN_DIR`` points the goldens elsewhere, for comparing two
versions of noWorkflow on one machine (the golden-run); the platform is not
checked then, because both sides run on the same machine.

When ``GOLDEN_ACTUAL_DIR`` is set, the actual output of every mismatch is
also written there, under the golden's relative path (CI uploads it).
"""
import ast
import difflib
import os
import re
import sys
from pathlib import Path

import pytest

E2E_DIR = Path(__file__).resolve().parent
REPOSITORY_GOLDENS = E2E_DIR / "goldens"
REFERENCE_NAME = "REFERENCE"
# Lowercase only: macOS and Windows file systems are case-insensitive, and
# two goldens that differ only in case would overwrite each other there.
NAME = re.compile(r"[a-z0-9][a-z0-9_.-]*")
MODES = ("", "overwrite", "require")
USED = pytest.StashKey[set]()
GOLDEN_ITEMS = pytest.StashKey[list]()
ORPHANS = pytest.StashKey[list]()
CONTAINER = ".github/reference-leg/run.sh"


def golden_dir():
    """Where the goldens are read and written"""
    custom = os.environ.get("NOW_GOLDEN_DIR")
    return Path(custom).resolve() if custom else REPOSITORY_GOLDENS


def current_platform():
    """``<sys.platform> <major>.<minor>``, as written in REFERENCE"""
    return "{} {}.{}".format(sys.platform, *sys.version_info[:2])


def reference_platform():
    """The platform the repository goldens were recorded on"""
    path = REPOSITORY_GOLDENS / REFERENCE_NAME
    return path.read_text(encoding="utf-8").strip()


def golden_mode(config):
    """The mode chosen by GOLDEN or --update-goldens"""
    if config.getoption("update_goldens"):
        return "overwrite"
    mode = os.environ.get("GOLDEN", "")
    if mode not in MODES:
        raise pytest.UsageError(
            "GOLDEN={!r}: expected one of overwrite, require or unset"
            .format(mode)
        )
    return mode


def golden_path(request, name):
    """``<golden dir>/<test module>/<test function>/<name>.txt``"""
    if not NAME.fullmatch(name):
        raise ValueError(
            "golden name {!r}: use lowercase letters, digits, '.', '_' and "
            "'-' only".format(name)
        )
    module = Path(request.node.path).stem
    function = request.node.originalname
    return golden_dir() / module / function / (name + ".txt")


def accept_command(request):
    """The command that rewrites this test's goldens on the reference
    platform, from any machine with Docker"""
    return "GOLDEN=overwrite {} '{}'".format(CONTAINER, request.node.nodeid)


def assert_golden(request, name, actual):
    """Compare ``actual`` with the golden ``name`` of the calling test"""
    if request.node.get_closest_marker("golden") is None:
        raise RuntimeError(
            "{} calls assert_golden without @pytest.mark.golden; the legs "
            "that deselect goldens (-m 'not golden') would run it"
            .format(request.node.nodeid)
        )
    config = request.config
    mode = golden_mode(config)
    path = golden_path(request, name)
    relative = path.relative_to(golden_dir()).as_posix()
    config.stash.setdefault(USED, set()).add(relative)

    if not os.environ.get("NOW_GOLDEN_DIR"):
        reference = reference_platform()
        if current_platform() != reference:
            message = (
                "goldens are recorded on {} and this is {}; run them in the "
                "reference container: GOLDEN={} {} -m golden".format(
                    reference, current_platform(), mode or "require",
                    CONTAINER,
                )
            )
            if mode:
                pytest.fail(message, pytrace=False)
            pytest.skip(message)

    if mode == "overwrite":
        write(path, actual)
        return
    if not path.exists():
        if mode == "require":
            pytest.fail(
                "golden {} does not exist (GOLDEN=require). Record it with: "
                "{}".format(relative, accept_command(request)),
                pytrace=False,
            )
        write(path, actual)
        pytest.skip("golden {} recorded; run again to compare".format(relative))

    expected = path.read_text(encoding="utf-8")
    if actual == expected:
        return
    actual_dir = os.environ.get("GOLDEN_ACTUAL_DIR")
    if actual_dir:
        write(Path(actual_dir) / relative, actual)
    diff = "".join(difflib.unified_diff(
        expected.splitlines(keepends=True), actual.splitlines(keepends=True),
        "golden/" + relative, "actual",
    ))
    pytest.fail(
        "the output differs from golden {}:\n{}\nIf the change is intended, "
        "rewrite it on the reference platform and review `git diff`:\n  {}"
        .format(relative, diff, accept_command(request)),
        pytrace=False,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def golden_functions():
    """``{(module stem, function name)}`` of the e2e tests marked golden

    Read from the source, so the answer does not depend on which tests the
    current run selected.
    """
    found = set()
    for path in sorted(E2E_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if any(ast.unparse(decorator).endswith("mark.golden")
                   for decorator in node.decorator_list):
                found.add((path.stem, node.name))
    return found


def stored_goldens(directory=None):
    """Relative paths of every golden file, REFERENCE excluded"""
    directory = directory or golden_dir()
    if not directory.exists():
        return []
    return sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*.txt")
    )


def pytest_addoption(parser):
    parser.addoption(
        "--update-goldens", action="store_true", default=False,
        help="rewrite the golden files of the e2e tests (same as "
             "GOLDEN=overwrite)",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(session, config, items):
    """Remember the golden tests before -m and -k deselect any of them"""
    config.stash[GOLDEN_ITEMS] = [
        (item.nodeid, Path(item.path).stem, item.originalname)
        for item in items
        if item.get_closest_marker("golden") is not None
    ]


def orphan_goldens(config, reporter):
    """Stored goldens that no test reads, as relative paths

    A directory whose test function no longer exists is an orphan in any
    run. A file under an existing function is an orphan only when every
    collected item of that function ran in this session (a skipped or
    deselected parameter may be the one that reads it) and none read it.
    """
    stored = stored_goldens()
    if not stored:
        return []
    functions = golden_functions()
    ran = {
        report.nodeid
        for key in ("passed", "failed", "xfailed", "xpassed")
        for report in reporter.stats.get(key, [])
        if getattr(report, "when", "call") == "call"
    }
    items = {}
    for nodeid, module, function in config.stash.get(GOLDEN_ITEMS, []):
        items.setdefault((module, function), []).append(nodeid)
    complete = {key for key, nodeids in items.items()
                if all(nodeid in ran for nodeid in nodeids)}
    used = config.stash.get(USED, set())
    orphans = []
    for path in stored:
        parts = path.split("/")
        key = tuple(parts[:2])
        if len(parts) != 3 or key not in functions:
            orphans.append(path)
        elif key in complete and path not in used:
            orphans.append(path)
    return orphans


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Fail a GOLDEN=require session that leaves orphan goldens"""
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None or os.environ.get("NOW_GOLDEN_DIR"):
        return
    orphans = orphan_goldens(session.config, reporter)
    session.config.stash[ORPHANS] = orphans
    if orphans and golden_mode(session.config) == "require":
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """List the orphan goldens found at the end of the session"""
    orphans = config.stash.get(ORPHANS, [])
    if not orphans:
        return
    terminalreporter.section("GOLDENS", sep="=", yellow=True)
    terminalreporter.write_line(
        "{} golden file(s) that no test reads; remove them (a failure "
        "under GOLDEN=require):".format(len(orphans)))
    for path in orphans:
        terminalreporter.write_line(
            "  git rm {}".format((golden_dir() / path).as_posix()))
