# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The activation rules: ``activation_rules.py`` and their rules.pl definitions

The rules relate evaluations to the activations that called them, to the
lines of their code and to the activations among a list of evaluations,
and collect every evaluation inside an activation. They run on the shared
two-trial weather store (``connected_two_trials``) and their answers are
checked against SQL on its ``db.sqlite``, the descendants of an activation
through a recursive query. The ids the tests ask about are found by SQL
too: the ``open`` of ``data1.dat``, the first ``csv_read``,
``run_simulation`` and the script's own evaluation. ``swipl`` runs the
rules.pl versions over ``now export prolog -r`` of the same trial; in those
comparisons rules.pl stands where the store stands in
``support.assert_rows``.

Known defects get a characterization of today's answer and a ``_desired``
twin marked ``xfail(strict=True)`` through ``Defect``. rules.pl's
``recursive_internal_evaluations_ids`` never ends on an activation without
evaluations of its own, so its goals run under the inference limit of
``helpers/swipl.py``, which stops them in a fraction of a second.
"""

import types

import pytest

from noworkflow.patterns import var
from noworkflow.patterns.machinery import Variable
from noworkflow.patterns.rules import (
    activation_id,
    called_activation_id,
    evaluation_line_id,
    filter_activation_ids,
    is_activation_id,
    map_evaluation_code_ids,
    map_evaluation_lines_id,
    recursive_internal_evaluations_ids,
)
from noworkflow.tests.helpers import swipl
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

BAGOF_REASON = (
    "#347: _bagof_append_sort "
    "(patterns/rules/helpers.py), behind map_evaluation_lines_id, puts the "
    "ids it found into a set, sorts it and requires it to equal the Ids as "
    "given, so ids in another order, or repeated, never match and the rule "
    "fails; rules.pl bagofs the lines of each id and sorts only the lines"
)
UNSORTED_IDS = Defect(
    BAGOF_REASON, signature="answers nothing for ids that are not sorted and distinct"
)
FILTER_REASON = "#353: filter_activation_ids (patterns/rules/activation_rules.py) "
FILTER_REPEATS = Defect(
    FILTER_REASON + "collects the ids into an OrderedDict, which keeps a "
    "repeated id once, while rules.pl's include/3 keeps every occurrence",
    signature="repeated ids dropped",
)
FILTER_UNBOUND = Defect(
    FILTER_REASON + "matches an unbound Ids with the ActivationIds "
    "variable before that variable holds the list, so Ids is bound to the "
    "Variable object itself",
    signature="Ids bound to Variable",
)
RECURSIVE_LOOPS = Defect(
    "#352: in rules.pl, the second "
    "clause of recursive_internal_evaluations_ids fails for an activation "
    "without evaluations of its own (its bagof finds none), and the third "
    "clause matches [A|[]] and calls the rule on [A] again, forever; an "
    "activation with such a leaf below it (a call of a builtin, such as "
    "open) never answers",
    signature="inference_limit_exceeded",
)

DESCENDANTS = (
    "WITH RECURSIVE down(id) AS ("
    "SELECT id FROM evaluation WHERE trial_id = :trial AND activation_id = "
    ":caller UNION ALL SELECT e.id FROM evaluation e JOIN down "
    "ON e.activation_id = down.id WHERE e.trial_id = :trial"
    ") SELECT id FROM down"
)


def weather_ids(project):
    """The first weather trial and the evaluations the tests ask about"""
    trial = project.trials()[0]
    trial_id = trial["id"]

    def one(sql, *params):
        rows = project.query(sql, trial_id, *params)
        assert rows, sql
        return next(iter(rows[0].values()))

    ids = types.SimpleNamespace(
        trial=trial_id,
        script=one(
            "SELECT id FROM evaluation WHERE trial_id = ? AND code_component_id = ?",
            trial["main_id"],
        ),
        open=one(
            "SELECT activation_id FROM file_access WHERE trial_id = ? "
            "AND name = 'data1.dat'"
        ),
        csv_read=one(
            "SELECT id FROM activation WHERE trial_id = ? "
            "AND name = 'csv_read' ORDER BY start_checkpoint"
        ),
        run_simulation=one(
            "SELECT id FROM activation WHERE trial_id = ? AND name = 'run_simulation'"
        ),
        plain=one(
            "SELECT MIN(e.id) FROM evaluation e WHERE e.trial_id = ? "
            "AND NOT EXISTS (SELECT 1 FROM activation a "
            "WHERE a.trial_id = e.trial_id AND a.id = e.id)"
        ),
    )
    # The open and run_simulation in ascending order, for the cases of
    # map_evaluation_lines_id that depend on the order of the ids.
    ids.low, ids.high = sorted([ids.open, ids.run_simulation])
    return ids


def activations(project, trial_id):
    """The activation ids of a trial, from SQL"""
    return [
        row["id"]
        for row in project.query(
            "SELECT id FROM activation WHERE trial_id = ? ORDER BY id", trial_id
        )
    ]


def lines(project, trial_id, evaluation):
    """The lines that the code component of an evaluation spans, from SQL"""
    row = project.query(
        "SELECT c.first_char_line AS first, c.last_char_line AS last "
        "FROM evaluation e JOIN code_component c ON c.trial_id = e.trial_id "
        "AND c.id = e.code_component_id WHERE e.trial_id = ? AND e.id = ?",
        trial_id,
        evaluation,
    )[0]
    return list(range(row["first"], row["last"] + 1))


def descendants(project, trial_id, caller):
    """Every evaluation inside an activation, at any depth, from SQL"""
    with project.db() as connection:
        return [
            row[0]
            for row in connection.execute(
                DESCENDANTS, {"trial": trial_id, "caller": caller}
            )
        ]


def rules_pl(facts, trial_id, goal, variables, **limits):
    """The solutions of a rules.pl goal about a trial, in the store's terms"""
    found = swipl.solutions(
        facts,
        "T = {}, {}".format(swipl.quoted_atom(trial_id), goal),
        variables,
        **limits,
    )
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


