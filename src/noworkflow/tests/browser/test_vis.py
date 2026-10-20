# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""What the vis draws and does in a browser, on the two-trial weather store

One test per view the history page opens, each on a page of its own: the
history graph, a trial and its tabs, the diff of the two trials, the
dataflow, the prospective graph, the Prolog export and its query, the main
tabs, the database graph, the SQL editor. Each sends the input a user
would (``conftest.Vis``) and checks what the view did with it, and that
the page reported nothing beyond the known 404s.

The store's two trials are tagged ``1.1.1`` and ``1.1.2``: a fresh store,
two runs of the same script with the same command line.
"""

import re

import pytest

pytestmark = pytest.mark.browser

TRIAL, OTHER = "1.1.1", "1.1.2"
MAIN_TABS = ["History", "Config", "Annotation", "Database"]


def scale_and_translation(transform):
    """(k, x, y) of a ``translate(x,y) scale(k)`` or a ``matrix(k,0,0,k,x,y)``"""
    numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", transform)]
    if transform.startswith("matrix"):
        return numbers[0], numbers[4], numbers[5]
    scale = numbers[2] if len(numbers) > 2 else 1.0
    return scale, numbers[0], numbers[1]


def history_node(tag):
    return "__vis.historyNode({!r})".format(tag)


def assert_quiet(vis):
    assert vis.unexpected_problems() == []


def test_the_history_graph_draws_both_trials_and_zooms_and_pans(vis):
    assert vis.js("__vis.historyNodes().map((r) => r.getAttribute('title'))") == [
        TRIAL,
        OTHER,
    ]
    assert vis.js("__vis.tabs()") == ["*History"] + MAIN_TABS[1:]
    svg = "__vis.historyGroup().ownerSVGElement"
    before = scale_and_translation(vis.js("__vis.transform(__vis.historyGroup())"))

    vis.wheel(svg, -240, empty=True)
    zoomed = scale_and_translation(vis.js("__vis.transform(__vis.historyGroup())"))
    assert zoomed[0] > before[0]

    vis.drag(svg, 60, 40, empty=True)
    panned = scale_and_translation(vis.js("__vis.transform(__vis.historyGroup())"))
    assert panned[0] == zoomed[0]
    assert panned[1] - zoomed[1] == pytest.approx(60, abs=1)
    assert panned[2] - zoomed[2] == pytest.approx(40, abs=1)
    assert_quiet(vis)


def test_clicking_a_trial_opens_its_graph_and_its_information(vis):
    vis.click(history_node(TRIAL))
    vis.wait("!!__vis.trialGraph()", "the trial graph")
    vis.settle()
    tabs = vis.js("__vis.tabs()")
    assert "*Trial " + TRIAL in tabs
    assert "*" + TRIAL + "- Information" in tabs
    group = "__vis.trialGroup()"
    nodes = vis.js("__vis.trialGraph().querySelectorAll('g.node').length")
    assert nodes > 1

    before = scale_and_translation(vis.js("__vis.transform({})".format(group)))
    vis.wheel("__vis.trialGraph()", -240, empty=True)
    zoomed = scale_and_translation(vis.js("__vis.transform({})".format(group)))
    assert zoomed[0] > before[0]
    vis.drag("__vis.trialGraph()", 60, 40, empty=True)
    panned = scale_and_translation(vis.js("__vis.transform({})".format(group)))
    assert (panned[1] - zoomed[1], panned[2] - zoomed[2]) == (
        pytest.approx(60, abs=1),
        pytest.approx(40, abs=1),
    )

    # The root folds its subtree away, and a second click brings it back.
    root = "__vis.trialGraph().querySelector('g.node rect')"
    vis.click(root)
    assert vis.js("__vis.trialGraph().querySelectorAll('g.node').length") == 1
    vis.click(root)
    assert vis.js("__vis.trialGraph().querySelectorAll('g.node').length") == nodes

    fold = "[...document.querySelectorAll('.fold')].find(__vis.visible)"
    assert vis.js("{}.querySelector('i').className".format(fold)) == "fa fa-minus"
    vis.click("{}.querySelector('span')".format(fold))
    assert vis.js("{}.querySelector('i').className".format(fold)) == "fa fa-plus"
    assert_quiet(vis)


def test_shift_click_on_a_second_trial_opens_the_diff_of_the_two(vis):
    vis.click(history_node(TRIAL))
    vis.wait("!!__vis.trialGraph()", "the trial graph")
    vis.click(history_node(OTHER), shift=True)
    diff = "Diff {}-{}".format(TRIAL, OTHER)
    info = "{}<->{} - Diff Info".format(TRIAL, OTHER)
    vis.wait(
        "__vis.tabs().includes({!r}) && __vis.tabs().includes({!r})".format(
            "*" + diff, "*" + info
        ),
        "the diff tabs",
    )
    vis.wait("!!__vis.diffGraph()", "the diff graph")
    vis.settle()
    assert vis.js("__vis.diffGraph().querySelectorAll('g.node').length") > 1
    assert_quiet(vis)


def test_the_dock_resizes_by_its_handle_and_closes_a_tab(vis):
    vis.click(history_node(TRIAL))
    vis.wait("!!__vis.trialGraph()", "the trial graph")
    vis.settle()
    history = "__vis.historyGroup().closest('.lm-DockPanel-widget')"
    height = "{}.getBoundingClientRect().height".format(history)
    before = vis.js(height)
    # The handle under the history pane: the one just below its bottom edge.
    handle = (
        "[...document.querySelectorAll('.lm-DockPanel-handle')].find((h) => "
        "Math.abs(h.getBoundingClientRect().top - {}.getBoundingClientRect().bottom) < 8 "
        "&& __vis.point(h))".format(history)
    )
    vis.drag(handle, 0, 60)
    assert vis.js(height) == pytest.approx(before + 60, abs=2)

    tabs = vis.js("__vis.tabs()")
    vis.click(
        "[...document.querySelectorAll('.lm-TabBar-tab.lm-mod-current.lm-mod-closable')]"
        ".find((t) => t.textContent === {!r}).querySelector('.lm-TabBar-tabCloseIcon')".format(
            "Trial " + TRIAL
        )
    )
    after = vis.js("__vis.tabs()")
    assert "Trial " + TRIAL not in [t.lstrip("*") for t in after]
    assert len(after) == len(tabs) - 1
    assert_quiet(vis)


def test_the_dataflow_of_a_trial_zooms_pans_and_selects_a_box(vis):
    vis.menu("dataflow-option")
    vis.wait("!!__vis.button('Generate dataflow')", "the dataflow form")
    vis.click("__vis.button('Generate dataflow')")
    vis.wait("!!__vis.dataflow()", "the dataflow graph", timeout=90000)
    vis.settle()
    assert "*Dataflow trial " + TRIAL in vis.js("__vis.tabs()")
    assert vis.js("__vis.dataflowBoxes().length") > 0
    svg = "__vis.dataflow().ownerSVGElement"
    transform = "__vis.transform(__vis.dataflow())"

    before = scale_and_translation(vis.js(transform))
    vis.wheel(svg, -240)
    assert scale_and_translation(vis.js(transform))[0] > before[0]

    # The SVG is drawn at its natural size, several times the window, and the
    # boxes may all be out of view: drag the background until the box
    # nearest to the visible part is in it.
    box = vis.js("__vis.nearest(__vis.dataflowBoxes(), {}).id".format(svg))
    target = "document.getElementById({!r})".format(box)
    for _ in range(8):
        if vis.js("!!__vis.point({})".format(target)):
            break
        before = scale_and_translation(vis.js(transform))
        step = vis.js("__vis.towards({}, {})".format(target, svg))
        vis.drag_from(step, step["dx"], step["dy"])
        after = scale_and_translation(vis.js(transform))
        assert (after[1] - before[1], after[2] - before[2]) == (
            pytest.approx(step["dx"], abs=1),
            pytest.approx(step["dy"], abs=1),
        )
    vis.click(target)
    assert vis.js("{}.children[1].getAttribute('stroke')".format(target)) == "red"
    assert_quiet(vis)


def test_the_prospective_graph_zooms_with_its_button_and_pans(vis):
    vis.menu("prospective-option")
    vis.wait("!!__vis.prospective()", "the prospective graph", timeout=60000)
    vis.settle()
    assert "*Prospective " + TRIAL in vis.js("__vis.tabs()")
    view_box = "__vis.prospective().getAttribute('viewBox').split(' ').map(Number)"
    x, y, width, height = vis.js(view_box)

    vis.click(
        "[...document.querySelectorAll('.prospective-toolbar a[title=\"Zoom In\"]')]"
        ".find(__vis.visible)"
    )
    zoomed = vis.js(view_box)
    assert zoomed[2:] == [pytest.approx(width / 1.2), pytest.approx(height / 1.2)]

    vis.drag("__vis.prospective()", 50, 30)
    panned = vis.js(view_box)
    assert panned[2:] == zoomed[2:]
    assert panned[0] < zoomed[0] and panned[1] < zoomed[1]
    assert_quiet(vis)


def test_the_prolog_export_of_a_trial_answers_a_query(vis):
    vis.menu("export-option")
    vis.wait("!!__vis.button('Generate prolog')", "the prolog form")
    vis.click("__vis.button('Generate prolog')")
    program = "document.querySelector('textarea[id^=exportPrologProgram]')"
    vis.wait("!!{}?.value".format(program), "the exported program", timeout=60000)
    vis.settle()
    assert "*Prolog trial " + TRIAL in vis.js("__vis.tabs()")

    vis.click("document.querySelector('textarea[id^=exportPrologQuery]')")
    vis.type("current_predicate(trial/A).")
    vis.click("__vis.button('Execute Query')")
    answers = "document.querySelector('[id^=\"Answers prolog card text\"]')"
    vis.wait("!!{}".format(answers), "the answers")
    vis.settle()
    assert vis.js("{}.innerHTML.split('<br>').filter(Boolean)".format(answers)) != []
    assert_quiet(vis)


def test_the_main_tabs_switch_on_click(vis):
    for label in MAIN_TABS[1:] + MAIN_TABS[:1]:
        vis.click("__vis.tab({!r})".format(label))
        assert vis.js("__vis.tabs()") == [
            ("*" if tab == label else "") + tab for tab in MAIN_TABS
        ]
    assert_quiet(vis)


def test_the_database_graph_draws_every_table_and_opens_one(vis):
    vis.click("__vis.tab('Database')")
    vis.wait("!!__vis.table('trial')", "the database graph")
    vis.settle()
    tables = vis.js("fetch('/db/tables').then((r) => r.json())")["tables"]
    names = vis.js(
        "[...document.querySelectorAll('svg g.node')].filter(__vis.visible)"
        ".map((g) => g.querySelector('text')?.textContent).filter(Boolean)"
    )
    assert sorted(names) == sorted(tables)

    vis.click("__vis.table('trial').querySelector('circle')")
    vis.wait("__vis.tabs().includes('*trial')", "the tab of the table")
    vis.settle()
    assert vis.js(
        "[...document.querySelectorAll('h4')].some((h) => h.textContent === 'trial' && __vis.visible(h))"
    )
    assert_quiet(vis)


def test_the_sql_editor_takes_typed_text_and_runs_it(vis):
    vis.click("__vis.tab('Database')")
    vis.wait("!!__vis.table('trial')", "the database graph")
    vis.click("document.getElementById('new-query-btn')")
    editor = "[...document.querySelectorAll('.ace_editor')].find(__vis.visible)"
    vis.wait("!!{}".format(editor), "the SQL editor")
    assert "*SQL Query" in vis.js("__vis.tabs()")

    query = "SELECT id FROM trial ORDER BY start;"
    # Typed into ace's own input: ace handles the keystrokes.
    vis.js(
        "(() => {{ const e = window.ace.edit({}); e.selectAll(); e.focus(); }})()".format(
            editor
        )
    )
    vis.type(query)
    assert vis.js("window.ace.edit({}).getValue()".format(editor)) == query

    vis.click(
        "[...document.querySelectorAll('button')]"
        ".find((b) => b.textContent.includes('Execute Query') && __vis.visible(b))"
    )
    vis.wait("__vis.tabs().some((t) => t.startsWith('*Query Result ('))", "the result")
    vis.settle()
    assert "*Query Result (2)" in vis.js("__vis.tabs()")
    assert_quiet(vis)


def test_a_table_of_the_database_graph_follows_a_drag(vis):
    vis.click("__vis.tab('Database')")
    vis.wait("!!__vis.table('trial')", "the database graph")
    vis.settle()
    position = "__vis.table('trial').getAttribute('transform')"
    before = vis.js(position)
    # Where it stops follows d3-force's clock; only that it moved is stable.
    vis.drag("__vis.table('trial').querySelector('circle')", 40, 25)
    assert vis.js(position) != before
    assert_quiet(vis)
