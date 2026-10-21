# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The temporal inference rules: ``temporal_inference_rules.py`` and rules.pl

Two families of rules. The stack rules follow the callers of an evaluation
up to the script (``activation_stack_id``, ``indirect_activation_id``, the
stacks of the activations that accessed a file, and their forms by name);
the influence rules relate what started before something else finished
(``temporal_activation_influence_id``, and ``access_influence_id`` for a
file read before another was written). They run on the shared two-trial
weather store (``connected_two_trials``); what they should answer comes
from SQL on its ``db.sqlite``: each evaluation's ``activation_id`` followed
upward, and the checkpoints that rules.pl's ``successor_id`` compares (the
start of an activation, the checkpoint of an evaluation, which is when it
finished, and the checkpoint of an access). ``swipl`` runs the rules.pl
versions over ``now export prolog -r`` of the same trial; in those
comparisons rules.pl stands where the store stands in
``support.assert_rows``.

Today the stack rules answer nothing, in Python and in rules.pl: the store
records the caller of the root evaluations as 0, and both versions end a
stack only at a caller that is None (``nil``). The influence rules crash
with ``KeyError: _`` through ``timestamp_id``, and rules.pl's
``access_influence_id`` calls a predicate it never defines. Each mechanism
gets a characterization of today's answer and a ``_desired`` twin marked
``xfail(strict=True)`` through ``Defect``. Calls whose cost grows once the
stacks work (``indirect_activation`` with both names unbound took about 8 s
on a store with the root fixed) bind one side.
"""

import pytest

from noworkflow.patterns import var
from noworkflow.patterns.rules import (
    access_influence,
    access_influence_id,
    access_stack,
    access_stack_id,
    activation_stack,
    activation_stack_id,
    indirect_access,
    indirect_access_id,
    indirect_activation,
    indirect_activation_id,
    temporal_activation_influence,
    temporal_activation_influence_id,
)
from noworkflow.tests.helpers import swipl
from noworkflow.tests.patterns.support import (
    Defect,
    assert_rows,
    bindings,
    defect_marks,
    differences,
    expect_known_failure,
    known_defects,
    normalize_prolog,
    outcome,
)

ROOT_CALLER_ZERO = Defect(
    "#342: the store records the caller "
    "of the root evaluations as 0 (EvaluationLW, "
    "persistence/lightweight/evaluation.py), while activation_stack_id "
    "(patterns/rules/temporal_inference_rules.py) ends a stack only at a "
    "caller that is None, and rules.pl only at nil: no stack reaches its "
    "base case, and every rule built on it (indirect_activation_id, "
    "access_stack_id, indirect_access_id and their forms by name) answers "
    "nothing",
    signature="found nothing; root caller 0",
)
STALE_ATTRIBUTES_REASON = (
    "#345: timestamp_id "
    "(patterns/rules/timestamp_rules.py) asks for activation(start=...) "
    "and access(timestamp=...), attributes the models call "
    "start_checkpoint and checkpoint; ModelRule maps an unknown keyword to "
    "BLANK, and ModelQuery.get_bound raises KeyError(BLANK), whose text is "
    "'_', so every successor_id on an activation or an access crashes"
)
STALE_ATTRIBUTES = Defect(STALE_ATTRIBUTES_REASON, signature="KeyError: _")
BLANK_OPTION_REASON = (
    "#348: RuleQuery.prepare_values "
    "(patterns/machinery.py) rejects a variable bound by an earlier join "
    "when it differs from the option, and BLANK, the option "
    "set_options_in_rule gives successor_id's before_id and after_id, "
    "differs from every value, so successor_id joined after the accesses "
    "answers nothing and access_influence_id with unbound ids is empty "
    "before timestamp_id runs"
)
BLANK_OPTION = Defect(
    BLANK_OPTION_REASON, signature="access_influence_id(T, A, B) -> []"
)
UNDEFINED_REASON = (
    "#351: rules.pl's "
    "access_influence_id calls activation_influence_id/3, which rules.pl "
    "never defines (the rule became temporal_activation_influence_id), so "
    "access_influence_id and access_influence raise existence_error"
)
UNDEFINED = Defect(
    UNDEFINED_REASON, signature="existence_error(procedure,activation_influence_id/3)"
)

# An activation may influence one that finishes after it starts: rules.pl's
# successor_id(T, activation, A, activation, B) compares A's start with the
# checkpoint of B's evaluation.
TEMPORAL = (
    "SELECT a.id AS influencer, b.id AS influenced FROM activation a "
    "JOIN activation b ON b.trial_id = a.trial_id "
    "JOIN evaluation eb ON eb.trial_id = b.trial_id AND eb.id = b.id "
    "WHERE a.trial_id = ? AND a.start_checkpoint <= eb.checkpoint"
)
# A read access may influence a written one when it came first and the
# activation that read started before the one that wrote finished.
ACCESS_INFLUENCE = (
    "SELECT r.id AS influencer, r.mode AS read, w.id AS influenced, "
    "w.mode AS written FROM file_access r "
    "JOIN file_access w ON w.trial_id = r.trial_id "
    "JOIN activation ra ON ra.trial_id = r.trial_id "
    "AND ra.id = r.activation_id "
    "JOIN evaluation we ON we.trial_id = w.trial_id "
    "AND we.id = w.activation_id "
    "WHERE r.trial_id = ? AND r.checkpoint <= w.checkpoint "
    "AND ra.start_checkpoint <= we.checkpoint"
)


class Weather:
    """What the store says of the first weather trial, from SQL"""

    def __init__(self, project):
        trial = project.trials()[0]
        self.project = project
        self.trial = trial["id"]
        query = self.query
        self.callers = {
            row["id"]: row["activation_id"]
            for row in query(
                "SELECT id, activation_id FROM evaluation WHERE trial_id = ?"
            )
        }
        self.names = {
            row["id"]: row["name"]
            for row in query("SELECT id, name FROM activation WHERE trial_id = ?")
        }
        self.accesses = query(
            "SELECT id, name, mode, activation_id FROM file_access "
            "WHERE trial_id = ? ORDER BY id"
        )
        self.access_names = {access["id"]: access["name"] for access in self.accesses}
        self.script = query(
            "SELECT id FROM evaluation WHERE trial_id = ? AND code_component_id = ?",
            trial["main_id"],
        )[0]["id"]
        self.root_caller = self.callers[self.script]
        self.data1 = [
            access for access in self.accesses if access["name"] == "data1.dat"
        ]
        self.output = [
            access for access in self.accesses if access["name"] == "output.csv"
        ]
        self.open = self.data1[0]["activation_id"]
        self.csv_read = query(
            "SELECT id FROM activation WHERE trial_id = ? "
            "AND name = 'csv_read' ORDER BY start_checkpoint"
        )[0]["id"]
        # rules.pl's activation_stack: the activations named open and the
        # evaluations whose code component is named open.
        self.called_open = [
            row["id"]
            for row in query(
                "SELECT id FROM activation WHERE trial_id = ? AND name = 'open'"
            )
        ] + [
            row["id"]
            for row in query(
                "SELECT e.id FROM evaluation e JOIN code_component c "
                "ON c.trial_id = e.trial_id AND c.id = e.code_component_id "
                "WHERE e.trial_id = ? AND c.name = 'open'"
            )
        ]

    def query(self, sql, *params):
        return self.project.query(sql, self.trial, *params)

    def stack(self, evaluation):
        """The activations above an evaluation, the nearest first, up to
        the last caller that is an evaluation of the trial
        """
        stack = []
        caller = self.callers[evaluation]
        while caller in self.callers:
            stack.append(caller)
            caller = self.callers[caller]
        return tuple(stack)

    def access_stack(self, access):
        """The activation that made an access, then its stack"""
        return (access["activation_id"],) + self.stack(access["activation_id"])

    def named(self, ids):
        return tuple(self.names[i] for i in ids)

    def ids(self):
        """The ids that rules.pl goals are formatted with"""
        return {"open": self.open, "csv_read": self.csv_read}


def open_semantics(directory, open_mode):
    """``(readable, writable)`` of a file Python's own ``open()`` opens"""
    path = directory / "mode-{}".format(len(list(directory.iterdir())))
    if "r" in open_mode:
        path.write_bytes(b"")
    with open(path, open_mode) as handle:
        return handle.readable(), handle.writable()