# --- is_activation_id, activation_id, called_activation_id ------------------


def test_is_activation_id_matches_the_activation_table(connected_two_trials):
    """is_activation_id answers the activations, accepts a bound activation
    and rejects an evaluation that is not one
    """
    project = connected_two_trials
    ids = weather_ids(project)
    assert_rows(
        lambda: bindings(is_activation_id(ids.trial, var("I")), "I"),
        [(i,) for i in activations(project, ids.trial)],
    )
    assert len(list(is_activation_id(ids.trial, ids.open))) == 1
    assert list(is_activation_id(ids.trial, ids.plain)) == []


def test_activation_id_lists_the_evaluations_of_a_caller(connected_two_trials):
    """activation_id answers the evaluations an activation called, and the
    caller of an evaluation: for the script, the store's root caller
    """
    project = connected_two_trials
    ids = weather_ids(project)
    called = [
        (row["id"],)
        for row in project.query(
            "SELECT id FROM evaluation WHERE trial_id = ? AND activation_id = ?",
            ids.trial,
            ids.run_simulation,
        )
    ]
    assert called
    assert_rows(
        lambda: bindings(activation_id(ids.trial, ids.run_simulation, var("C")), "C"),
        called,
    )
    root = project.query(
        "SELECT activation_id FROM evaluation WHERE trial_id = ? AND id = ?",
        ids.trial,
        ids.script,
    )[0]["activation_id"]
    assert bindings(activation_id(ids.trial, var("A"), ids.script), "A") == [(root,)]


