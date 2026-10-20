# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The id and name rules, in Python and in rules.pl, against the store

``evaluation_code_id``, ``code_name``, ``evaluation_name``,
``activation_name``, ``access_name``, ``name`` and ``map_names`` exist
twice: as Python rules (``patterns/rules/id_rules.py`` and
``name_rules.py``), run here in-process on ``connected_two_trials``, and
as predicates of ``resources/rules.pl``, run by ``swipl`` over the facts
of ``now export prolog -r`` for the same trial (``two_trial_prolog``).
Both are compared, for each of the two trials, with the rows SQL finds in
the store's ``db.sqlite``, as multisets; agreement between the two
follows from both agreeing with SQL.

The export writes some names its own way: a code component's name that
starts with a quote (a string literal, a docstring) loses a layer of
quotes, and a letter before a quote (#103); access ids are atoms ``f<id>``
(#57) and None is ``nil``. So on the rules.pl side the expected code
component names are the ones the export's ``code_component`` facts spell
(read by ``swipl``, independently of the rules), and ids are mapped back
with ``normalize_prolog``. A test holds those spellings to the store: they
differ from its names only for string literals, and only by characters
removed.

The cases carry the defects that make them fail today (each case states
the desired answer): a ``name`` with an unbound model binds it only on the
first result of each model (rule-option-binding-lost); ``name`` of the
trial ignores the id (name-trial-ignores-id); rules.pl names the trial
through ``trial/9``, while the export declares ``trial/12`` (#249); and the
name rules of rules.pl enumerate lists when the id is unbound
(rules-pl-name-enumerates-lists). Characterizations pin today's behavior
of each.
"""
import collections

import pytest

from noworkflow.patterns import BLANK, rules, var
from noworkflow.tests.helpers import swipl
from noworkflow.tests.patterns.support import (
    ABSENT,
    Defect,
    assert_rows,
    bindings,
    defect_marks,
    known_defects,
    normalize_prolog,
)

TRIALS = pytest.mark.parametrize("number", [1, 2], ids=["trial1", "trial2"])
NEEDS_SWIPL = pytest.mark.skipif(swipl.SWIPL is None,
                                 reason=swipl.SKIP_REASON)

# The signature is a row whose first value, Model, is BLANK (printed _):
# "unbound in" alone would also match the trial's row, which binds no Id.
OPTION_BINDING = Defect(
    "#344: name explores its restricted option "
    "model when it is unbound, and RuleQuery.apply_function resets the "
    "variable that prepare_values bound after the first result of each "
    "model",
    "(_, ")
NAME_TRIAL_REASON = (
    "#353: name_rules.name returns "
    "trial(trial_id, name) for the model 'trial' whatever the id, and "
    "leaves Id unbound; rules.pl names the trial only for Id 0")
STALE_ARITY = Defect(
    "#249: rules.pl names the trial through trial/9, while the export "
    "declares trial/12",
    "Unknown procedure: trial/9")
NAME_LISTS = Defect(
    "#350: the name rules of rules.pl list "
    "their [] and [Id|Ids] clauses before the scalar one, with no guard, so "
    "an unbound Id unifies with [], [[]], [[], []]... forever and never "
    "reaches the facts",
    "bind Id to a list")


def name_trial(signature):
    return Defect(NAME_TRIAL_REASON, signature)


class PythonSide:
    """The store's names as the Python rules answer them: unchanged"""

    @staticmethod
    def name(code_id, name):
        return name


class PrologSide:
    """The store's code component names as the export spells them"""

    def __init__(self, spellings):
        self.spellings = spellings

    def name(self, code_id, name):
        return self.spellings[code_id]


PYTHON = PythonSide()


def trial_id(project, number):
    return project.trials()[number - 1]["id"]


def sql_rows(project, sql, *params):
    """The rows of a query as tuples (give columns distinct names)"""
    return [tuple(row.values()) for row in project.query(sql, *params)]


# --- what the store holds ----------------------------------------------------


def evaluation_code_ids(project, trial, side):
    return sql_rows(project, "SELECT id, code_component_id FROM evaluation "
                    "WHERE trial_id = ?", trial)


def code_names(project, trial, side):
    return [(code, side.name(code, name)) for code, name in sql_rows(
        project, "SELECT id, name FROM code_component WHERE trial_id = ?",
        trial)]


def evaluation_names(project, trial, side):
    return [(evaluation, side.name(code, name))
            for evaluation, code, name in sql_rows(
                project, "SELECT evaluation.id AS evaluation_id, "
                "code_component.id AS code_id, code_component.name "
                "FROM evaluation JOIN code_component "
                "ON code_component.trial_id = evaluation.trial_id "
                "AND code_component.id = evaluation.code_component_id "
                "WHERE evaluation.trial_id = ?", trial)]


def activation_names(project, trial, side):
    return sql_rows(project, "SELECT id, name FROM activation "
                    "WHERE trial_id = ?", trial)


def access_names(project, trial, side):
    return sql_rows(project, "SELECT id, name FROM file_access "
                    "WHERE trial_id = ?", trial)


def trial_names(project, trial, side):
    return sql_rows(project, "SELECT 0, script FROM trial WHERE id = ?",
                    trial)


MODEL_NAMES = {
    "code_component": code_names,
    "code_block": code_names,
    "evaluation": evaluation_names,
    "activation": activation_names,
    "access": access_names,
    "trial": trial_names,
}


def names_by_model(project, trial, side):
    """(model, id, name) of every model that ``name`` knows"""
    return [(model,) + row for model, names in MODEL_NAMES.items()
            for row in names(project, trial, side)]


def names_of_id(identifier):
    """(model, name) of the instances whose id is ``identifier``"""
    def expected(project, trial, side):
        return [(model, name) for model, found, name
                in names_by_model(project, trial, side)
                if found == identifier]
    return expected


def only(identifier, names):
    """The names of ``names`` for one id, without the id"""
    def expected(project, trial, side):
        return [(name,) for found, name in names(project, trial, side)
                if found == identifier]
    return expected


def names_of_list(identifiers, names):
    """One row: the tuple of the names of ``identifiers``, in order"""
    def expected(project, trial, side):
        found = dict(names(project, trial, side))
        return [(tuple(found[identifier] for identifier in identifiers),)]
    return expected


def ids_of_names(wanted):
    """The lists of ids whose names are ``wanted``, one id per name"""
    def expected(project, trial, side):
        ids = collections.defaultdict(list)
        for code, name in code_names(project, trial, side):
            ids[name].append(code)
        rows = [()]
        for name in wanted:
            rows = [row + (code,) for row in rows for code in ids[name]]
        return [(row,) for row in rows]
    return expected


def nothing(project, trial, side):
    return []


def one_empty_solution(project, trial, side):
    return [()]


# --- the Python rules --------------------------------------------------------


def rule_case(case_id, rule, names, expected, *defects):
    """``rule(trial, *variables)``, the variables named by ``names``"""
    return pytest.param(rule, names, expected, defects, id=case_id,
                        marks=defect_marks(defects))


RULE_CASES = [
    rule_case("evaluation_code_id", rules.evaluation_code_id, "Id CodeId",
              evaluation_code_ids),
    rule_case("evaluation_code_id-of-1",
              lambda t, c: rules.evaluation_code_id(t, 1, c), "CodeId",
              only(1, evaluation_code_ids)),
    rule_case("code_name", rules.code_name, "Id Name", code_names),
    rule_case("code_name-list", lambda t, n: rules.code_name(t, [1, 2], n),
              "Names", names_of_list([1, 2], code_names)),
    rule_case("code_name-by-names", lambda t, i: rules.code_name(
        t, i, ["csv_read", "simulate"]), "Ids",
        ids_of_names(["csv_read", "simulate"])),
    rule_case("code_name-size-mismatch",
              lambda t: rules.code_name(t, [1, 2], ["x"]), "", nothing),
    rule_case("code_name-unknown-id",
              lambda t, n: rules.code_name(t, [1, 999999], n), "Names",
              nothing),
    rule_case("code_name-name-omitted", lambda t: rules.code_name(t, [1, 2]),
              "", one_empty_solution),
    rule_case("evaluation_name", rules.evaluation_name, "Id Name",
              evaluation_names),
    rule_case("evaluation_name-list",
              lambda t, n: rules.evaluation_name(t, [1, 2], n), "Names",
              names_of_list([1, 2], evaluation_names)),
    rule_case("activation_name", rules.activation_name, "Id Name",
              activation_names),
    rule_case("access_name", rules.access_name, "Id Name", access_names),
] + [
    rule_case("name-" + model, lambda t, i, n, model=model: rules.name(
        t, model, i, n), "Id Name", MODEL_NAMES[model])
    for model in ("code_component", "code_block", "evaluation", "activation",
                  "access")
] + [
    rule_case("name-trial-of-0", lambda t, n: rules.name(t, "trial", 0, n),
              "Name", only(0, trial_names)),
    rule_case("name-trial", lambda t, i, n: rules.name(t, "trial", i, n),
              "Id Name", trial_names,
              name_trial("only in the rule (1): (<absent>,")),
    rule_case("name-trial-of-another-id",
              lambda t, n: rules.name(t, "trial", 12345, n), "Name", nothing,
              name_trial("1 solutions in the rule, 0 in the store")),
    rule_case("name-of-id-5", lambda t, m, n: rules.name(t, m, 5, n),
              "Model Name", names_of_id(5),
              name_trial("only in the rule (1): ('trial',")),
    # The trial's row is wrong: name binds no Id for it, and the Id it
    # shows is the last one of the model before it, left in the binds.
    rule_case("name-unbound-model", rules.name, "Model Id Name",
              names_by_model, OPTION_BINDING, name_trial("('trial', ")),
]


@TRIALS
@pytest.mark.parametrize("rule, names, expected, defects", RULE_CASES)
def test_rule_matches_the_store(connected_two_trials, number, rule, names,
                                expected, defects):
    """The Python rule answers the rows SQL finds for the trial"""
    project = connected_two_trials
    trial = trial_id(project, number)
    variables = [var(name) for name in names.split()]
    assert_rows(lambda: bindings(rule(trial, *variables), *variables),
                expected(project, trial, PYTHON), defects)


@TRIALS
def test_name_with_an_unbound_model_binds_it_once_per_model(
        connected_two_trials, number):
    """``name(T, Model, Id, Name)`` binds Model on the first result of each
    model with rows, and leaves it BLANK on every other result
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    store = collections.Counter(
        row[0] for row in names_by_model(project, trial, PYTHON))
    model, identifier, name = var("Model Id Name")
    found = collections.Counter(row[0] for row in bindings(
        rules.name(trial, model, identifier, name), model))
    expected = {model: 1 for model in store}
    expected[BLANK] = sum(store.values()) - len(store)
    assert found == expected


@TRIALS
def test_name_of_the_trial_ignores_the_id(connected_two_trials, number):
    """``name`` of the model trial answers the script for any id, binds no
    Id, and ``name(T, Model, 5, Name)`` names the trial too
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    script = project.trial(trial)["script"]
    name, identifier, model = var("Name Id Model")
    assert bindings(rules.name(trial, "trial", 12345, name), name) == [
        (script,)]
    assert bindings(rules.name(trial, "trial", identifier, name),
                    identifier, name) == [(ABSENT, script)]
    assert ("trial", script) in bindings(
        rules.name(trial, model, 5, name), model, name)


def test_map_names_is_prolog_only(two_trial_project):
    """By design, ``map_names`` points to ``name`` instead of answering"""
    trial = trial_id(two_trial_project, 1)
    with pytest.raises(NotImplementedError, match="Please use the 'name'"):
        list(rules.map_names(trial, "activation", [1], var("Names")))


# --- rules.pl ----------------------------------------------------------------


@pytest.fixture(scope="module")
def spellings(two_trial_prolog):
    """``{trial id: {code component id: its name in the export}}``"""
    result = {}
    for trial, path in two_trial_prolog.items():
        rows = swipl.solutions(
            path, "code_component({}, Id, Name, _, _, _, _, _, _, _)".format(
                swipl.quoted_atom(trial)), "Id Name").rows_or_raise()
        result[trial] = dict(rows)
    return result


QUOTES = ("'", '"')


def string_literal(name):
    """Whether ``name`` is the source of a string literal: it starts with a
    quote, or with a prefix letter and a quote
    """
    return name[:1] in QUOTES or (name[:1].isalpha() and name[1:2] in QUOTES)


@NEEDS_SWIPL
@TRIALS
def test_the_export_spells_code_names_as_the_store_but_string_literals(
        two_trial_project, spellings, number):
    """The names the rules.pl cases expect are the store's: ``spellings``
    differs from SQL only for string literals (#103), and only by
    characters removed
    """
    project = two_trial_project
    trial = trial_id(project, number)
    store = dict(sql_rows(project, "SELECT id, name FROM code_component "
                          "WHERE trial_id = ?", trial))
    spelled = spellings[trial]
    assert set(spelled) == set(store)
    assert any(string_literal(name) for name in store.values()), (
        "the script has no string literal")
    unexplained = sorted(
        code for code, name in store.items() if spelled[code] != name
        and not (string_literal(name) and spelled[code] in name))
    assert unexplained == [], "ids spelled apart from the store"


def prolog_case(case_id, goal, names, expected, *defects, ids=()):
    """``goal`` over the trial's facts, T bound to the trial id

    ``ids`` lists the columns that hold ids or nullable values, which
    ``normalize_prolog`` maps back to the store's.
    """
    return pytest.param(goal, names, ids, expected, defects, id=case_id,
                        marks=defect_marks(defects))


# A goal that enumerates the ids of each model through its facts.
MODEL_IDS = {
    "code_component": "code_component(T, Id, _, _, _, _, _, _, _, _)",
    "code_block": "code_component(T, Id, _, _, _, _, _, _, _, _)",
    "evaluation": "evaluation(T, Id, _, _, _, _, _)",
    "activation": "activation(T, Id, _, _, _)",
    "access": "access(T, Id, _, _, _, _, _, _)",
}

PROLOG_CASES = [
    prolog_case("evaluation_code_id", "evaluation_code_id(T, Id, CodeId)",
                "Id CodeId", evaluation_code_ids),
    prolog_case("code_name", MODEL_IDS["code_component"]
                + ", code_name(T, Id, Name)", "Id Name", code_names),
    prolog_case("code_name-list", "code_name(T, [1, 2], Names)", "Names",
                names_of_list([1, 2], code_names)),
    prolog_case("evaluation_name", MODEL_IDS["evaluation"]
                + ", evaluation_name(T, Id, Name)", "Id Name",
                evaluation_names),
    prolog_case("evaluation_name-list", "evaluation_name(T, [1, 2], Names)",
                "Names", names_of_list([1, 2], evaluation_names)),
    prolog_case("activation_name", MODEL_IDS["activation"]
                + ", activation_name(T, Id, Name)", "Id Name",
                activation_names),
    prolog_case("access_name", MODEL_IDS["access"]
                + ", access_name(T, Id, Name)", "Id Name", access_names,
                ids=(0,)),
] + [
    prolog_case("name-" + model, "{}, name(T, {}, Id, Name)".format(
        MODEL_IDS[model], model), "Id Name", MODEL_NAMES[model], ids=(0,))
    for model in MODEL_IDS
] + [
    prolog_case("name-trial", "name(T, trial, Id, Name)", "Id Name",
                trial_names, STALE_ARITY),
    prolog_case("name-of-id-0", "name(T, Model, 0, Name)", "Model Name",
                names_of_id(0), STALE_ARITY),
    prolog_case("name-of-id-5", "name(T, Model, 5, Name)", "Model Name",
                names_of_id(5)),
    prolog_case("map_names", "map_names(T, code_component, [1, 2, 3], Ns)",
                "Ns", names_of_list([1, 2, 3], code_names)),
    prolog_case("map_names-activation",
                "map_names(T, activation, [1], Ns)", "Ns",
                names_of_list([1], activation_names)),
]


@NEEDS_SWIPL
@TRIALS
@pytest.mark.parametrize("goal, names, ids, expected, defects", PROLOG_CASES)
def test_rules_pl_matches_the_store(two_trial_project, two_trial_prolog,
                                    spellings, number, goal, names, ids,
                                    expected, defects):
    """The predicate of rules.pl answers the rows SQL finds for the trial"""
    project = two_trial_project
    trial = trial_id(project, number)

    def answer():
        rows = swipl.solutions(
            two_trial_prolog[trial],
            "T = {}, {}".format(swipl.quoted_atom(trial), goal),
            names).rows_or_raise()
        return [tuple(normalize_prolog(value) if index in ids else value
                      for index, value in enumerate(row)) for row in rows]

    assert_rows(answer, expected(project, trial, PrologSide(
        spellings[trial])), defects)


NAME_RULES = pytest.mark.parametrize("rule, names", [
    ("code_name", code_names),
    ("evaluation_name", evaluation_names),
    ("activation_name", activation_names),
    ("access_name", access_names),
], ids=["code_name", "evaluation_name", "activation_name", "access_name"])


@NEEDS_SWIPL
@NAME_RULES
def test_rules_pl_name_rules_enumerate_lists_for_an_unbound_id(
        two_trial_project, two_trial_prolog, rule, names):
    """With Id unbound, the first solutions bind Id and Name to [], [[]]
    and [[], []]: the list clauses come first and never reach the facts
    """
    trial = trial_id(two_trial_project, 1)
    rows = swipl.solutions(
        two_trial_prolog[trial], "T = {}, limit(3, {}(T, Id, Name))".format(
            swipl.quoted_atom(trial), rule), "Id Name").rows_or_raise()
    assert rows == [((), ()), (((),), ((),)), (((), ()), ((), ()))]


@NEEDS_SWIPL
@NAME_RULES
@known_defects(NAME_LISTS)
def test_rules_pl_name_rules_answer_the_facts_for_an_unbound_id_desired(
        two_trial_project, two_trial_prolog, spellings, rule, names):
    """With Id unbound, a name rule answers each instance's id and name,
    and nothing more (bounded by one solution past the store's count)
    """
    project = two_trial_project
    trial = trial_id(project, 1)
    expected = names(project, trial, PrologSide(spellings[trial]))
    rows = swipl.solutions(
        two_trial_prolog[trial], "T = {}, limit({}, {}(T, Id, Name))".format(
            swipl.quoted_atom(trial), len(expected) + 1, rule),
        "Id Name").rows_or_raise()
    lists = sum(1 for row in rows if isinstance(row[0], tuple))
    assert not lists, "{} solutions bind Id to a list".format(lists)
    rows = [(normalize_prolog(identifier), name) for identifier, name in rows]
    assert_rows(lambda: rows, expected)


@NEEDS_SWIPL
def test_rules_pl_names_the_trial_through_a_stale_arity(
        two_trial_project, two_trial_prolog):
    """Naming the trial (Id 0, or the model trial) raises an existence error
    for trial/9: the runtime effect of #249 on the name rules
    """
    trial = trial_id(two_trial_project, 1)
    for goal in ("name(T, trial, Id, Name)", "name(T, Model, 0, Name)"):
        found = swipl.solutions(
            two_trial_prolog[trial],
            "T = {}, {}".format(swipl.quoted_atom(trial), goal), "Name")
        assert found.rows == [], goal
        assert "Unknown procedure: trial/9" in (found.error or ""), goal
