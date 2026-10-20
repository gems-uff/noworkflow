# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The routes of ``now vis`` that describe one trial

Covered, on the shared two-trial weather store (``vis``, read-only): the
modules (``dependencies.json``), the environment (``environment.json``,
whose values are compared with the store through booleans, so that no
assertion prints one), the file accesses (``file_accesses.json``), an activation
(``activations/<aid>.json``), the prospective graph (``prospective.dot``),
the dataflow as PDF (``flow.pdf``) and the definition AST
(``/definition/<trial_id>/ast.json``). Each route is called in every form
``views.py`` declares: with and without ``.json`` where both exist, and under
``/experiments/<expCode>/`` (``Vis.routes``). Expected values come from the
store (SQL) and from the files of the weather corpus in the project.

Known defects have a characterization of today's behavior and a
``_desired`` twin marked through ``known_defects``:

- ``EXPERIMENT_PREFIX`` (support.py): the ``activations`` and ``flow.pdf``
  views take no ``expCode``, so their experiment routes raise ``TypeError``.
  The frontend builds the activation URL from the root
  (``/trials/<tid>/activations/<aid>.json``), so only a URL typed by hand
  reaches it; it builds no ``flow.pdf`` URL at all.
- #241: the definition AST rebuilt by ``TrialAst`` fails from Python 3.14
  (``ast.parse`` validates the tree, whose statements have no ``lineno``)
  and, differently, from 3.15 (``ast.Module(name=...)`` is rejected).
- ``#366`` (the defect ``test_diff_routes.py``
  pins on ``info.json``): an activation's start and finish are the local
  wall-clock times labeled GMT, which the activation tooltip shows; the
  twin's mark applies only where the local time ``now run`` records is not
  UTC.

Measured on macOS with Python 3.11 to 3.15.

