# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``trials/<tid>/prospective.dot`` over constructs of the syntax corpus

The route (``views.prospective_provenance``) serves the graph that
``generate_prospective_prov`` (``models/prospective/generate.py``) draws
with ``DefinitionProvenanceAnalyzer`` (``models/prospective/analyzer.py``)
from the trial's code components; ``now export prospective`` prints the
same graph. The graph of the weather store and an unknown trial are in
``test_trial_routes.py``. Here a store of the module holds one trial per
script of ``e2e/corpus/syntax`` that it runs, read-only: its fingerprint is
checked after each test.

Controls, which draw: ``if_elif_else`` (a node per if, elif, else and for
line, the True edge of each if and elif into its body and the False edge
into each else from the if it belongs to) and ``with_statement`` (a node per
with statement, labeled with its source, and per method). Expected labels
come from the script's AST and source.

The view catches every exception: a ``ValueError`` answers 400 and any
other 500, with ``Unexpected error: <message>`` as text, so a crash
answers 500 here as in ``now vis`` and only its message reaches the
response. ``analyzer_failure`` runs the generator in this process for the
exception's type and the function of analyzer.py where it raised.

Known defects (#364), each with a characterization
and a ``_desired`` twin that wants a DOT digraph; one script per
mechanism. With ``now export prospective``, the scripts of the syntax
corpus that fail, each by one mechanism unless said otherwise:

- ``UNDRAWN_FUNCTION_END`` (``raise_from``): a function whose last line
  holds no node the analyzer draws. Also ``async_for``,
  ``async_for_iterator``, ``async_with``, ``except_star``, ``walrus_yield``
  and ``yield_from``.
- ``TRY_WITHOUT_EXCEPT`` (``try_finally``): a try whose only handler is a
  finally; that script's other try has an else, which fails next
  (``ELSE_WITHOUT_IF``).
- ``ELSE_WITHOUT_IF`` (``while_else``): the else of a loop or of a try.
  Also ``for_multiple_targets``.
- ``NO_COMPONENTS`` (``sys_exit_no_code``): a trial without code
  components, which that script's ``now run`` leaves (#226).

The 400 branch is characterized through a stand-in for ``Trial``: the only
``ValueError`` the generator raises on purpose, for a trial without id,
formats an undefined name and raises ``NameError`` instead, and ``Trial()``
never yields such a trial. A ``ValueError`` of the analyzer's
``list.index`` calls would reach it; no script of the syntax corpus does.

Measured on macOS with Python 3.11 to 3.15, through this route and
through ``now export prospective``: the same scripts fail the same way on
every version.
"""
import ast
import re
import traceback
import types
from pathlib import Path

import pytest

from noworkflow.now.models.prospective.generate import (
    generate_prospective_prov,
)
from noworkflow.now.vis import views
from noworkflow.tests.e2e.harness import CORPUS, NowProject
from noworkflow.tests.e2e.paper import parse_dot

from .support import Defect, known_defects

SYNTAX = CORPUS / "syntax"
ROUTE = "/trials/{}/prospective.dot"
DIGRAPH = re.compile(r"(strict )?digraph \{")
CONTROLS = ("if_elif_else", "with_statement")
# sys.exit() without a code makes `now run` crash (#226), and the run that
# fails is the subject of test_syntax_corpus.py: here any outcome goes.
FAILING_RUN = "sys_exit_no_code"
SCRIPTS = CONTROLS + ("raise_from", "try_finally", "while_else", FAILING_RUN)

UNDRAWN_FUNCTION_END = Defect(
    reason="#364: _limited "
           "(models/prospective/analyzer.py), the first of the analyzer's "
           "lookups of a function's last line among the first lines of the "
           "nodes it drew (_create_function_end_list and "
           "_create_boxes_in_functions repeat it), calls "
           "SyntaxUtils.get_index_array (prospective/utils/syntax_utils.py), "
           "whose key[len(key) - 1] raises IndexError when no drawn node "
           "starts on that line: a function that ends in a statement "
           "create_all_nodes does not draw, such as the raise that ends "
           "parse() in raise_from.py",
    signature="IndexError in _limited: list index out of range",
)
TRY_WITHOUT_EXCEPT = Defect(
    reason="#364: _check_try "
           "(models/prospective/analyzer.py) draws an edge from a try to "
           "self.try_except[key][1] whenever the handlers it collected end "
           "in a finally, and a try whose only handler is a finally (the "
           "try in the loop of try_finally.py) collects that one alone: "
           "IndexError; the first try of that script also has an else, so "
           "its case flips only when ELSE_WITHOUT_IF is fixed too",
    signature="IndexError in _check_try: list index out of range",
)
ELSE_WITHOUT_IF = Defect(
    reason="#364: linking_nodes_graph "
           "(models/prospective/analyzer.py) draws the False edge into an "
           "else node from self.node_if[i], which only "
           "_create_condition_node sets, for an else that follows an if at "
           "its column; the else of a while (while_else.py), of a for or of "
           "a try has none, and graphviz's Digraph.edge fails quoting None "
           "as the tail: AttributeError",
    signature="AttributeError in linking_nodes_graph: "
              "'NoneType' object has no attribute 'partition'",
)
NO_COMPONENTS = Defect(
    reason="#364: for a trial without code "
           "components, code_components (models/prospective/analyzer.py) "
           "prints a message and returns None, which create_all_nodes "
           "iterates: TypeError; sys_exit_no_code.py reaches it because its "
           "now run crashes before it stores the definition provenance "
           "(#226), so the case flips when either is fixed",
    signature="TypeError in create_all_nodes: "
              "'NoneType' object is not iterable",
)


@pytest.fixture(scope="module")
def _prospective_store(tmp_path_factory):
    """One trial per script of ``SCRIPTS``, in this order

    Returns the project and ``{script: trial id}``.
    """
    project = NowProject(tmp_path_factory.mktemp("vis_prospective"))
    trials = {}
    for name in SCRIPTS:
        project.write(name + ".py", (SYNTAX / (name + ".py")).read_text(
            encoding="utf-8"))
        failing = name == FAILING_RUN
        project.run("run", name + ".py", expect=None if failing else 0,
                    allow_stderr=failing)
        trials[name] = project.trials()[-1]["id"]
    assert len(set(trials.values())) == len(SCRIPTS), "one trial per script"
    return types.SimpleNamespace(project=project, trials=trials)


@pytest.fixture
def prospective(_prospective_store, vis_for):
    """The vis of the module's store: read-only

    ``trials`` maps each script to its trial.
    """
    project = _prospective_store.project
    before = project.fingerprint()
    vis = vis_for(project)
    vis.trials = _prospective_store.trials
    yield vis
    same = project.fingerprint() == before
    assert same, "the test changed the module's prospective store"


def graph_of(vis, name):
    """GET ``prospective.dot`` of the trial of script ``name``"""
    return vis.get(ROUTE.format(vis.trials[name]))


def analyzer_failure(trial_id):
    """What ``generate_prospective_prov`` raises for a trial, or None

    ``"<type> in <function>: <message>"``, the function being the innermost
    frame of analyzer.py. The trial is a stand-in with its id, the only
    attribute the generator reads, so that no ``Trial`` (whose repr holds
    ``user_id``) is an argument of a frame in a report.
    """
    try:
        generate_prospective_prov(types.SimpleNamespace(id=trial_id))
    except Exception as error:  # pylint: disable=broad-except
        frames = [frame.name for frame in traceback.extract_tb(
            error.__traceback__)
            if Path(frame.filename).parts[-2:] == ("prospective",
                                                   "analyzer.py")]
        return "{} in {}: {}".format(
            type(error).__name__, frames[-1] if frames else "?", error)
    return None


def assert_digraph(vis, name):
    """The graph of script ``name`` is a DOT digraph served as text

    Returns the text. On another status the message names what the
    generator raises.
    """
    response = graph_of(vis, name)
    assert response.status_code == 200, "{}: status {} ({})".format(
        name, response.status_code, analyzer_failure(vis.trials[name]))
    assert response.mimetype == "text/plain", name
    text = response.get_data(as_text=True)
    assert DIGRAPH.match(text), text[:40]
    return text


def assert_answers_500(vis, name, message):
    """The graph of script ``name`` answers 500 with ``message`` as text"""
    response = graph_of(vis, name)
    assert response.status_code == 500, name
    assert response.mimetype == "text/plain", name
    assert response.get_data(as_text=True) == "Unexpected error: " + message


def script_source(vis, name):
    return (vis.project.path / (name + ".py")).read_text(encoding="utf-8")


def labelled(text):
    """``(labels, edges)`` of a DOT graph: ``{node id: label}`` and
    ``{(source id, target id, edge label)}``"""
    nodes, edges, _ = parse_dot(text)
    labels = {node: attrs.get("label", node) for node, attrs in nodes.items()}
    return labels, {(source, target, attrs.get("label", "").strip())
                    for source, target, attrs in edges}


# --- controls ---------------------------------------------------------------


def test_prospective_dot_draws_the_branches_of_if_elif_else(prospective):
    """The graph of ``if_elif_else.py`` has the node ``<line>: <keyword>``
    of each if, elif, else and for, and ``<line>: def <name>(`` of the
    function; each if and elif has a True edge to the first statement of its
    body, and the False edge into each else leaves the if or elif it
    belongs to
    """
    text = assert_digraph(prospective, "if_elif_else")
    labels, edges = labelled(text)
    source = script_source(prospective, "if_elif_else")
    lines = source.splitlines()

    def keyword(line):
        words = lines[line - 1].split()
        return words[0].rstrip(":") if words else ""

    def node(label):
        found = [key for key, value in labels.items() if value == label]
        assert len(found) == 1, "{!r}: {} nodes".format(label, len(found))
        return found[0]

    def starting(line):
        prefix = "{}: ".format(line)
        return {key for key, value in labels.items()
                if value.startswith(prefix)}

    tests, elses = [], []
    for statement in ast.walk(ast.parse(source)):
        if isinstance(statement, ast.FunctionDef):
            prefix = "{}: def {}(".format(statement.lineno, statement.name)
            assert any(value.startswith(prefix)
                       for value in labels.values()), prefix
        elif isinstance(statement, ast.For):
            node("{}: for".format(statement.lineno))
        elif isinstance(statement, ast.If):
            tests.append(statement)
    assert tests, "if_elif_else.py has no if"
    for statement in tests:
        test = node("{}: {}".format(statement.lineno,
                                    keyword(statement.lineno)))
        body = starting(statement.body[0].lineno)
        assert any((test, target, "True") in edges for target in body), (
            "no True edge from line {}".format(statement.lineno))
        orelse = statement.orelse
        if not orelse or (isinstance(orelse[0], ast.If)
                          and keyword(orelse[0].lineno) == "elif"):
            continue
        line = max(number for number in range(
            statement.body[-1].end_lineno + 1, orelse[0].lineno)
            if keyword(number) == "else")
        elses.append(line)
        assert (test, node("{}: else".format(line)), "False") in edges, (
            "no False edge from line {} to line {}".format(
                statement.lineno, line))
    assert elses, "if_elif_else.py has no else"


def test_prospective_dot_draws_the_with_statements_and_methods(prospective):
    """The graph of ``with_statement.py`` has a node per with statement,
    labeled ``<line>: <its source>``, and ``<line>: def <name>(`` per method
    """
    text = assert_digraph(prospective, "with_statement")
    labels, _ = labelled(text)
    source = script_source(prospective, "with_statement")
    tree = ast.parse(source)
    withs = [node for node in ast.walk(tree) if isinstance(node, ast.With)]
    methods = [node for node in ast.walk(tree)
               if isinstance(node, ast.FunctionDef)]
    assert withs and methods, "with_statement.py changed"
    for node in withs:
        label = "{}: {}".format(node.lineno,
                                ast.get_source_segment(source, node))
        assert label in labels.values(), "no node for line {}".format(
            node.lineno)
    for node in methods:
        prefix = "{}: def {}(".format(node.lineno, node.name)
        assert any(value.startswith(prefix)
                   for value in labels.values()), prefix


# --- a function whose last line draws nothing ---------------------------------


def test_prospective_dot_of_a_function_ending_in_raise_answers_500(
        prospective):
    """Today the graph of ``raise_from.py``, whose ``parse()`` ends in a
    raise, answers 500: IndexError in ``_limited``
    """
    assert_answers_500(prospective, "raise_from", "list index out of range")
    assert analyzer_failure(prospective.trials["raise_from"]) == (
        UNDRAWN_FUNCTION_END.signature)


@known_defects(UNDRAWN_FUNCTION_END)
def test_prospective_dot_of_a_function_ending_in_raise_desired(prospective):
    """The graph of ``raise_from.py`` is a DOT digraph"""
    assert_digraph(prospective, "raise_from")


# --- a try whose only handler is a finally ------------------------------------


def test_prospective_dot_of_try_finally_answers_500(prospective):
    """Today the graph of ``try_finally.py``, whose loop holds a try with a
    finally and no except, answers 500: IndexError in ``_check_try``
    """
    assert_answers_500(prospective, "try_finally", "list index out of range")
    assert analyzer_failure(prospective.trials["try_finally"]) == (
        TRY_WITHOUT_EXCEPT.signature)


@known_defects(TRY_WITHOUT_EXCEPT, ELSE_WITHOUT_IF)
def test_prospective_dot_of_try_finally_desired(prospective):
    """The graph of ``try_finally.py`` is a DOT digraph"""
    assert_digraph(prospective, "try_finally")


# --- the else of a loop ---------------------------------------------------------


def test_prospective_dot_of_while_else_answers_500(prospective):
    """Today the graph of ``while_else.py`` answers 500: AttributeError in
    ``linking_nodes_graph``, where the else of a while has no if
    """
    assert_answers_500(prospective, "while_else",
                       "'NoneType' object has no attribute 'partition'")
    assert analyzer_failure(prospective.trials["while_else"]) == (
        ELSE_WITHOUT_IF.signature)


@known_defects(ELSE_WITHOUT_IF)
def test_prospective_dot_of_while_else_desired(prospective):
    """The graph of ``while_else.py`` is a DOT digraph"""
    assert_digraph(prospective, "while_else")


# --- a trial without code components ------------------------------------------


def test_prospective_dot_of_a_trial_without_components_answers_500(
        prospective):
    """Today the graph of the ``sys_exit_no_code.py`` trial, which has no
    code components (#226), answers 500: TypeError in ``create_all_nodes``
    """
    trial_id = prospective.trials[FAILING_RUN]
    assert prospective.project.count("code_component", trial_id) == 0
    assert_answers_500(prospective, FAILING_RUN,
                       "'NoneType' object is not iterable")
    assert analyzer_failure(trial_id) == NO_COMPONENTS.signature


@known_defects(NO_COMPONENTS)
def test_prospective_dot_of_a_trial_without_components_desired(prospective):
    """The graph of the ``sys_exit_no_code.py`` trial is a DOT digraph"""
    assert_digraph(prospective, FAILING_RUN)


# --- the 400 branch -----------------------------------------------------------


def test_prospective_dot_of_a_trial_without_id_answers_500_not_400(
        prospective, monkeypatch):
    """Today a trial whose id is None answers 500 ``name 'e' is not
    defined``: the guard of ``generate_prospective_prov`` formats an
    undefined ``e`` into its ``ValueError``, so the view's 400 branch never
    sees it

    Characterization only: ``Trial()`` never yields such a trial (an
    unknown id raises ``RuntimeError``, see ``test_trial_routes.py``), so a
    stand-in replaces it in the view.
    """
    monkeypatch.setattr(views, "Trial",
                        lambda tid: types.SimpleNamespace(id=None))
    response = prospective.get(ROUTE.format(prospective.trials["raise_from"]))
    assert response.status_code == 500
    assert response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == (
        "Unexpected error: name 'e' is not defined")
