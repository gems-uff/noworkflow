# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""What the vis draws and does in a browser, on the two-trial weather store

One test per view the history page opens, each on a page of its own: the
history graph, a trial and its tabs, the diff of the two trials, the
dataflow, the prospective graph, the Prolog export and its query, the main
tabs, the database graph, the SQL editor; then the parts of those views
that take more input: the filters of a trial's information tab and of the
diff information, the prov and function-diff commands of the context menu,
the hover of a table of the database graph. Each sends the input a user
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


# The views below the fold of the others: the filters of a trial's
# information tab and of the diff information, the two commands of the
# context menu that open a window of their own, and the hover of a table
# of the database graph. Their counts come from the store's script: one
# module of its own (`simulator`, without a version), two data files read
# and one written, and an environment the two trials share but for a few
# attributes.


def select_in(lst, index):
    """The ``index``-th select of the filter of the last visible list ``lst``"""
    return (
        "[...document.querySelectorAll('ul.{}')].filter(__vis.visible).at(-1)"
        ".parentElement.querySelectorAll('select')[{}]".format(lst, index)
    )


def choose(vis, select, value):
    """Set a filter select to ``value`` the way the DOM reports a user's choice"""
    vis.js(
        "(() => {{ const s = {}; s.value = {!r}; s.dispatchEvent(new Event('change')); }})()".format(
            select, value
        )
    )
    vis.settle()


def items(vis, lst):
    return vis.js(
        "[...document.querySelectorAll('ul.{}')].filter(__vis.visible).at(-1)"
        ".querySelectorAll('li').length".format(lst)
    )


def counts(vis, lst, select, values):
    """The number of items of ``lst`` for each value of its filter ``select``"""
    result = {}
    for value in values:
        choose(vis, select, value)
        result[value] = items(vis, lst)
    choose(vis, select, values[0])
    return result


def test_the_information_tab_filters_its_three_lists(vis):
    vis.click(history_node(TRIAL))
    vis.wait("!!__vis.trialGraph()", "the trial graph")
    vis.settle()

    # Modules: version (both, with, without) and locality (all, local, other).
    assert counts(vis, "mod-list", select_in("mod-list", 0), ["both", "1", "0"]) == {
        "both": 1,
        "1": 0,
        "0": 1,
    }
    assert counts(vis, "mod-list", select_in("mod-list", 1), ["0", "1", "2"]) == {
        "0": 1,
        "1": 1,
        "2": 0,
    }
    search = (
        "[...document.querySelectorAll('ul.mod-list')].filter(__vis.visible).at(-1)"
        ".parentElement.querySelector('input[type=search]')"
    )
    for text, expected in (("sim", 1), ("xyz", 0), ("", 1)):
        vis.js(
            "(() => {{ const i = {}; i.value = {!r}; i.dispatchEvent(new KeyboardEvent('keyup')); }})()".format(
                search, text
            )
        )
        vis.settle()
        assert items(vis, "mod-list") == expected, text

    # File accesses: existence (all, only before, only after, changed,
    # unchanged) and locality.
    assert counts(
        vis, "fac-list", select_in("fac-list", 0), ["0", "1", "2", "3", "7"]
    ) == {"0": 3, "1": 0, "2": 1, "3": 0, "7": 2}
    assert counts(vis, "fac-list", select_in("fac-list", 1), ["0", "1", "2"]) == {
        "0": 3,
        "1": 3,
        "2": 0,
    }

    # Environment: the main attributes and the others partition the whole.
    environment = counts(vis, "env-list", select_in("env-list", 0), ["0", "1", "2"])
    assert environment["1"] > 0 and environment["2"] > 0
    assert environment["0"] == environment["1"] + environment["2"]
    assert_quiet(vis)


def test_the_diff_information_filters_each_list_by_trial(vis):
    vis.click(history_node(TRIAL))
    vis.wait("!!__vis.trialGraph()", "the trial graph")
    vis.click(history_node(OTHER), shift=True)
    vis.wait("!!__vis.diffGraph()", "the diff graph")
    vis.settle()
    # The trial select is the last one of each filter: 3 does not filter,
    # 1 and 2 keep what is in the first or the second trial only, 4 what is
    # in both, 5 and 6 what exists in the first or in the second. Two runs
    # of the same script import the same module, so the diff has no Modules
    # section to filter; the environment and the file accesses it has.
    folds = vis.js(
        "[...document.querySelectorAll('.fold span')].filter(__vis.visible)"
        ".map((s) => s.textContent)"
    )
    assert "Modules" not in folds and {"Environment", "File Accesses"} <= set(folds)
    for lst, index in (("fac-list", 2), ("env-list", 1)):
        by_trial = counts(
            vis, lst, select_in(lst, index), ["3", "1", "2", "4", "5", "6"]
        )
        assert by_trial["3"] == by_trial["1"] + by_trial["2"] + by_trial["4"], lst
        assert by_trial["5"] == by_trial["1"] + by_trial["4"], lst
        assert by_trial["6"] == by_trial["2"] + by_trial["4"], lst
        assert by_trial["3"] > 0, lst
    # The two data files read are in both trials, and nothing is in one only.
    assert counts(vis, "fac-list", select_in("fac-list", 2), ["3", "4"]) == {
        "3": 2,
        "4": 2,
    }
    assert_quiet(vis)


def test_the_prov_command_opens_the_prov_of_the_trial(vis):
    vis.menu("prov-option")
    vis.wait("__vis.tabs().includes('*Prov trial {}')".format(TRIAL), "the prov tab")
    vis.settle()
    text = vis.js(
        "[...document.querySelectorAll('p, pre')].filter(__vis.visible)"
        ".map((e) => e.textContent).join('\\n')"
    )
    assert text.startswith("prefix script")
    assert "entity(" in text
    assert_quiet(vis)


def test_the_function_activation_diff_command_opens_its_modal(vis):
    vis.menu("trial-function-diff-option")
    vis.wait(
        "[...document.querySelectorAll('.modal')].some("
        "(m) => __vis.visible(m) && m.textContent.includes('Function activation diff'))",
        "the modal",
    )
    vis.settle()
    # One select of activations per trial to compare, with the same choices.
    options = vis.js(
        "[...document.querySelectorAll('.modal select')].filter(__vis.visible)"
        ".map((s) => s.options.length)"
    )
    assert len(options) >= 2
    assert options[0] == options[-1] > 1
    assert_quiet(vis)


def test_hovering_a_table_of_the_database_graph_highlights_its_links(vis):
    vis.click("__vis.tab('Database')")
    vis.wait("!!__vis.table('trial')", "the database graph")
    vis.settle()
    circle = "__vis.table('trial').querySelector('circle')"
    state = (
        "(() => {{ const c = {}; return {{"
        "width: c.getAttribute('stroke-width'), stroke: c.getAttribute('stroke'),"
        "links: [...document.querySelectorAll('svg line')].filter(__vis.visible)"
        ".map((l) => l.getAttribute('stroke-opacity')).sort().join(',')}}; }})()"
    ).format(circle)
    before = vis.js(state)
    assert (before["width"], before["stroke"]) == ("3", "#fff")
    assert set(before["links"].split(",")) == {"0.6"}

    vis.hover(circle)
    hovered = vis.js(state)
    assert (hovered["width"], hovered["stroke"]) == ("4", "#87CEEB")
    # The links of the hovered table light up, the others fade.
    assert set(hovered["links"].split(",")) == {"0.1", "1"}

    vis.hover("__vis.tab('Database')")
    assert vis.js(state) == before
    assert_quiet(vis)