def test_called_activation_id_lists_the_activations_a_caller_started(
    connected_two_trials,
):
    """called_activation_id answers the evaluations of a caller that are
    activations, not all of its evaluations, and the caller of an
    activation
    """
    project = connected_two_trials
    ids = weather_ids(project)
    started = [
        (row["id"],)
        for row in project.query(
            "SELECT e.id FROM evaluation e JOIN activation a "
            "ON a.trial_id = e.trial_id AND a.id = e.id "
            "WHERE e.trial_id = ? AND e.activation_id = ?",
            ids.trial,
            ids.csv_read,
        )
    ]
    evaluations = project.query(
        "SELECT id FROM evaluation WHERE trial_id = ? AND activation_id = ?",
        ids.trial,
        ids.csv_read,
    )
    assert 0 < len(started) < len(evaluations)
    assert_rows(
        lambda: bindings(called_activation_id(ids.trial, ids.csv_read, var("C")), "C"),
        started,
    )
    assert bindings(called_activation_id(ids.trial, var("A"), ids.csv_read), "A") == [
        (ids.run_simulation,)
    ]


# --- evaluation_line_id, map_evaluation_lines_id ----------------------------


def test_evaluation_line_id_spans_the_lines_of_the_code_component(connected_two_trials):
    """evaluation_line_id answers every line of an evaluation's code
    component, and the evaluations whose component spans a line
    """
    project = connected_two_trials
    ids = weather_ids(project)
    for evaluation in (ids.open, ids.script):
        assert_rows(
            lambda: bindings(evaluation_line_id(ids.trial, evaluation, var("L")), "L"),
            [(line,) for line in lines(project, ids.trial, evaluation)],
        )
    spanning = [
        (row["id"],)
        for row in project.query(
            "SELECT e.id FROM evaluation e JOIN code_component c "
            "ON c.trial_id = e.trial_id AND c.id = e.code_component_id "
            "WHERE e.trial_id = ? AND c.first_char_line <= 13 "
            "AND c.last_char_line >= 13",
            ids.trial,
        )
    ]
    assert len(spanning) > 1
    assert_rows(
        lambda: bindings(evaluation_line_id(ids.trial, var("I"), 13), "I"), spanning
    )


def test_map_evaluation_lines_id_of_sorted_ids(connected_two_trials):
    """map_evaluation_lines_id of ids in ascending order answers the sorted
    union of their lines; it accepts that list bound, and fails on a list
    without the lines of one id and on an unknown id
    """
    project = connected_two_trials
    ids = weather_ids(project)
    pair = [ids.low, ids.high]
    union = sorted(
        set(lines(project, ids.trial, pair[0]))
        | set(lines(project, ids.trial, pair[1]))
    )
    assert bindings(map_evaluation_lines_id(ids.trial, pair, var("L")), "L") == [
        (tuple(union),)
    ]
    assert len(list(map_evaluation_lines_id(ids.trial, pair, union))) == 1
    assert (
        list(
            map_evaluation_lines_id(
                ids.trial, pair, lines(project, ids.trial, ids.open)
            )
        )
        == []
    )
    assert bindings(map_evaluation_lines_id(ids.trial, [], var("L")), "L") == [((),)]
    unknown = (
        max(
            row["id"]
            for row in project.query(
                "SELECT id FROM evaluation WHERE trial_id = ?", ids.trial
            )
        )
        + 1
    )
    assert list(map_evaluation_lines_id(ids.trial, [unknown], var("L"))) == []


def unsorted_cases(project, ids):
    """``[(ids, expected lines)]``: a descending pair and a repeated id"""
    union = sorted(
        set(lines(project, ids.trial, ids.low))
        | set(lines(project, ids.trial, ids.high))
    )
    return [
        ([ids.high, ids.low], union),
        ([ids.low, ids.low], lines(project, ids.trial, ids.low)),
    ]


def test_map_evaluation_lines_id_of_unsorted_or_repeated_ids(connected_two_trials):
    """map_evaluation_lines_id answers nothing when the ids come in
    descending order or repeated

    Characterization of bagof-append-sort-compare.
    """
    project = connected_two_trials
    ids = weather_ids(project)
    for given, _ in unsorted_cases(project, ids):
        assert list(map_evaluation_lines_id(ids.trial, given, var("L"))) == [], given