def access_influences(weather, directory):
    """The (read, written) access pairs that may influence, from SQL"""
    pairs = []
    for row in weather.query(ACCESS_INFLUENCE):
        if (
            open_semantics(directory, row["read"])[0]
            and open_semantics(directory, row["written"])[1]
        ):
            pairs.append((row["influencer"], row["influenced"]))
    return pairs


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


def test_the_weather_trial_has_the_structure_the_rules_rely_on(connected_two_trials):
    """The open of data1.dat runs inside the first csv_read, which runs
    inside run_simulation: the shape the expected stacks assume
    """
    weather = Weather(connected_two_trials)
    names = [weather.names.get(caller) for caller in weather.stack(weather.open)]
    assert names == ["csv_read", "run_simulation", "__main__"]
    assert weather.stack(weather.open)[0] == weather.csv_read
    assert [access["name"] for access in weather.accesses] == [
        "data1.dat",
        "data2.dat",
        "output.csv",
    ]


# --- the stacks -------------------------------------------------------------

# Each case: the rule called on the first trial, the variables it binds,
# the rows SQL expects, and the rules.pl goal formatted with Weather.ids.
STACKS = {
    "activation_stack_id-open": (
        lambda w: activation_stack_id(w.trial, w.open, var("S")),
        "S",
        lambda w: [(w.stack(w.open),)],
        "activation_stack_id(T, {open}, S)",
    ),
    "activation_stack_id-unbound": (
        lambda w: activation_stack_id(w.trial, var("C"), var("S")),
        "C S",
        lambda w: [(evaluation, w.stack(evaluation)) for evaluation in w.callers],
        "activation_stack_id(T, C, S)",
    ),
    "indirect_activation_id-open": (
        lambda w: indirect_activation_id(w.trial, var("A"), w.open),
        "A",
        lambda w: [(caller,) for caller in w.stack(w.open)],
        "indirect_activation_id(T, A, {open})",
    ),
    "access_stack_id": (
        lambda w: access_stack_id(w.trial, var("F"), var("S")),
        "F S",
        lambda w: [(access["id"], w.access_stack(access)) for access in w.accesses],
        "access_stack_id(T, F, S)",
    ),
    "indirect_access_id": (
        lambda w: indirect_access_id(w.trial, var("A"), var("F")),
        "A F",
        lambda w: [
            (caller, access["id"])
            for access in w.accesses
            for caller in w.access_stack(access)
        ],
        "indirect_access_id(T, A, F)",
    ),
    "activation_stack-open": (
        lambda w: activation_stack(w.trial, "open", var("S")),
        "S",
        lambda w: [(w.named(w.stack(called)),) for called in w.called_open],
        "activation_stack(T, open, S)",
    ),
    "indirect_activation-open": (
        lambda w: indirect_activation(w.trial, var("A"), "open"),
        "A",
        lambda w: [
            (w.names[caller],) for called in w.called_open for caller in w.stack(called)
        ],
        "indirect_activation(T, A, open)",
    ),
    "access_stack-data1": (
        lambda w: access_stack(w.trial, "data1.dat", var("S")),
        "S",
        lambda w: [(w.named(w.access_stack(access)),) for access in w.data1],
        "access_stack(T, 'data1.dat', S)",
    ),
    "indirect_access-data1": (
        lambda w: indirect_access(w.trial, var("A"), "data1.dat"),
        "A",
        lambda w: [
            (w.names[caller],)
            for access in w.data1
            for caller in w.access_stack(access)
        ],
        "indirect_access(T, A, 'data1.dat')",
    ),
}


