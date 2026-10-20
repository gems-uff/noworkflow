# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The mode and access rules: ``mode_access_rules.py`` and ``access_rules.py``

The rules answer which mode an access, a code component or an evaluation
has, and which files a trial read or wrote. They run here on the shared
two-trial weather store (``connected_two_trials``) and their answers are
checked against SQL on its ``db.sqlite``; whether a mode reads or writes is
what Python's own ``open()`` says of a file opened in it. ``now export
prolog -r`` appends ``rules.pl``, the Prolog version of the same rules,
which ``swipl`` runs over the facts of the same trial; in those comparisons
rules.pl stands where the store stands in ``support.assert_rows`` (its
solutions are the ones "in the store").

``read_mode`` and ``write_mode`` accept closed lists of modes, while the
collector records the mode string as the script wrote it, so the rules
miss binary, text and update modes (``rb``, ``rt``, ``r+``, ``wb``...).
The weather script opens files in ``r`` and ``w`` only: a private store,
built once per module by ``modes.py``, holds the other modes.

Known defects get a characterization of today's answer and a ``_desired``
twin marked ``xfail(strict=True)`` through ``Defect``.
"""

import collections

import pytest

from noworkflow.patterns import BLANK, var
from noworkflow.patterns.rules import (
    access_id,
    access_mode_id,
    code_mode_id,
    delete_mode,
    file_read,
    file_read_id,
    file_written,
    file_written_id,
    mode,
    mode_id,
    param_mode,
    read_mode,
    write_mode,
)
from noworkflow.tests.e2e.harness import NowProject
from noworkflow.tests.helpers import swipl
from noworkflow.tests.helpers.persistence import connected_to
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

# The modes the rules are asked about: every combination of a base mode
# with b, t and + that Python's open() accepts and the scripts use.
OPEN_MODES = (
    "r",
    "rb",
    "rt",
    "r+",
    "rb+",
    "r+b",
    "w",
    "wb",
    "w+",
    "wb+",
    "a",
    "ab",
    "a+",
    "x",
    "xb",
    "x+",
)
# The closed lists of read_mode and write_mode (mode_access_rules.py).
CLOSED_READ = ("r", "r+", "a+")
CLOSED_WRITE = ("w", "w+", "x", "x+", "a", "a+")
# The modes on which the closed lists and open() disagree.
DIVERGING_MODES = ("rb", "rt", "r+", "rb+", "r+b", "wb", "w+", "wb+", "ab", "xb", "x+")
CLOSED_LISTS_REASON = (
    "#349: read_mode and write_mode "
    "(patterns/rules/mode_access_rules.py) restrict the mode to the closed "
    "lists ['r', 'r+', 'a+'] and ['w', 'w+', 'x', 'x+', 'a', 'a+'], while "
    "the collector records the mode string as the script gave it (rb, wb, "
    "rt, rb+...), so file_read_id, file_written_id, file_read and "
    "file_written drop binary, text and update modes, and r+ is not a "
    "write nor w+ a read; rules.pl tests sub_atom, as open() does"
)
BINDING_LOST = Defect(
    "#344: RuleQuery.apply_function "
    "(patterns/machinery.py) resets every variable of its binds to BLANK "
    "after each result, and a variable that an option of restrict_rule "
    "bound in prepare_values is never bound again, so mode_id with an "
    "unbound Model reports the model of the first result of each option "
    "only",
    signature="unbound in",
)

# modes.py: the files it opens and the mode of each open, in order.
MODES_SCRIPT = '''\
"""Open files in binary, text and update modes"""
with open("in.bin", "rb") as handle:
    handle.read()
with open("out.bin", "wb") as handle:
    handle.write(b"x")
with open("log.txt", "a") as handle:
    handle.write("x")
with open("both.txt", "r+") as handle:
    handle.read()
with open("new.txt", "w+") as handle:
    handle.write("x")
with open("both_b.bin", "rb+") as handle:
    handle.read()
with open("in.bin") as handle:
    handle.read()
with open("in.bin", mode="rt") as handle:
    handle.read()
'''
MODES_INPUTS = ("in.bin", "both.txt", "both_b.bin")
# open() without a mode opens in "r".
SCRIPT_MODES = ["rb", "wb", "a", "r+", "w+", "rb+", "r", "rt"]


def closed_lists(mode):
    """The defect of a mode whose closed-list answer open() contradicts"""
    if mode not in DIVERGING_MODES:
        return ()
    today = (mode in CLOSED_READ, mode in CLOSED_WRITE)
    return (
        Defect(
            CLOSED_LISTS_REASON,
            signature="{}({!r}) -> {}".format("read_mode/write_mode", mode, today),
        ),
    )


def open_modes(directory, modes):
    """``{mode: (readable, writable)}`` as Python's own ``open()`` says

    Each mode opens a file of its own in ``directory``: an existing one for
    the modes that read without creating, a missing one for the others.
    """
    result = {}
    for index, open_mode in enumerate(sorted(set(modes))):
        path = directory / "mode{}".format(index)
        if "r" in open_mode:
            path.write_bytes(b"")
        with open(path, open_mode) as handle:
            result[open_mode] = (handle.readable(), handle.writable())
    return result


def classify(open_mode):
    """Whether ``read_mode`` and ``write_mode`` accept a mode"""
    return (bool(list(read_mode(open_mode))), bool(list(write_mode(open_mode))))


def trial_ids(project):
    return [trial["id"] for trial in project.trials()]


def rules_pl(facts, trial_id, goal, variables, **limits):
    """The solutions of a rules.pl goal about a trial, in the store's terms

    ``T`` is bound to the trial; access ids come back as ints.
    """
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


@pytest.fixture(scope="module")
def modes_project(tmp_path_factory):
    """A store of one trial of ``modes.py``: eight opens in eight modes"""
    project = NowProject(tmp_path_factory.mktemp("open_modes"))
    for name in MODES_INPUTS:
        project.write(name, "abc\n")
    project.write("modes.py", MODES_SCRIPT)
    project.run("run", "modes.py")
    return project


@pytest.fixture(scope="module")
def modes_prolog(modes_project, tmp_path_factory):
    """``now export prolog -r`` of the trial of ``modes_project``"""
    trial_id = trial_ids(modes_project)[0]
    result = modes_project.run("export", "prolog", "-r", trial_id)
    path = tmp_path_factory.mktemp("open_modes_prolog") / "modes.pl"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(result.stdout)
    return path


def recorded_modes(project, trial_id):
    """``{access id: mode}`` of a trial, from SQL"""
    return {
        row["id"]: row["mode"]
        for row in project.query(
            "SELECT id, mode FROM file_access WHERE trial_id = ? ORDER BY id", trial_id
        )
    }


# --- read_mode, write_mode, delete_mode, param_mode -------------------------


def test_read_and_write_mode_of_each_open_mode():
    """read_mode accepts r, r+ and a+ only, and write_mode w, w+, x, x+, a
    and a+ only: the closed lists, also what they enumerate

    Characterization of mode-rules-closed-lists.
    """
    mode_var = var("M")
    assert bindings(read_mode(mode_var), mode_var) == [
        (open_mode,) for open_mode in CLOSED_READ
    ]
    assert bindings(write_mode(mode_var), mode_var) == [
        (open_mode,) for open_mode in CLOSED_WRITE
    ]
    assert {open_mode: classify(open_mode) for open_mode in OPEN_MODES} == {
        open_mode: (open_mode in CLOSED_READ, open_mode in CLOSED_WRITE)
        for open_mode in OPEN_MODES
    }


@pytest.mark.parametrize(
    "open_mode",
    [
        pytest.param(open_mode, marks=defect_marks(closed_lists(open_mode)))
        for open_mode in OPEN_MODES
    ],
)
def test_read_and_write_mode_of_each_open_mode_desired(tmp_path, open_mode):
    """read_mode accepts the modes that open() opens for reading, and
    write_mode the modes it opens for writing
    """
    expected = open_modes(tmp_path, [open_mode])[open_mode]
    actual = classify(open_mode)
    if actual != expected:
        message = "read_mode/write_mode({!r}) -> {}, open() -> {}".format(
            open_mode, actual, expected
        )
        expect_known_failure(closed_lists(open_mode), message)
        raise AssertionError(message)


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
def test_rules_pl_read_and_write_mode_classify_like_open(tmp_path, two_trial_prolog):
    """rules.pl's read_mode and write_mode (sub_atom of r, +, w, x, a)
    accept each mode exactly when open() reads or writes in it
    """
    facts = next(iter(two_trial_prolog.values()))
    modes = ", ".join(swipl.quoted_atom(open_mode) for open_mode in OPEN_MODES)
    rows = swipl.solutions(
        facts,
        "member(M, [{}]), "
        "( read_mode(M) -> R = true ; R = false ), "
        "( write_mode(M) -> W = true ; W = false )".format(modes),
        "M R W",
    ).rows_or_raise()
    assert {
        open_mode: (read == "true", written == "true")
        for open_mode, read, written in rows
    } == open_modes(tmp_path, OPEN_MODES)


def test_delete_and_param_mode_match_their_letter():
    """delete_mode accepts d and param_mode p, and neither accepts r, as
    the rules.pl clauses (sub_atom of d, p) answer for a bound mode
    """
    # Only bound modes: rules.pl's sub_atom raises instantiation_error on
    # an unbound one, so it says nothing of what the rules enumerate.
    assert len(list(delete_mode("d"))) == 1
    assert list(delete_mode("r")) == []
    assert len(list(param_mode("p"))) == 1
    assert list(param_mode("r")) == []


# --- access_mode_id, code_mode_id, mode_id, mode ----------------------------


def test_access_mode_id_lists_the_mode_of_every_access(connected_two_trials):
    """access_mode_id answers the (id, mode) of each file access of a trial;
    with a blank trial, the accesses of every trial
    """
    project = connected_two_trials
    for trial_id in trial_ids(project):
        expected = [
            (row["id"], row["mode"])
            for row in project.query(
                "SELECT id, mode FROM file_access WHERE trial_id = ?", trial_id
            )
        ]
        assert_rows(
            lambda: bindings(access_mode_id(trial_id, var("I"), var("M")), "I", "M"),
            expected,
        )
        for access, access_mode in expected:
            assert bindings(access_mode_id(trial_id, access, var("M")), "M") == [
                (access_mode,)
            ]
    expected = [
        (row["id"],)
        for row in project.query("SELECT id FROM file_access WHERE mode = 'w'")
    ]
    assert len(expected) == 2
    assert_rows(lambda: bindings(access_mode_id(BLANK, var("I"), "w"), "I"), expected)


def test_code_mode_id_lists_the_mode_of_every_code_component(connected_two_trials):
    """code_mode_id answers the (id, mode) of each code component, and the
    mode of a bound one: the script's own code block
    """
    project = connected_two_trials
    trial = project.trials()[0]
    expected = [
        (row["id"], row["mode"])
        for row in project.query(
            "SELECT id, mode FROM code_component WHERE trial_id = ?", trial["id"]
        )
    ]
    assert_rows(
        lambda: bindings(code_mode_id(trial["id"], var("I"), var("M")), "I", "M"),
        expected,
    )
    assert bindings(code_mode_id(trial["id"], trial["main_id"], var("M")), "M") == [
        (dict(expected)[trial["main_id"]],)
    ]


MODEL_SQL = {
    "access": "SELECT id, mode FROM file_access WHERE trial_id = ?",
    "code_component": "SELECT id, mode FROM code_component WHERE trial_id = ?",
    "code_block": "SELECT id, mode FROM code_component WHERE trial_id = ?",
    # rules.pl: the mode of an evaluation, or of an activation, is the
    # mode of its code component, for every evaluation.
    "evaluation": "SELECT e.id, c.mode FROM evaluation e "
    "JOIN code_component c ON c.trial_id = e.trial_id "
    "AND c.id = e.code_component_id WHERE e.trial_id = ?",
    "activation": "SELECT e.id, c.mode FROM evaluation e "
    "JOIN code_component c ON c.trial_id = e.trial_id "
    "AND c.id = e.code_component_id WHERE e.trial_id = ?",
    # Neither the rule nor rules.pl has a clause for a trial.
    "trial": None,
}


@pytest.mark.parametrize("model", list(MODEL_SQL))
def test_mode_id_follows_the_model(connected_two_trials, model):
    """mode_id answers the modes of the model it is given"""
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    sql = MODEL_SQL[model]
    expected = (
        []
        if sql is None
        else [(row["id"], row["mode"]) for row in project.query(sql, trial_id)]
    )
    assert_rows(
        lambda: bindings(mode_id(trial_id, model, var("I"), var("M")), "I", "M"),
        expected,
    )


def model_counts(project, trial_id):
    """How many (id, mode) solutions mode_id has for each model, from SQL"""
    return {
        model: len(project.query(sql, trial_id))
        for model, sql in MODEL_SQL.items()
        if sql is not None
    }


def test_mode_id_with_an_unbound_model(connected_two_trials):
    """With Model unbound, mode_id binds Model in the first solution of each
    model and leaves it BLANK in the others

    Characterization of rule-option-binding-lost.
    """
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    counts = model_counts(project, trial_id)
    models = collections.Counter(
        row[0]
        for row in bindings(
            mode_id(trial_id, var("Model"), var("I"), var("M")), "Model"
        )
    )
    expected = {model: 1 for model in counts}
    expected[BLANK] = sum(counts.values()) - len(counts)
    assert models == expected


@known_defects(BINDING_LOST)
def test_mode_id_with_an_unbound_model_desired(connected_two_trials):
    """With Model unbound, mode_id binds Model in every solution"""
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    expected = [
        (model,)
        for model, count in model_counts(project, trial_id).items()
        for _ in range(count)
    ]
    assert_rows(
        lambda: bindings(mode_id(trial_id, var("Model"), var("I"), var("M")), "Model"),
        expected,
    )


MODE_BY_NAME = {
    "access-named": (
        lambda t: mode(t, "access", "data1.dat", var("M")),
        "M",
        "SELECT mode FROM file_access WHERE trial_id = ? AND name = 'data1.dat'",
    ),
    "access-any": (
        lambda t: mode(t, "access", var("N"), var("M")),
        "N M",
        "SELECT name, mode FROM file_access WHERE trial_id = ?",
    ),
    "activation-named": (
        lambda t: mode(t, "activation", "csv_read", var("M")),
        "M",
        "SELECT c.mode FROM activation a "
        "JOIN evaluation e ON e.trial_id = a.trial_id AND e.id = a.id "
        "JOIN code_component c ON c.trial_id = e.trial_id "
        "AND c.id = e.code_component_id "
        "WHERE a.trial_id = ? AND a.name = 'csv_read'",
    ),
}


@pytest.mark.parametrize("case", list(MODE_BY_NAME))
def test_mode_names_the_entity(connected_two_trials, case):
    """mode answers the modes of the accesses or activations with a name"""
    query, variables, sql = MODE_BY_NAME[case]
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    expected = [tuple(row.values()) for row in project.query(sql, trial_id)]
    assert expected
    assert_rows(lambda: bindings(query(trial_id), *variables.split()), expected)


# --- file_read_id, file_written_id, access_id, file_read, file_written ------


def test_file_read_id_and_file_written_id_split_the_accesses_by_mode(
    connected_two_trials, tmp_path
):
    """file_read_id answers the accesses whose mode opens for reading and
    file_written_id the ones whose mode opens for writing; the written
    access is not a read
    """
    project = connected_two_trials
    for trial_id in trial_ids(project):
        modes = recorded_modes(project, trial_id)
        directory = tmp_path / trial_id
        directory.mkdir()
        semantics = open_modes(directory, modes.values())
        read = [(i,) for i, m in modes.items() if semantics[m][0]]
        written = [(i,) for i, m in modes.items() if semantics[m][1]]
        assert len(read) == 2 and len(written) == 1
        assert_rows(lambda: bindings(file_read_id(trial_id, var("I")), "I"), read)
        assert_rows(lambda: bindings(file_written_id(trial_id, var("I")), "I"), written)
        assert list(file_read_id(trial_id, written[0][0])) == []


def test_access_id_maps_each_access_to_its_activation(connected_two_trials):
    """access_id answers the (activation, access) pairs; an activation
    gives its access and an access its activation
    """
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    rows = project.query(
        "SELECT activation_id, id, name FROM file_access WHERE trial_id = ?", trial_id
    )
    assert_rows(
        lambda: bindings(access_id(trial_id, var("A"), var("I")), "A", "I"),
        [(row["activation_id"], row["id"]) for row in rows],
    )
    for row in rows:
        assert bindings(access_id(trial_id, row["activation_id"], var("I")), "I") == [
            (row["id"],)
        ]
        assert bindings(access_id(trial_id, var("A"), row["id"]), "A") == [
            (row["activation_id"],)
        ]


def test_file_read_and_file_written_name_the_files(connected_two_trials):
    """file_read names the two inputs of the weather script and
    file_written its output, in every trial that touched them
    """
    project = connected_two_trials
    trial_id = trial_ids(project)[0]
    assert_rows(
        lambda: bindings(file_read(trial_id, var("N")), "N"),
        [("data1.dat",), ("data2.dat",)],
    )
    assert_rows(
        lambda: bindings(file_written(trial_id, var("N")), "N"), [("output.csv",)]
    )
    assert_rows(
        lambda: bindings(file_read(var("T"), "data2.dat"), "T"),
        [(trial,) for trial in trial_ids(project)],
    )
    assert list(file_written(trial_id, "data1.dat")) == []


def test_file_access_rules_of_binary_and_update_modes(modes_project):
    """The store records each mode as the script gave it (r for no mode),
    and file_read_id and file_written_id keep only the modes of the closed
    lists: r+ and r are read, a and w+ written

    Characterization of mode-rules-closed-lists.
    """
    trial_id = trial_ids(modes_project)[0]
    modes = recorded_modes(modes_project, trial_id)
    assert list(modes.values()) == SCRIPT_MODES
    with connected_to(modes_project.path):
        read = bindings(file_read_id(trial_id, var("I")), "I")
        written = bindings(file_written_id(trial_id, var("I")), "I")
    assert sorted(read) == [(i,) for i, m in modes.items() if m in CLOSED_READ]
    assert sorted(written) == [(i,) for i, m in modes.items() if m in CLOSED_WRITE]
    assert [modes[i] for (i,) in sorted(read)] == ["r+", "r"]
    assert [modes[i] for (i,) in sorted(written)] == ["a", "w+"]


@known_defects(
    Defect(
        CLOSED_LISTS_REASON,
        signature="file_read_id misses ['rb', 'rb+', 'rt', 'w+']; "
        "file_written_id misses ['r+', 'rb+', 'wb']",
    )
)
def test_file_access_rules_of_binary_and_update_modes_desired(modes_project, tmp_path):
    """file_read_id and file_read answer every access whose mode open()
    reads in, file_written_id and file_written every one it writes in
    """
    trial_id = trial_ids(modes_project)[0]
    modes = recorded_modes(modes_project, trial_id)
    names = {
        row["id"]: row["name"]
        for row in modes_project.query(
            "SELECT id, name FROM file_access WHERE trial_id = ?", trial_id
        )
    }
    semantics = open_modes(tmp_path, modes.values())
    expected_read = {i for i, m in modes.items() if semantics[m][0]}
    expected_written = {i for i, m in modes.items() if semantics[m][1]}
    with connected_to(modes_project.path):
        read = {i for (i,) in bindings(file_read_id(trial_id, var("I")), "I")}
        written = {i for (i,) in bindings(file_written_id(trial_id, var("I")), "I")}
        read_names = bindings(file_read(trial_id, var("N")), "N")
        written_names = bindings(file_written(trial_id, var("N")), "N")
    if (read, written) != (expected_read, expected_written):
        message = "file_read_id misses {}; file_written_id misses {}".format(
            sorted(modes[i] for i in expected_read - read),
            sorted(modes[i] for i in expected_written - written),
        )
        extra = sorted(
            modes[i] for i in (read - expected_read) | (written - expected_written)
        )
        if extra:
            message += "; answers too {}".format(extra)
        raise AssertionError(message)
    assert_rows(lambda: read_names, [(names[i],) for i in expected_read])
    assert_rows(lambda: written_names, [(names[i],) for i in expected_written])


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
def test_rules_pl_file_access_rules_of_binary_and_update_modes(
    modes_project, modes_prolog, tmp_path
):
    """rules.pl's file_read_id and file_written_id answer the accesses
    whose mode open() reads or writes in, binary and update modes included
    """
    trial_id = trial_ids(modes_project)[0]
    modes = recorded_modes(modes_project, trial_id)
    semantics = open_modes(tmp_path, modes.values())
    assert_rows(
        lambda: rules_pl(modes_prolog, trial_id, "file_read_id(T, I)", "I"),
        [(i,) for i, m in modes.items() if semantics[m][0]],
    )
    assert_rows(
        lambda: rules_pl(modes_prolog, trial_id, "file_written_id(T, I)", "I"),
        [(i,) for i, m in modes.items() if semantics[m][1]],
    )


# --- rules.pl ---------------------------------------------------------------


def agree(case_id, query, goal, variables, defects=()):
    """A rule called on trial 1 and the rules.pl goal that defines it"""
    return pytest.param(
        query, goal, variables, defects, id=case_id, marks=defect_marks(defects)
    )


AGREE = (
    [
        agree(
            "access_mode_id",
            lambda t: access_mode_id(t, var("I"), var("M")),
            "access_mode_id(T, I, M)",
            "I M",
        ),
        agree(
            "code_mode_id",
            lambda t: code_mode_id(t, var("I"), var("M")),
            "code_mode_id(T, I, M)",
            "I M",
        ),
    ]
    + [
        agree(
            "mode_id-" + model,
            lambda t, model=model: mode_id(t, model, var("I"), var("M")),
            "mode_id(T, {}, I, M)".format(model),
            "I M",
        )
        for model in MODEL_SQL
        if model != "trial"
    ]
    + [
        agree(
            "mode_id-unbound-model",
            lambda t: mode_id(t, var("Model"), var("I"), var("M")),
            "mode_id(T, Model, I, M)",
            "Model I M",
            (BINDING_LOST,),
        ),
        agree(
            "mode-access",
            lambda t: mode(t, "access", var("N"), var("M")),
            "mode(T, access, N, M)",
            "N M",
        ),
        agree(
            "mode-activation",
            lambda t: mode(t, "activation", var("N"), var("M")),
            "mode(T, activation, N, M)",
            "N M",
        ),
        agree(
            "mode-csv_read",
            lambda t: mode(t, "activation", "csv_read", var("M")),
            "mode(T, activation, csv_read, M)",
            "M",
        ),
        agree(
            "file_read_id",
            lambda t: file_read_id(t, var("I")),
            "file_read_id(T, I)",
            "I",
        ),
        agree(
            "file_written_id",
            lambda t: file_written_id(t, var("I")),
            "file_written_id(T, I)",
            "I",
        ),
        agree(
            "access_id",
            lambda t: access_id(t, var("A"), var("I")),
            "access_id(T, A, I)",
            "A I",
        ),
        agree("file_read", lambda t: file_read(t, var("N")), "file_read(T, N)", "N"),
        agree(
            "file_written",
            lambda t: file_written(t, var("N")),
            "file_written(T, N)",
            "N",
        ),
    ]
)


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
@pytest.mark.parametrize("query, goal, variables, defects", AGREE)
def test_mode_and_access_rules_agree_with_rules_pl(
    connected_two_trials, two_trial_prolog, query, goal, variables, defects
):
    """The rule and its rules.pl definition answer the same solutions on
    the first weather trial
    """
    trial_id, facts = next(iter(two_trial_prolog.items()))
    assert_agree(
        lambda: bindings(query(trial_id), *variables.split()),
        lambda: rules_pl(facts, trial_id, goal, variables),
        defects,
    )
