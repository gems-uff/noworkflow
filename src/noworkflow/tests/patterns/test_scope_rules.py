# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The scope rules: ``scope_rules.py`` and their rules.pl definitions

The scope of a code component is the type of its container (``script``,
``function_def``, ``class_def``), or ``project`` for a component without
one; the scope of an evaluation is the scope of its code component. The
rules run on the shared two-trial weather store (``connected_two_trials``)
and their answers are checked against SQL on its ``db.sqlite``: a
component joined to its container. ``swipl`` runs the rules.pl versions
over ``now export prolog -r`` of the same trial; in those comparisons
rules.pl stands where the store stands in ``support.assert_rows``.

Both rules enumerate ``project`` as an option of the type
(``set_options_in_rule``). With the type unbound, the option's binding is
lost after the first solution, and ``evaluation_scope_id`` answers each
project-scope evaluation twice, once through its own option and once
through ``code_scope_id``'s. In rules.pl, ``scope/4`` with an unbound name
never ends: the name rules enumerate lists first.

Known defects get a characterization of today's answer and a ``_desired``
twin marked ``xfail(strict=True)`` through ``Defect``.
"""
import collections

import pytest

from noworkflow.patterns import BLANK, var
from noworkflow.patterns.rules import (
    code_scope_id,
    evaluation_scope_id,
    scope,
    scope_id,
)
from noworkflow.tests.helpers import swipl
from noworkflow.tests.helpers.swipl import Compound
from noworkflow.tests.patterns.support import (
    Defect,
    assert_rows,
    bindings,
    defect_marks,
    expect_known_failure,
    known_defects,
    normalize_prolog,
    outcome,
)

BINDING_LOST_REASON = (
    "#344: RuleQuery.apply_function "
    "(patterns/machinery.py) resets every variable of its binds to BLANK "
    "after each result, and a variable that an option of "
    "set_options_in_rule or restrict_rule bound in prepare_values is never "
    "bound again: an option left unbound (the type of code_scope_id and "
    "evaluation_scope_id, the model of scope) is BLANK in every solution "
    "of the option but the first"
)
BINDING_LOST = Defect(BINDING_LOST_REASON, signature="unbound in")
PROJECT_TWICE_REASON = (
    "#353: evaluation_scope_id and "
    "code_scope_id (patterns/rules/scope_rules.py) both carry "
    "set_options_in_rule(type=['project', BLANK]); the BLANK branch of "
    "evaluation_scope_id passes the unbound type to code_scope_id, which "
    "enumerates 'project' again, so every evaluation whose code component "
    "has no container comes out of both branches"
)
PROJECT_TWICE = Defect(PROJECT_TWICE_REASON, signature="repeats")
# The twin's first check: the script's evaluation says 'project' twice.
SCRIPT_TWICE = Defect(
    PROJECT_TWICE_REASON,
    signature="repeats 1 solutions\nonly in the rule (1): ('project',)")
NAME_ENUMERATES_LISTS = Defect(
    "#350: in rules.pl, code_name, "
    "evaluation_name, activation_name and access_name have their list "
    "clauses before the fact clause, so name/4 with the id and the name "
    "unbound enumerates [], [[]], [[],[]]... and never reaches a fact; "
    "scope/4 calls name/4 first, so scope with an unbound name never ends",
    signature="time_limit_exceeded")
STALE_TRIAL_ARITY = Defect(
    "#249: with the model unbound, rules.pl's scope/4 reaches "
    "name(T, trial, ...), which calls trial/9 while the facts are "
    "trial/12",
    signature="existence_error(procedure,trial/9)")
# The time limit of a rules.pl goal that never ends today; a correct
# answer takes about 30 ms.
HANG_LIMIT = 1

CODE_SCOPE = (
    "SELECT c.id AS id, c.name AS name, "
    "CASE WHEN c.container_id IS NULL THEN 'project' ELSE k.type END "
    "AS scope FROM code_component c LEFT JOIN code_component k "
    "ON k.trial_id = c.trial_id AND k.id = c.container_id "
    "WHERE c.trial_id = ?"
)
EVALUATION_SCOPE = (
    "SELECT e.id AS id, s.scope AS scope, s.name AS name "
    "FROM evaluation e JOIN ({}) s ON s.id = e.code_component_id "
    "WHERE e.trial_id = ?".format(CODE_SCOPE)
)


def trial_ids(project):
    return [trial["id"] for trial in project.trials()]


def code_scopes(project, trial_id):
    """``{code component id: scope}`` from SQL"""
    return {row["id"]: row["scope"]
            for row in project.query(CODE_SCOPE, trial_id)}


def evaluation_scopes(project, trial_id):
    """``{evaluation id: scope}`` from SQL"""
    return {row["id"]: row["scope"] for row in project.query(
        EVALUATION_SCOPE, trial_id, trial_id)}


def script_evaluation(project, trial_id):
    """The evaluation of the script itself: the trial's main code block"""
    rows = project.query(
        "SELECT e.id FROM evaluation e JOIN trial t ON t.id = e.trial_id "
        "AND e.code_component_id = t.main_id WHERE t.id = ?", trial_id)
    assert len(rows) == 1
    return rows[0]["id"]