@known_defects(UNSORTED_IDS)
def test_map_evaluation_lines_id_of_unsorted_or_repeated_ids_desired(
    connected_two_trials,
):
    """map_evaluation_lines_id answers the sorted union of the lines
    whatever the order of the ids, and repeats change nothing
    """
    project = connected_two_trials
    ids = weather_ids(project)
    answers = {}
    for given, expected in unsorted_cases(project, ids):
        answers[tuple(given)] = (
            bindings(map_evaluation_lines_id(ids.trial, given, var("L")), "L"),
            [(tuple(expected),)],
        )
    if all(found == [] for found, _ in answers.values()):
        raise AssertionError(
            "map_evaluation_lines_id answers nothing for ids that are not "
            "sorted and distinct: {}".format(sorted(answers))
        )
    assert {given: found for given, (found, _) in answers.items()} == {
        given: expected for given, (_, expected) in answers.items()
    }


def test_map_evaluation_code_ids_maps_each_id(connected_two_trials):
    """map_evaluation_code_ids answers the code component of each id, in
    order, or of a single id; an unknown id fails the list
    """
    project = connected_two_trials
    ids = weather_ids(project)
    given = [ids.open, ids.run_simulation, ids.script]
    codes = {
        row["id"]: row["code_component_id"]
        for row in project.query(
            "SELECT id, code_component_id FROM evaluation WHERE trial_id = ?", ids.trial
        )
    }
    assert bindings(map_evaluation_code_ids(ids.trial, given, var("C")), "C") == [
        (tuple(codes[i] for i in given),)
    ]
    assert bindings(map_evaluation_code_ids(ids.trial, ids.open, var("C")), "C") == [
        (codes[ids.open],)
    ]
    assert (
        list(map_evaluation_code_ids(ids.trial, [ids.open, max(codes) + 1], var("C")))
        == []
    )


# --- filter_activation_ids --------------------------------------------------


def test_filter_activation_ids_keeps_the_activations_in_order(connected_two_trials):
    """filter_activation_ids answers the activations among the ids, in
    their order, and fails on a bound list that is not that answer
    """
    project = connected_two_trials
    ids = weather_ids(project)
    given = [ids.open, ids.plain, ids.csv_read, ids.script]
    expected = [i for i in given if i in activations(project, ids.trial)]
    assert expected == [ids.open, ids.csv_read, ids.script]
    assert bindings(filter_activation_ids(ids.trial, given, var("A")), "A") == [
        (tuple(expected),)
    ]
    assert list(filter_activation_ids(ids.trial, given, expected[:1])) == []


def repeated_ids(ids):
    return [ids.open, ids.plain, ids.csv_read, ids.open, ids.script]


def test_filter_activation_ids_of_repeated_ids(connected_two_trials):
    """filter_activation_ids answers a repeated activation once

    Characterization of filter-activation-ids.
    """
    ids = weather_ids(connected_two_trials)
    assert bindings(
        filter_activation_ids(ids.trial, repeated_ids(ids), var("A")), "A"
    ) == [((ids.open, ids.csv_read, ids.script),)]


@known_defects(FILTER_REPEATS)
def test_filter_activation_ids_of_repeated_ids_desired(connected_two_trials):
    """filter_activation_ids keeps every occurrence of an activation, as
    include/3 does
    """
    project = connected_two_trials
    ids = weather_ids(project)
    given = repeated_ids(ids)
    expected = [i for i in given if i in activations(project, ids.trial)]
    found = bindings(filter_activation_ids(ids.trial, given, var("A")), "A")
    if found == [(tuple(dict.fromkeys(expected)),)]:
        raise AssertionError("repeated ids dropped: {} -> {}".format(given, found))
    assert found == [(tuple(expected),)]


