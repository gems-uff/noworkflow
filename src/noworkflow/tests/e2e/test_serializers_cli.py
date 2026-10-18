# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now run -r`` with each serializer, and a quoted file name in the export

The serializer decides the text that a real store keeps in
``evaluation.repr`` for every value. The other e2e tests run the default,
``repr``; these run ``-r jsonpickle`` and ``-r jsonpickle_content``
with the jsonpickle stub of ``helpers/jsonpickle_stub.py`` written next to
the script (jsonpickle is not a dependency, and the script's directory
shadows an installed one), and ``-r simple`` on a class whose ``__repr__``
reads an attribute that ``__init__`` sets, which crashes the default
serializer (#307). The values are read back with SQL on the store.

``now export prolog`` writes text columns through ``PrologRepr``, which
drops the first letter of a file name such as ``l'Avenue.txt``
(prolog-repr-strips-letter-before-quote; the unit tests are in
``utils/test_prolog.py``). The export also holds the environment facts:
assertion messages here print only the ``access`` facts.

A known defect has a characterization of what ``now`` does today and a
``_desired`` twin, marked through ``known_defects``, that states what it
should do. A twin asserts only that the run no longer fails and what it
stores, never the return code or the stream of the error, which #226
changes, so that each twin flips with the fix of its own defect.
"""
from ..helpers import jsonpickle_stub, swipl
from ..helpers.defects import Defect, known_defects

CONTENT_PUTS_STR = Defect(
    "#339: jsonpickle_content "
    "(persistence/serializers.py) passes the str that jsonpickle.encode "
    "returns to content.put, and the plain engine's do_put "
    "(persistence/content/plain_engine.py) hashes it with hashlib.sha1, "
    "which takes bytes only: the first value the collector serializes "
    "raises TypeError, the script body never runs and the trial stays "
    "unfinished",
    signature="Strings must be encoded before hashing")
LETTER_BEFORE_QUOTE = Defect(
    "#338: PrologRepr.fact "
    "(utils/prolog.py) applies the heuristics meant for a stored repr() to "
    "the file name that file_access keeps, dropping the letter before a "
    "quote and then the quote, so `now export prolog` writes l'Avenue.txt "
    "as '''Avenue.txt'",
    signature="'''Avenue.txt'")

# A script with one value whose serialization the tests read back.
LIST_SCRIPT = "x = [1, 2]\nprint(len(x))\n"
# #307's shape: __repr__ reads an attribute that __init__ sets.
POINT_SCRIPT = '''\
class Point:
    def __init__(self, x):
        self.x = x

    def __repr__(self):
        return "Point({})".format(self.x)


point = Point(1)
values = [1, (2, "a")]
print(repr(point), len(values))
'''
# A file name whose second character is a quote.
APOSTROPHE_NAME = "l'Avenue.txt"
APOSTROPHE_SCRIPT = '''\
with open("l'Avenue.txt", "w", encoding="utf-8") as handle:
    handle.write("x")
'''
CONTENT_PREFIX = "now-content:"


def only_trial(project):
    """The single trial of a store that ran once"""
    trials = project.trials()
    assert len(trials) == 1, "expected one trial, found {}".format(
        len(trials))
    return trials[0]


def written(project, name):
    """``evaluation.repr`` of each assignment to ``name``, in order"""
    trial = only_trial(project)
    return [row["repr"] for row in project.query(
        "SELECT evaluation.repr FROM evaluation JOIN code_component "
        "ON code_component.trial_id = evaluation.trial_id "
        "AND code_component.id = evaluation.code_component_id "
        "WHERE evaluation.trial_id = ? AND code_component.name = ? "
        "AND code_component.mode = 'w' ORDER BY evaluation.id",
        trial["id"], name)]


def run_with_stub(project, serializer, **kwargs):
    """``now run -r <serializer>`` on LIST_SCRIPT, with the jsonpickle stub
    next to it"""
    jsonpickle_stub.write_into(project)
    project.write("script.py", LIST_SCRIPT)
    return project.run("run", "-r", serializer, "script.py", **kwargs)


# --- -r jsonpickle and -r jsonpickle_content --------------------------------

def test_run_with_the_jsonpickle_serializer_records_what_encode_returns(
        project):
    """``-r jsonpickle`` runs the script and records, for each value, the
    text that ``jsonpickle.encode(value, keys=True)`` returns"""
    result = run_with_stub(project, "jsonpickle")
    assert result.stdout == "2\n", str(result)
    assert only_trial(project)["status"] == "finished"
    assert written(project, "x") == [
        jsonpickle_stub.encode([1, 2], keys=True)]


def test_run_with_the_jsonpickle_content_serializer(project):
    """Characterization: ``-r jsonpickle_content`` fails at the first value
    with a TypeError reported on stdout and return code 0; the script body
    never runs and the trial is unfinished (#226 changes the return code
    and the stream)"""
    result = run_with_stub(project, "jsonpickle_content")
    lines = result.stdout.splitlines()
    assert lines[0] == (
        "[now] TypeError('Strings must be encoded before hashing')"), (
        str(result))
    assert "2" not in lines, str(result)
    assert only_trial(project)["status"] == "unfinished"


@known_defects(CONTENT_PUTS_STR)
def test_run_with_the_jsonpickle_content_serializer_desired(project):
    """``-r jsonpickle_content`` runs the script, records a reference to the
    content store for each value, and the store holds the encoding"""
    result = run_with_stub(project, "jsonpickle_content", expect=None,
                           allow_stderr=True)
    assert result.stdout == "2\n", str(result)
    assert only_trial(project)["status"] == "finished"
    reprs = written(project, "x")
    assert len(reprs) == 1, reprs
    assert reprs[0].startswith(CONTENT_PREFIX), reprs
    stored = project.content(reprs[0][len(CONTENT_PREFIX):])
    assert stored.decode("utf-8") == jsonpickle_stub.encode([1, 2], keys=True)


# --- -r simple --------------------------------------------------------------

def test_run_with_the_simple_serializer_records_values_without_calling_repr(
        project):
    """``-r simple`` runs a script whose ``__repr__`` the default serializer
    would call too early (#307), records containers item by item with the
    ``repr()`` of each leaf, and an object by its class and address"""
    project.write("script.py", POINT_SCRIPT)
    result = project.run("run", "-r", "simple", "script.py")
    assert result.stdout == "Point(1) 2\n", str(result)
    assert only_trial(project)["status"] == "finished"
    assert written(project, "values") == [
        "list([{}, tuple([{}, {}])])".format(repr(1), repr(2), repr("a"))]
    point = written(project, "point")
    assert len(point) == 1, point
    assert point[0].startswith("<Point instance at 0x"), point


# --- now export prolog ------------------------------------------------------

def access_facts(project):
    """The ``access`` facts of ``now export prolog -t``

    The rest of the export (the environment above all) never reaches an
    assertion message.
    """
    text = project.run("export", "prolog", "-t").stdout
    return [line for line in text.splitlines() if line.startswith("access(")]


def stored_names(project):
    """``file_access.name`` of every access of the only trial"""
    trial = only_trial(project)
    return [row["name"] for row in project.query(
        "SELECT name FROM file_access WHERE trial_id = ? ORDER BY id",
        trial["id"])]


def test_export_prolog_file_name_with_an_apostrophe_after_a_letter(project):
    """Characterization: the store keeps ``l'Avenue.txt``, and its
    ``access`` fact names the file ``'''Avenue.txt'``, an atom without the
    first letter"""
    project.write("script.py", APOSTROPHE_SCRIPT)
    project.run("run", "script.py")
    assert stored_names(project) == [APOSTROPHE_NAME]
    facts = access_facts(project)
    assert len(facts) == 1, facts
    assert ", '''Avenue.txt', 'w', " in facts[0], facts


@known_defects(LETTER_BEFORE_QUOTE)
def test_export_prolog_file_name_with_an_apostrophe_after_a_letter_desired(
        project):
    """The ``access`` fact names the file with the quoted atom of the name
    the store keeps"""
    project.write("script.py", APOSTROPHE_SCRIPT)
    project.run("run", "script.py")
    names = stored_names(project)
    assert names == [APOSTROPHE_NAME]
    facts = access_facts(project)
    assert len(facts) == 1, facts
    expected = ", {}, 'w', ".format(swipl.quoted_atom(names[0]))
    assert expected in facts[0], facts
