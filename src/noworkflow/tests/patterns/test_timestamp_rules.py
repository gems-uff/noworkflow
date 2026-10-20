# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The timestamp rules, in Python and in rules.pl, against the store

``timestamp_id``, ``duration_id``, ``successor_id`` and their by-name
forms ``timestamp``, ``duration`` and ``successor`` exist as Python rules
(``patterns/rules/timestamp_rules.py``), run here in-process on
``connected_two_trials``, and as predicates of ``resources/rules.pl``, run
by ``swipl`` over the facts of ``now export prolog -r`` for the same trial
(``two_trial_prolog``). Both are compared, for each of the two trials,
with what SQL finds in the store's ``db.sqlite``, as multisets.

What the store holds: the trial's ``start`` and ``finish`` are absolute
timestamps; every other moment is a checkpoint in seconds since the trial
started (``activation.start_checkpoint``, ``evaluation.checkpoint``,
``file_access.checkpoint``); id 0 stands for the trial itself. The Python
rules answer the trial's moments as the datetimes SQLAlchemy reads, and
its duration as a timedelta; the export writes them as seconds since the
epoch, so the expected values on each side are converted from the same SQL
text. Code component names on the rules.pl side are spelled as the
export's own facts spell them (#103; ``test_id_name_rules.py`` checks that
they differ from the store's only for string literals), and access ids
(``f<id>``, #57) are mapped back.

The cases state the desired answers and carry the defects that break them
today: the Python rules still pass ``start=``, ``timestamp=`` and
``moment=`` to model rules whose attributes became ``start_checkpoint``
and ``checkpoint`` (timestamp-rules-stale-attributes), ``successor_id``
compares the trial's absolute times with relative checkpoints
(trial-timestamps-absolute), and every predicate of rules.pl that reaches
the trial calls ``trial/9``, while the export declares ``trial/12``
(#249). On a copy of the export with #249 fixed by hand (the three calls
rewritten to ``trial/12``), every rules.pl case answered as SQL does but
the successors of the trial's start, which had no solution at all: that
case carries both defects. In the same way, with the Python rules'
attribute names fixed by hand, every Python case of the stale attributes
answered as SQL does but the successors of an access, which lose their
before id after the first pair (rule-option-binding-lost): those two cases
carry both defects too. A
successor query never runs with both ids
unbound on evaluations (the square of their number in pairs, one query
each); the before-id is bound instead.
"""
import datetime

import pytest

from noworkflow.patterns import BLANK, rules, var
from noworkflow.tests.helpers import swipl
from noworkflow.tests.patterns.support import (
    Defect,
    assert_rows,
    bindings,
    defect_marks,
    normalize_prolog,
)

TRIALS = pytest.mark.parametrize("number", [1, 2], ids=["trial1", "trial2"])
NEEDS_SWIPL = pytest.mark.skipif(swipl.SWIPL is None,
                                 reason=swipl.SKIP_REASON)
EPOCH = datetime.datetime(1970, 1, 1)
# An evaluation in the middle of the script, so that the successor cases
# leave out the evaluations that end before it.
MIDDLE_EVALUATION = 150

STALE_ATTRIBUTES = Defect(
    "#345: timestamp_rules.py passes "
    "start=, timestamp= and moment= to the activation, access and "
    "evaluation model rules, whose attributes are start_checkpoint and "
    "checkpoint; ModelRule.__call__ maps an unknown keyword to the "
    "attribute BLANK, and the first row raises KeyError(BLANK)",
    "raises KeyError: _")
ABSOLUTE_REASON = (
    "#346: timestamp_id answers the trial's start "
    "and finish as absolute times (a datetime in Python, epoch seconds in "
    "the export), while every other moment is a checkpoint in seconds since "
    "the trial started, and successor_id compares the two")
ABSOLUTE_BEFORE = Defect(
    ABSOLUTE_REASON, "'<=' not supported between instances of "
    "'datetime.datetime' and 'float'")
ABSOLUTE_AFTER = Defect(
    ABSOLUTE_REASON, "'<=' not supported between instances of 'float' and "
    "'datetime.datetime'")
# Measured on a copy of the export with #249 fixed: no solution at all.
ABSOLUTE_PROLOG = Defect(ABSOLUTE_REASON, "0 solutions in the rule")
# Measured with the attribute names of timestamp-rules-stale-attributes
# fixed by hand: the successors of an access then show BeforeId BLANK
# (printed _) on 3 of the 6 pairs, and successor by name answers 12 pairs
# with repeats; removing the per-result reset of RuleQuery.apply_function
# on top made both answer as SQL does.
BEFORE_ID_REASON = (
    "#344: successor_id explores before_id, and "
    "when it is unbound the left side of the rule's join binds BeforeId "
    "once for several AfterIds; RuleQuery.apply_function resets it after "
    "the first, so the others answer BeforeId BLANK, and successor then "
    "names them after every access")
BEFORE_ID_LOST = Defect(BEFORE_ID_REASON, "(_, ")
BEFORE_NAME_LOST = Defect(BEFORE_ID_REASON, "repeats ")
STALE_ARITY = Defect(
    "#249: the timestamp rules of rules.pl reach the trial through "
    "trial/9, while the export declares trial/12",
    "Unknown procedure: trial/9")


class PythonSide:
    """The store's values as the Python rules answer them"""

    @staticmethod
    def name(code_id, name):
        return name

    @staticmethod
    def time(text):
        return datetime.datetime.fromisoformat(text)

    def duration(self, start, finish):
        return self.time(finish) - self.time(start)


class PrologSide:
    """The store's values as the export writes them

    A trial time is seconds since the epoch (``now export prolog``
    computes it from the naive datetime of the store), and a duration is
    the difference of two of them, computed in floats as ``is/2`` does.
    """

    def __init__(self, spellings):
        self.spellings = spellings

    def name(self, code_id, name):
        return self.spellings[code_id]

    @staticmethod
    def time(text):
        return (datetime.datetime.fromisoformat(text) - EPOCH).total_seconds()

    def duration(self, start, finish):
        return self.time(finish) - self.time(start)


PYTHON = PythonSide()


def trial_id(project, number):
    return project.trials()[number - 1]["id"]


def sql_rows(project, sql, *params):
    """The rows of a query as tuples (give columns distinct names)"""
    return [tuple(row.values()) for row in project.query(sql, *params)]


# --- what the store holds ----------------------------------------------------


def trial_times(project, trial):
    """The SQL text of the trial's start and finish"""
    row = project.query("SELECT start, finish FROM trial WHERE id = ?",
                        trial)[0]
    return row["start"], row["finish"]


def activation_starts(project, trial):
    return sql_rows(project, "SELECT id, start_checkpoint FROM activation "
                    "WHERE trial_id = ?", trial)


def evaluation_checkpoints(project, trial):
    return sql_rows(project, "SELECT id, checkpoint FROM evaluation "
                    "WHERE trial_id = ?", trial)


def access_checkpoints(project, trial):
    return sql_rows(project, "SELECT id, checkpoint FROM file_access "
                    "WHERE trial_id = ?", trial)


def moment_timestamps(moment):
    """(Id, Timestamp) of ``timestamp_id`` for a moment

    start and finish are the trial's (id 0) plus each activation's start
    or each evaluation's checkpoint, as the documentation of the rule says.
    """
    def expected(project, trial, side):
        start, finish = trial_times(project, trial)
        return {
            "start": lambda: [(0, side.time(start))]
            + activation_starts(project, trial),
            "finish": lambda: [(0, side.time(finish))]
            + evaluation_checkpoints(project, trial),
            "activation": lambda: activation_starts(project, trial),
            "evaluation": lambda: evaluation_checkpoints(project, trial),
            "access": lambda: access_checkpoints(project, trial),
        }[moment]()
    return expected


def trial_moment(moment):
    """(Timestamp) of the trial's start or finish"""
    def expected(project, trial, side):
        return [(side.time(trial_times(project, trial)[
            0 if moment == "start" else 1]),)]
    return expected


def activation_durations(project, trial):
    """(Id, Duration) of each activation that finished: the checkpoint of
    its evaluation minus its start
    """
    finishes = dict(evaluation_checkpoints(project, trial))
    return [(identifier, finishes[identifier] - start)
            for identifier, start in activation_starts(project, trial)
            if identifier in finishes]


def durations(project, trial, side):
    return [(0, side.duration(*trial_times(project, trial)))] + (
        activation_durations(project, trial))


def trial_duration(project, trial, side):
    return [(side.duration(*trial_times(project, trial)),)]


def one_empty_solution(project, trial, side):
    return [()]


def evaluations_after(project, trial, side):
    """(AfterId) of the evaluations that end at or after the middle one"""
    checkpoints = dict(evaluation_checkpoints(project, trial))
    before = checkpoints[MIDDLE_EVALUATION]
    return [(identifier,) for identifier, checkpoint in checkpoints.items()
            if before <= checkpoint]


def activations_after(project, trial, side):
    """(AfterId) of the activations whose evaluation ends at or after the
    middle evaluation
    """
    starts = dict(activation_starts(project, trial))
    return [(identifier,) for identifier, in evaluations_after(
        project, trial, side) if identifier in starts]


def access_pairs(project, trial, side):
    """(BeforeId, AfterId) of the accesses in checkpoint order"""
    accesses = access_checkpoints(project, trial)
    return [(before, after) for before, first in accesses
            for after, second in accesses if first <= second]


def evaluations_in_the_trial(project, trial, side):
    """(Id) of the evaluations after the trial started: checkpoints count
    seconds since the start
    """
    return sql_rows(project, "SELECT id FROM evaluation WHERE trial_id = ? "
                    "AND checkpoint >= 0", trial)


def evaluations_before_the_end(project, trial, side):
    """(Id) of the evaluations before the trial finished"""
    start, finish = trial_times(project, trial)
    seconds = (PythonSide.time(finish) - PythonSide.time(start)
               ).total_seconds()
    return [(identifier,) for identifier, checkpoint
            in evaluation_checkpoints(project, trial)
            if checkpoint <= seconds]


def evaluation_names(project, trial, side):
    """{evaluation id: name}, the name of its code component"""
    return {evaluation: side.name(code, name)
            for evaluation, code, name in sql_rows(
                project, "SELECT evaluation.id AS evaluation_id, "
                "code_component.id AS code_id, code_component.name "
                "FROM evaluation JOIN code_component "
                "ON code_component.trial_id = evaluation.trial_id "
                "AND code_component.id = evaluation.code_component_id "
                "WHERE evaluation.trial_id = ?", trial)}


def activation_names(project, trial):
    return dict(sql_rows(project, "SELECT id, name FROM activation "
                         "WHERE trial_id = ?", trial))


def access_names(project, trial):
    return dict(sql_rows(project, "SELECT id, name FROM file_access "
                         "WHERE trial_id = ?", trial))


def timestamps_by_name(moment):
    """(Name, Timestamp) of ``timestamp`` for a moment

    The trial is named ``trial``; start and finish name activations.
    """
    def expected(project, trial, side):
        start, finish = trial_times(project, trial)
        activations = activation_names(project, trial)
        if moment == "evaluation":
            names = evaluation_names(project, trial, side)
            return [(names[identifier], checkpoint) for identifier, checkpoint
                    in evaluation_checkpoints(project, trial)]
        if moment == "access":
            names = access_names(project, trial)
            return [(names[identifier], checkpoint) for identifier, checkpoint
                    in access_checkpoints(project, trial)]
        if moment == "activation":
            return [(activations[identifier], checkpoint)
                    for identifier, checkpoint
                    in activation_starts(project, trial)]
        if moment == "start":
            return [("trial", side.time(start))] + [
                (activations[identifier], checkpoint)
                for identifier, checkpoint
                in activation_starts(project, trial)]
        return [("trial", side.time(finish))] + [
            (activations[identifier], checkpoint)
            for identifier, checkpoint in evaluation_checkpoints(
                project, trial) if identifier in activations]
    return expected


def durations_by_name(project, trial, side):
    activations = activation_names(project, trial)
    return [("trial", side.duration(*trial_times(project, trial)))] + [
        (activations[identifier], duration)
        for identifier, duration in activation_durations(project, trial)]


def access_name_pairs(project, trial, side):
    names = access_names(project, trial)
    return [(names[before], names[after])
            for before, after in access_pairs(project, trial, side)]


# --- the Python rules --------------------------------------------------------


def rule_case(case_id, rule, names, expected, *defects):
    """``rule(trial, *variables)``, the variables named by ``names``"""
    return pytest.param(rule, names, expected, defects, id=case_id,
                        marks=defect_marks(defects))


RULE_CASES = [
    rule_case("timestamp_id-" + moment,
              lambda t, i, ts, moment=moment: rules.timestamp_id(
                  t, i, ts, moment), "Id Timestamp",
              moment_timestamps(moment), *defects)
    for moment, defects in (
        ("start", (STALE_ATTRIBUTES,)),
        ("finish", ()),
        ("activation", (STALE_ATTRIBUTES,)),
        ("evaluation", ()),
        ("access", (STALE_ATTRIBUTES,)),
    )
] + [
    rule_case("timestamp_id-trial-" + moment,
              lambda t, ts, moment=moment: rules.timestamp_id(
                  t, 0, ts, moment), "Timestamp", trial_moment(moment))
    for moment in ("start", "finish")
] + [
    rule_case("duration_id-trial", lambda t, d: rules.duration_id(t, 0, d),
              "Duration", trial_duration),
    rule_case("duration_id", rules.duration_id, "Id Duration", durations,
              STALE_ATTRIBUTES),
    rule_case("successor_id-start-finish", lambda t: rules.successor_id(
        t, "start", 0, "finish", 0), "", one_empty_solution),
    rule_case("successor_id-evaluation-evaluation",
              lambda t, a: rules.successor_id(
                  t, "evaluation", MIDDLE_EVALUATION, "evaluation", a),
              "AfterId", evaluations_after),
    rule_case("successor_id-evaluation-activation",
              lambda t, a: rules.successor_id(
                  t, "evaluation", MIDDLE_EVALUATION, "activation", a),
              "AfterId", activations_after),
    rule_case("successor_id-access-access", lambda t, b, a: rules.successor_id(
        t, "access", b, "access", a), "BeforeId AfterId", access_pairs,
        STALE_ATTRIBUTES, BEFORE_ID_LOST),
    rule_case("successor_id-trial-evaluation",
              lambda t, a: rules.successor_id(t, "trial", 0, "evaluation", a),
              "AfterId", evaluations_in_the_trial, ABSOLUTE_BEFORE),
    rule_case("successor_id-evaluation-trial",
              lambda t, b: rules.successor_id(t, "evaluation", b, "trial", 0),
              "BeforeId", evaluations_before_the_end, ABSOLUTE_AFTER),
] + [
    rule_case("timestamp-trial-" + moment,
              lambda t, ts, moment=moment: rules.timestamp(
                  t, "trial", ts, moment), "Timestamp", trial_moment(moment))
    for moment in ("start", "finish")
] + [
    rule_case("timestamp-by-name-" + moment,
              lambda t, n, ts, moment=moment: rules.timestamp(
                  t, n, ts, moment), "Name Timestamp",
              timestamps_by_name(moment), *defects)
    for moment, defects in (
        ("start", (STALE_ATTRIBUTES,)),
        ("finish", ()),
        ("activation", (STALE_ATTRIBUTES,)),
        ("evaluation", ()),
        ("access", (STALE_ATTRIBUTES,)),
    )
] + [
    rule_case("duration-trial", lambda t, d: rules.duration(t, "trial", d),
              "Duration", trial_duration),
    rule_case("duration-by-name", rules.duration, "Name Duration",
              durations_by_name, STALE_ATTRIBUTES),
    rule_case("successor-access", lambda t, b, a: rules.successor(
        t, "access", b, "access", a), "BeforeName AfterName",
        access_name_pairs, STALE_ATTRIBUTES, BEFORE_NAME_LOST),
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


STALE_CALLS = {
    "timestamp_id start": lambda t: rules.timestamp_id(
        t, var("Id"), var("Timestamp"), "start"),
    "timestamp_id activation": lambda t: rules.timestamp_id(
        t, var("Id"), var("Timestamp"), "activation"),
    "timestamp_id access": lambda t: rules.timestamp_id(
        t, var("Id"), var("Timestamp"), "access"),
    "duration_id": lambda t: rules.duration_id(t, var("Id"), var("Duration")),
    "duration": lambda t: rules.duration(t, var("Name"), var("Duration")),
    "successor_id access": lambda t: rules.successor_id(
        t, "access", var("BeforeId"), "access", var("AfterId")),
    "successor access": lambda t: rules.successor(
        t, "access", var("BeforeName"), "access", var("AfterName")),
    "timestamp access": lambda t: rules.timestamp(
        t, var("Name"), var("Timestamp"), "access"),
}


@TRIALS
@pytest.mark.parametrize("call", list(STALE_CALLS.values()),
                         ids=list(STALE_CALLS))
def test_timestamp_rules_raise_key_error_on_activations_and_accesses(
        connected_two_trials, number, call):
    """Every query that reaches an activation's start or an access's
    checkpoint raises KeyError(BLANK) on its first such row
    """
    trial = trial_id(connected_two_trials, number)
    with pytest.raises(KeyError) as caught:
        list(call(trial))
    assert caught.value.args == (BLANK,)


@TRIALS
def test_successor_between_the_trial_and_a_checkpoint_raises_type_error(
        connected_two_trials, number):
    """The trial's start and finish are datetimes and its duration a
    timedelta, while checkpoints are floats, so ``successor_id`` between
    the trial and an evaluation compares a datetime with a float
    """
    trial = trial_id(connected_two_trials, number)
    timestamp, duration = var("Timestamp Duration")
    starts = bindings(rules.timestamp_id(trial, 0, timestamp, "start"),
                      timestamp)
    assert [type(value) for value, in starts] == [datetime.datetime]
    durations = bindings(rules.duration_id(trial, 0, duration), duration)
    assert [type(value) for value, in durations] == [datetime.timedelta]
    message = "'<=' not supported between instances of {} and {}"
    for before in ("trial", "start"):
        with pytest.raises(TypeError, match=message.format(
                "'datetime.datetime'", "'float'")):
            list(rules.successor_id(trial, before, 0, "evaluation",
                                    var("AfterId")))
    for after in ("trial", "finish"):
        with pytest.raises(TypeError, match=message.format(
                "'float'", "'datetime.datetime'")):
            list(rules.successor_id(trial, "evaluation", var("BeforeId"),
                                    after, 0))


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


def prolog_case(case_id, goal, names, expected, *defects, ids=()):
    """``goal`` over the trial's facts, T bound to the trial id

    ``ids`` lists the columns that hold access ids, which
    ``normalize_prolog`` maps back to the store's.
    """
    return pytest.param(goal, names, ids, expected, defects, id=case_id,
                        marks=defect_marks(defects))


PROLOG_CASES = [
    prolog_case("timestamp_id-" + moment,
                "timestamp_id(T, Id, Timestamp, {})".format(moment),
                "Id Timestamp", moment_timestamps(moment), *defects, ids=(0,))
    for moment, defects in (
        ("start", (STALE_ARITY,)),
        ("finish", (STALE_ARITY,)),
        ("activation", ()),
        ("evaluation", ()),
        ("access", ()),
    )
] + [
    prolog_case("timestamp_id-trial-" + moment,
                "timestamp_id(T, 0, Timestamp, {})".format(moment),
                "Timestamp", trial_moment(moment), STALE_ARITY)
    for moment in ("start", "finish")
] + [
    prolog_case("duration_id-trial", "duration_id(T, 0, Duration)",
                "Duration", trial_duration, STALE_ARITY),
    prolog_case("duration_id", "duration_id(T, Id, Duration)",
                "Id Duration", durations, STALE_ARITY),
    prolog_case("successor_id-start-finish",
                "successor_id(T, start, 0, finish, 0)", "",
                one_empty_solution, STALE_ARITY),
    prolog_case("successor_id-evaluation-evaluation",
                "successor_id(T, evaluation, {}, evaluation, AfterId)".format(
                    MIDDLE_EVALUATION), "AfterId", evaluations_after),
    prolog_case("successor_id-evaluation-activation",
                "successor_id(T, evaluation, {}, activation, AfterId)".format(
                    MIDDLE_EVALUATION), "AfterId", activations_after),
    prolog_case("successor_id-access-access",
                "successor_id(T, access, BeforeId, access, AfterId)",
                "BeforeId AfterId", access_pairs, ids=(0, 1)),
    prolog_case("successor_id-trial-evaluation",
                "successor_id(T, trial, 0, evaluation, AfterId)", "AfterId",
                evaluations_in_the_trial, STALE_ARITY, ABSOLUTE_PROLOG),
    prolog_case("successor_id-evaluation-trial",
                "successor_id(T, evaluation, BeforeId, trial, 0)",
                "BeforeId", evaluations_before_the_end, STALE_ARITY),
] + [
    prolog_case("timestamp-trial-" + moment,
                "timestamp(T, trial, Timestamp, {})".format(moment),
                "Timestamp", trial_moment(moment), STALE_ARITY)
    for moment in ("start", "finish")
] + [
    prolog_case("timestamp-by-name-" + moment,
                "timestamp(T, Name, Timestamp, {})".format(moment),
                "Name Timestamp", timestamps_by_name(moment), *defects)
    for moment, defects in (
        ("start", (STALE_ARITY,)),
        ("finish", (STALE_ARITY,)),
        ("activation", ()),
        ("evaluation", ()),
        ("access", ()),
    )
] + [
    prolog_case("duration-trial", "duration(T, trial, Duration)",
                "Duration", trial_duration, STALE_ARITY),
    prolog_case("duration-by-name", "duration(T, Name, Duration)",
                "Name Duration", durations_by_name, STALE_ARITY),
    prolog_case("successor-access",
                "successor(T, access, BeforeName, access, AfterName)",
                "BeforeName AfterName", access_name_pairs),
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


STALE_GOALS = [
    "timestamp_id(T, Id, Timestamp, start)",
    "timestamp_id(T, Id, Timestamp, finish)",
    "duration_id(T, 0, Duration)",
    "successor_id(T, start, 0, finish, 0)",
    "successor_id(T, trial, 0, evaluation, AfterId)",
    "timestamp(T, trial, Timestamp, start)",
    "timestamp(T, Name, Timestamp, finish)",
    "duration(T, trial, Duration)",
]


@NEEDS_SWIPL
@pytest.mark.parametrize("goal", STALE_GOALS)
def test_rules_pl_timestamps_of_the_trial_call_a_stale_arity(
        two_trial_project, two_trial_prolog, goal):
    """A timestamp predicate that reaches the trial's start or finish
    raises an existence error for trial/9 before any solution: the runtime
    effect of #249 on the timestamp rules
    """
    trial = trial_id(two_trial_project, 1)
    found = swipl.solutions(
        two_trial_prolog[trial],
        "T = {}, {}".format(swipl.quoted_atom(trial), goal), [])
    assert found.rows == []
    assert "Unknown procedure: trial/9" in (found.error or "")