@pytest.mark.parametrize("case", list(STACKS))
def test_stack_rules_from_a_call_up_to_the_script(connected_two_trials, case):
    """Each stack rule answers nothing, while the store records 0 as the
    caller of the script's evaluation

    Characterization of root-caller-zero-ends-no-stack.
    """
    query, variables, _, _ = STACKS[case]
    weather = Weather(connected_two_trials)
    assert weather.root_caller == 0
    assert bindings(query(weather), *variables.split()) == []


@pytest.mark.parametrize("case", list(STACKS))
@known_defects(ROOT_CALLER_ZERO)
def test_stack_rules_from_a_call_up_to_the_script_desired(connected_two_trials, case):
    """Each stack rule follows the callers of an evaluation up to the
    script: the open of data1.dat was called by csv_read, run_simulation
    and the script
    """
    query, variables, expected_rows, _ = STACKS[case]
    weather = Weather(connected_two_trials)
    expected = expected_rows(weather)
    assert expected
    actual = outcome(lambda: bindings(query(weather), *variables.split()))
    if actual == []:
        message = "{} found nothing; root caller {!r}".format(case, weather.root_caller)
    elif isinstance(actual, str):
        message = "raises " + actual
    else:
        message = differences(actual, expected)
    assert not message, message


# --- temporal_activation_influence_id, access_influence_id ------------------

