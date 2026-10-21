# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now export prospective --executed``: the code nodes a trial did not run (#452)

The prospective graph comes from the code alone (README, "now export
prospective"), and so does ``now export prospective`` without options and
the vis route ``trials/<tid>/prospective.dot``: two trials of the same code
draw the same graph. ``--executed`` (``?executed=1`` on the route) draws, on
top of it, each code node that the trial did not run in the color
``GraphDrawer.color["inactive"]``; the nodes that ran keep their colors.

A node is named by its label, ``<line>: <code>``, as the graph draws it.
Each scenario names the nodes that did not run, which are drawn inactive,
and the nodes that ran, which are not; the expectation is what plain Python
runs. When the store cannot tell whether a node ran, the node is left as
it is: a node that ran is never drawn inactive. That is the case of a trial
whose capture was limited by ``now run -d`` or ``-cg``, which records part
of what ran.

Measured in the review of #198: these scenarios are where a node is judged
by whether its first line holds an evaluated component. Statements that
record no evaluation (``import``, ``global``, a bare ``return``), a header
judged by the node drawn after it, the body of a one-line compound
statement, a line of another file with the same number and a capture
limited by ``-d`` or ``-cg`` each draw a node on the wrong side.
"""

import pytest

from noworkflow.now.models.prospective.utils.graph_drawer import GraphDrawer
from noworkflow.tests.e2e.harness import NowProject
from noworkflow.tests.e2e.paper import parse_dot
from noworkflow.tests.helpers.persistence import connected_to

INACTIVE = GraphDrawer(None).color["inactive"]
NOTES = ("Condition:", "Variable:")

BRANCH = """\
import sys

if len(sys.argv) > 1:
    mode = 1
else:
    mode = 2
print(mode)
"""

# Statements for which the collector records no evaluation, in a function
# that runs and in one that is never called. Line 1 holds the script's own
# component, so the first import is on line 2.
SILENT = """\
COUNT = 0
import json


def bump():
    global COUNT
    COUNT += 1
    return


def never():
    import csv
    global COUNT
    return


bump()
print(json.dumps(COUNT))
"""

# The body of a one-line compound statement shares the line of its header.
ONE_LINE = """\
flag = False
if flag: chosen = 1
while flag: looped = 2
print(flag)
"""

# Headers whose body starts with another header, and a handler that was
# not entered, whose body the graph does not draw, next to a sibling that
# ran.
HEADERS = """\
print(1)
try:
    try:
        print(4)
    except ValueError:
        print(6)
except KeyError:
    print(8)
value = int("1")
if value > 5:
    pass
else:
    try:
        print(14)
    except ValueError:
        print(16)
try:
    number = int("x")
except KeyError:
    raise
except ValueError:
    number = 22
print(number)
"""

# Line 4 of the script does not run; line 4 of the module it imports does.
PACKAGE_SCRIPT = """\
import helper

if helper.SEP == "?":
    print(4)
print(5)
"""
PACKAGE_HELPER = """\
import os


SEP = os.sep
"""

# Every line runs; the capture of the function body is what the flags cut.
CALLED = """\
total = 0


def add(value):
    result = value + 1
    return result


total = add(total)
print(total)
"""

# A function that is never called, with a condition and a loop variable.
NOTED = """\
def never(n):
    if n > 0:
        n = 0
    for i in range(n):
        n = i
    return n


print(0)
"""


def colors(dot):
    """``{label: inactive?}`` of the code nodes of a prospective graph"""
    nodes, _, _ = parse_dot(dot)
    return {
        attrs["label"]: attrs.get("fillcolor") == INACTIVE
        for attrs in nodes.values()
        if "label" in attrs
    }


def executed_graph(project, script, *run_args, files=()):
    """``now export prospective --executed`` after ``now run`` of ``script``"""
    for name, text in files:
        project.write(name, text)
    project.write("script.py", script)
    project.run("run", *run_args, "script.py")
    return project.run("export", "prospective", "--executed").stdout


def assert_drawn(drawn, inactive=(), ran=()):
    """Each label of ``inactive`` is drawn inactive, each of ``ran`` is not"""
    missing = [label for label in (*inactive, *ran) if label not in drawn]
    assert not missing, "nodes not in the graph: {}\n{}".format(missing, drawn)
    wrong = sorted(
        ["ran, drawn inactive: " + label for label in ran if drawn[label]]
        + [
            "did not run, drawn as run: " + label
            for label in inactive
            if not drawn[label]
        ]
    )
    assert not wrong, "\n".join(wrong)


def test_export_prospective_draws_the_code_alone(project):
    """Without ``--executed`` no node is drawn inactive, and two trials of
    the same code that took different branches draw the same graph"""
    project.write("script.py", BRANCH)
    project.run("run", "script.py")
    project.run("run", "script.py", "argument")
    first, second = (trial["id"] for trial in project.trials())

    one = project.run("export", "prospective", first).stdout
    two = project.run("export", "prospective", second).stdout

    assert one == two
    assert not any(colors(one).values()), one


def test_executed_draws_the_branch_a_trial_did_not_take(project):
    """``--executed`` of each trial draws inactive the branch it skipped"""
    project.write("script.py", BRANCH)
    project.run("run", "script.py")
    project.run("run", "script.py", "argument")
    first, second = (trial["id"] for trial in project.trials())

    without = colors(project.run("export", "prospective", "--executed", first).stdout)
    with_argument = colors(
        project.run("export", "prospective", "--executed", second).stdout
    )

    assert_drawn(
        without,
        inactive=["4: mode = 1"],
        ran=["1: import sys", "3: if", "5: else", "6: mode = 2", "7: print(mode)"],
    )
    assert_drawn(
        with_argument,
        inactive=["5: else", "6: mode = 2"],
        ran=["1: import sys", "3: if", "4: mode = 1", "7: print(mode)"],
    )


def test_executed_of_statements_that_record_no_evaluation(project):
    """``import``, ``global`` and a bare ``return`` are drawn as run where
    they ran, and inactive in a function that is never called"""
    drawn = colors(executed_graph(project, SILENT))

    assert_drawn(
        drawn,
        inactive=[
            "11: def never()",
            "12: import csv",
            "13: global COUNT",
            "14: return",
        ],
        ran=[
            "2: import json",
            "5: def bump()",
            "6: global COUNT",
            "7: COUNT += 1",
            "8: return",
        ],
    )


def test_executed_of_the_body_of_a_one_line_compound_statement(project):
    """The body of ``if flag: chosen = 1`` is drawn inactive when ``flag``
    is false, although its header, on the same line, ran"""
    drawn = colors(executed_graph(project, ONE_LINE))

    assert_drawn(
        drawn,
        inactive=["2: chosen = 1", "3: looped = 2"],
        ran=["1: flag = False", "2: if", "3: while", "4: print(flag)"],
    )


def test_executed_of_nested_headers_and_sibling_handlers(project):
    """A ``try`` or an ``else`` whose body starts with another header is
    drawn as run when its body ran, and a handler that was not entered is
    drawn inactive whatever the node drawn after it"""
    drawn = colors(executed_graph(project, HEADERS))

    assert_drawn(
        drawn,
        inactive=[
            "5: except",
            "7: except",
            "11: pass",
            "15: except",
            "19: except",
        ],
        ran=[
            "2: try",
            "3: try",
            "12: else",
            "13: try",
            "17: try",
            "21: except",
            "22: number = 22",
        ],
    )


def test_executed_of_a_line_that_another_file_ran(project):
    """Under ``now run -c package`` the module the script imports is
    traced too: its line 4 ran, the script's line 4 did not"""
    drawn = colors(
        executed_graph(
            project,
            PACKAGE_SCRIPT,
            "-c",
            "package",
            files=[("helper.py", PACKAGE_HELPER)],
        )
    )

    assert_drawn(drawn, inactive=["4: print(4)"], ran=["3: if", "5: print(5)"])


@pytest.mark.parametrize(
    "flags", [("-d", "0"), ("-d", "1"), ("-cg",)], ids=["d0", "d1", "cg"]
)
def test_executed_of_a_trial_whose_capture_was_limited(project, flags):
    """Every node of the script ran: a capture limited by ``-d`` or
    ``-cg`` records part of it, and no node is drawn inactive"""
    drawn = colors(executed_graph(project, CALLED, *flags))

    inactive = sorted(label for label, gray in drawn.items() if gray)
    assert inactive == [], "\n".join(inactive)


def test_executed_draws_the_notes_of_an_inactive_node_inactive(project):
    """The condition of an ``if`` and the variable of a ``for`` that did
    not run are drawn in the color of their node"""
    dot = executed_graph(project, NOTED)
    nodes, edges, _ = parse_dot(dot)

    def inactive(node):
        return nodes[node].get("fillcolor") == INACTIVE

    notes = [
        (note, node)
        for source, target, _ in edges
        for note, node in ((source, target), (target, source))
        if nodes.get(note, {}).get("label", "").strip().startswith(NOTES)
    ]
    assert len(notes) == 2, dot
    assert all(inactive(node) for _, node in notes), dot
    assert [note for note, _ in notes if not inactive(note)] == [], dot


def test_prospective_route_draws_inactive_nodes_only_when_asked(tmp_path):
    """``trials/<tid>/prospective.dot`` draws the code alone, and with
    ``?executed=1`` the branch the trial did not take"""
    project = NowProject(tmp_path)
    project.write("script.py", BRANCH)
    project.run("run", "script.py")
    (trial,) = project.trials()

    with connected_to(project.path):
        from noworkflow.now.vis.views import app

        client = app.test_client()
        route = "/trials/{}/prospective.dot".format(trial["id"])
        plain = client.get(route)
        executed = client.get(route + "?executed=1")

    assert plain.status_code == executed.status_code == 200
    assert not any(colors(plain.get_data(as_text=True)).values())
    assert_drawn(
        colors(executed.get_data(as_text=True)),
        inactive=["4: mode = 1"],
        ran=["3: if", "6: mode = 2"],
    )
