# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""A failing test never prints this machine's hostname

A trial's repr (its Prolog fact) ends with ``user_id``,
``<hostname>\\<login>``, and pytest's report of a failure prints the reprs
of frame arguments, assertion operands, chained exceptions and captured
output. The root ``conftest.py`` masks the hostname in every report
(``helpers/reports.py``).

The property is checked end to end: a child pytest under a copy of the
root conftest runs tests that fail on purpose while a trial of the real
two-trial store (``connected_two_trials``) is within reach of the report,
in each way the suite's own tests can hold one: the argument of a helper
that raises, the operand of a failed assertion, the message of
``NowProject.run`` with an output that names the host, captured output, a
fixture that fails in its setup, a ``unittest`` method, and a ``_desired``
twin of ``known_defects`` that crashes (a chained traceback) or asserts.
The twins only print under ``--runxfail``, so the child runs with and
without it. The output must not hold the hostname, read as
``test_normalize.py`` reads it (``socket.gethostname()``); it must still
show what makes a report useful (the message, the chained cause), and
each report must hold the placeholder where the trial was, so that a
vector that stopped reaching the report cannot pass for a masked one. A
test module that fails to import is a report of its own, a collection's,
and is checked the same way. The hostname never goes into a message: the
checks are counts.

The mask itself is checked on every traceback style pytest renders, with
an invented hostname.
"""

import getpass
import re
import socket
import sys
from pathlib import Path

import pytest

from .e2e.normalize import usable_hostname
from .helpers.child_pytest import run_child_pytest
from .helpers.reports import (
    HOSTNAME_RULES,
    PLACEHOLDER,
    hostname_rules,
    mask,
    mask_report,
)

MARK = "report-368"

HOLDS_A_TRIAL = """\
import unittest

import pytest

from noworkflow.now.persistence.models import Trial
from noworkflow.tests.helpers.defects import Defect, known_defects

MARK = "{mark}"


def first_trial(project):
    return Trial(project.trials()[0]["id"])


def fails_holding(trial, vector):
    raise ValueError("{{}} {{}}".format(MARK, vector))


def test_frame_arguments(connected_two_trials):
    fails_holding(first_trial(connected_two_trials), "frame-arguments")


def test_assertion_operand(connected_two_trials):
    assert first_trial(connected_two_trials).sequence_key == -368


def test_harness_message(connected_two_trials):
    # The PROV document names the user, and the user's id the host.
    connected_two_trials.run("export", "prov", expect=-368)


def test_captured_output(connected_two_trials):
    print(first_trial(connected_two_trials))
    fails_holding(None, "captured-output")


@pytest.fixture
def broken(connected_two_trials):
    fails_holding(first_trial(connected_two_trials), "fixture-setup")


def test_fixture_setup(broken):
    pass


class TestMethod(unittest.TestCase):

    @pytest.fixture(autouse=True)
    def store(self, connected_two_trials):
        self.project = connected_two_trials

    def test_unittest_method(self):
        fails_holding(first_trial(self.project), "unittest-method")


@known_defects(Defect("#368: a deliberate crash", "ValueError: " + MARK))
def test_twin_crash_desired(connected_two_trials):
    fails_holding(first_trial(connected_two_trials), "twin-crash")


@known_defects(Defect("#368: a deliberate assertion", MARK))
def test_twin_assertion_desired(connected_two_trials):
    check_status(first_trial(connected_two_trials))


def check_status(trial):
    assert trial.status == MARK, MARK + " twin-assertion"