def rules_pl(facts, trial_id, goal, variables, **limits):
    """The solutions of a rules.pl goal about a trial, in the store's terms"""
    found = swipl.solutions(
        facts, "T = {}, {}".format(swipl.quoted_atom(trial_id), goal),
        variables, **limits)
    return [normalize_prolog(row) for row in found.rows_or_raise()]


def assert_agree(python, prolog, defects=()):
    """Assert that a rule and rules.pl answer the same rows

    ``python`` and ``prolog`` are thunks; when rules.pl raises, the message
    is ``rules.pl raises <error>``.
    """
    expected = outcome(prolog)
    if isinstance(expected, str):
        message = "rules.pl raises " + expected
        expect_known_failure(defects, message)
        raise AssertionError(message)
    return assert_rows(python, expected, defects)


# --- code_scope_id ----------------------------------------------------------


def test_code_scope_id_of_each_component_is_its_container_type(
        connected_two_trials):
    """code_scope_id of a bound component answers the type of its
    container, or 'project' when it has none
    """
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    expected = code_scopes(project, trial_id)
    assert {"project", "script", "function_def"} <= set(expected.values())
    found = {}
    for code_id in expected:
        found[code_id] = [row[0] for row in bindings(
            code_scope_id(trial_id, code_id, var("Ty")), "Ty")]
    assert found == {code_id: [scope_type]
                     for code_id, scope_type in expected.items()}


@pytest.mark.parametrize("scope_type", ["project", "script", "function_def"])
def test_code_scope_id_with_a_bound_type_lists_its_components(
        connected_two_trials, scope_type):
    """code_scope_id with a bound type answers the components in it"""
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    expected = [(code_id,) for code_id, found in code_scopes(
        project, trial_id).items() if found == scope_type]
    assert expected
    assert_rows(lambda: bindings(
        code_scope_id(trial_id, var("I"), scope_type), "I"), expected)


def test_code_scope_id_with_unbound_ids(connected_two_trials):
    """With the id and the type unbound, code_scope_id answers every
    component once, but only the first project-scope one says 'project':
    the others leave the type BLANK

    Characterization of rule-option-binding-lost.
    """
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    expected = code_scopes(project, trial_id)
    rows = bindings(code_scope_id(trial_id, var("I"), var("Ty")), "I", "Ty")
    assert sorted(code_id for code_id, _ in rows) == sorted(expected)
    counts = collections.Counter(expected.values())
    counts[BLANK] = counts["project"] - 1
    counts["project"] = 1
    assert collections.Counter(scope_type for _, scope_type in rows) == (
        counts)


@known_defects(BINDING_LOST)
def test_code_scope_id_with_unbound_ids_desired(connected_two_trials):
    """With the id and the type unbound, code_scope_id answers every
    component with its scope
    """
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    assert_rows(
        lambda: bindings(code_scope_id(trial_id, var("I"), var("Ty")),
                         "I", "Ty"),
        list(code_scopes(project, trial_id).items()))


# --- evaluation_scope_id, scope_id, scope -----------------------------------