# Each case: the rule called on the first trial, the variables it binds and
# the rows SQL expects; the influence rules take a directory for open().
INFLUENCES = {
    "temporal_activation_influence_id-influencer": (
        lambda w: temporal_activation_influence_id(w.trial, w.csv_read, var("B")),
        "B",
        lambda w, _: [
            (row["influenced"],)
            for row in w.query(TEMPORAL)
            if row["influencer"] == w.csv_read
        ],
    ),
    "temporal_activation_influence_id-influenced": (
        lambda w: temporal_activation_influence_id(w.trial, var("A"), w.csv_read),
        "A",
        lambda w, _: [
            (row["influencer"],)
            for row in w.query(TEMPORAL)
            if row["influenced"] == w.csv_read
        ],
    ),
    "temporal_activation_influence-csv_read": (
        lambda w: temporal_activation_influence(w.trial, "csv_read", var("B")),
        "B",
        lambda w, _: [
            (w.names[row["influenced"]],)
            for row in w.query(TEMPORAL)
            if w.names[row["influencer"]] == "csv_read"
        ],
    ),
    "access_influence_id-bound": (
        lambda w: access_influence_id(w.trial, w.data1[0]["id"], w.output[0]["id"]),
        "",
        lambda w, directory: [
            ()
            for pair in access_influences(w, directory)
            if pair == (w.data1[0]["id"], w.output[0]["id"])
        ],
    ),
    "access_influence-unbound": (
        lambda w: access_influence(w.trial, var("A"), var("B")),
        "A B",
        lambda w, directory: [
            tuple(w.access_names[i] for i in pair)
            for pair in access_influences(w, directory)
        ],
    ),
}


@pytest.mark.parametrize("case", list(INFLUENCES))
def test_influence_rules_of_the_weather_trial(connected_two_trials, case):
    """Each influence rule whose query reaches timestamp_id on an
    activation or an access raises KeyError: _

    Characterization of timestamp-rules-stale-attributes.
    """
    query, variables, _ = INFLUENCES[case]
    weather = Weather(connected_two_trials)
    assert outcome(lambda: bindings(query(weather), *variables.split())) == (
        "KeyError: _"
    )


@pytest.mark.parametrize("case", list(INFLUENCES))
@known_defects(STALE_ATTRIBUTES)
def test_influence_rules_of_the_weather_trial_desired(
    connected_two_trials, tmp_path, case
):
    """Each influence rule answers what started before the other finished:
    csv_read influences the 54 activations that end after it starts, and
    both inputs influence output.csv
    """
    query, variables, expected_rows = INFLUENCES[case]
    weather = Weather(connected_two_trials)
    expected = expected_rows(weather, tmp_path)
    assert expected
    assert_rows(lambda: bindings(query(weather), *variables.split()), expected)


def test_access_influence_id_with_unbound_ids(connected_two_trials, tmp_path):
    """access_influence_id with both ids unbound answers nothing, without
    reaching timestamp_id, while the trial read both inputs before writing
    its output

    Characterization of blank-option-rejects-bound-variable.
    """
    weather = Weather(connected_two_trials)
    assert len(access_influences(weather, tmp_path)) == 2
    assert (
        bindings(access_influence_id(weather.trial, var("A"), var("B")), "A", "B") == []
    )


