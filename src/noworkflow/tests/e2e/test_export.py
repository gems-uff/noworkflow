# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now export``: prolog, prov, dataflow, ast, prospective and ipynb

The prolog, prov, ast and prospective exports read the shared
``two_trial_project`` and never write to it: they only print to stdout.
``export dataflow`` runs on the dataflow corpus, built once per module and
read-only afterwards: ``simulation.py``, on which the five modes work and
whose ``-w`` graphs are checked against the whole graph of the same mode
(the clustered modes crash with ``-w`` on one of its writes, #200), and the
two scripts that crash the clustered modes without ``-w``
(#242). ``export ast`` fails on recent Pythons: the
text and ``-j`` forms from 3.14 (#241), every form from
3.15 (#241); ``harness.export_ast_failure`` says which form
fails where. ``export ipynb`` writes a notebook into the current directory,
so each of its tests builds a weather project of its own. The scripts
whose text writes a double quote or a backslash into the DOT of ``export
dataflow`` or ``export prospective`` (#401) are run each in a project of
its own, and their graphs are read by ``DotGraph``, which follows
Graphviz's lexer and grammar, so that no test needs Graphviz (#393); the
graphs of the shared stores are its control.

The goldens are compared on the reference leg only; the structural tests run
on every leg. ``export prolog`` records the whole environment of the machine
that ran the script, so its goldens are taken after the ``environment``
predicate is removed, and the environment facts are checked by name on the
raw output, which is never stored and never printed. The same goes for the
hostname in ``export prov``: the assertions that read it compare booleans
with fixed messages.

Known defects get a characterization of what ``now`` does today and a
``_desired`` twin marked ``xfail(strict=True, raises=AssertionError)``,
which turns green when the issue in its reason is fixed. The two share a
name that says the scenario, never the outcome. The twins of #401 go
through ``known_defects``, which also checks that today's failure carries
the signature of its defect, and accept any escaping that Graphviz reads
back as the text of the code or of the value: they check what a label
draws, not how it is spelled.
"""

import ast
import collections
import html
import json
import os
import re
import socket
import sys

import pytest

from noworkflow.tests.e2e.golden import assert_golden
from noworkflow.tests.e2e.harness import (
    EXPORT_AST_FORMS,
    EXPORT_AST_PY314,
    EXPORT_AST_PY315,
    USER,
    NowProject,
    export_ast_failure,
    last_line,
    runs_this_interpreter,
)
from noworkflow.tests.e2e.normalize import (
    clause_arity,
    prolog_facts,
    prolog_statements,
    strip_prolog_predicate,
    usable_hostname,
)
from noworkflow.tests.helpers.defects import Defect, known_defects

# --- export prolog ----------------------------------------------------------

PROLOG_CASES = [
    ("prolog-t", ("-t",)),
    ("prolog-t-r", ("-t", "-r")),
]
# Attributes that deployment.py records on every system.
REQUIRED_ENVIRONMENT = {"PYTHON_VERSION", "NOWORKFLOW_VERSION", "USER", "HOSTNAME"}
ENVIRONMENT_FACT = re.compile(
    r"environment\('(?:[^']|'')*', '((?:[^']|'')*)', '((?:[^']|'')*)'\)\.\s*$",
    re.DOTALL,
)
# A call inside a rule body: an atom followed by an opening parenthesis.
CALL = re.compile(r"(?<![\w])([a-z]\w*)\(")
# ``member/2`` in a rule body is the list builtin, not the ``member/8`` facts.
BUILTIN_CALLS = {("member", 2)}

# --- export dataflow --------------------------------------------------------

DATAFLOW_MODES = (
    "activation",
    "coarseGrain",
    "looplessCoarseGrain",
    "fineGrain",
    "all",
)
# `-w` with the write of `data` crashes the clustered modes, and so does the
# default mode (coarseGrain) when `-m` is omitted.
WDF_CRASHES = [
    pytest.param(("-m", "coarseGrain"), id="coarseGrain"),
    pytest.param(("-m", "looplessCoarseGrain"), id="looplessCoarseGrain"),
    pytest.param((), id="default"),
]
WDF_REASON = (
    "#200: `export dataflow -w` with the write of `data` crashes with "
    "KeyError in coarseGrain and looplessCoarseGrain, the default mode "
    "included"
)
# `-w` works in the three unclustered modes with the write of `data`, and in
# every mode with the write of `size`.
WDF_CONTROLS = [(mode, "data") for mode in ("activation", "fineGrain", "all")] + [
    (mode, "size") for mode in DATAFLOW_MODES
]
# The label of a DOT node or cluster: `label="..."` or `label = "..."`.
DOT_LABEL = re.compile(r'\blabel\s*=\s*"((?:[^"\\]|\\.)*)"')
# A file access node: `a_<n> [label="<file name>" ...`.
ACCESS_NODE = re.compile(r'^\s*a_\d+ \[label="((?:[^"\\]|\\.)*)"', re.MULTILINE)
PLOT = re.compile(r"\bplot\b")
CALL_SCRIPTS = ("nested_call.py", "repeated_call.py")
# f(g(x)) crashes both clustered modes; a call site that runs more than once
# crashes looplessCoarseGrain.
CALL_CRASHES = [
    ("nested_call.py", "coarseGrain"),
    ("nested_call.py", "looplessCoarseGrain"),
    ("repeated_call.py", "looplessCoarseGrain"),
]
CALL_CONTROLS = [
    (script, mode)
    for script in CALL_SCRIPTS
    for mode in DATAFLOW_MODES
    if (script, mode) not in CALL_CRASHES
]
CALL_REASON = (
    "#242: `export dataflow` without -w crashes with "
    "KeyError on a nested call to a user function (coarseGrain and "
    "looplessCoarseGrain) and on a call site that runs more than once "
    "(looplessCoarseGrain)"
)
KEY_ERROR = re.compile(r"KeyError: 'e_\d+'")
# Scripts whose text writes a double quote or a backslash into a label
# (#401), each run in a project of its own.
ESCAPED_QUOTE_SCRIPT = 'print("say \\"hi\\"")\n'
QUOTED_CLASS_SCRIPT = (
    "def init(self, v):\n"
    "    self.v = v * 2\n"
    "\n"
    "\n"
    "K = type('a\"b', (), {'__init__': init})\n"
    "k = K(1)\n"
)
# The repr of a str always ends in its quote: only a __repr__ ends a value
# in a backslash.
BACKSLASH_REPR_SCRIPT = (
    'class R:\n    def __repr__(self):\n        return "C:\\\\data\\\\"\n\n\nr = R()\n'
)
ESCAPED_QUOTE = Defect(
    reason="#401: dot_visitor.escape puts a backslash before each double "
    "quote of a name but doubles no backslash, and Attributes.dot "
    'writes it between quotes as it is: the \\" of a string literal '
    'becomes \\\\", which DOT reads as an escaped backslash and the '
    "closing quote of the label",
    signature=r'[label="1 \"say \\"hi\\"\""',
)
CLUSTER_LABEL = Defect(
    reason="#401: DotVisitor.visit_cluster writes the activation name into "
    "the cluster's label with no escaping at all: a double quote in "
    "the name closes the label, and the rest of the name is read as "
    "DOT",
    signature='label = "a"b";',
)
TRAILING_BACKSLASH = Defect(
    reason="#401: dot_visitor.escape doubles no backslash, so a value whose "
    "repr ends in an odd number of backslashes escapes the closing "
    "quote of its label, which runs on into the next attribute",
    signature=r"C:\data\" fillcolor",
)

# --- export ast -------------------------------------------------------------

# What the last line of stderr holds for each failure that
# harness.export_ast_failure() names.
EXPORT_AST_ERRORS = {
    EXPORT_AST_PY314: 'required field "lineno" missing',
    EXPORT_AST_PY315: "unexpected keyword argument",
}


def ast_form_params():
    """The forms of ``export ast``, each marked xfail where
    ``export_ast_failure`` names a defect on this interpreter
    """
    params = []
    for form in EXPORT_AST_FORMS:
        failure = export_ast_failure(form)
        marks = (
            [pytest.mark.xfail(strict=True, raises=AssertionError, reason=failure)]
            if failure
            else []
        )
        params.append(pytest.param(form, marks=marks, id=form))
    return params


AST_FORMS = ast_form_params()

# A dict display with a ** item between two key-value pairs (#427), and the
# ast.dump of the display that `export ast` rebuilds, whose constants hold
# the source text of each key and value.
DICT_UNPACKING_SCRIPT = "base = {'a': 1}\nmerged = {'z': 0, **base, 'y': 2}\n"
DICT_UNPACKING_DUMP = (
    "Dict(keys=[Constant(value=\"'z'\"), None, Constant(value=\"'y'\")], "
    "values=[Constant(value='0'), Name(id='base', ctx=Load()), "
    "Constant(value='2')])"
)

# --- export prospective -----------------------------------------------------

# The condition `s == r"a\:b"`, which the prospective graph cuts at its
# first ':' (#401): whole, and as it is cut.
BACKSLASH_CONDITION_SCRIPT = 's = "x"\nif s == r"a\\:b":\n    print("match")\n'
CONDITION = " Condition:"
WHOLE_CONDITION = 's == r"a\\:b"'
CUT_CONDITION = 's == r"a\\'
PROSPECTIVE_LABEL = Defect(
    reason="#401: GraphDrawer passes code text to the graphviz library as "
    "labels without graphviz.escape, and NodeMapper.get_condition "
    "cuts the condition at the first ':' of the line, one inside a "
    "string literal too: a condition cut after a backslash ends its "
    "label in an odd backslash, which the library warns about and "
    "leaves in place",
    signature="DotSyntaxWarning: expect syntax error scanning invalid quoted string",
)

# --- export ipynb -----------------------------------------------------------

CURRENT_NOTEBOOK = "Current Trial.ipynb"


def environment_facts(text):
    """``[(name, value)]`` of the ``environment/3`` facts of a Prolog export

    A value may hold a newline, so the facts are read as whole statements.
    """
    facts = []
    for kind, body in prolog_statements(text):
        if kind == "clause" and body.startswith("environment("):
            match = ENVIRONMENT_FACT.match(body)
            assert match, "an environment fact does not have three atoms"
            facts.append((match.group(1), match.group(2)))
    return facts


def declared_arities(text):
    """``{name: N}`` of the ``:- dynamic(name/N).`` declarations"""
    return {
        name: declared
        for name, (declared, _) in prolog_facts(text).items()
        if declared is not None
    }


def rule_calls(rules):
    """``Counter((name, arity))`` of every call in the rule bodies

    The rules part of ``export prolog -r`` is ``resources/rules.pl``: rules
    are indented, comments start with ``%`` after the indentation, and a
    rule ends with the line that ends with ``.``.
    """
    clauses, current = [], []
    for line in rules.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        current.append(stripped)
        if stripped.endswith("."):
            clauses.append(" ".join(current))
            current = []
    assert not current, "a rule does not end with a period"
    calls = collections.Counter()
    for clause in clauses:
        _, neck, body = clause.partition(":-")
        if not neck:
            continue
        for match in CALL.finditer(body):
            calls[(match.group(1), clause_arity(body[match.end() :]))] += 1
    return calls


def prolog_parts(project):
    """``(facts, rules)``: ``export prolog -t`` and what ``-r`` appends"""
    facts = project.run("export", "prolog", "-t").stdout
    with_rules = project.run("export", "prolog", "-t", "-r").stdout
    # A boolean, so that a failure never prints the environment facts.
    same_facts = with_rules.startswith(facts)
    assert same_facts, "`-t -r` does not start with the facts of `-t`"
    return facts, with_rules[len(facts) :]


def stale_rule_calls(project):
    """``{(name, used, declared)}`` of the rule calls to a fact predicate
    with an arity other than the declared one
    """
    facts, rules = prolog_parts(project)
    declared = declared_arities(facts)
    calls = rule_calls(rules)
    # Not vacuous: the rules call the facts.
    assert ("evaluation", declared["evaluation"]) in calls, (
        "the rules never call evaluation/{}".format(declared["evaluation"])
    )
    return {
        (name, arity, declared[name])
        for name, arity in calls
        if name in declared
        and arity != declared[name]
        and (name, arity) not in BUILTIN_CALLS
    }


def written_evaluation(project, variable):
    """Id of the evaluation that wrote ``variable`` in the last trial"""
    trial_id = project.trials()[-1]["id"]
    rows = project.query(
        "SELECT evaluation.id FROM evaluation JOIN code_component "
        "ON code_component.id = evaluation.code_component_id "
        "AND code_component.trial_id = evaluation.trial_id "
        "WHERE evaluation.trial_id = ? AND code_component.name = ? "
        "AND code_component.mode = 'w' AND code_component.type = 'name'",
        trial_id,
        variable,
    )
    assert len(rows) == 1, "{} writes of {!r}".format(len(rows), variable)
    return rows[0]["id"]


def attribute_lines(dot):
    """Lines of a DOT graph that carry ``[...]``: its nodes and edges"""
    return sum("[" in line for line in dot.splitlines())


def not_derived(dot, variable):
    """Labels of a dataflow graph of ``simulation.py`` that did not derive
    the write of ``variable``

    ``plot`` runs after ``data`` is written: for ``data``, every node or
    cluster label that names ``plot``. ``result.txt`` is opened after
    ``size`` is written: for ``size``, its access node.
    """
    if variable == "data":
        return [label for label in DOT_LABEL.findall(dot) if PLOT.search(label)]
    return [label for label in ACCESS_NODE.findall(dot) if label == "result.txt"]


def assert_derivation_graph(project, mode_args, variable):
    """``export dataflow <mode_args> -w <eid>``, with the write of
    ``variable`` in ``simulation.py``, draws only what derived it

    Compared with the graph of the same mode without ``-w``: fewer lines
    with attributes, none of the labels that ``not_derived`` finds there,
    and the access to ``input.txt``, which derived both writes. Every mode
    but activation (whose nodes are activations) keeps the node of the
    evaluation.
    """
    eid = written_evaluation(project, variable)
    whole = project.run("export", "dataflow", *mode_args)
    result = project.run("export", "dataflow", *mode_args, "-w", eid)
    assert_digraph(result)
    graph = result.stdout
    assert attribute_lines(graph) < attribute_lines(whole.stdout), (
        "-w did not shrink the graph\n{}".format(result)
    )
    # Not vacuous: the whole graph has what -w must leave out.
    assert not_derived(whole.stdout, variable), str(whole)
    assert not_derived(graph, variable) == [], str(result)
    assert "input.txt" in ACCESS_NODE.findall(graph), str(result)
    if "activation" not in mode_args:
        node = re.compile(r"^\s*e_{} \[".format(eid), re.MULTILINE)
        assert node.search(graph), "no node e_{}\n{}".format(eid, result)


def build_dataflow(tmp_path_factory, script, *args):
    """The dataflow corpus after ``now run <script> <args>``"""
    project = NowProject(tmp_path_factory.mktemp("dataflow"))
    project.copy_corpus("dataflow")
    project.run("run", script, *args)
    return project


def read_only(*projects):
    """Yield, then fail if the stores or the project files changed"""
    before = [project.fingerprint() for project in projects]
    yield
    assert [project.fingerprint() for project in projects] == before, (
        "the test changed a store shared by the module"
    )


@pytest.fixture(scope="module")
def _simulation_store(tmp_path_factory):
    return build_dataflow(tmp_path_factory, "simulation.py", "input.txt", "xyz")


@pytest.fixture(scope="module")
def _call_stores(tmp_path_factory):
    return {script: build_dataflow(tmp_path_factory, script) for script in CALL_SCRIPTS}


@pytest.fixture
def dataflow_project(_simulation_store):
    """``simulation.py`` of the dataflow corpus after one run: read-only"""
    for _ in read_only(_simulation_store):
        yield _simulation_store


@pytest.fixture
def call_projects(_call_stores):
    """``{script: project}`` for the nested and repeated calls: read-only"""
    for _ in read_only(*_call_stores.values()):
        yield _call_stores


def assert_digraph(result, prefix="digraph "):
    """The command printed a whole DOT graph and nothing on stderr"""
    assert result.stderr == "", str(result)
    assert result.stdout.startswith(prefix), str(result)
    assert result.stdout.rstrip().endswith("}"), str(result)


def skip_unless_same_python(project):
    """Skip unless ``now`` runs on this interpreter's minor version

    ``export_ast_failure`` and the marks built from it read the version of
    this interpreter. Under a ``NOW_E2E_CMD``, the version that ran the
    trials is read from the store, and a different one skips the test.
    """
    if runs_this_interpreter(project.command):
        return
    rows = project.query(
        "SELECT value FROM environment_attr WHERE name = 'PYTHON_VERSION' LIMIT 1"
    )
    version = tuple(int(part) for part in rows[0]["value"].split(".")[:2])
    if version != sys.version_info[:2]:
        pytest.skip(
            "NOW_E2E_CMD runs another Python version, for which "
            "export_ast_failure() and the xfail marks do not hold"
        )


def export_of(project, script, *args, **kwargs):
    """``now export <args>`` after ``now run script.py``, with ``script``
    as the text of ``script.py``; ``kwargs`` go to the export's run
    """
    project.write("script.py", script)
    project.run("run", "script.py")
    return project.run("export", *args, **kwargs)


# --- DOT text, read without Graphviz (#393) ---------------------------------

# The tokens of DOT (https://graphviz.org/doc/info/lang.html) that the
# exports write. In a quoted string the lexer takes a backslash and the
# character after it as a pair, so `\\"` ends the string. The exports write
# neither comments nor HTML strings, so a `#` or a `<` outside a quoted
# string means that a string ended early.
DOT_TOKEN = re.compile(
    r"""
    (?P<space>\s+)
  | (?P<string>"(?:[^"\\]|\\.)*")
  | (?P<edgeop>->|--)
  | (?P<id>[A-Za-z_\x80-\U0010ffff][\w\x80-\U0010ffff]*
          |-?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?))
  | (?P<punct>[{}\[\];,=:])
""",
    re.VERBOSE | re.DOTALL,
)
DOT_KEYWORDS = {"strict", "graph", "digraph", "subgraph", "node", "edge"}
DOT_ESCAPE = re.compile(r"\\(.)", re.DOTALL)
# The HTML entities Graphviz decodes in a label, always with the semicolon.
HTML_ENTITY = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")


class DotGraph:
    """A DOT graph as Graphviz's grammar reads it: the attributes of each
    node statement (``nodes``), the attributes each subgraph assigns
    (``subgraphs``) and the edges, every value as written, without its
    quotes (``rendered`` gives the text a label draws)

    Raises AssertionError, with the whole text, where the grammar rejects
    it or where a quoted string ended early (a ``#`` or a ``<`` outside
    one, which Graphviz may still read as a comment or an HTML string), so
    a test can assert that an export is well-formed DOT without Graphviz
    (#393). Only what the exports write is read: an edge joins node ids,
    never subgraphs, and no ``+`` joins two strings.
    """

    def __init__(self, text):
        self.text = text
        self.tokens = []
        position = 0
        while position < len(text):
            match = DOT_TOKEN.match(text, position)
            if match is None:
                self.fail("unexpected {!r}".format(text[position]), position)
            if match.lastgroup != "space":
                self.tokens.append((match.lastgroup, match.group(), position))
            position = match.end()
        self.index = 0
        self.nodes, self.subgraphs, self.edges = {}, [], []
        self.read_graph()

    def fail(self, problem, position=None):
        if position is None:
            position = (
                self.tokens[self.index][2]
                if self.index < len(self.tokens)
                else len(self.text)
            )
        raise AssertionError(
            "not a DOT graph: {} at line {}\n{}".format(
                problem, self.text.count("\n", 0, position) + 1, self.text
            )
        )

    def peek(self, offset=0):
        """``(kind, text)`` of a token ahead, ``(None, None)`` past the end"""
        index = self.index + offset
        if index < len(self.tokens):
            return self.tokens[index][:2]
        return None, None

    def keyword(self):
        """The next token as a lowercase keyword, or None"""
        kind, text = self.peek()
        if kind == "id" and text.lower() in DOT_KEYWORDS:
            return text.lower()
        return None

    def accept(self, punctuation):
        """Consume the next token if it is ``punctuation``"""
        if self.peek() == ("punct", punctuation):
            self.index += 1
            return True
        return False

    def expect(self, punctuation):
        if not self.accept(punctuation):
            self.fail(
                "expected {!r} instead of {!r}".format(punctuation, self.peek()[1])
            )

    def take_id(self):
        """The next token, an ID, without the quotes of a string"""
        kind, text = self.peek()
        if kind not in ("id", "string") or self.keyword():
            self.fail("expected an ID instead of {!r}".format(text))
        self.index += 1
        return text[1:-1] if kind == "string" else text

    def read_graph(self):
        if self.keyword() == "strict":
            self.index += 1
        if self.keyword() not in ("graph", "digraph"):
            self.fail("expected graph or digraph")
        self.index += 1
        if self.peek() != ("punct", "{"):
            self.take_id()
        self.read_body()
        if self.index < len(self.tokens):
            self.fail("text after the graph")

    def read_body(self):
        """``{ statements }``: the attributes they assign to the graph"""
        assigned = {}
        self.expect("{")
        while not self.accept("}"):
            self.read_statement(assigned)
            self.accept(";")
        return assigned

    def read_statement(self, assigned):
        keyword = self.keyword()
        if keyword in ("graph", "node", "edge"):
            self.index += 1
            attributes = self.read_attributes()
            if keyword == "graph":
                assigned.update(attributes)
        elif keyword == "subgraph" or self.peek() == ("punct", "{"):
            name = None
            if keyword == "subgraph":
                self.index += 1
                if self.peek() != ("punct", "{"):
                    name = self.take_id()
            self.subgraphs.append((name, self.read_body()))
        elif self.peek(1) == ("punct", "="):
            name = self.take_id()
            self.index += 1
            assigned[name] = self.take_id()
        else:
            tail = self.read_node_id()
            heads = []
            while self.peek()[0] == "edgeop":
                self.index += 1
                heads.append(self.read_node_id())
            attributes = self.read_attributes()
            if not heads:
                self.nodes.setdefault(tail, {}).update(attributes)
            for head in heads:
                self.edges.append((tail, head, attributes))
                tail = head

    def read_node_id(self):
        name = self.take_id()
        while self.accept(":"):  # a port, then a compass point
            self.take_id()
        return name

    def read_attributes(self):
        attributes = {}
        while self.accept("["):
            while not self.accept("]"):
                key = self.take_id()
                self.expect("=")
                attributes[key] = self.take_id()
                if not self.accept(";"):
                    self.accept(",")
        return attributes


def rendered(value):
    """The text Graphviz draws for a label, given its value as ``DotGraph``
    returns it

    In Graphviz's order (``make_label`` in ``lib/common/labels.c``): the
    lexer reads ``\\"`` as a quote and drops a backslash before a line end;
    ``\\N``, ``\\G``, ``\\E``, ``\\H``, ``\\T`` and ``\\L`` become names of
    the graph (kept here as a NUL and the letter, which no text of these
    tests holds); HTML entities are decoded; then ``\\n``, ``\\l`` and
    ``\\r`` break the line, and any other escaped character, a backslash
    included, stands for itself.
    """
    text = DOT_ESCAPE.sub(
        lambda match: {'"': '"', "\n": ""}.get(match.group(1), match.group()), value
    )
    text = DOT_ESCAPE.sub(
        lambda match: (
            "\0" + match.group(1) if match.group(1) in "GNETHL" else match.group()
        ),
        text,
    )
    text = HTML_ENTITY.sub(lambda match: html.unescape(match.group()), text)
    return DOT_ESCAPE.sub(
        lambda match: "\n" if match.group(1) in "nlr" else match.group(1), text
    )


def drawn_labels(graph):
    """``{node: text}``: what the label of each node statement draws"""
    return {
        node: rendered(attributes["label"])
        for node, attributes in graph.nodes.items()
        if "label" in attributes
    }


def drawn_cluster_labels(graph):
    """What the label each subgraph assigns draws, sorted"""
    return sorted(
        rendered(assigned["label"])
        for _, assigned in graph.subgraphs
        if "label" in assigned
    )


def same_expression(text, source):
    """Whether Python reads ``text`` as the same expression as ``source``,
    whatever its spelling (quotes, raw prefix, spaces)
    """
    try:
        return ast.dump(ast.parse(text, mode="eval")) == ast.dump(
            ast.parse(source, mode="eval")
        )
    except (SyntaxError, ValueError):
        return False


# --- test 13: export prolog -------------------------------------------------


@pytest.mark.golden
@pytest.mark.parametrize("name, args", PROLOG_CASES, ids=["t", "t-r"])
def test_export_prolog_without_the_environment_matches_golden(
    request, two_trial_project, name, args
):
    """``export prolog -t`` and ``-t -r`` print the same facts as the golden
    once the ``environment`` predicate is removed

    The environment is the machine's: it is checked by name in the next
    test and never stored.
    """
    result = two_trial_project.run("export", "prolog", *args)
    stripped = strip_prolog_predicate(result.stdout, "environment")
    # Booleans, so that a failure never prints the environment facts.
    leftover = "environment(" in stripped
    assert not leftover, "environment facts survived the strip"
    text = two_trial_project.normalize(stripped)
    leftover = "environment(" in text
    assert not leftover, "environment facts survived the normalization"
    assert_golden(request, name, text)


def test_export_prolog_records_the_environment_by_attribute_name(two_trial_project):
    """``export prolog`` emits one ``environment/3`` fact per attribute,
    with the synthetic user, and stripping the predicate removes them all

    Only names and counts are asserted: a failure prints no value.
    """
    result = two_trial_project.run("export", "prolog", "-t")
    facts = environment_facts(result.stdout)
    names = {name for name, _ in facts}
    assert REQUIRED_ENVIRONMENT - names == set()
    # Booleans with fixed messages: the values are the machine's.
    users = [value for name, value in facts if name == "USER"]
    has_user = bool(users)
    assert has_user, "no USER attribute"
    other_users = sum(value != USER for value in users)
    assert other_users == 0, "a USER attribute is not the harness user"
    stripped = strip_prolog_predicate(result.stdout, "environment")
    leftover = "environment(" in stripped
    assert not leftover, "environment facts survived the strip"
    declared = ":- dynamic(environment/" in stripped
    assert not declared, "the environment declaration survived the strip"
    # The rest of the export stays.
    assert prolog_facts(stripped).keys() == (
        prolog_facts(result.stdout).keys() - {"environment"}
    )


def test_export_prolog_facts_match_their_declarations(two_trial_project):
    """Every fact of ``export prolog -t`` has a ``:- dynamic(name/N).``
    declaration and N arguments, and ``-r`` appends the rules after the
    same facts
    """
    facts, rules = prolog_parts(two_trial_project)
    found = prolog_facts(facts)
    assert {"trial", "environment", "evaluation", "dependency"} <= set(found)
    undeclared = sorted(
        name for name, (declared, _) in found.items() if declared is None
    )
    assert undeclared == []
    mismatched = {
        name: (declared, sorted(arities))
        for name, (declared, arities) in found.items()
        if not arities <= {declared}
    }
    assert mismatched == {}
    assert rules.strip(), "`-r` appended no rules"


def test_export_prolog_rules_calling_trial_and_dependency(two_trial_project):
    """The rules of ``export prolog -r`` call ``trial/9`` and
    ``dependency/6``, while the facts are ``trial/12`` and
    ``dependency/10``, so those rules never match

    Characterization of #249; every other fact predicate
    is called with its declared arity.
    """
    assert stale_rule_calls(two_trial_project) == {
        ("trial", 9, 12),
        ("dependency", 6, 10),
    }


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="#249: the rules of `export prolog -r` call "
    "trial/9 and dependency/6, while the facts are trial/12 and "
    "dependency/10",
)
def test_export_prolog_rules_calling_trial_and_dependency_desired(two_trial_project):
    """Every rule of ``export prolog -r`` calls the fact predicates with
    their declared arity
    """
    assert stale_rule_calls(two_trial_project) == set()


# --- test 14: export prov ---------------------------------------------------


@pytest.mark.golden
def test_export_prov_matches_golden(request, two_trial_project):
    """``export prov`` prints the PROV-N text of the golden, with the
    hostname in the user entity masked
    """
    result = two_trial_project.run("export", "prov")
    text = two_trial_project.normalize(result.stdout)
    # A boolean, so that a failure never prints an unmasked hostname.
    masked = (
        'entity(user_<HOSTNAME>\\nowtest, [type="script:user", label="nowtest"])'
    ) in text.splitlines()
    assert masked, "no user entity masked as user_<HOSTNAME>\\nowtest"
    assert_golden(request, "prov", text)


def test_export_prov_names_the_user_after_the_host_and_the_user(two_trial_project):
    """``export prov`` declares its two prefixes and ends with one user
    entity named ``user_<hostname>\\<user>``, which the normalizer masks
    """
    result = two_trial_project.run("export", "prov")
    lines = result.stdout.splitlines()
    assert lines[:2] == [
        "prefix script <https://dew-uff.github.io/versioned-prov/ns/script#>",
        "prefix version <https://dew-uff.github.io/versioned-prov/ns#>",
    ]
    # Booleans with fixed messages: the user entity holds the hostname.
    users = [line for line in lines if line.startswith("entity(user_")]
    one_user = len(users) == 1
    assert one_user, "expected one user entity"
    host = socket.gethostname()
    expected = 'entity(user_{}\\{}, [type="script:user", label="{}"])'.format(
        host, USER, USER
    )
    named_after_host = users[0] == expected
    assert named_after_host, "the user entity is not user_<hostname>\\<user>"
    if usable_hostname(host):
        masked = two_trial_project.normalize(users[0]) == (
            'entity(user_<HOSTNAME>\\nowtest, [type="script:user", label="nowtest"])\n'
        )
        assert masked, "the normalizer does not mask the hostname"


# --- test 15: export dataflow -----------------------------------------------


@pytest.mark.golden
@pytest.mark.parametrize("mode", DATAFLOW_MODES)
def test_export_dataflow_in_each_mode_matches_golden(request, dataflow_project, mode):
    """``export dataflow -m <mode>`` prints the DOT graph of the golden"""
    result = dataflow_project.run("export", "dataflow", "-m", mode)
    assert_golden(
        request, "dataflow-" + mode.lower(), dataflow_project.normalize(result.stdout)
    )


@pytest.mark.parametrize("mode", DATAFLOW_MODES)
def test_export_dataflow_draws_a_graph_in_each_mode(dataflow_project, mode):
    """Each mode draws a DOT graph that reaches the file the script read"""
    result = dataflow_project.run("export", "dataflow", "-m", mode)
    assert_digraph(result)
    assert '"input.txt"' in result.stdout


def test_export_dataflow_defaults_to_coarse_grain(dataflow_project):
    """``export dataflow`` without ``-m`` prints the coarseGrain graph"""
    default = dataflow_project.run("export", "dataflow")
    coarse = dataflow_project.run("export", "dataflow", "-m", "coarseGrain")
    assert default.stdout == coarse.stdout


@pytest.mark.parametrize("mode, variable", WDF_CONTROLS)
def test_export_dataflow_wdf_draws_only_what_derived_the_evaluation(
    dataflow_project, mode, variable
):
    """``-w <eid>`` draws a smaller graph than the same mode without it,
    keeping what derived the evaluation and leaving out what did not

    Control for #200, measured on ``simulation.py``: ``-w`` works in
    activation, fineGrain and all with the write of ``data``, and in every
    mode, coarseGrain and looplessCoarseGrain included, with the write of
    ``size``. The crash of the clustered modes therefore depends on the
    evaluation, not on the mode alone.
    """
    assert_derivation_graph(dataflow_project, ("-m", mode), variable)


@pytest.mark.parametrize("mode_args", WDF_CRASHES)
def test_export_dataflow_wdf_in_a_clustered_mode(dataflow_project, mode_args):
    """``-w`` with the write of ``data`` in coarseGrain, looplessCoarseGrain
    or the default mode exits with 1 and a ``KeyError`` traceback

    Characterization of #200: ``RetrospectiveClusterizer.process_cluster``
    looks up the activation node of a dependency that the
    ``wasDerivedFrom`` filter of ``-w`` left out of the graph.
    """
    eid = written_evaluation(dataflow_project, "data")
    result = dataflow_project.run(
        "export", "dataflow", *mode_args, "-w", eid, expect=1, allow_stderr=True
    )
    assert result.stdout == "", str(result)
    assert "Traceback (most recent call last):" in result.stderr, str(result)
    assert KEY_ERROR.fullmatch(last_line(result.stderr)), str(result)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=WDF_REASON)
@pytest.mark.parametrize("mode_args", WDF_CRASHES)
def test_export_dataflow_wdf_in_a_clustered_mode_desired(dataflow_project, mode_args):
    """``-w`` with the write of ``data`` draws, in the clustered modes too,
    only what derived the evaluation
    """
    assert_derivation_graph(dataflow_project, mode_args, "data")


@pytest.mark.parametrize("script, mode", CALL_CRASHES)
def test_export_dataflow_of_nested_and_repeated_calls(call_projects, script, mode):
    """Without ``-w``, a nested call ``f(g(x))`` crashes both clustered
    modes and a call site that runs more than once crashes
    looplessCoarseGrain: rc 1 and a ``KeyError`` traceback

    Characterization of #242. The lookup that fails is
    the one of #200 (``created[dep_act_node_id]`` in ``process_cluster``),
    but no ``-w`` filter is involved: the graph is the whole trial.
    """
    result = call_projects[script].run(
        "export", "dataflow", "-m", mode, expect=1, allow_stderr=True
    )
    assert result.stdout == "", str(result)
    assert "Traceback (most recent call last):" in result.stderr, str(result)
    assert KEY_ERROR.fullmatch(last_line(result.stderr)), str(result)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=CALL_REASON)
@pytest.mark.parametrize("script, mode", CALL_CRASHES)
def test_export_dataflow_of_nested_and_repeated_calls_desired(
    call_projects, script, mode
):
    """Every mode draws the graph of a nested or repeated call"""
    result = call_projects[script].run("export", "dataflow", "-m", mode)
    assert_digraph(result)


@pytest.mark.parametrize("script, mode", CALL_CONTROLS)
def test_export_dataflow_of_nested_and_repeated_calls_in_the_other_modes(
    call_projects, script, mode
):
    """The modes that #242 does not break draw the same
    scripts
    """
    result = call_projects[script].run("export", "dataflow", "-m", mode)
    assert_digraph(result)


@pytest.mark.parametrize("mode", DATAFLOW_MODES)
def test_export_dataflow_reads_as_dot_in_each_mode(dataflow_project, mode):
    """``DotGraph`` reads the graph of each mode of ``simulation.py``, and
    its access node draws ``input.txt``

    Control of the #401 twins: the text of ``simulation.py`` holds double
    quotes, but no ``\\"`` and no trailing backslash, so its graphs are
    well-formed today, and the reader accepts them.
    """
    result = dataflow_project.run("export", "dataflow", "-m", mode)
    graph = DotGraph(result.stdout)
    assert "input.txt" in drawn_labels(graph).values(), str(result)
    assert graph.edges, str(result)


def test_export_dataflow_of_a_string_literal_with_an_escaped_quote(project):
    """``export dataflow`` of ``print("say \\"hi\\"")``, with the default
    options, writes each ``\\"`` of the literal as ``\\\\"``: an escaped
    backslash, then the quote that closes the label, so Graphviz rejects
    the graph, and so does ``DotGraph`` (#401 changes it)
    """
    result = export_of(project, ESCAPED_QUOTE_SCRIPT, "dataflow")

    assert r'[label="1 print(\"say \\"hi\\"\")"' in result.stdout, str(result)
    assert r'[label="1 \"say \\"hi\\"\""' in result.stdout, str(result)
    with pytest.raises(AssertionError, match=r"^not a DOT graph: unexpected '\\\\'"):
        DotGraph(result.stdout)


@known_defects(ESCAPED_QUOTE)
def test_export_dataflow_of_a_string_literal_with_an_escaped_quote_desired(project):
    """``export dataflow`` of ``print("say \\"hi\\"")`` is well-formed DOT
    whose labels draw the source text of each node, ``\\"`` included

    Any escaping that Graphviz reads back as that text passes (a backslash
    before each backslash and quote, or HTML entities): what is checked is
    what ``rendered`` draws, not how the label is spelled.
    """
    result = export_of(project, ESCAPED_QUOTE_SCRIPT, "dataflow")

    graph = DotGraph(result.stdout)
    assert sorted(drawn_labels(graph).values()) == sorted(
        [
            '1 print("say \\"hi\\"")',
            "-1 print",
            '1 "say \\"hi\\""',
        ]
    ), result.stdout


def test_export_dataflow_of_a_class_named_with_a_quote(project):
    """``export dataflow`` of a class built with ``type('a"b', ...)``
    writes its activation name into the cluster's label as it is, so the
    label ends at the name's quote and the rest is read as DOT: Graphviz
    draws stray nodes made of the graph's own text, and ``DotGraph``
    rejects the graph (#401 changes it)
    """
    result = export_of(project, QUOTED_CLASS_SCRIPT, "dataflow")

    lines = [line.strip() for line in result.stdout.splitlines()]
    assert 'label = "a"b";' in lines, str(result)
    assert 'label = "init";' in lines, str(result)
    with pytest.raises(AssertionError, match="^not a DOT graph: unexpected '#'"):
        DotGraph(result.stdout)


@known_defects(CLUSTER_LABEL)
def test_export_dataflow_of_a_class_named_with_a_quote_desired(project):
    """``export dataflow`` of a class named ``a"b`` is well-formed DOT: the
    cluster of the class draws ``a"b``, the one of ``init`` draws
    ``init``, and every node is an evaluation or an activation (``e_N``),
    none made of the graph's text
    """
    result = export_of(project, QUOTED_CLASS_SCRIPT, "dataflow")

    graph = DotGraph(result.stdout)
    assert drawn_cluster_labels(graph) == ['a"b', "init"], result.stdout
    strays = sorted(node for node in graph.nodes if not re.fullmatch(r"e_\d+", node))
    assert strays == [], result.stdout


def test_export_dataflow_of_a_value_ending_in_a_backslash(project):
    """``export dataflow --value-length 55`` of an object whose repr is
    ``C:\\data\\`` ends the value's label in a backslash, which escapes the
    closing quote: the label runs on into ``fillcolor``, and Graphviz and
    ``DotGraph`` reject the graph (#401 changes it)
    """
    result = export_of(
        project, BACKSLASH_REPR_SCRIPT, "dataflow", "--value-length", "55"
    )

    assert result.stdout.count(r"C:\data\" fillcolor") == 2, str(result)
    with pytest.raises(AssertionError, match="^not a DOT graph: unexpected '#'"):
        DotGraph(result.stdout)


@known_defects(TRAILING_BACKSLASH)
def test_export_dataflow_of_a_value_ending_in_a_backslash_desired(project):
    """``export dataflow --value-length 55`` of an object whose repr is
    ``C:\\data\\`` is well-formed DOT whose labels draw that repr, every
    backslash kept, under the code of each node
    """
    result = export_of(
        project, BACKSLASH_REPR_SCRIPT, "dataflow", "--value-length", "55"
    )

    graph = DotGraph(result.stdout)
    assert sorted(drawn_labels(graph).values()) == sorted(
        [
            "1 return =\n<class '__main__.R'>",
            "6 R() =\nC:\\data\\",
            "6 r =\nC:\\data\\",
        ]
    ), result.stdout


# --- test 16: export ast ----------------------------------------------------


@pytest.mark.golden
@pytest.mark.parametrize("form", AST_FORMS)
def test_export_ast_matches_golden(request, two_trial_project, form):
    """``export ast`` (text), ``-j`` and ``-d`` print the tree of the golden

    ``-j`` prints a Python dict, not JSON, so it is compared as text; the
    ``-d`` node ids come from ``id()`` and are numbered by the normalizer.
    A form is xfail where ``export_ast_failure`` names a defect.
    """
    skip_unless_same_python(two_trial_project)
    result = two_trial_project.run("export", "ast", *EXPORT_AST_FORMS[form])
    assert_golden(request, "ast-" + form, two_trial_project.normalize(result.stdout))


@pytest.mark.parametrize("form", EXPORT_AST_FORMS)
def test_export_ast_in_each_form(two_trial_project, form):
    """Where ``export_ast_failure`` names a defect, ``export ast`` in that
    form exits with 1, prints nothing on stdout and ends stderr with the
    defect's ``TypeError``: ``required field "lineno" missing`` for the text
    and ``-j`` forms on 3.14, ``unexpected keyword argument`` for every form
    from 3.15

    Characterization of #241 and #241.
    """
    failure = export_ast_failure(form)
    if failure is None:
        pytest.skip(
            "`export ast` in this form works on this Python; the "
            "_desired twin is the test"
        )
    skip_unless_same_python(two_trial_project)
    result = two_trial_project.run(
        "export", "ast", *EXPORT_AST_FORMS[form], expect=1, allow_stderr=True
    )
    assert result.stdout == "", str(result)
    error = last_line(result.stderr)
    assert error.startswith("TypeError: "), str(result)
    assert EXPORT_AST_ERRORS[failure] in error, str(result)


@pytest.mark.parametrize("form", AST_FORMS)
def test_export_ast_in_each_form_desired(two_trial_project, form):
    """``export ast`` prints the tree of the last trial as ``ast.dump``
    text, as a dict keyed by the trial id (``-j``) or as a DOT graph (``-d``)
    """
    skip_unless_same_python(two_trial_project)
    result = two_trial_project.run("export", "ast", *EXPORT_AST_FORMS[form])
    output = result.stdout
    if form == "text":
        assert output.startswith("Module("), str(result)
    elif form == "json":
        trial_id = two_trial_project.trials()[-1]["id"]
        data = ast.literal_eval(output)
        assert set(data) == {"ast", "trial"}
        assert data["trial"] == trial_id
        assert list(data["ast"]) == [trial_id]
        assert data["ast"][trial_id].startswith("Module("), str(result)
    else:
        assert output.startswith("digraph {"), str(result)
        assert re.search(r"^\s*node\d+ \[label=\"Module\b", output, re.MULTILINE), str(
            result
        )


@pytest.mark.parametrize("form", AST_FORMS)
def test_export_ast_of_a_dict_display_that_unpacks(project, form):
    """``export ast`` rebuilds ``{'z': 0, **base, 'y': 2}`` as Python's AST
    has it, with ``None`` as the key of ``**base`` between the other two
    items: the transformer records no ``key_value`` for a ``**`` item, only
    its operand (#427)
    """
    result = export_of(project, DICT_UNPACKING_SCRIPT, "ast", *EXPORT_AST_FORMS[form])
    if form == "dot":
        graph = DotGraph(result.stdout)
        labels = drawn_labels(graph)
        display = [
            node
            for node, label in labels.items()
            if label == "Dict\n{'z': 0, **base, 'y': 2}"
        ]
        assert len(display) == 1, str(result)
        items = sorted(
            labels[head] for tail, head, _ in graph.edges if tail == display[0]
        )
        assert items == [
            "Constant\n'y'",
            "Constant\n'z'",
            "Constant\n0",
            "Constant\n2",
            "Name\nbase",
        ], str(result)
        return
    if form == "json":
        trial_id = project.trials()[-1]["id"]
        dump = ast.literal_eval(result.stdout)["ast"][trial_id]
    else:
        dump = result.stdout
    assert re.sub(r"\s", "", DICT_UNPACKING_DUMP) in re.sub(r"\s", "", dump), str(
        result
    )


# --- export prospective -----------------------------------------------------


@pytest.mark.golden
def test_export_prospective_matches_golden(request, two_trial_project):
    """``export prospective`` prints the DOT graph of the golden"""
    result = two_trial_project.run("export", "prospective")
    assert_golden(request, "prospective", two_trial_project.normalize(result.stdout))


def test_export_prospective_is_the_same_for_two_trials_of_the_same_code(
    two_trial_project,
):
    """The prospective graph comes from the code alone: the two trials ran
    the same script on different data and draw the same graph
    """
    first, second = (trial["id"] for trial in two_trial_project.trials())
    one = two_trial_project.run("export", "prospective", first)
    two = two_trial_project.run("export", "prospective", second)
    assert_digraph(one, prefix="strict digraph {")
    assert one.stdout == two.stdout


def test_export_prospective_reads_as_dot(two_trial_project):
    """``DotGraph`` reads the prospective graph of the weather script, and
    its ``Start`` and ``End`` nodes draw their names

    Control of the #401 twin: the labels of the weather script hold double
    quotes, written as ``\\"``, but no trailing backslash.
    """
    result = two_trial_project.run("export", "prospective")
    graph = DotGraph(result.stdout)
    labels = drawn_labels(graph)
    assert (labels.get("start"), labels.get("end")) == ("Start", "End"), str(result)
    assert graph.edges, str(result)


def test_export_prospective_of_a_condition_ending_in_a_backslash(project):
    """``export prospective`` of ``if s == r"a\\:b":`` cuts the condition
    at the ``:`` inside the literal, so its label ends in a backslash,
    which escapes the closing quote: the graphviz library warns on stderr,
    ``now`` exits 0, and Graphviz and ``DotGraph`` reject the graph (#401
    changes it)
    """
    result = export_of(
        project, BACKSLASH_CONDITION_SCRIPT, "prospective", allow_stderr=True
    )

    assert PROSPECTIVE_LABEL.signature in result.stderr, str(result)
    assert r'  s == r\"a\" color="#808080"' in result.stdout, str(result)
    with pytest.raises(AssertionError, match="^not a DOT graph: unexpected '#'"):
        DotGraph(result.stdout)


@known_defects(PROSPECTIVE_LABEL)
def test_export_prospective_of_a_condition_ending_in_a_backslash_desired(project):
    """``export prospective`` of ``if s == r"a\\:b":`` prints no warning
    and well-formed DOT, whose condition note draws the condition, every
    backslash kept: cut at the first ``:`` as today (``s == r"a\\``), or
    whole, as its source text or in any other form Python reads as the
    same expression (``ast.unparse`` writes ``s == 'a\\\\:b'``)

    A fix may leave the cut alone, or take the condition from the tree.
    """
    result = export_of(
        project,
        BACKSLASH_CONDITION_SCRIPT,
        "prospective",
        expect=None,
        allow_stderr=True,
    )

    assert result.stderr == "", str(result)
    assert result.returncode == 0, str(result)
    graph = DotGraph(result.stdout)
    notes = [
        label for label in drawn_labels(graph).values() if label.startswith(CONDITION)
    ]
    assert len(notes) == 1, result.stdout
    condition = notes[0][len(CONDITION) :].strip()
    assert condition == CUT_CONDITION or same_expression(condition, WHOLE_CONDITION), (
        result.stdout
    )


# --- export ipynb -----------------------------------------------------------


def test_export_ipynb_writes_the_current_trial_notebook(weather_project):
    """``export ipynb`` prints nothing and writes ``Current Trial.ipynb``, a
    JSON notebook, into the project directory
    """
    before = weather_project.files()
    result = weather_project.run("export", "ipynb")
    assert result.stdout == "", str(result)
    after = weather_project.files()
    assert set(after) - set(before) == {CURRENT_NOTEBOOK}
    path = weather_project.path / CURRENT_NOTEBOOK
    notebook = json.loads(path.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert notebook["cells"]


def test_export_ipynb_writes_into_the_current_directory_despite_dir(weather_project):
    """``export ipynb --dir <project>`` reads the store in ``--dir`` and
    writes the notebook into the current directory, not into ``--dir``

    Characterization: ``--dir`` only says where the store is.
    """
    elsewhere = weather_project.root / "elsewhere"
    elsewhere.mkdir()
    before = weather_project.files()
    result = weather_project.run(
        "export", "ipynb", "--dir", weather_project.path, cwd=elsewhere
    )
    assert result.stdout == "", str(result)
    assert sorted(os.listdir(elsewhere)) == [CURRENT_NOTEBOOK]
    json.loads((elsewhere / CURRENT_NOTEBOOK).read_text(encoding="utf-8"))
    assert weather_project.files() == before
