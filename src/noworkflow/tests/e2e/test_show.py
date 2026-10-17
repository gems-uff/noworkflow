# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now list``, ``now show`` and ``now history`` on a store with two trials

Every test reads the shared ``two_trial_project`` (the weather corpus run
twice; the second run changed the last row of ``data2.dat``) and never
writes to it: these three commands only read the store.

The goldens (``now list``, ``now history`` and ``now show`` with each flag
but ``-e``) are compared on the reference leg only. The structural tests
run on every leg and check, against the store, what the goldens would show
there: which trials are listed, which trial ``show`` picks, the history
filters, and the environment attributes. ``now show -e`` is never a golden:
it prints the machine's environment, so its test checks attribute names and
the few values the harness controls, and never prints a value, not even in
an assertion message.
"""
import collections
import platform
import re
from pathlib import Path

import pytest

import noworkflow
from noworkflow.tests.e2e.golden import assert_golden
from noworkflow.tests.e2e.harness import USER, runs_this_interpreter

# One golden per flag of `now show`; `-e` is tested structurally below.
SHOW_CASES = [
    ("show", ()),
    ("show-1", ("1",)),
    ("show-m", ("-m",)),
    ("show-d", ("-d",)),
    ("show-a", ("-a",)),
    ("show-f", ("-f",)),
    ("show-p", ("-p",)),
]

ENVIRONMENT_HEADER = (
    "[now] this trial has been executed under the following environment "
    "conditions"
)
# Attributes that every system records (deployment.py); the rest depends on
# os.sysconf_names, os.confstr_names and the environment of the system.
REQUIRED_ATTRIBUTES = {
    "PYTHON_VERSION", "NOWORKFLOW_VERSION", "USER", "HOSTNAME", "PID",
    "OS_NAME",
}
VERSION = re.compile(r"\d+\.\d+\.\d+\S*")


def checkout_version():
    """The version.txt of the noworkflow package this interpreter imports"""
    path = Path(noworkflow.__file__).resolve().parent / "resources" / (
        "version.txt")
    return path.read_text(encoding="utf-8").strip()


def environment_attributes(stdout):
    """``[(name, value)]`` of the lines after the ``show -e`` header

    Each attribute is a ``  NAME: value`` line; the value may be empty (the
    line then ends in ``": "``) and a name may repeat (``OS_NAME`` and
    ``USER`` are recorded twice). The split is on ``": "``, not on the first
    ``:``, because a Windows variable name may hold a colon (``=C:``).
    """
    lines = stdout.splitlines()
    # A boolean: pytest would print the lines of a failed `in`.
    found = ENVIRONMENT_HEADER in lines
    assert found, "no environment header in show -e"
    start = lines.index(ENVIRONMENT_HEADER) + 1
    attributes = []
    for line in lines[start:]:
        name, _, value = line.lstrip().partition(": ")
        attributes.append((name, value))
    return attributes


@pytest.mark.golden
def test_list_shows_each_trial_with_its_code_hash_sequence_key_and_tag(
        request, two_trial_project):
    """``now list`` prints every trial with its command, code hash, times,
    sequence key and automatic tag."""
    result = two_trial_project.run("list")
    assert_golden(request, "list", two_trial_project.normalize(result.stdout))


def test_list_names_every_stored_trial_in_the_order_they_ran(
        two_trial_project):
    """``now list`` names each trial of the store once, in insertion order
    (the query has no ORDER BY), with its sequence key and tag."""
    project = two_trial_project
    stdout = project.run("list").stdout
    trials = project.trials()
    assert len(trials) == 2
    ids = re.findall(r"^  \[\*\]Trial (\S+): run simulation\.py "
                     r"data1\.dat data2\.dat$", stdout, re.MULTILINE)
    keys = re.findall(r"^ +Sequence Key: (\d+)$", stdout, re.MULTILINE)
    tags = re.findall(r"^ +Tag: (\S+) Type: AUTO$", stdout, re.MULTILINE)
    assert ids == [trial["id"] for trial in trials]
    assert keys == [str(trial["sequence_key"]) for trial in trials]
    assert tags == [project.tags(trial["id"])[0]["name"] for trial in trials]
    assert tags == ["1.1.1", "1.1.2"]


@pytest.mark.golden
@pytest.mark.parametrize(
    "name, args", SHOW_CASES, ids=[name for name, _ in SHOW_CASES])
def test_show_prints_the_trial_and_the_section_each_flag_selects(
        request, two_trial_project, name, args):
    """``now show [trial] [flag]`` prints the tags and the trial, then the
    modules (-m), code blocks (-d), activation tree (-a), file accesses (-f)
    or arguments (-p)."""
    result = two_trial_project.run("show", *args)
    assert_golden(request, name, two_trial_project.normalize(result.stdout))


def test_show_without_a_trial_shows_the_last_trial(two_trial_project):
    """``now show`` with no trial equals ``now show`` of the last trial named
    by its sequence key, its tag or its id, and differs from the first."""
    project = two_trial_project
    last = project.trials()[-1]
    tag = project.tags(last["id"])[0]["name"]
    default = project.run("show").stdout
    assert "  Id: {}\n".format(last["id"]) in default
    for ref in (last["sequence_key"], tag, last["id"]):
        assert project.run("show", ref).stdout == default, (
            "now show {} differs from now show".format(ref))
    assert project.run("show", "1").stdout != default


def test_show_environment_lists_the_recorded_attributes_with_the_synthetic_user(
        two_trial_project):
    """``now show -e`` prints every environment attribute recorded for the
    last trial, including the ones every system records; the user is the
    harness's, HOME its temporary home, and the versions are the child's.

    Values are compared, never printed: the store holds the machine's
    environment (hostname, PATH). The command runs with ``expect=None``,
    because the harness prints the output of a failed command, and every
    comparison of values is a boolean with a fixed message.
    """
    project = two_trial_project
    last = project.trials()[-1]
    result = project.run("show", "-e", expect=None, allow_stderr=True)
    clean = result.returncode == 0 and result.stderr == ""
    assert clean, "now show -e: return code {}, {} characters on stderr".format(
        result.returncode, len(result.stderr))
    attributes = environment_attributes(result.stdout)
    names = collections.Counter(name for name, _ in attributes)
    stored = collections.Counter(row["name"] for row in project.query(
        "SELECT name FROM environment_attr WHERE trial_id = ?", last["id"]))
    assert names == stored, "show -e and the store disagree on the names"
    missing = REQUIRED_ATTRIBUTES - set(names)
    assert not missing, "attributes missing from show -e: {}".format(
        sorted(missing))

    def values(name):
        return [value for key, value in attributes if key == name]

    # One USER comes from os.environ, the other from getpass.getuser(),
    # which reads LOGNAME first: both must be the synthetic user.
    users = values("USER")
    synthetic = len(users) == 2 and all(value == USER for value in users)
    assert synthetic, "{} USER attribute(s), not all {!r}".format(
        len(users), USER)
    homes = values("HOME")
    temporary = homes == [str(project.home)]
    assert temporary, (
        "{} HOME attribute(s), expected one equal to the temporary home"
        .format(len(homes)))

    python, = values("PYTHON_VERSION")
    version, = values("NOWORKFLOW_VERSION")
    if runs_this_interpreter(project.command):
        same = (python == platform.python_version()
                and version == checkout_version())
        assert same, "the recorded versions are not this interpreter's"
    else:
        shaped = bool(VERSION.fullmatch(python) and VERSION.fullmatch(version))
        assert shaped, "the recorded versions are not version numbers"


@pytest.mark.golden
def test_history_draws_every_trial_newest_first(request, two_trial_project):
    """``now history`` draws one node per trial, newest first, with its
    script and tag."""
    result = two_trial_project.run("history")
    assert_golden(request, "history",
                  two_trial_project.normalize(result.stdout))


def test_history_filtered_by_the_script_that_ran_equals_the_full_history(
        two_trial_project):
    """``now history -s simulation.py`` keeps both trials: its output is
    the unfiltered history, byte for byte."""
    project = two_trial_project
    full = project.run("history").stdout
    assert project.run("history", "-s", "simulation.py").stdout == full
    ids = re.findall(r"^ \*  (\S+) simulation\.py ", full, re.MULTILINE)
    assert ids == [trial["id"] for trial in reversed(project.trials())]


@pytest.mark.parametrize("args", [
    ("-e", "backup"),
    ("-s", "other.py"),
], ids=["no-backup-trial", "no-trial-of-the-script"])
def test_history_without_a_matching_trial_prints_a_single_empty_line(
        two_trial_project, args):
    """``now history`` whose filter matches no trial prints one empty line
    and returns 0."""
    assert two_trial_project.run("history", *args).stdout == "\n"
