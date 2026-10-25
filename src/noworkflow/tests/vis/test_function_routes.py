# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The routes of ``now vis`` behind the function diff and the dataflow dialog

- ``/getFunctionActivations/<trial_id>``: every activation of a trial with
  its arguments, which fills the selects of the function diff dialog
  (``nowvis/src/graph/history_graph.ts``);
- ``/diff/getFunctionActivationArguments/<trial_id>/<function_id>``: the
  arguments of one activation (``trial/src/graph.ts``);
- ``/dataflow/evaluations/<trial_id>``: the evaluations the dataflow dialog
  offers;
- ``/commands/diff/<trial1>/<activation1>/<trial2>/<activation2>``: the
  function diff. Unlike the other ``/commands/*`` routes it starts no
  process: it calls ``cmd_diff.Diff.get_diff_function_info`` and
  ``build_variables_lcs`` in the server, which the ``commands`` recorder
  checks.

Expected values come from the store's tables: the arguments are the
evaluations an ``argument`` dependency points to, the variables the
evaluations inside the activation, the file accesses those whose
activation is the compared one or below it (until #361 only the accesses
of the compared activation itself, an ``open()`` call). In the two-trial
store the second trial changes the last row of data2.dat, so the values
read from it and the accesses of data2.dat and output.csv differ; a store
of its own, whose second trial reads data3.dat instead of data2.dat, gives
the diff an added and a removed access, and so do the two calls of
``csv_read`` in one trial.

Known defect, with a characterization and a ``_desired`` twin:
``EXPERIMENT_PREFIX`` (``/experiments/<code>/getFunctionActivations``).
The route prints nothing on the server's stdout: until #204 it printed a
debug line per replaced access (#248). A non-integer activation id and an activation the trial does not have raise
(characterized only: the frontend builds both from the store). Measured on
macOS with Python 3.11 to 3.15: none of it depends on the version.
"""

import re
from datetime import datetime, timedelta

import pytest
from werkzeug.http import http_date

from noworkflow.tests.e2e.harness import WEATHER_ARGS, WEATHER_DATA2_TRIAL2

from .support import EXPERIMENT_PREFIX, known_defects

DIFF_KEYS = {
    "output_function_trial1",
    "output_function_trial2",
    "arguments_function_trial1",
    "arguments_function_trial2",
    "duration_function_trial1",
    "duration_function_trial2",
    "variables_function_trial1",
    "variables_function_trial2",
    "file_accesses_added",
    "file_accesses_removed",
    "file_accesses_replaced",
    "trial1_variables_that_changed",
    "trial2_variables_added",
    "trial1_variables_removed",
}
ACCESS_KEYS = {
    "name",
    "mode",
    "buffering",
    "content_hash_before",
    "content_hash_after",
    "timestamp",
    "stack",
}
REPLACED_KEYS = {
    "name",
    "content_hash_before_first_trial",
    "content_hash_before_second_trial",
    "content_hash_after_first_trial",
    "content_hash_after_second_trial",
    "timestamp_first_trial",
    "timestamp_second_trial",
    "checkpoint_first_trial",
    "checkpoint_second_trial",
}
# A line of an entry of trial1_variables_that_changed: difflib's "- " or
# "+ " and the str() of the variable's dict.
CHANGED_LINE = re.compile(r"^([-+]) \{'evaluation_id': (\d+),", re.M)


def one(rows, what):
    """The single row of a query"""
    assert len(rows) == 1, "{}: {} rows".format(what, len(rows))
    return rows[0]


def activation_name(project, trial_id, activation_id):
    return one(
        project.query(
            "SELECT name FROM activation WHERE trial_id = ? AND id = ?",
            trial_id,
            activation_id,
        ),
        "activation",
    )["name"]


def caller(project, trial_id, activation_id):
    """The activation where an activation was evaluated (0 at the top)"""
    return one(
        project.query(
            "SELECT activation_id FROM evaluation WHERE trial_id = ? AND id = ?",
            trial_id,
            activation_id,
        ),
        "evaluation",
    )["activation_id"]


def chain(project, trial_id, activation_id):
    """The activation ids from ``activation_id`` up to the script's"""
    ids = []
    while activation_id:
        ids.append(activation_id)
        activation_id = caller(project, trial_id, activation_id)
    return ids


def activation_reading(project, trial_id, function, name="data2.dat"):
    """The activation of ``function`` on the stack that opened ``name``"""
    access = one(
        project.query(
            "SELECT activation_id FROM file_access WHERE trial_id = ? AND name = ?",
            trial_id,
            name,
        ),
        name,
    )
    for activation_id in chain(project, trial_id, access["activation_id"]):
        if activation_name(project, trial_id, activation_id) == function:
            return activation_id
    raise AssertionError("no {} on the stack that opened {}".format(function, name))


def arguments(project, trial_id, activation_id):
    """The reprs of the activation's arguments, in dependency order"""
    return [
        row["repr"]
        for row in project.query(
            "SELECT evaluation.repr FROM dependency JOIN evaluation "
            "ON evaluation.trial_id = dependency.trial_id "
            "AND evaluation.id = dependency.dependency_id "
            "WHERE dependency.trial_id = ? AND dependency.dependent_id = ? "
            "AND dependency.type = 'argument' ORDER BY dependency.id",
            trial_id,
            activation_id,
        )
    ]


def variables(project, trial_id, activation_id):
    """``{evaluation id: variable}`` of the evaluations inside an
    activation, with the keys the function diff gives them
    """
    rows = project.query(
        "SELECT evaluation.id AS evaluation_id, code_component.name, "
        "evaluation.repr AS value, code_component.type, "
        "code_component.first_char_line AS code_line, "
        "code_component.first_char_column AS code_column "
        "FROM evaluation JOIN code_component "
        "ON code_component.trial_id = evaluation.trial_id "
        "AND code_component.id = evaluation.code_component_id "
        "WHERE evaluation.trial_id = ? AND evaluation.activation_id = ?",
        trial_id,
        activation_id,
    )
    return {row["evaluation_id"]: row for row in rows}


def duration(project, trial_id, activation_id):
    """Microseconds from the activation's start to its evaluation"""
    row = one(
        project.query(
            "SELECT evaluation.checkpoint - activation.start_checkpoint AS d "
            "FROM activation JOIN evaluation "
            "ON evaluation.trial_id = activation.trial_id "
            "AND evaluation.id = activation.id "
            "WHERE activation.trial_id = ? AND activation.id = ?",
            trial_id,
            activation_id,
        ),
        "duration",
    )
    return row["d"] * 1000000


def output(project, trial_id, activation_id):
    return one(
        project.query(
            "SELECT repr FROM evaluation WHERE trial_id = ? AND id = ?",
            trial_id,
            activation_id,
        ),
        "output",
    )["repr"]


def accesses_under(project, trial_id, activation_id):
    """``{name: row}`` of the accesses made by an activation or below it"""
    result = {}
    for row in project.query(
        "SELECT file_access.*, trial.start FROM file_access "
        "JOIN trial ON trial.id = file_access.trial_id "
        "WHERE file_access.trial_id = ?",
        trial_id,
    ):
        if activation_id in chain(project, trial_id, row["activation_id"]):
            result[row["name"]] = row
    return result


def timestamp(access):
    """The JSON of ``FileAccess.timestamp``: trial start plus checkpoint

    Today's form: the naive local time as an HTTP date, labeled GMT
    (``LOCAL_TIME_AS_GMT`` in ``support.py``, whose twins are in
    ``test_diff_routes.py`` and ``test_trial_routes.py``).
    """
    start = datetime.fromisoformat(access["start"])
    return http_date(start + timedelta(seconds=access["checkpoint"]))


def stack(project, access):
    """``FileAccess.stack``: the names from below the script's activation
    down to the access's
    """
    ids = chain(project, access["trial_id"], access["activation_id"])[:-1]
    return " -> ".join(
        activation_name(project, access["trial_id"], activation_id)
        for activation_id in reversed(ids)
    )


def function_diff(vis, pair, prefixed=False):
    """The JSON of the function diff of ``pair``: two (trial, activation)"""
    (trial1, activation1), (trial2, activation2) = pair
    route = "commands/diff/{}/{}/{}/{}".format(trial1, activation1, trial2, activation2)
    return vis.json(vis.routes(route)[prefixed])


def pair_of(vis, function, name="data2.dat"):
    """``((trial1, activation), (trial2, activation))`` of ``function``
    on the stack that read ``name`` in each trial
    """
    return tuple(
        (trial_id, activation_reading(vis.project, trial_id, function, name))
        for trial_id in vis.trial_ids
    )


def build_renamed_input(project):
    """Weather twice, the second trial reading data3.dat for data2.dat"""
    project.copy_corpus("weather")
    project.run(*WEATHER_ARGS)
    project.write("data3.dat", WEATHER_DATA2_TRIAL2)
    project.run(*WEATHER_ARGS[:-1], "data3.dat")
    return project


# --- getFunctionActivations and its arguments --------------------------------


def test_function_activations_list_every_activation_with_arguments(vis):
    """Each activation of the trial comes with its id, its name and the
    reprs of its arguments; ``params`` is ``""`` for an activation without
    arguments
    """
    for trial_id in vis.trial_ids:
        answer = vis.json("/getFunctionActivations/" + trial_id)
        assert set(answer) == {"function_activations"}
        listed = {item["id"]: item for item in answer["function_activations"]}
        rows = vis.project.query(
            "SELECT id, name FROM activation WHERE trial_id = ?", trial_id
        )
        assert sorted(listed) == sorted(row["id"] for row in rows), (
            "the activation ids differ from the store"
        )
        without_arguments = 0
        for row in rows:
            item = listed[row["id"]]
            assert set(item) == {"id", "name", "params"}
            assert item["name"] == row["name"], row["id"]
            expected = arguments(vis.project, trial_id, row["id"])
            if not expected:
                without_arguments += 1
                assert item["params"] == "", row["name"]
            else:
                assert sorted(item["params"]) == sorted(expected), row["name"]
        assert without_arguments, "every activation has arguments"


def test_function_activation_arguments_answer_each_activation(vis):
    """The arguments route answers the reprs of an activation's arguments,
    or the text "This function has no params", at the root and under an
    experiment
    """
    trial_id = vis.trial_ids[0]
    for row in vis.project.query(
        "SELECT id, name FROM activation WHERE trial_id = ?", trial_id
    ):
        route = "diff/getFunctionActivationArguments/{}/{}".format(trial_id, row["id"])
        plain, prefixed = vis.routes(route)
        answer = vis.json(plain)
        assert vis.json(prefixed) == answer, row["name"]
        expected = arguments(vis.project, trial_id, row["id"])
        if expected:
            assert sorted(answer["function_params"]) == sorted(expected), row["name"]
        else:
            assert answer == {"function_params": "This function has no params"}, row[
                "name"
            ]


def test_function_activation_arguments_keep_the_call_order(vis):
    """``run_simulation(data_a, data_b, scale)`` lists its arguments in
    the order they appear in the call (the route has no ORDER BY: SQLite
    returns the dependencies by id)
    """
    for trial_id in vis.trial_ids:
        activation_id = activation_reading(vis.project, trial_id, "run_simulation")
        answer = vis.json(
            "/diff/getFunctionActivationArguments/{}/{}".format(trial_id, activation_id)
        )
        expected = [
            row["repr"]
            for row in vis.project.query(
                "SELECT evaluation.repr FROM dependency JOIN evaluation "
                "ON evaluation.trial_id = dependency.trial_id "
                "AND evaluation.id = dependency.dependency_id "
                "JOIN code_component "
                "ON code_component.trial_id = evaluation.trial_id "
                "AND code_component.id = evaluation.code_component_id "
                "WHERE dependency.trial_id = ? AND dependency.dependent_id = ? "
                "AND dependency.type = 'argument' ORDER BY "
                "code_component.first_char_line, code_component.first_char_column",
                trial_id,
                activation_id,
            )
        ]
        assert len(expected) == 3, "run_simulation takes three arguments"
        assert answer["function_params"] == expected


def test_function_activation_arguments_of_a_non_integer_id(vis):
    """A function id that is not an integer raises ``ValueError``"""
    with pytest.raises(ValueError, match="invalid literal for int"):
        vis.get("/diff/getFunctionActivationArguments/{}/main".format(vis.trial_ids[0]))


def test_function_activations_under_an_experiment_raise_type_error(vis):
    """Today ``/experiments/<code>/getFunctionActivations/<id>`` raises
    ``TypeError`` (the frontend builds the absolute form)
    """
    _, prefixed = vis.routes("getFunctionActivations/" + vis.trial_ids[0])
    with pytest.raises(TypeError, match="unexpected keyword argument 'expCode'"):
        vis.get(prefixed)


@known_defects(EXPERIMENT_PREFIX)
def test_function_activations_under_an_experiment_desired(vis):
    """Under an experiment, the activations are the same"""
    plain, prefixed = vis.routes("getFunctionActivations/" + vis.trial_ids[0])
    assert vis.json(prefixed) == vis.json(plain)


# --- /dataflow/evaluations ---------------------------------------------------


def test_dataflow_evaluations_list_every_evaluation(vis):
    """Each evaluation of the trial comes with its id, its code
    component's name and the line where it starts
    """
    for trial_id in vis.trial_ids:
        answer = vis.json("/dataflow/evaluations/" + trial_id)
        assert set(answer) == {"evaluations"}
        listed = sorted(
            (item["evaluation_id"], item["name"], item["first_char_line"])
            for item in answer["evaluations"]
        )
        rows = vis.project.query(
            "SELECT evaluation.id, code_component.name, "
            "code_component.first_char_line FROM evaluation "
            "JOIN code_component "
            "ON code_component.trial_id = evaluation.trial_id "
            "AND code_component.id = evaluation.code_component_id "
            "WHERE evaluation.trial_id = ?",
            trial_id,
        )
        expected = sorted(
            (row["id"], row["name"], row["first_char_line"]) for row in rows
        )
        assert expected, "the trial has no evaluation"
        assert listed == expected


@pytest.mark.parametrize(
    "route",
    [
        "getFunctionActivations/{}",
        "dataflow/evaluations/{}",
    ],
)
def test_unknown_trial_lists_nothing(vis, route):
    """A trial id the store does not have answers an empty list"""
    answer = vis.json("/" + route.format("no-such-trial"))
    assert list(answer.values()) == [[]]


# --- The function diff -------------------------------------------------------


@pytest.mark.parametrize("function", ["run_simulation", "csv_read", "open"])
def test_function_diff_compares_outputs_arguments_and_durations(
    vis, commands, function
):
    """The function diff runs in the server, without a process, and gives
    each trial's output, arguments and duration of the activation as the
    store has them
    """
    pair = pair_of(vis, function)
    answer = function_diff(vis, pair)
    assert commands.calls == [], "the function diff started a process"
    assert set(answer) == DIFF_KEYS
    for number, (trial_id, activation_id) in enumerate(pair, 1):
        suffix = "_function_trial{}".format(number)
        assert answer["output" + suffix] == output(
            vis.project, trial_id, activation_id
        ), number
        assert sorted(answer["arguments" + suffix]) == sorted(
            arguments(vis.project, trial_id, activation_id)
        ), number
        assert answer["duration" + suffix] == pytest.approx(
            duration(vis.project, trial_id, activation_id)
        ), number


@pytest.mark.parametrize("function", ["run_simulation", "csv_read"])
def test_function_diff_compares_the_variables(vis, function):
    """The variables of each trial are the evaluations inside the
    activation; the same code ran twice, so none is added or removed, and
    the ones that changed are those whose repr differs
    """
    pair = pair_of(vis, function)
    answer = function_diff(vis, pair)
    stored = [variables(vis.project, *side) for side in pair]
    for number, expected in enumerate(stored, 1):
        listed = {
            item["evaluation_id"]: item
            for item in answer["variables_function_trial{}".format(number)]
        }
        same = listed == expected
        assert same, "variables_function_trial{} differ from the store".format(number)
    first, second = stored
    shape = {
        key: (value["name"], value["type"], value["code_line"], value["code_column"])
        for key, value in first.items()
    }
    assert shape == {
        key: (value["name"], value["type"], value["code_line"], value["code_column"])
        for key, value in second.items()
    }, "the two trials evaluated other code in the activation"
    changed = {key for key in first if first[key]["value"] != second[key]["value"]}
    assert changed, "no value changed in the activation"
    assert answer["trial2_variables_added"] == []
    assert answer["trial1_variables_removed"] == []
    listed = set()
    for entry in answer["trial1_variables_that_changed"]:
        lines = CHANGED_LINE.findall(entry)
        assert sorted(sign for sign, _ in lines) == ["+", "-"], (
            "a changed variable without its two sides"
        )
        assert lines[0][1] == lines[1][1], "two variables paired"
        listed.add(int(lines[0][1]))
    assert len(listed) == len(answer["trial1_variables_that_changed"])
    assert listed == changed


def test_function_diff_of_an_open_call_lists_its_replaced_access(vis):
    """The diff of the ``open()`` call that read data2.dat lists that
    access as replaced, with both trials' hashes, timestamps and
    checkpoints
    """
    pair = pair_of(vis, "open")
    answer = function_diff(vis, pair)
    assert answer["file_accesses_added"] == []
    assert answer["file_accesses_removed"] == []
    first, second = (accesses_under(vis.project, *side)["data2.dat"] for side in pair)
    assert first["content_hash_after"] != second["content_hash_after"], (
        "data2.dat did not change"
    )
    expected = {"name": "data2.dat"}
    for access, ordinal in ((first, "first"), (second, "second")):
        expected.update(
            {
                "content_hash_before_{}_trial".format(ordinal): access[
                    "content_hash_before"
                ],
                "content_hash_after_{}_trial".format(ordinal): access[
                    "content_hash_after"
                ],
                "timestamp_{}_trial".format(ordinal): timestamp(access),
                "checkpoint_{}_trial".format(ordinal): access["checkpoint"],
            }
        )
    replaced = answer["file_accesses_replaced"]
    assert len(replaced) == 1, "{} replaced accesses".format(len(replaced))
    assert set(replaced[0]) == REPLACED_KEYS
    assert replaced[0] == expected


@pytest.mark.parametrize("function", ["run_simulation", "csv_read"])
def test_function_diff_of_a_function_lists_the_file_accesses_below_it(vis, function):
    """The diff of a function lists the accesses made below it that
    changed between the trials: data2.dat as replaced, although the access
    belongs to the activation of the ``open()`` call below the function
    (until #361 the list was empty)
    """
    pair = pair_of(vis, function)
    under = [accesses_under(vis.project, *side) for side in pair]
    expected = sorted(
        name
        for name in set(under[0]) & set(under[1])
        if (under[0][name]["content_hash_before"], under[0][name]["content_hash_after"])
        != (under[1][name]["content_hash_before"], under[1][name]["content_hash_after"])
    )
    assert expected == ["data2.dat"], "the store has other changes"
    answer = function_diff(vis, pair)
    names = sorted(item["name"] for item in answer["file_accesses_replaced"])
    assert names == expected, (
        "file_accesses_replaced is empty"
        if not names
        else "file_accesses_replaced names {}".format(names)
    )


def test_function_diff_of_a_renamed_input_lists_added_and_removed(project, vis_for):
    """Where the second trial's ``open()`` reads data3.dat instead of
    data2.dat, its diff lists data3.dat as added and data2.dat as removed,
    each with its mode, buffering, hashes, timestamp and stack
    """
    vis = vis_for(build_renamed_input(project))
    first, second = vis.trial_ids
    pair = (
        (first, activation_reading(vis.project, first, "open")),
        (second, activation_reading(vis.project, second, "open", "data3.dat")),
    )
    answer = function_diff(vis, pair)
    assert answer["file_accesses_replaced"] == []
    for key, (trial_id, activation_id), name in (
        ("file_accesses_removed", pair[0], "data2.dat"),
        ("file_accesses_added", pair[1], "data3.dat"),
    ):
        access = accesses_under(vis.project, trial_id, activation_id)[name]
        assert len(answer[key]) == 1, "{}: {} accesses".format(key, len(answer[key]))
        listed = answer[key][0]
        assert set(listed) == ACCESS_KEYS, key
        assert listed == {
            "name": name,
            "mode": access["mode"],
            "buffering": access["buffering"],
            "content_hash_before": access["content_hash_before"],
            "content_hash_after": access["content_hash_after"],
            "timestamp": timestamp(access),
            "stack": stack(vis.project, access),
        }, key
        assert listed["stack"].endswith("csv_read -> open"), key


def test_function_diff_of_two_calls_of_one_trial(vis):
    """The diff of the two calls of ``csv_read`` in one trial lists the
    file the first call read as removed and the one the second read as
    added: the diff of a trial with itself has no file access to filter,
    so the function diff compares the accesses below each activation
    (until #361 both lists were empty)
    """
    trial_id = vis.trial_ids[0]
    pair = tuple(
        (trial_id, activation_reading(vis.project, trial_id, "csv_read", name))
        for name in ("data1.dat", "data2.dat")
    )
    answer = function_diff(vis, pair)
    assert answer["file_accesses_replaced"] == []
    for key, name in (
        ("file_accesses_removed", "data1.dat"),
        ("file_accesses_added", "data2.dat"),
    ):
        assert [access["name"] for access in answer[key]] == [name], key


def test_function_diff_under_an_experiment_is_the_same(vis):
    """``/experiments/<code>/commands/diff/...`` answers the same diff"""
    pair = pair_of(vis, "open")
    assert function_diff(vis, pair, prefixed=True) == function_diff(vis, pair)


def test_function_diff_of_an_activation_the_trial_lacks(vis):
    """An activation id the first trial does not have raises
    ``IndexError`` (``now vis`` answers 500)
    """
    trial1, trial2 = vis.trial_ids
    missing = one(
        vis.project.query(
            "SELECT MAX(id) + 1 AS id FROM evaluation WHERE trial_id = ?", trial1
        ),
        "max",
    )["id"]
    with pytest.raises(IndexError, match="There isn't a function with the id"):
        vis.get("/commands/diff/{}/{}/{}/1".format(trial1, missing, trial2))


def replaced_in_trials(project):
    """Names accessed in both trials with other hashes in the second"""
    first, second = (
        {
            row["name"]: (row["content_hash_before"], row["content_hash_after"])
            for row in project.query(
                "SELECT * FROM file_access WHERE trial_id = ?", trial_id
            )
        }
        for trial_id in (row["id"] for row in project.trials())
    )
    return sorted(
        name for name in set(first) & set(second) if first[name] != second[name]
    )


@pytest.mark.parametrize("function", ["run_simulation", "open"])
def test_function_diff_prints_nothing(vis, capsys, function):
    """The function diff writes nothing on the server's stdout, for a
    function and for the ``open()`` call below it, whose diffs list an
    access replaced between the trials (until #204 it printed one
    ``access(...)`` pair per replaced access of the trial diff, #248)
    """
    assert replaced_in_trials(vis.project), "no access changed between the trials"
    function_diff(vis, pair_of(vis, function))
    assert capsys.readouterr().out == ""