def test_evaluation_scope_id_of_an_evaluation_in_a_definition(
        connected_two_trials):
    """evaluation_scope_id of a bound evaluation whose code component has a
    container answers the scope of that component
    """
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    expected = {evaluation_id: [scope_type] for evaluation_id, scope_type
                in evaluation_scopes(project, trial_id).items()
                if scope_type != "project"}
    assert expected
    found = {}
    for evaluation_id in expected:
        found[evaluation_id] = [row[0] for row in bindings(
            evaluation_scope_id(trial_id, evaluation_id, var("Ty")), "Ty")]
    assert found == expected


def test_evaluation_scope_id_of_every_evaluation(connected_two_trials):
    """evaluation_scope_id answers 'project' twice for the script, and with
    the id unbound answers each project-scope evaluation twice and every
    other one once

    Characterization of evaluation-scope-project-twice.
    """
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    script = script_evaluation(project, trial_id)
    assert bindings(evaluation_scope_id(trial_id, script, var("Ty")),
                    "Ty") == [("project",), ("project",)]
    scopes = evaluation_scopes(project, trial_id)
    counts = collections.Counter(row[0] for row in bindings(
        evaluation_scope_id(trial_id, var("I"), var("Ty")), "I"))
    assert counts == {
        evaluation_id: 2 if scope_type == "project" else 1
        for evaluation_id, scope_type in scopes.items()}


@known_defects(SCRIPT_TWICE)
def test_evaluation_scope_id_of_every_evaluation_desired(
        connected_two_trials):
    """evaluation_scope_id answers 'project' once for the script, and each
    evaluation once with the id unbound
    """
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    script = script_evaluation(project, trial_id)
    assert_rows(lambda: bindings(
        evaluation_scope_id(trial_id, script, var("Ty")), "Ty"),
        [("project",)])
    assert_rows(lambda: bindings(
        evaluation_scope_id(trial_id, var("I"), var("Ty")), "I"),
        [(evaluation_id,) for evaluation_id in evaluation_scopes(
            project, trial_id)])


def test_scope_id_dispatches_on_the_model(connected_two_trials):
    """scope_id answers the code scope of a code component or block and the
    evaluation scope of an evaluation or activation; it has no access case
    """
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    code_id, code_type = next(
        (code_id, scope_type) for code_id, scope_type
        in sorted(code_scopes(project, trial_id).items())
        if scope_type == "function_def")
    opener = project.query(
        "SELECT activation_id FROM file_access WHERE trial_id = ? "
        "AND name = 'data1.dat'", trial_id)[0]["activation_id"]
    opener_type = evaluation_scopes(project, trial_id)[opener]
    for model, entity, expected in [
            ("code_component", code_id, code_type),
            ("code_block", code_id, code_type),
            ("evaluation", opener, opener_type),
            ("activation", opener, opener_type)]:
        assert bindings(scope_id(trial_id, model, entity, var("Ty")),
                        "Ty") == [(expected,)], model
    assert list(scope_id(trial_id, "access", 1, var("Ty"))) == []


SCOPE_BY_NAME = {
    "code_component-path": ("code_component", "path", CODE_SCOPE, 1),
    "activation-csv_read": (
        "activation", "csv_read",
        "SELECT s.scope AS scope, a.name AS name FROM activation a "
        "JOIN evaluation e ON e.trial_id = a.trial_id AND e.id = a.id "
        "JOIN ({}) s ON s.id = e.code_component_id "
        "WHERE a.trial_id = ?".format(CODE_SCOPE), 2),
}


@pytest.mark.parametrize("case", list(SCOPE_BY_NAME))
def test_scope_names_the_scope(connected_two_trials, case):
    """scope with a bound name answers the scope of each entity with that
    name: the five components named path are in a function, and so are
    the two calls of csv_read
    """
    model, name, sql, parameters = SCOPE_BY_NAME[case]
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    expected = [(row["scope"],) for row in project.query(
        sql, *[trial_id] * parameters) if row["name"] == name]
    assert expected
    assert_rows(lambda: bindings(scope(trial_id, model, name, var("Ty")),
                                 "Ty"), expected)


# --- rules.pl ---------------------------------------------------------------


