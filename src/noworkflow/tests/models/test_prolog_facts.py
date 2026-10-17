# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The Prolog facts of every model, and how a trial loads them into Prolog

Twenty-one models carry a ``prolog_description``; ``now export prolog``
writes the facts of twelve of them, and the e2e tests read only those, from a
store where every value is tame. Here each model gets one row built from
its table alone (``model_rows.insert_model_row``), with text that a Prolog
writer must escape in every text column, and its fact must keep the
declared arity with every argument a Prolog term that SWI-Prolog reads as
atomic (``model_rows.ATOMIC``): counting commas alone misses an unquoted
``None``, which Prolog reads as a variable, and an unquoted UUID, which is
not a term at all. NULL columns behind the nullable attributes must give
``nil``; the other forms of a description (the declaration, the comment,
the empty fact, the retract) must agree on the arity.

``TrialProlog`` is read on the shared two-trial store, connected in-process
(``connected_two_trials``): one fact per row of the trial, counted against
SQL, and the loading into SWI-Prolog through a stand-in for ``pyswip``,
which the locked environment does not install. That loading asserts one
rule per line of ``rules.pl``, which the premise here pins.

The in-process tests write to the in-memory store and erase it before and
after (``clean_store``). Known defects have a characterization of today's
behavior and a ``_desired`` twin marked through ``known_defects``; the
mechanisms are plain Python string formatting, the same on every system
and Python version (measured on macOS with 3.11 to 3.15).
"""
import collections
import gc
import re
import sys
import types
from pathlib import Path

import pytest
import sqlalchemy as sa

import noworkflow
from noworkflow.now.models.trial_prolog import TrialProlog
from noworkflow.now.persistence import relational
from noworkflow.now.persistence.lightweight.experiment import ExperimentLW
from noworkflow.now.persistence.lightweight.extendedAnnotation import (
    ExtendedAnnotationLW,
)
from noworkflow.now.persistence.models import (
    ORDER, Experiment, ExtendedAnnotation, Head, Module, Remote, Trial,
)
from noworkflow.now.utils.prolog import (
    PrologNullable, PrologNullableRepr, PrologTimestamp, PrologTrial,
)
from noworkflow.tests.e2e.normalize import prolog_statements
from noworkflow.tests.helpers import swipl
from noworkflow.tests.helpers.defects import Defect, known_defects
from noworkflow.tests.helpers.models import (
    TrialConfig, erase_database, new_trial,
)
from noworkflow.tests.models.model_rows import (
    ATOMIC, TRIAL_ID, fact_arguments, insert_model_row, non_atomic,
)

RULES = Path(noworkflow.__file__).resolve().parent / "resources" / "rules.pl"

MODELS = [model for model in list(ORDER) + [Remote]
          if getattr(model, "prolog_description", None) is not None]
# Head writes the trial id unquoted: it has its own pair of tests.
ROW_MODELS = [model for model in MODELS if model is not Head]
# Head and Module define a __repr__ of their own instead of the fact.
REPR_MODELS = [model for model in MODELS if model not in (Head, Module)]
NULLABLE = (PrologNullable, PrologNullableRepr, PrologTimestamp)
NULLABLE_MODELS = [
    model for model in MODELS
    if any(isinstance(attribute, NULLABLE)
           for attribute in model.prolog_description.attributes)
]
# StageTagsLW stores neither column, so they are NULL in every stored row.
UNSTORED = {"StageTags": ("variable_name", "variable_value")}

# What `now export prolog` writes, in its order (trial_prolog.py).
EXPORTED = ["trial", "tag", "argument", "module", "environment",
            "code_component", "code_block", "activation", "evaluation",
            "dependency", "access", "member"]
# The table of each exported predicate, and the column that names the trial.
EXPORTED_TABLES = {
    "trial": ("trial", "id"),
    "tag": ("tag", "trial_id"),
    "argument": ("argument", "trial_id"),
    "module": ("module", "trial_id"),
    "environment": ("environment_attr", "trial_id"),
    "code_component": ("code_component", "trial_id"),
    "code_block": ("code_block", "trial_id"),
    "activation": ("activation", "trial_id"),
    "evaluation": ("evaluation", "trial_id"),
    "dependency": ("dependency", "trial_id"),
    "access": ("file_access", "trial_id"),
    "member": ("member", "trial_id"),
}
# `now export prolog` declares trial/12; the empty trial that SWI-Prolog
# starts with has a 0 in each argument.
TRIAL_ARITY = 12

DECLARATION = re.compile(r":- dynamic\((\w+)/(\d+)\)\.?")
VARIABLE = re.compile(r"[A-Z_][A-Za-z0-9_]*")

# Text that SWI-Prolog reads as one argument, and whether it is atomic.
# None of them leaves a quote open, which would swallow the next lines.
GRAMMAR_CASES = [
    ("'a'", True),
    ("'a, b) c'", True),
    ("'it''s'", True),
    ("'a\\\\b'", True),
    ("'tab\\tx'", True),
    ("'\\x41\\'", True),
    ("'two\nlines'", True),
    ("''", True),
    ("nil", True),
    ("f7", True),
    ("-1", True),
    ("0.5", True),
    ("5e-06", True),
    ("1e+20", True),
    ("1460078280.0", True),
    ("None", False),
    ("X", False),
    ("_", False),
    ("1b2c", False),
    ("0e4f1c2a-1b2c-4d5e-8f90-1234567890ab", False),
    ("'a\\db'", False),
    ("'a' 'b'", False),
    ("f(1)", False),
    ("a b", False),
]

HEAD_UNQUOTED = Defect(
    reason="#353: Head.prolog_description describes "
           "trial_id with PrologAttribute, which writes the UUID unquoted: "
           "the fact is not valid Prolog and retract does not bind the "
           "trial",
    signature="non-atomic arguments in head(",
)
NONE_ATOM = Defect(
    reason="#353: module.fullpath and the attributes of "
           "the collaboration models (experiment, extendedAnnotation) are "
           "described with PrologRepr, which writes a NULL column as the "
           "atom 'None' instead of nil",
    signature="is 'None', not nil",
)


def name(model):
    return model.__name__


def quoted(text):
    """``text`` as a quoted atom, the way every trial-scoped fact quotes
    the trial id (quotes doubled)"""
    return "'{}'".format(text.replace("'", "''"))


def declared_arity(description):
    """N of the ``:- dynamic(name/N).`` that ``description`` declares"""
    match = DECLARATION.fullmatch(description.dynamic())
    assert match, description.dynamic()
    assert match.group(1) == description.name
    return int(match.group(2))


def sql(statement, **params):
    """Rows of a query on the store the persistence layer is connected to"""
    return relational.session.execute(sa.text(statement), params).all()


def rule_line_problems(text):
    """``[(line number, line)]`` of the lines of a rules file that are not
    one whole clause: a line that is not blank or a comment must end with
    its only period
    """
    problems = []
    for number, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        if not stripped.endswith(".") or "." in stripped[:-1]:
            problems.append((number, stripped))
    return problems


def rule_clauses(text):
    """The clauses of a rules file of one clause per line, without their
    period"""
    return [line.strip()[:-1] for line in text.split("\n")
            if line.strip() and not line.strip().startswith("%")]


def predicate_counts(clauses):
    """``Counter(name)`` of the facts among ``clauses``, declarations left
    out"""
    counts = collections.Counter()
    for clause in clauses:
        if clause.startswith(":-"):
            continue
        counts[re.match(r"(\w+)\(", clause).group(1)] += 1
    return counts


def heads(clauses):
    """The predicate of each clause, for messages: the clauses of a real
    trial hold its environment, and its user id the hostname"""
    return [re.match(r"[^(]*", clause).group() for clause in clauses]


def trial_row_counts(project, trial_id):
    """``{predicate: rows of its table that belong to the trial}``"""
    return {
        predicate: project.query(
            'SELECT COUNT(*) AS n FROM "{}" WHERE "{}" = ?'.format(
                table, column), trial_id)[0]["n"]
        for predicate, (table, column) in EXPORTED_TABLES.items()
    }


@pytest.fixture
def clean_store():
    """The in-memory store, empty before the test and after it"""
    erase_database()
    yield
    erase_database()


# --- the grammar of an argument ---------------------------------------------


def test_the_atomic_grammar_tells_terms_from_non_terms():
    """``ATOMIC`` accepts quoted atoms, numbers and lowercase atoms, and
    rejects variables, a bare UUID, an invalid escape, compounds and two
    terms in a row
    """
    accepted = [text for text, _ in GRAMMAR_CASES if ATOMIC.fullmatch(text)]
    assert accepted == [text for text, atomic in GRAMMAR_CASES if atomic]


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
def test_the_atomic_grammar_agrees_with_swi_prolog(tmp_path):
    """SWI-Prolog reads as atomic exactly the cases that ``ATOMIC``
    accepts; the others are variables, compounds or syntax errors
    """
    path = tmp_path / "candidates.pl"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for index, (text, _) in enumerate(GRAMMAR_CASES):
            handle.write("candidate({}, {}).\n".format(index, text))
    result = swipl.solutions(path, "candidate(I, X), atomic(X)", "I")
    assert result.error is None
    found = sorted(GRAMMAR_CASES[row[0]][0] for row in result.rows)
    assert found == sorted(text for text, atomic in GRAMMAR_CASES if atomic)
    # Not vacuous: the cases that are not terms did not load at all.
    assert "Syntax error" in result.stderr


# --- the facts of every model -----------------------------------------------


@pytest.mark.parametrize("model", ROW_MODELS, ids=name)
def test_prolog_fact_keeps_the_declared_arity(clean_store, model):
    """A row whose text columns hold a quote, a comma, a backslash, a
    newline and a parenthesis gives a fact with the declared number of
    arguments, each one a Prolog term that SWI-Prolog reads as atomic
    """
    description = model.prolog_description
    proxy = insert_model_row(model, nulls=UNSTORED.get(name(model), ()))
    arity = declared_arity(description)
    assert arity == len(description.attributes)
    fact = description.fact(proxy)
    assert fact.endswith(")."), fact
    arguments = fact_arguments(fact, description.name)
    assert arguments is not None, fact
    assert len(arguments) == arity, fact
    assert non_atomic(arguments) == [], (
        "non-atomic arguments in {}".format(fact))


@pytest.mark.parametrize("model", NULLABLE_MODELS, ids=name)
def test_prolog_fact_writes_nil_for_null_nullable_attributes(
        clean_store, monkeypatch, model):
    """Where the column behind a nullable attribute is NULL, the fact
    writes ``nil`` in its place and keeps its arity; a NULL timestamp is
    ``-1``, or ``nil`` under ``PrologTimestamp.use_nil`` (``export -t``)
    """
    description = model.prolog_description
    nullable = {index: attribute
                for index, attribute in enumerate(description.attributes)
                if isinstance(attribute, NULLABLE)}
    proxy = insert_model_row(model, nulls=[
        attribute.attr_name for attribute in nullable.values()])
    for use_nil in (False, True):
        monkeypatch.setattr(PrologTimestamp, "use_nil", use_nil)
        fact = description.fact(proxy)
        arguments = fact_arguments(fact, description.name)
        assert len(arguments) == len(description.attributes), fact
        written = {index: arguments[index].strip() for index in nullable}
        assert written == {
            index: "-1" if isinstance(attribute, PrologTimestamp)
            and not use_nil else "nil"
            for index, attribute in nullable.items()
        }, fact


@pytest.mark.parametrize("model", MODELS, ids=name)
def test_prolog_description_forms_agree_on_the_arity(model):
    """The declaration, the comment, the empty fact and the retract of a
    description all have one argument per attribute: distinct variables
    in the comment, ``0`` in the empty fact, and in the retract the trial
    id at the trial attributes and ``_`` everywhere else
    """
    description = model.prolog_description
    size = len(description.attributes)
    assert description.dynamic() == ":- dynamic({}/{}).".format(
        description.name, size)
    variables = [text.strip()
                 for text in fact_arguments(repr(description),
                                            description.name)]
    assert len(variables) == size
    assert all(VARIABLE.fullmatch(variable) for variable in variables)
    assert len(set(variables)) == size, variables
    assert "% FACT DEFINITION: {}\n".format(repr(description)) in (
        description.comment())
    empty = fact_arguments(description.empty(), description.name)
    assert [text.strip() for text in empty] == ["0"] * size
    retract = description.retract("t'1")
    assert retract.startswith("retract(") and retract.endswith("))")
    bound = fact_arguments(retract[len("retract("):], description.name)
    assert [text.strip() for text in bound] == [
        "'t''1'" if isinstance(attribute, PrologTrial) else "_"
        for attribute in description.attributes
    ]


@pytest.mark.parametrize("model", REPR_MODELS, ids=name)
def test_prolog_repr_of_a_model_is_its_fact(clean_store, model):
    """The repr of a model's proxy is its Prolog fact

    Head and Module are left out: each defines a ``__repr__`` of its own.
    """
    proxy = insert_model_row(model, nulls=UNSTORED.get(name(model), ()))
    assert repr(proxy) == model.prolog_description.fact(proxy)


def test_models_with_a_prolog_description():
    """Every model but GraphCache has a Prolog description, and the export
    writes twelve of them; the head, composition, StageTags, remote and
    collaboration descriptions are never exported

    The models left out are commented out in ``trial_prolog.py`` (a TODO
    of the collaboration features); this pins that choice, it does not
    claim a defect.
    """
    without = [name(model) for model in list(ORDER) + [Remote]
               if model not in MODELS]
    assert without == ["GraphCache"]
    exported = [model for model, _ in TrialProlog.prolog_models()]
    assert [model.prolog_description.name for model in exported] == EXPORTED
    assert sorted(name(model) for model in MODELS
                  if model not in exported) == [
        "Composition", "Experiment", "ExtendedAnnotation", "Group", "Head",
        "MemberOfGroup", "Remote", "StageTags", "User",
    ]


# --- head -------------------------------------------------------------------


def main_head():
    """The head of ``main.py`` after a trial of it: ``(proxy, id, trial
    id)``, the ids read with SQL"""
    trial_id = new_trial(TrialConfig(script="main.py"), erase=True)
    Trial(trial_id).create_head()
    rows = sql("SELECT id, trial_id FROM head WHERE script = :script",
               script="main.py")
    assert len(rows) == 1
    head_id, stored = rows[0]
    assert stored == trial_id
    return Head.load_head("main.py"), head_id, stored


def test_head_prolog_fact(clean_store):
    """Head's fact writes the trial id unquoted, which is not a Prolog
    term; its repr has three arguments while the declaration is
    ``head/2``, and its retract binds no argument

    Characterization of #353.
    """
    head, head_id, trial_id = main_head()
    fact = Head.prolog_description.fact(head)
    assert fact == "head('main.py', {}).".format(trial_id)
    assert non_atomic(fact_arguments(fact, "head")) == [(1, " " + trial_id)]
    assert repr(head) == "head({}, 'main.py', {}).".format(head_id, trial_id)
    assert Head.prolog_description.dynamic() == ":- dynamic(head/2)."
    assert Head.prolog_description.retract(trial_id) == "retract(head(_, _))"


@known_defects(HEAD_UNQUOTED)
def test_head_prolog_fact_desired(clean_store):
    """Head's fact quotes the trial id like every other trial-scoped fact,
    and its retract binds it
    """
    head, _, trial_id = main_head()
    fact = Head.prolog_description.fact(head)
    arguments = fact_arguments(fact, "head")
    assert non_atomic(arguments) == [], (
        "non-atomic arguments in {}".format(fact))
    assert [text.strip() for text in arguments] == [
        "'main.py'", quoted(trial_id)]
    assert quoted(trial_id) in Head.prolog_description.retract(trial_id)


# --- a missing value ----------------------------------------------------------


def module_without_fullpath():
    """A module row whose fullpath is NULL, as the weather corpus stores
    for its local ``simulator`` module (``test_prolog_cli.py``)"""
    return insert_model_row(Module, nulls=("fullpath",))


def experiment_without_description():
    """An experiment created without a description, as ``POST
    /experiments`` does when the description is null"""
    created = Experiment.create(ExperimentLW("experiment", "", None))
    return Experiment(created.id)


def annotation_of_an_experiment():
    """An annotation of an experiment, which has no trial: ``POST
    /experiments/<id>/extendedAnnotation`` (vis/views.py)"""
    experiment = Experiment.create(ExperimentLW("experiment", "", "about"))
    created = ExtendedAnnotation.create(ExtendedAnnotationLW(
        None, "note", "about", "plainText", "prospective", "Experiment",
        experiment.id, None))
    return ExtendedAnnotation(created.id)


def annotation_of_a_trial():
    """An annotation of a trial, which has no experiment: ``POST
    /trials/<id>/extendedAnnotation`` (vis/views.py)"""
    created = ExtendedAnnotation.create(ExtendedAnnotationLW(
        None, "note", "about", "plainText", "retrospective", "Trial",
        None, TRIAL_ID))
    return ExtendedAnnotation(created.id)


# (builder, table, column): the column the builder leaves NULL.
MISSING_VALUES = [
    pytest.param(module_without_fullpath, "module", "fullpath",
                 id="module-fullpath"),
    pytest.param(experiment_without_description, "experiment",
                 "description", id="experiment-description"),
    pytest.param(annotation_of_an_experiment, "extendedAnnotation",
                 "relatedTrial", id="annotation-relatedTrial"),
    pytest.param(annotation_of_a_trial, "extendedAnnotation",
                 "relatedExperiment", id="annotation-relatedExperiment"),
]


def missing_value(build, table, column):
    """``(fact, argument)``: the fact of the row ``build`` makes and its
    argument for ``column``, which SQL shows NULL"""
    proxy = build()
    nulls = sql('SELECT COUNT(*) FROM "{}" WHERE "{}" IS NULL'.format(
        table, column))
    assert nulls[0][0] == 1, "{}.{} is not NULL".format(table, column)
    description = type(proxy).prolog_description
    index = [attribute.attr_name
             for attribute in description.attributes].index(column)
    fact = description.fact(proxy)
    arguments = fact_arguments(fact, description.name)
    assert len(arguments) == len(description.attributes), fact
    return fact, arguments[index].strip()


@pytest.mark.parametrize("build, table, column", MISSING_VALUES)
def test_prolog_fact_of_a_missing_value(clean_store, build, table, column):
    """A NULL column described with ``PrologRepr`` is written as the atom
    ``'None'``, the same atom as the text ``None``

    Characterization of #353.
    """
    _, argument = missing_value(build, table, column)
    assert argument == "'None'"


@pytest.mark.parametrize("build, table, column", MISSING_VALUES)
@known_defects(NONE_ATOM)
def test_prolog_fact_of_a_missing_value_desired(
        clean_store, build, table, column):
    """A NULL column is written as ``nil``, like the nullable attributes
    of the other facts
    """
    fact, argument = missing_value(build, table, column)
    assert argument == "nil", "{} is {}, not nil, in {}".format(
        column, argument, fact)


# --- a trial's facts in Prolog ----------------------------------------------


def test_every_rule_of_rules_pl_is_one_line_ending_with_its_only_period():
    """Each line of ``rules.pl`` that is not blank or a comment is one
    whole clause, ending with its only period

    Premise of ``TrialProlog.load_cli_facts``, which asserts a clause at
    each line that holds a period, and of ``rule_calls`` in
    ``e2e/test_export.py``, which ends a rule at the line that ends with
    one.
    """
    text = RULES.read_text(encoding="utf-8")
    assert rule_line_problems(text) == []
    assert rule_clauses(text), "rules.pl has no clause"


def test_the_rule_line_scanner_flags_a_split_rule_and_an_inner_period():
    """Control: a rule split over two lines and a period inside a clause
    are flagged, comments and blank lines are not
    """
    text = ("% a comment. With periods.\n"
            "\n"
            "ok(X) :- X > 0.\n"
            "split(X) :-\n"
            "    ok(X).\n"
            "half(X) :- X > 0.5.\n")
    assert [number for number, _ in rule_line_problems(text)] == [4, 6]


def test_trial_prolog_exports_one_fact_per_row_of_the_trial(
        connected_two_trials):
    """The facts that a trial exports are one per row of its tables, for
    each of the twelve exported predicates

    The messages hold counts only: the export holds the environment.
    """
    trial = Trial()
    is_last = trial.id == connected_two_trials.trials()[-1]["id"]
    assert is_last, "Trial() is not the last trial"
    clauses = [body.strip() for kind, body
               in prolog_statements(trial.prolog.export_text_facts())
               if kind == "clause"]
    declared = [DECLARATION.fullmatch(clause).group(1)
                for clause in clauses if clause.startswith(":- dynamic(")]
    assert declared == EXPORTED
    counts = predicate_counts(clauses)
    expected = trial_row_counts(connected_two_trials, trial.id)
    assert set(counts) <= set(expected)
    assert {predicate: counts[predicate] for predicate in expected} == (
        expected)
    # Not vacuous: the trial has evaluations.
    assert expected["evaluation"] > 0


class FakeProlog:
    """The part of ``pyswip.Prolog`` that ``TrialProlog`` uses

    It records every clause asserted and every query. A query succeeds
    once, with no bindings, when the same text was asserted, as a ground
    goal does in Prolog; any other query has the solutions given in
    ``answers``, or none.
    """

    def __init__(self):
        self.asserted = []
        self.queries = []
        self.answers = {}

    def assertz(self, clause):
        self.asserted.append(clause)

    def query(self, goal):
        self.queries.append(goal)
        if goal in self.asserted:
            return iter([{}])
        return iter(self.answers.get(goal, []))


@pytest.fixture
def fake_pyswip(monkeypatch):
    """``pyswip`` replaced by a module whose ``Prolog`` is ``FakeProlog``,
    and no Prolog started yet; both restored afterwards"""
    module = types.ModuleType("pyswip")
    module.Prolog = FakeProlog
    monkeypatch.setitem(sys.modules, "pyswip", module)
    monkeypatch.setattr(TrialProlog, "prolog_cli", None)
    # prolog_query reads the trial of every live TrialProlog, through a
    # weak proxy that a dead trial would break.
    gc.collect()
    return module


def test_trial_prolog_loads_its_facts_and_the_rules_into_prolog(
        connected_two_trials, fake_pyswip):
    """``load_cli_facts`` starts Prolog with an empty trial and
    ``load_rules(0)``, then asserts the declarations and one fact per row of
    the trial, one clause per rule of ``rules.pl`` and ``load_rules(1)``,
    each without its period; a second load asserts nothing, ``retract``
    retracts the trial's facts of every predicate, and ``query`` returns
    what Prolog answers

    The messages name predicates or count clauses: the clauses of the trial
    hold the environment of the machine that built the store.
    """
    trial = Trial()
    trial.prolog.load_cli_facts()
    cli = TrialProlog.prolog_cli
    assert isinstance(cli, FakeProlog)
    rules = rule_clauses(RULES.read_text(encoding="utf-8"))
    started = cli.asserted[:2] == [
        "trial({})".format(", ".join(["0"] * TRIAL_ARITY)), "load_rules(0)"]
    assert started, heads(cli.asserted[:2])
    assert cli.asserted[-len(rules) - 1:] == rules + ["load_rules(1)"]
    loaded = cli.asserted[2:-len(rules) - 1]
    with_period = collections.Counter(
        heads(clause for clause in loaded if clause.endswith(".")))
    assert with_period == collections.Counter()
    declared = {}
    for clause in loaded:
        match = DECLARATION.fullmatch(clause)
        if match:
            declared[match.group(1)] = int(match.group(2))
    assert list(declared) == EXPORTED
    facts = [clause for clause in loaded if not clause.startswith(":-")]
    assert len(facts) + len(declared) == len(loaded)
    expected = trial_row_counts(connected_two_trials, trial.id)
    counts = predicate_counts(facts)
    assert {predicate: counts[predicate] for predicate in expected} == (
        expected)
    wrong_arity = collections.Counter(
        predicate for predicate in EXPORTED for fact in facts
        if fact.startswith(predicate + "(")
        and len(fact_arguments(fact, predicate)) != declared[predicate])
    assert wrong_arity == collections.Counter()
    # Prolog was asked whether the trial and the rules were loaded.
    assert len(cli.queries) == 2
    trial_fact = cli.queries[0]
    of_the_trial = trial_fact.startswith("trial({}, ".format(quoted(trial.id)))
    assert of_the_trial, "the first query is not the trial's fact"
    asserted = trial_fact in facts
    assert asserted, "the trial's fact is not among the facts asserted"
    assert cli.queries[1] == "load_rules(1)"

    # Loaded once: a query asserts nothing more. A trial without the cache
    # would have its facts retracted before the query (prolog_query), so
    # this one uses it, as `export dataflow` does.
    total = len(cli.asserted)
    trial.prolog.use_cache = True
    goal = "load_rules(X)"
    cli.answers[goal] = [{"X": 1}]
    assert list(trial.prolog.query(goal)) == [{"X": 1}]
    assert len(cli.asserted) == total
    assert cli.queries[-1] == goal

    del cli.queries[:]
    trial.prolog.retract()
    retracted = [re.match(r"retract\((\w+)\(", text).group(1)
                 for text in cli.queries]
    assert retracted == EXPORTED
    unbound = [text for text in cli.queries if quoted(trial.id) not in text]
    assert unbound == []