def test_filter_activation_ids_with_unbound_ids(connected_two_trials):
    """With Ids unbound, filter_activation_ids answers every activation in
    ActivationIds and binds Ids to the ActivationIds variable itself

    Characterization of filter-activation-ids.
    """
    project = connected_two_trials
    ids = weather_ids(project)
    given, result = var("I"), var("A")
    [(bound, found)] = bindings(
        filter_activation_ids(ids.trial, given, result), given, result
    )
    assert bound is result
    assert sorted(found) == activations(project, ids.trial)
    assert len(found) == len(set(found))


@known_defects(FILTER_UNBOUND)
def test_filter_activation_ids_with_unbound_ids_desired(connected_two_trials):
    """With Ids unbound, filter_activation_ids binds Ids and ActivationIds
    to the same list: every activation
    """
    project = connected_two_trials
    ids = weather_ids(project)
    given, result = var("I"), var("A")
    [(bound, found)] = bindings(
        filter_activation_ids(ids.trial, given, result), given, result
    )
    if isinstance(bound, Variable):
        raise AssertionError("Ids bound to Variable {!r}".format(bound))
    assert bound == found
    assert sorted(found) == activations(project, ids.trial)


# --- recursive_internal_evaluations_ids -------------------------------------


def test_recursive_internal_evaluations_ids_lists_every_descendant(
    connected_two_trials,
):
    """recursive_internal_evaluations_ids answers every evaluation inside
    the activations, at any depth, once each; nothing inside a call of
    open or an empty list; it fails on a wrong bound answer and refuses
    unbound activations
    """
    project = connected_two_trials
    ids = weather_ids(project)
    for caller in (ids.run_simulation, ids.script):
        expected = descendants(project, ids.trial, caller)
        [(found,)] = bindings(
            recursive_internal_evaluations_ids(ids.trial, [caller], var("E")), "E"
        )
        assert len(found) == len(set(found))
        assert set(found) == set(expected)
    for given in ([ids.open], []):
        assert bindings(
            recursive_internal_evaluations_ids(ids.trial, given, var("E")), "E"
        ) == [((),)]
    assert (
        list(recursive_internal_evaluations_ids(ids.trial, [ids.open], [ids.script]))
        == []
    )
    with pytest.raises(ValueError, match="requires the activations list to be bound"):
        list(recursive_internal_evaluations_ids(ids.trial, var("Acts"), var("E")))


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
def test_recursive_internal_evaluations_ids_in_rules_pl(
    two_trial_project, two_trial_prolog
):
    """In rules.pl, recursive_internal_evaluations_ids answers [] for an
    empty list and never ends for the call of open, or for csv_read, which
    calls it

    Characterization of rules-pl-recursive-internal-loops.
    """
    ids = weather_ids(two_trial_project)
    facts = two_trial_prolog[ids.trial]
    assert rules_pl(
        facts, ids.trial, "recursive_internal_evaluations_ids(T, [], E)", "E"
    ) == [((),)]
    for caller in (ids.open, ids.csv_read):
        assert outcome(
            lambda: rules_pl(
                facts,
                ids.trial,
                "recursive_internal_evaluations_ids(T, [{}], E)".format(caller),
                "E",
            )
        ) == ("PrologError: inference_limit_exceeded: Inference limit exceeded")


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
@known_defects(RECURSIVE_LOOPS)
def test_recursive_internal_evaluations_ids_in_rules_pl_desired(
    two_trial_project, two_trial_prolog
):
    """In rules.pl, recursive_internal_evaluations_ids answers [] for the
    call of open and every evaluation inside csv_read, once each
    """
    ids = weather_ids(two_trial_project)
    facts = two_trial_prolog[ids.trial]
    for caller in (ids.open, ids.csv_read):
        rows = rules_pl(
            facts,
            ids.trial,
            "recursive_internal_evaluations_ids(T, [{}], E)".format(caller),
            "E",
        )
        expected = descendants(two_trial_project, ids.trial, caller)
        assert len(rows) == 1, rows
        assert sorted(rows[0][0]) == sorted(expected)