""".format(mark=MARK)

# Each failure the child reports: the title of its section, and the text
# that shows the report is still useful.
REPORTS = {
    "test_frame_arguments": MARK + " frame-arguments",
    "test_assertion_operand": "assert 1 == -368",
    "test_harness_message": "expected return code -368",
    "test_captured_output": MARK + " captured-output",
    "ERROR at setup of test_fixture_setup": MARK + " fixture-setup",
    "TestMethod.test_unittest_method": MARK + " unittest-method",
}
TWIN_REPORTS = {
    "test_twin_crash_desired": "direct cause of the following exception",
    "test_twin_assertion_desired": MARK + " twin-assertion",
}
SECTION = re.compile(r"^_{3,} (.+?) _{3,}$", re.MULTILINE)


def searchable_hostnames(request, tmp_path):
    """This machine's hostname and its first label, or skip

    Skips when no name is long and specific enough to search for, or when
    a piece of one is part of a path or a name that the child prints
    anyway (its temporary directory, the home directory, the login, the
    interpreter and the checkout), where it would be counted as a leak.
    """
    host = socket.gethostname()
    names = [name for name in {host, host.split(".")[0]} if usable_hostname(name)]
    if not names:
        pytest.skip(
            "this machine's hostname is too short or too generic "
            "to search for (normalize.usable_hostname)"
        )
    try:
        login = getpass.getuser()
    except (KeyError, OSError):  # no login name for this uid (a container)
        login = ""
    printed = " ".join(
        (
            str(tmp_path),
            str(Path.home()),
            login,
            sys.prefix,
            sys.base_prefix,
            str(request.config.rootpath),
        )
    )
    if occurrences(names, printed):
        pytest.skip(
            "this machine's hostname is part of a path or a name "
            "that a report prints anyway"
        )
    return names


def pieces(name, size=12):
    """The pieces of ``size`` characters of ``name``, or the whole name"""
    if len(name) <= size:
        return {name.lower()}
    return {name[index : index + size].lower() for index in range(len(name) - size + 1)}


def occurrences(names, text):
    """How many times a piece of ``names`` appears in ``text``, in any case

    A piece of twelve characters, so that what is left where pytest cut a
    long hostname counts too, or a whole name when it is shorter.
    """
    lower = text.lower()
    found = set().union(*(pieces(name) for name in names))
    return sum(lower.count(piece) for piece in found)


def sections(output):
    """``{title: body}`` of the failure sections of a pytest report"""
    found = {}
    marks = list(SECTION.finditer(output))
    for index, match in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(output)
        found[match.group(1)] = output[match.end() : end]
    return found


def child_output(result, tmp_path):
    """Everything the child printed, also kept in a file for whoever
    investigates a failure here; never printed"""
    output = result.stdout + result.stderr
    saved = tmp_path / "child-output.txt"
    saved.write_text(output, encoding="utf-8")
    return output, saved


@pytest.mark.parametrize("runxfail", [False, True], ids=["plain", "runxfail"])
def test_a_failing_test_that_holds_a_trial_never_prints_the_hostname(
    request, tmp_path, runxfail
):
    """The child's report names no host, and still says what failed"""
    names = searchable_hostnames(request, tmp_path)
    args = ["--runxfail"] if runxfail else []
    result = run_child_pytest(request, tmp_path, HOLDS_A_TRIAL, args=args)
    output, saved = child_output(result, tmp_path)
    expected = dict(REPORTS, **(TWIN_REPORTS if runxfail else {}))
    found = sections(output)
    missing = sorted(set(expected) - set(found))
    assert not missing, "no report for {} (the child's output is in {})".format(
        missing, saved
    )
    useless = sorted(
        title for title, text in expected.items() if text not in found[title]
    )
    assert not useless, "reports without their message: {} (see {})".format(
        useless, saved
    )
    count = occurrences(names, output)
    per_report = {
        title: occurrences(names, text)
        for title, text in found.items()
        if occurrences(names, text)
    }
    assert count == 0, (
        "the child's output names this machine's hostname {} time(s), per "
        "report {}; see {}, never paste it".format(count, per_report, saved)
    )
    unmasked = sorted(title for title in expected if PLACEHOLDER not in found[title])
    assert not unmasked, (
        "reports where no trial was masked, so the test no longer holds "
        "one there: {} (see {})".format(unmasked, saved)
    )


COLLECTION_ERROR = """\
import socket

raise RuntimeError("collected on " + socket.gethostname())
"""


@pytest.mark.parametrize("args", [(), ("--pdb",)], ids=["plain", "pdb"])
def test_a_collection_error_never_prints_the_hostname(request, tmp_path, args):
    """A test module that fails to import is reported masked as well,
    also by ``--pdb``, which prints the report before
    ``pytest_collectreport`` (the child's stdin is empty, so the debugger
    quits at once)"""
    names = searchable_hostnames(request, tmp_path)
    result = run_child_pytest(request, tmp_path, COLLECTION_ERROR, args=args)
    output, saved = child_output(result, tmp_path)
    count = occurrences(names, output)
    assert count == 0, (
        "the child's output names this machine's hostname {} time(s); see "
        "{}, never paste it".format(count, saved)
    )
    assert "collected on " + PLACEHOLDER in output, (
        "the message is not in the report (see {})".format(saved)
    )


FAKE_HOST = "fakehost-368.example.org"
FAKE_RULES = hostname_rules(FAKE_HOST)
# Shaped like the hostnames of GitHub's macOS runners (test_normalize.py),
# long enough for pytest to cut it inside a repr.
LONG_HOST = "iad20-eo1214-1524f517-96a6-4d74-9157-c1ff51b279a0-56481D34DF8F.local"


def holds(argument):
    raise ValueError("raised by holds() with " + argument)


def wraps(argument):
    try:
        holds(argument)
    except ValueError as error:
        raise RuntimeError("raised by wraps() with " + argument) from error