An unknown trial id crashes most of these routes (``now vis`` answers an
HTML 500): characterized only, since the frontend builds these URLs from
the ids the history gives it.
"""
import ast
import re
import shutil
from datetime import datetime, timedelta

import pytest
from werkzeug.http import http_date

from noworkflow.now.ipython import dotmagic
from noworkflow.tests.e2e.harness import WEATHER_ARGS, same_path

from .support import (
    EXPERIMENT_PREFIX,
    LOCAL_TIME_AS_GMT,
    NOW_RUN_UTC_OFFSET,
    NOW_RUN_ZONE,
    Defect,
    Vis,
    known_defects,
    served_instant,
    unknown_trial_id,
)

SCRIPT = "simulation.py"
# A function of the weather script that takes parameters and has a body.
FUNCTION = "run_simulation"


AST_LINENO = Defect(
    reason="#241: from Python 3.14 ast.parse() validates the tree that "
           "TrialAst (models/ast/trial_ast.py) rebuilds from the store, "
           "whose statements have no lineno",
    signature='required field "lineno" missing',
    since=(3, 14), before=(3, 15),
)
AST_MODULE_NAME = Defect(
    reason="#241: from Python 3.15 AST constructors reject unknown "
           "keywords, and TrialAst (models/ast/trial_ast.py) builds "
           "ast.Module(name=...)",
    signature="ast.Module.__init__ got an unexpected keyword argument 'name'",
    since=(3, 15),
)
AST_DEFECTS = (AST_LINENO, AST_MODULE_NAME)
ACTIVATION_KEYS = {
    "id", "line", "name", "start", "finish", "duration", "globals",
    "parameters", "return_value", "hash",
}
ENVIRONMENT_KEYS = {"trial_id", "id", "name", "value"}


# --- helpers ----------------------------------------------------------------


def one(rows, what):
    """The single row of a query"""
    assert len(rows) == 1, "{}: {} rows".format(what, len(rows))
    return rows[0]


def script_source(project):
    """The text of the weather script the trials ran, as it is on disk"""
    return (project.path / SCRIPT).read_bytes().decode("utf-8")


def script_functions(project):
    """The ``FunctionDef`` nodes of the weather script, in order"""
    tree = ast.parse(script_source(project))
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]


def script_function(project, name):
    """The ``FunctionDef`` of ``name`` in the weather script"""
    nodes = [node for node in script_functions(project) if node.name == name]
    assert len(nodes) == 1, "{} defines {} {}".format(SCRIPT, len(nodes), name)
    return nodes[0]


def first_activation(project, trial_id, name):
    """The first activation of a function in a trial"""
    rows = project.query(
        "SELECT * FROM activation WHERE trial_id = ? AND name = ? "
        "ORDER BY id", trial_id, name)
    assert rows, "no activation of {} in the trial".format(name)
    return rows[0]


def activation_row(project, trial_id, activation_id):
    """The activation row, or None"""
    rows = project.query(
        "SELECT * FROM activation WHERE trial_id = ? AND id = ?",
        trial_id, activation_id)
    return rows[0] if rows else None


def evaluation_row(project, trial_id, evaluation_id):
    """The evaluation row and the line of its code component"""
    return one(project.query(
        "SELECT evaluation.*, code_component.first_char_line AS line "
        "FROM evaluation JOIN code_component "
        "ON code_component.trial_id = evaluation.trial_id "
        "AND code_component.id = evaluation.code_component_id "
        "WHERE evaluation.trial_id = ? AND evaluation.id = ?",
        trial_id, evaluation_id), "evaluation {}".format(evaluation_id))


def evaluations_of_type(project, trial_id, activation_id, type_):
    """``"name = repr"`` of the evaluations of a component type inside an
    activation, sorted: the route's query has no ORDER BY
    """
    rows = project.query(
        "SELECT code_component.name, evaluation.repr "
        "FROM evaluation JOIN code_component "
        "ON code_component.trial_id = evaluation.trial_id "
        "AND code_component.id = evaluation.code_component_id "
        "WHERE evaluation.trial_id = ? AND evaluation.activation_id = ? "
        "AND code_component.type = ?", trial_id, activation_id, type_)
    return sorted("{} = {}".format(row["name"], row["repr"]) for row in rows)


def access_stack(project, trial_id, activation_id):
    """The stack of a file access, walked through the store

    The names of the activations from the access up to the script, the
    script's own activation left out, ending in ``open``.
    """
    names = []
    current = activation_row(project, trial_id, activation_id)
    while current is not None:
        caller_id = evaluation_row(
            project, trial_id, current["id"])["activation_id"]
        caller = activation_row(project, trial_id, caller_id)
        if caller is not None:
            names.insert(0, current["name"])
        current = caller
    if not names or names[-1] != "open":
        names.append("... -> open")
    return " -> ".join(names)


def stored_times(project, trial_row, activation):
    """``{"start": ..., "finish": ...}``: the naive times the model reads

    The trial's start plus the activation's start checkpoint and the
    checkpoint of its evaluation (``Activation.start`` and ``finish``).
    """
    start = datetime.fromisoformat(trial_row["start"])
    evaluation = evaluation_row(project, trial_row["id"], activation["id"])
    return {
        "start": start + timedelta(seconds=activation["start_checkpoint"]),
        "finish": start + timedelta(seconds=evaluation["checkpoint"]),
    }


def call_name(node):
    """The name of the class a node of a parsed ``ast.dump`` calls"""
    assert isinstance(node, ast.Call), ast.dump(node)[:80]
    return node.func.id


def keyword(node, name):
    """The value of a keyword of a parsed ``ast.dump`` call"""
    values = [item.value for item in node.keywords if item.arg == name]
    assert len(values) == 1, "{}: no {}=".format(call_name(node), name)
    return values[0]


def get_pdf(vis, route):
    """GET a ``flow.pdf`` route; skip where graphviz cannot draw it

    Without ``dot``, ``DotDisplay`` falls back to the DOT text and the view
    raises ``KeyError: 'application/pdf'``. The dataflow export runs before
    that, so a failure there is not skipped.
    """
    try:
        return vis.get(route)
    except KeyError as error:
        if error.args == ("application/pdf",) and shutil.which("dot") is None:
            pytest.skip("graphviz `dot` is not on the PATH: no PDF to send")
        raise


# --- dependencies -----------------------------------------------------------


@pytest.mark.parametrize("route", Vis.routes("trials/{}/dependencies.json")
                         + ["/trials/{}/dependencies"])
def test_dependencies_are_the_modules_of_each_trial(vis, route):
    """Each trial's ``dependencies`` lists the rows of ``module`` for that
    trial (or for the trial it inherited them from), every column plus the
    ``code_hash`` of the module's code block, and ``trial_path`` is the
    trial's path
    """
    for trial in vis.project.trials():
        body = vis.json(route.format(trial["id"]))
        assert set(body) == {"all", "trial_path"}
        assert body["trial_path"] == trial["path"]
        owner = trial["modules_inherited_from_trial_id"] or trial["id"]
        rows = vis.project.query(
            "SELECT module.*, code_block.code_hash FROM module "
            "LEFT JOIN code_block ON code_block.trial_id = module.trial_id "
            "AND code_block.id = module.code_block_id "
            "WHERE module.trial_id = ? ORDER BY module.id", owner)
        assert rows, "the weather trials import a local module"
        modules = sorted(body["all"], key=lambda module: module["id"])
        assert [module["id"] for module in modules] == [
            row["id"] for row in rows]
        for module, row in zip(modules, rows):
            assert set(module) == set(row)
            if row["transformed"] is not None:
                row["transformed"] = bool(row["transformed"])
            assert module == row


def test_dependencies_code_hash_names_the_source_of_the_module(vis):
    """The one module of the weather script is its local ``simulator``: the
    path is the project's file and ``code_hash`` names its stored source
    """
    trial_id = vis.trial_ids[-1]
    body = vis.json("/trials/{}/dependencies.json".format(trial_id))
    local = sorted(path.stem for path in vis.project.path.glob("*.py")
                   if path.name != SCRIPT)
    assert sorted(module["name"] for module in body["all"]) == local
    for module in body["all"]:
        source = vis.project.path / (module["name"] + ".py")
        assert same_path(module["path"], source), "the module's path"
        assert vis.project.content(module["code_hash"]) == (
            source.read_bytes()), "the stored source of " + module["name"]


# --- environment ------------------------------------------------------------


@pytest.mark.parametrize("route", Vis.routes("trials/{}/environment.json")
                         + ["/trials/{}/environment"])
def test_environment_has_one_item_per_attribute_name(vis, route):
    """``environment`` lists one item per attribute name the store recorded
    for the trial (a name recorded twice, as ``OS_NAME``, comes once), each
    with the keys of an ``environment_attr`` row: the id of a row of that
    name and that row's value, a string

    The values are the machine's: they are compared through booleans, so a
    failure names the attribute and never prints a value.
    """
    for trial in vis.project.trials():
        body = vis.json(route.format(trial["id"]))
        assert set(body) == {"all"}
        items = body["all"]
        rows = vis.project.query(
            "SELECT id, name, value FROM environment_attr WHERE trial_id = ?",
            trial["id"])
        names = [item["name"] for item in items]
        assert len(names) == len(set(names)), "a name comes twice"
        assert set(names) == {row["name"] for row in rows}
        ids = {(row["id"], row["name"]) for row in rows}
        values = {row["id"]: row["value"] for row in rows}
        for item in items:
            assert set(item) == ENVIRONMENT_KEYS, item["name"]
            assert item["trial_id"] == trial["id"], item["name"]
            assert (item["id"], item["name"]) in ids, item["name"]
            # Booleans first: introspection would print the value.
            is_text = isinstance(item["value"], str)
            assert is_text, "{}: the value is not a string".format(
                item["name"])
            stored = item["value"] == values[item["id"]]
            assert stored, "{}: not the value of its row".format(
                item["name"])


# --- file accesses ----------------------------------------------------------


@pytest.mark.parametrize("route", Vis.routes("trials/{}/file_accesses.json")
                         + ["/trials/{}/file_accesses"])
def test_file_accesses_are_the_rows_of_each_trial(vis, route):
    """``file_accesses`` lists the rows of ``file_access`` for the trial,
    every column, plus the ``stack`` of activations that opened the file;
    ``trial_path`` is the trial's path
    """
    for trial in vis.project.trials():
        body = vis.json(route.format(trial["id"]))
        assert set(body) == {"file_accesses", "trial_path"}
        assert body["trial_path"] == trial["path"]
        rows = vis.project.query(
            "SELECT * FROM file_access WHERE trial_id = ? ORDER BY id",
            trial["id"])
        assert rows, "the weather script reads and writes files"
        accesses = sorted(body["file_accesses"],
                          key=lambda access: access["id"])
        assert len(accesses) == len(rows)
        for access, row in zip(accesses, rows):
            stack = access.pop("stack")
            assert access == row
            assert stack == access_stack(
                vis.project, trial["id"], row["activation_id"])


def test_file_accesses_of_the_last_trial_hash_the_project_files(vis):
    """In the last trial, a read file's hash before the access and a written
    file's hash after it are those of the file in the project now; each
    stack ends in ``open``
    """
    trial_id = vis.trial_ids[-1]
    body = vis.json("/trials/{}/file_accesses.json".format(trial_id))
    files = vis.project.files()
    modes = set()
    for access in body["file_accesses"]:
        modes.add(access["mode"])
        key = ("content_hash_after" if "w" in access["mode"]
               else "content_hash_before")
        assert access[key] == files[access["name"]], access["name"]
        assert access["stack"].endswith(" -> open"), access["name"]
    assert modes == {"r", "w"}


# --- activations ------------------------------------------------------------


ACTIVATION_ROUTES = ["/trials/{}/activations/{}.json",
                     "/trials/{}/activations/{}"]
EXPERIMENT_ACTIVATION_ROUTES = [
    Vis.routes("trials/{}/activations/{}.json")[1],
    Vis.routes("trials/{}/activations/{}")[1],
]


@pytest.mark.parametrize("route", ACTIVATION_ROUTES)
def test_activation_answers_its_record(vis, route):
    """The activation of a function: its id, its name, the line of the
    call, start and finish as far apart as its checkpoints, the duration in
    microseconds, the globals and the parameters it evaluated as ``name =
    repr``, the repr of its return value and the hash of its code block

    Where start and finish are in time is the subject of
    ``test_activation_times_*``.
    """
    trial = vis.project.trials()[0]
    activation = first_activation(vis.project, trial["id"], FUNCTION)
    aid = activation["id"]
    body = vis.json(route.format(trial["id"], aid))
    assert set(body) == ACTIVATION_KEYS
    evaluation = evaluation_row(vis.project, trial["id"], aid)
    block = one(vis.project.query(
        "SELECT code_hash FROM code_block WHERE trial_id = ? AND id = ?",
        trial["id"], activation["code_block_id"]), "code block")
    elapsed = evaluation["checkpoint"] - activation["start_checkpoint"]
    # The frontend only prints the id: a string today, the URL's segment.
    assert str(body["id"]) == str(aid)
    assert body["name"] == activation["name"]
    assert body["line"] == evaluation["line"]
    served = (served_instant(body["finish"])
              - served_instant(body["start"])).total_seconds()
    # Each time is truncated to the second.
    assert abs(served - elapsed) < 1
    assert abs(body["duration"] - elapsed * 1000000) <= 1
    assert sorted(body["globals"]) == evaluations_of_type(
        vis.project, trial["id"], aid, "global")
    assert sorted(body["parameters"]) == evaluations_of_type(
        vis.project, trial["id"], aid, "param")
    assert body["return_value"] == evaluation["repr"]
    assert body["hash"] == block["code_hash"]


def test_activation_matches_the_script(vis):
    """Against the weather script: the line is the one that calls the
    function, the parameters are its arguments, with the command line's
    file names as values, and the hash names the stored source of the
    function
    """
    trial_id = vis.trial_ids[0]
    aid = first_activation(vis.project, trial_id, FUNCTION)["id"]
    body = vis.json("/trials/{}/activations/{}.json".format(trial_id, aid))
    source = script_source(vis.project)
    node = script_function(vis.project, FUNCTION)
    calls = [call.lineno for call in ast.walk(ast.parse(source))
             if isinstance(call, ast.Call)
             and getattr(call.func, "id", None) == FUNCTION]
    assert body["line"] in calls
    names = [parameter.split(" = ")[0] for parameter in body["parameters"]]
    assert sorted(names) == sorted(arg.arg for arg in node.args.args)
    first, second = node.args.args[:2]
    assert "{} = {!r}".format(first.arg, WEATHER_ARGS[2]) in body[
        "parameters"]
    assert "{} = {!r}".format(second.arg, WEATHER_ARGS[3]) in body[
        "parameters"]
    assert vis.project.content(body["hash"]) == ast.get_source_segment(
        source, node).encode("utf-8")


def test_activation_without_code_block_has_an_empty_hash(vis):
    """An activation of a function without a code block (a builtin such as
    the ``open`` of a file access) answers an empty ``hash``
    """
    trial_id = vis.trial_ids[0]
    activation = vis.project.query(
        "SELECT * FROM activation WHERE trial_id = ? "
        "AND code_block_id IS NULL ORDER BY id", trial_id)[0]
    body = vis.json("/trials/{}/activations/{}.json".format(
        trial_id, activation["id"]))
    assert body["name"] == activation["name"]
    assert body["hash"] == ""


def test_activation_times_are_local_times_labeled_gmt(vis):
    """Today start and finish are the naive times of the store (the trial's
    start plus the checkpoints) formatted as HTTP dates, which say GMT
    whatever zone ``now run`` recorded them in

    Characterization of LOCAL_TIME_AS_GMT.
    """
    trial = vis.project.trials()[0]
    activation = first_activation(vis.project, trial["id"], FUNCTION)
    body = vis.json("/trials/{}/activations/{}.json".format(
        trial["id"], activation["id"]))
    for key, stored in stored_times(vis.project, trial, activation).items():
        # A boolean: both sides together would tell the machine's zone.
        naive = body[key] == http_date(stored)
        assert naive, "{}: not the store's naive time as an HTTP date".format(
            key)
        assert body[key].endswith(" GMT"), key


@known_defects(LOCAL_TIME_AS_GMT)
def test_activation_times_desired(vis):
    """Read as a client reads them, start and finish name the instants the
    activation started and finished (to the second)
    """
    trial = vis.project.trials()[0]
    activation = first_activation(vis.project, trial["id"], FUNCTION)
    body = vis.json("/trials/{}/activations/{}.json".format(
        trial["id"], activation["id"]))
    for key, stored in stored_times(vis.project, trial, activation).items():
        recorded = stored.replace(tzinfo=NOW_RUN_ZONE)
        gap = (served_instant(body[key]) - recorded).total_seconds()
        # Today's gap is the zone's offset (the local clock read as UTC),
        # give or take the truncation to the second. Booleans only: the
        # offset would tell the machine's zone.
        on_time = abs(gap) < 1
        shifted = abs(gap - NOW_RUN_UTC_OFFSET) < 1
        assert on_time, "{}: not the recorded instant{}".format(
            key, ", off by the UTC offset of now run's zone"
            if shifted else "")


@pytest.mark.parametrize("route", EXPERIMENT_ACTIVATION_ROUTES)
def test_activation_under_an_experiment_raises_type_error(vis, route):
    """Today the activation routes under ``/experiments/<expCode>/`` raise
    ``TypeError``: the view takes no ``expCode``

    Characterization of EXPERIMENT_PREFIX.
    """
    trial_id = vis.trial_ids[0]
    aid = first_activation(vis.project, trial_id, FUNCTION)["id"]
    with pytest.raises(TypeError, match=re.escape(
            EXPERIMENT_PREFIX.signature)):
        vis.get(route.format(trial_id, aid))


@pytest.mark.parametrize("route", EXPERIMENT_ACTIVATION_ROUTES)
@known_defects(EXPERIMENT_PREFIX)
def test_activation_under_an_experiment_desired(vis, route):
    """Under ``/experiments/<expCode>/`` an activation answers what it
    answers at the root
    """
    trial_id = vis.trial_ids[0]
    aid = first_activation(vis.project, trial_id, FUNCTION)["id"]
    expected = vis.json(ACTIVATION_ROUTES[0].format(trial_id, aid))
    assert vis.json(route.format(trial_id, aid)) == expected


# --- prospective.dot --------------------------------------------------------


@pytest.mark.parametrize("route", Vis.routes("trials/{}/prospective.dot"))
def test_prospective_dot_draws_the_functions_of_the_script(vis, route):
    """``prospective.dot`` answers a DOT digraph as text, with a node per
    function the script defines, labeled ``<line>: def <name>(``
    """
    trial_id = vis.trial_ids[0]
    response = vis.get(route.format(trial_id))
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    text = response.get_data(as_text=True)
    assert re.match(r"(strict )?digraph \{", text), text[:40]
    for node in script_functions(vis.project):
        assert "{}: def {}(".format(node.lineno, node.name) in text, node.name


def test_prospective_dot_of_an_unknown_trial_answers_500(vis):
    """Today ``prospective.dot`` of an unknown trial answers 500 with the
    text ``Unexpected error: Trial <id> not found``: ``Trial()`` raises
    ``RuntimeError``, which the view's 400 branch (``ValueError``) misses
    """
    trial_id = unknown_trial_id(vis)
    response = vis.get("/trials/{}/prospective.dot".format(trial_id))
    assert response.status_code == 500
    assert response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == (
        "Unexpected error: Trial {} not found".format(trial_id))


# --- flow.pdf ---------------------------------------------------------------


def test_flow_pdf_answers_the_dataflow_as_a_pdf(vis_own):
    """``flow.pdf`` answers the trial's dataflow drawn by graphviz as a PDF
    named ``flow.pdf`` (skipped without ``dot``, after the dataflow export
    has run)
    """
    trial_id = vis_own.trial_ids[0]
    response = get_pdf(vis_own, "/trials/{}/flow.pdf".format(trial_id))
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert "flow.pdf" in response.headers.get("Content-Disposition", "")
    assert response.get_data().startswith(b"%PDF")


def test_flow_pdf_sends_what_graphviz_draws_of_the_dataflow(vis, monkeypatch):
    """``flow.pdf`` hands the trial's dataflow to graphviz and sends the PDF
    it draws, named ``flow.pdf``; graphviz is replaced, so this runs where
    ``dot`` is not on the PATH too
    """
    drawn = []

    def fake_dot_to_pdf(dot, prog, extra, force_ink=False):
        drawn.append(dot)
        return b"%PDF-fake"

    monkeypatch.setattr(dotmagic, "dot_to_pdf", fake_dot_to_pdf)
    trial_id = vis.trial_ids[0]
    response = vis.get("/trials/{}/flow.pdf".format(trial_id))
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers.get("Content-Disposition") == (
        "inline; filename=flow.pdf")
    assert response.get_data() == b"%PDF-fake"
    assert len(drawn) == 1
    assert drawn[0].startswith("digraph e_")


def test_flow_pdf_under_an_experiment_raises_type_error(vis):
    """Today ``flow.pdf`` under ``/experiments/<expCode>/`` raises the
    ``TypeError`` of EXPERIMENT_PREFIX before the view runs

    Characterization of EXPERIMENT_PREFIX.
    """
    trial_id = vis.trial_ids[0]
    with pytest.raises(TypeError, match=re.escape(
            EXPERIMENT_PREFIX.signature)):
        vis.get(Vis.routes("trials/{}/flow.pdf")[1].format(trial_id))


@known_defects(EXPERIMENT_PREFIX)
def test_flow_pdf_under_an_experiment_desired(vis_own):
    """Under ``/experiments/<expCode>/`` ``flow.pdf`` answers what it
    answers at the root
    """
    trial_id = vis_own.trial_ids[0]
    route = Vis.routes("trials/{}/flow.pdf")[1].format(trial_id)
    response = get_pdf(vis_own, route)
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert "flow.pdf" in response.headers.get("Content-Disposition", "")
    assert response.get_data().startswith(b"%PDF")


# --- definition AST ---------------------------------------------------------


@pytest.mark.skipif(not any(defect.applies() for defect in AST_DEFECTS),
                    reason="#241 does not show on this Python: the "
                           "_desired twin is the test")
def test_definition_ast_raises_type_error_on_recent_pythons(vis):
    """Today ``/definition/<trial_id>/ast.json`` raises ``TypeError``: on
    3.14 ``required field "lineno" missing``, from 3.15
    ``ast.Module.__init__ got an unexpected keyword argument 'name'``

    Characterization of #241.
    """
    (defect,) = [defect for defect in AST_DEFECTS if defect.applies()]
    trial_id = vis.trial_ids[0]
    with pytest.raises(TypeError, match=re.escape(defect.signature)):
        vis.get("/definition/{}/ast.json".format(trial_id))


@known_defects(*AST_DEFECTS)
def test_definition_ast_desired(vis):
    """``ast.json`` answers ``{"ast": {<id>: <ast.dump>}, "trial": <id>}``,
    whose tree is a ``Module`` with the script's top-level statements, in
    order, the functions under their names
    """
    trial_id = vis.trial_ids[0]
    body = vis.json("/definition/{}/ast.json".format(trial_id))
    assert set(body) == {"ast", "trial"}
    assert body["trial"] == trial_id
    assert list(body["ast"]) == [trial_id]
    root = ast.parse(body["ast"][trial_id], mode="eval").body
    assert call_name(root) == "Module"
    statements = keyword(root, "body").elts
    script = ast.parse(script_source(vis.project))
    assert [call_name(node) for node in statements] == [
        type(node).__name__ for node in script.body]
    functions = [keyword(node, "name").value for node in statements
                 if call_name(node) == "FunctionDef"]
    assert functions == [node.name for node in script_functions(vis.project)]


# --- unknown ids ------------------------------------------------------------


@pytest.mark.parametrize("route", [
    "/trials/{}/dependencies.json",
    "/trials/{}/environment.json",
    "/trials/{}/file_accesses.json",
    "/trials/{}/flow.pdf",
    "/definition/{}/ast.json",
])
def test_an_unknown_trial_raises_runtime_error(vis, route):
    """Today an unknown trial id raises ``RuntimeError: Trial <id> not
    found`` from ``Trial()``, before anything else the view does; ``now
    vis`` answers an HTML 500
    """
    trial_id = unknown_trial_id(vis)
    with pytest.raises(RuntimeError, match="Trial {} not found".format(
            re.escape(trial_id))):
        vis.get(route.format(trial_id))


@pytest.mark.parametrize("which", ["trial", "activation"])
def test_an_unknown_activation_raises_attribute_error(vis, which):
    """Today an activation that is not in the store (unknown trial, or an id
    past the trial's last) raises ``AttributeError`` on ``None``:
    ``Activation()`` copies the columns of a row it did not find
    """
    trial_id = vis.trial_ids[0]
    last = vis.project.query(
        "SELECT MAX(id) AS id FROM activation WHERE trial_id = ?",
        trial_id)[0]["id"]
    if which == "trial":
        trial_id, aid = unknown_trial_id(vis), 1
    else:
        aid = last + 1
    with pytest.raises(AttributeError, match="'NoneType' object"):
        vis.get("/trials/{}/activations/{}.json".format(trial_id, aid))