# --- rules.pl ---------------------------------------------------------------


def agree(case_id, query, goal, variables, defects=()):
    """A rule called on trial 1 and the rules.pl goal that defines it

    ``query`` takes the trial id and the ids of ``weather_ids``; ``goal``
    is formatted with the same ids.
    """
    return pytest.param(
        query, goal, variables, defects, id=case_id, marks=defect_marks(defects)
    )


AGREE = [
    agree(
        "is_activation_id",
        lambda t, ids: is_activation_id(t, var("I")),
        "is_activation_id(T, I)",
        "I",
    ),
    agree(
        "activation_id",
        lambda t, ids: activation_id(t, var("A"), var("C")),
        "activation_id(T, A, C)",
        "A C",
    ),
    agree(
        "called_activation_id",
        lambda t, ids: called_activation_id(t, var("A"), var("C")),
        "called_activation_id(T, A, C)",
        "A C",
    ),
    agree(
        "evaluation_line_id",
        lambda t, ids: evaluation_line_id(t, var("I"), var("L")),
        "evaluation_line_id(T, I, L)",
        "I L",
    ),
    agree(
        "map_evaluation_lines_id-sorted",
        lambda t, ids: map_evaluation_lines_id(t, [ids.low, ids.high], var("L")),
        "map_evaluation_lines_id(T, [{low}, {high}], L)",
        "L",
    ),
    agree(
        "map_evaluation_lines_id-descending",
        lambda t, ids: map_evaluation_lines_id(t, [ids.high, ids.low], var("L")),
        "map_evaluation_lines_id(T, [{high}, {low}], L)",
        "L",
        (Defect(BAGOF_REASON, "0 solutions in the rule, 1 in the store"),),
    ),
    agree(
        "map_evaluation_lines_id-repeated",
        lambda t, ids: map_evaluation_lines_id(t, [ids.open, ids.open], var("L")),
        "map_evaluation_lines_id(T, [{open}, {open}], L)",
        "L",
        (Defect(BAGOF_REASON, "0 solutions in the rule, 1 in the store"),),
    ),
    agree(
        "map_evaluation_code_ids",
        lambda t, ids: map_evaluation_code_ids(
            t, [ids.open, ids.run_simulation, ids.script], var("C")
        ),
        "map_evaluation_code_ids(T, [{open}, {run_simulation}, {script}], C)",
        "C",
    ),
    agree(
        "filter_activation_ids",
        lambda t, ids: filter_activation_ids(
            t, [ids.open, ids.plain, ids.csv_read, ids.script], var("A")
        ),
        "filter_activation_ids(T, [{open}, {plain}, {csv_read}, {script}], A)",
        "A",
    ),
    agree(
        "filter_activation_ids-repeated",
        lambda t, ids: filter_activation_ids(t, repeated_ids(ids), var("A")),
        "filter_activation_ids(T, [{open}, {plain}, {csv_read}, {open}, {script}], A)",
        "A",
        # One list each side, the rule's without the repeat.
        (
            Defect(
                FILTER_REPEATS.reason,
                "1 solutions in the rule, 1 in the store\nonly in the rule (1)",
            ),
        ),
    ),
]


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
@pytest.mark.parametrize("query, goal, variables, defects", AGREE)
def test_activation_rules_agree_with_rules_pl(
    connected_two_trials, two_trial_prolog, query, goal, variables, defects
):
    """The rule and its rules.pl definition answer the same solutions on
    the first weather trial
    """
    ids = weather_ids(connected_two_trials)
    facts = two_trial_prolog[ids.trial]
    assert_agree(
        lambda: bindings(query(ids.trial, ids), *variables.split()),
        lambda: rules_pl(facts, ids.trial, goal.format(**vars(ids)), variables),
        defects,
    )