def failure_holding_the_fake_host():
    try:
        wraps("user " + FAKE_HOST + "\\nowtest")
    except RuntimeError:
        return pytest.ExceptionInfo.from_current()
    raise AssertionError("wraps() did not raise")


@pytest.mark.parametrize("style", ["long", "short", "line", "native", "value", "no"])
def test_mask_reaches_every_traceback_style(style):
    """Arguments, locals, messages and the chained cause are masked in
    every style, and what is not the hostname stays"""
    longrepr = failure_holding_the_fake_host().getrepr(
        style=style, funcargs=True, showlocals=True, chain=True
    )
    assert FAKE_HOST in str(longrepr), "the style does not show the host"
    text = str(mask(longrepr, FAKE_RULES))
    assert occurrences([FAKE_HOST], text) == 0, text
    assert "raised by wraps() with user {}\\nowtest".format(PLACEHOLDER) in text, text


def cut_by_pytest(head, tail):
    """A frame's arguments, which pytest cuts in the middle when long"""
    raise ValueError("cut")


def test_mask_reaches_a_hostname_that_pytest_cut():
    """The head and the tail of a long hostname, where pytest's repr of an
    argument was cut, are masked like the whole name"""
    head = "p" * 100 + "user_" + LONG_HOST + "\\nowtest" + "s" * 300
    tail = "p" * 300 + "user_" + LONG_HOST + "\\nowtest" + "s" * 90
    try:
        cut_by_pytest(head, tail)
    except ValueError:
        excinfo = pytest.ExceptionInfo.from_current()
    text = str(excinfo.getrepr(style="long", funcargs=True))
    assert LONG_HOST not in text and occurrences([LONG_HOST], text) >= 2, (
        "pytest no longer cuts both arguments inside the host:\n" + text
    )
    masked = str(
        mask(excinfo.getrepr(style="long", funcargs=True), hostname_rules(LONG_HOST))
    )
    assert occurrences([LONG_HOST], masked) == 0, masked
    assert "user_" + PLACEHOLDER + "..." in masked, masked
    assert "..." + PLACEHOLDER + "\\\\nowtest" in masked, masked


def test_the_reports_mask_this_machine_with_every_rule():
    """The suite's reports use the rules of a whole name and of a cut one,
    for this machine's hostname, read once"""
    expected = hostname_rules(socket.gethostname())
    assert [rule.pattern for rule in HOSTNAME_RULES] == [
        rule.pattern for rule in expected
    ]


def test_mask_report_masks_the_failure_and_the_captured_output():
    """A report's sections, a string failure, an xfail reason and a skip's
    tuple"""
    report = pytest.TestReport(
        "test_x.py::test_x",
        ("test_x.py", 1, "test_x"),
        {},
        "failed",
        "failed on " + FAKE_HOST.upper(),
        "call",
        sections=[("Captured stdout call", "user " + FAKE_HOST + "\n")],
    )
    mask_report(report, FAKE_RULES)
    assert report.longrepr == "failed on " + PLACEHOLDER
    assert report.sections == [("Captured stdout call", "user " + PLACEHOLDER + "\n")]
    xfailed = pytest.TestReport(
        "test_x.py::test_z",
        ("test_x.py", 3, "test_z"),
        {},
        "skipped",
        None,
        "call",
        wasxfail="fails on " + FAKE_HOST,
    )
    mask_report(xfailed, FAKE_RULES)
    assert xfailed.wasxfail == "fails on " + PLACEHOLDER
    skipped = pytest.TestReport(
        "test_x.py::test_y",
        ("test_x.py", 2, "test_y"),
        {},
        "skipped",
        ("test_x.py", 2, "Skipped: no " + FAKE_HOST),
        "setup",
    )
    mask_report(skipped, FAKE_RULES)
    assert skipped.longrepr == ("test_x.py", 2, "Skipped: no " + PLACEHOLDER)


def test_mask_keeps_a_longer_label_that_contains_the_host():
    """The rules of the goldens: the host is never part of a longer label"""
    text = "xfakehost-368.example.org, fakehost-3689 and fakehost-368..."
    assert mask(text, FAKE_RULES) == text.replace(
        "fakehost-368...", PLACEHOLDER + "..."
    )


def test_an_unsearchable_hostname_masks_nothing():
    """``localhost`` and short names have no rule, and a report is left
    as it is"""
    assert hostname_rules("localhost") == [] and hostname_rules("abc") == []
    report = pytest.TestReport(
        "test_x.py::test_x",
        ("test_x.py", 1, "test_x"),
        {},
        "failed",
        "failed on localhost",
        "call",
    )
    mask_report(report, hostname_rules("localhost"))
    assert report.longrepr == "failed on localhost"