@known_defects(BLANK_OPTION, STALE_ATTRIBUTES)
def test_access_influence_id_with_unbound_ids_desired(connected_two_trials, tmp_path):
    """access_influence_id with both ids unbound answers each read access
    that may have influenced a written one: both inputs, the output
    """
    weather = Weather(connected_two_trials)
    expected = access_influences(weather, tmp_path)
    actual = bindings(access_influence_id(weather.trial, var("A"), var("B")), "A", "B")
    if actual == []:
        raise AssertionError(
            "access_influence_id(T, A, B) -> [] while the store has {} "
            "read-then-write pairs".format(len(expected))
        )
    assert_rows(lambda: actual, expected)


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
@pytest.mark.parametrize(
    "goal", ["access_influence_id(T, A, B)", "access_influence(T, A, B)"]
)
def test_access_influence_in_rules_pl(two_trial_project, two_trial_prolog, goal):
    """rules.pl's access_influence_id, and access_influence through it,
    raise existence_error for activation_influence_id/3

    Characterization of rules-pl-access-influence-undefined.
    """
    weather = Weather(two_trial_project)
    found = swipl.solutions(
        two_trial_prolog[weather.trial],
        "T = {}, {}".format(swipl.quoted_atom(weather.trial), goal),
        "A B",
    )
    assert found.rows == []
    assert found.error.startswith(
        "error(existence_error(procedure,activation_influence_id/3),"
    )


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
@known_defects(UNDEFINED)
def test_access_influence_in_rules_pl_desired(
    two_trial_project, two_trial_prolog, tmp_path
):
    """rules.pl's access_influence_id answers each read access that may
    have influenced a written one, and access_influence their names
    """
    weather = Weather(two_trial_project)
    facts = two_trial_prolog[weather.trial]
    expected = access_influences(weather, tmp_path)
    assert_rows(
        lambda: rules_pl(facts, weather.trial, "access_influence_id(T, A, B)", "A B"),
        expected,
    )
    assert_rows(
        lambda: rules_pl(facts, weather.trial, "access_influence(T, A, B)", "A B"),
        [
            (weather.access_names[read], weather.access_names[written])
            for read, written in expected
        ],
    )


# --- rules.pl ---------------------------------------------------------------


def agree(case_id, query, variables, goal, defects=()):
    """A rule called on trial 1 and the rules.pl goal that defines it"""
    return pytest.param(
        query, variables, goal, defects, id=case_id, marks=defect_marks(defects)
    )


# Today both sides of the stack cases are empty; a fix on one side only
# turns them red.
AGREE = [
    agree(case, query, variables, goal)
    for case, (query, variables, _, goal) in STACKS.items()
] + [
    agree(
        "temporal_activation_influence_id-influencer",
        INFLUENCES["temporal_activation_influence_id-influencer"][0],
        "B",
        "temporal_activation_influence_id(T, {csv_read}, B)",
        (STALE_ATTRIBUTES,),
    ),
    agree(
        "temporal_activation_influence_id-influenced",
        INFLUENCES["temporal_activation_influence_id-influenced"][0],
        "A",
        "temporal_activation_influence_id(T, A, {csv_read})",
        (STALE_ATTRIBUTES,),
    ),
    agree(
        "temporal_activation_influence-csv_read",
        INFLUENCES["temporal_activation_influence-csv_read"][0],
        "B",
        "temporal_activation_influence(T, csv_read, B)",
        (STALE_ATTRIBUTES,),
    ),
    agree(
        "access_influence_id-unbound",
        lambda w: access_influence_id(w.trial, var("A"), var("B")),
        "A B",
        "access_influence_id(T, A, B)",
        (
            UNDEFINED,
            Defect(BLANK_OPTION_REASON, "0 solutions in the rule, 2 in the store"),
            STALE_ATTRIBUTES,
        ),
    ),
    agree(
        "access_influence-unbound",
        INFLUENCES["access_influence-unbound"][0],
        "A B",
        "access_influence(T, A, B)",
        (UNDEFINED, STALE_ATTRIBUTES),
    ),
]


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
@pytest.mark.parametrize("query, variables, goal, defects", AGREE)
def test_temporal_rules_agree_with_rules_pl(
    connected_two_trials, two_trial_prolog, query, variables, goal, defects
):
    """The rule and its rules.pl definition answer the same solutions on
    the first weather trial
    """
    weather = Weather(connected_two_trials)
    facts = two_trial_prolog[weather.trial]
    assert_agree(
        lambda: bindings(query(weather), *variables.split()),
        lambda: rules_pl(facts, weather.trial, goal.format(**weather.ids()), variables),
        defects,
    )