def agree(case_id, query, goal, variables, defects=()):
    """A rule called on trial 1 and the rules.pl goal that defines it"""
    return pytest.param(query, goal, variables, defects, id=case_id,
                        marks=defect_marks(defects))


AGREE = [
    agree("code_scope_id-" + scope_type,
          lambda t, scope_type=scope_type: code_scope_id(
              t, var("I"), scope_type),
          "code_scope_id(T, I, {})".format(scope_type), "I")
    for scope_type in ("project", "script", "function_def")
] + [
    agree("code_scope_id-unbound",
          lambda t: code_scope_id(t, var("I"), var("Ty")),
          "code_scope_id(T, I, Ty)", "I Ty", (BINDING_LOST,)),
    agree("evaluation_scope_id-unbound",
          lambda t: evaluation_scope_id(t, var("I"), var("Ty")),
          "evaluation_scope_id(T, I, Ty)", "I Ty",
          (BINDING_LOST, PROJECT_TWICE)),
    agree("scope_id-activation",
          lambda t: scope_id(t, "activation", var("I"), var("Ty")),
          "scope_id(T, activation, I, Ty)", "I Ty",
          (BINDING_LOST, PROJECT_TWICE)),
    agree("scope_id-code_block",
          lambda t: scope_id(t, "code_block", var("I"), var("Ty")),
          "scope_id(T, code_block, I, Ty)", "I Ty", (BINDING_LOST,)),
    agree("scope-path",
          lambda t: scope(t, "code_component", "path", var("Ty")),
          "scope(T, code_component, path, Ty)", "Ty"),
    agree("scope-csv_read",
          lambda t: scope(t, "activation", "csv_read", var("Ty")),
          "scope(T, activation, csv_read, Ty)", "Ty"),
    agree("scope-unbound-model",
          lambda t: scope(t, var("Model"), "csv_read", var("Ty")),
          "scope(T, Model, csv_read, Ty)", "Model Ty",
          (STALE_TRIAL_ARITY, Defect(BINDING_LOST_REASON, "unbound in"))),
]


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
@pytest.mark.parametrize("query, goal, variables, defects", AGREE)
def test_scope_rules_agree_with_rules_pl(
        connected_two_trials, two_trial_prolog, query, goal, variables,
        defects):
    """The rule and its rules.pl definition answer the same solutions on
    the first weather trial
    """
    trial_id, facts = next(iter(two_trial_prolog.items()))
    assert_agree(
        lambda: bindings(query(trial_id), *variables.split()),
        lambda: rules_pl(facts, trial_id, goal, variables), defects)


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
def test_scope_with_an_unbound_name_in_rules_pl(two_trial_prolog):
    """In rules.pl, name/4 with the id and the name unbound answers lists
    of empty lists before any fact, and scope/4 with an unbound name never
    ends

    Characterization of rules-pl-name-enumerates-lists.
    """
    trial_id, facts = next(iter(two_trial_prolog.items()))
    pairs = rules_pl(facts, trial_id,
                     "findall(I-N, limit(3, name(T, evaluation, I, N)), L)",
                     "L")
    assert pairs == [((
        Compound("-", ((), ())),
        Compound("-", (((),), ((),))),
        Compound("-", (((), ()), ((), ()))),
    ),)]
    found = swipl.solutions(
        facts, "T = {}, scope(T, evaluation, N, Ty)".format(
            swipl.quoted_atom(trial_id)),
        "Ty", time_limit=HANG_LIMIT)
    assert (found.rows, found.error) == (
        [], "time_limit_exceeded: Time limit exceeded")


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
@known_defects(NAME_ENUMERATES_LISTS)
def test_scope_with_an_unbound_name_in_rules_pl_desired(
        two_trial_project, two_trial_prolog):
    """In rules.pl, scope/4 with an unbound name answers the scope of every
    evaluation

    Compared by type only: the export writes some names without the quotes
    of their literals.
    """
    trial_id, facts = next(iter(two_trial_prolog.items()))
    expected = [(scope_type,) for scope_type in evaluation_scopes(
        two_trial_project, trial_id).values()]
    assert_rows(lambda: rules_pl(
        facts, trial_id, "scope(T, evaluation, N, Ty)", "Ty",
        time_limit=HANG_LIMIT), expected)
