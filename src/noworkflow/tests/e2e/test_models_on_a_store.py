# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Compositions, users and stage tags read by the models from a real store

``Composition`` links each AST node of a script to the node it is part of,
and ``relationships.py`` turns those rows into ``Trial.compositions``,
``CodeComponent.parents``/``children`` and the part and whole of a
composition. No command prints them, so they are read here in-process on
the shared two-trial weather store (``connected_two_trials``) and compared
with SQL on its ``db.sqlite``. Both trials run the same script and number
their code components the same way, so a relationship that forgets the
trial id finds the rows of the other trial too.

The trial's user is the synthetic user of the harness, recorded under the
hostname: those assertions are booleans with fixed messages.

``StageTags`` holds what ``now_tag_variable`` and ``now_tag_cell`` record.
Those builtins exist only under ``now run``, so a tagged script runs once
per module into a store of its own, read through ``connected_to`` and
checked unchanged after each test.

Known defects have a characterization of today's behavior and a
``_desired`` twin marked through ``known_defects``. Their mechanisms are
plain Python, the same on every system (measured on macOS with Python 3.11
to 3.15).
"""

import pytest

from noworkflow.now.persistence.models import (
    CodeComponent,
    Composition,
    StageTags,
    Trial,
)
from noworkflow.tests.e2e.harness import USER, NowProject
from noworkflow.tests.e2e.normalize import argument_spans
from noworkflow.tests.helpers.defects import Defect, known_defects
from noworkflow.tests.helpers.persistence import connected_to
from noworkflow.tests.helpers.swipl import quoted_atom

COMPOSITION_COLUMNS = ("id", "part_id", "whole_id", "type", "position", "extra")
# The script's own code component: the whole of its top-level statements.
SCRIPT = 1

TAGGED = (
    "def double(x):\n"
    "    return x * 2\n"
    "\n"
    "a = 3\n"
    "b = double(a)\n"
    'c = now_tag_variable("result", b)\n'
    'now_tag_cell("stage_one")\n'
    "print(c)\n"
)

LOST_ACTIVATION = Defect(
    reason="#326: now_tag_cell and "
    "now_tag_variable pass the activation id as the fourth argument "
    "of stage_tags.add, which StageTagsLW takes as var_name; "
    "activation_id keeps its default -1, stored as NULL, and the "
    "variable name and value are never stored",
    signature="activation_id=None",
)
NO_RELATIONSHIPS = Defect(
    reason="#353: stage_tags.py announces the "
    "relationships trial and activation, but relationships.py never "
    "declares them, nor Trial.stage_tags",
    signature="'StageTags' object has no attribute 'trial'",
)


def composition_rows(project, trial_id, where="", *params, limit=-1):
    """The composition rows of a trial in id order, as tuples of
    COMPOSITION_COLUMNS; ``where`` adds conditions (``AND ...``)"""
    rows = project.query(
        "SELECT {} FROM composition WHERE trial_id = ? {} ORDER BY id LIMIT ?".format(
            ", ".join(COMPOSITION_COLUMNS), where
        ),
        trial_id,
        *params,
        limit,
    )
    return [tuple(row[column] for column in COMPOSITION_COLUMNS) for row in rows]


def fact_arguments(fact, name):
    """The texts of the top-level arguments of the fact ``name(...).``"""
    assert fact.startswith(name + "(") and fact.endswith(")."), fact
    spans = argument_spans(fact, len(name) + 1)
    return [fact[start:end].strip() for start, end in spans]


def as_row(composition):
    return tuple(getattr(composition, column) for column in COMPOSITION_COLUMNS)


# --- compositions -----------------------------------------------------------


def test_compositions_of_each_trial_are_the_rows_of_the_store(connected_two_trials):
    """``Trial.compositions`` of each trial lists the composition rows of
    that trial, and only them
    """
    trial_ids = [row["id"] for row in connected_two_trials.trials()]
    assert len(trial_ids) == 2
    for trial_id in trial_ids:
        expected = composition_rows(connected_two_trials, trial_id)
        # Not vacuous: the script is made of many AST nodes.
        assert len(expected) > 100
        found = sorted(as_row(each) for each in Trial(trial_id).compositions)
        assert found == expected


def test_composition_reprs_as_the_fact_of_its_row(connected_two_trials):
    """A composition loads by ``(trial id, id)`` and its fact holds the
    trial id, the whole, the part, the type, the position and the extra of
    its row, ``nil`` where the column is NULL
    """
    trial_id = connected_two_trials.trials()[-1]["id"]
    with_position = composition_rows(
        connected_two_trials,
        trial_id,
        "AND position IS NOT NULL AND extra IS NULL",
        limit=1,
    )
    with_extra = composition_rows(
        connected_two_trials,
        trial_id,
        "AND position IS NULL AND extra IS NOT NULL",
        limit=1,
    )
    assert with_position and with_extra
    for row in with_position + with_extra:
        id_, part, whole, type_, position, extra = row
        composition = Composition((trial_id, id_))
        assert as_row(composition) == row
        assert repr(composition) == "composition({}).".format(
            ", ".join(
                [
                    quoted_atom(trial_id),
                    str(whole),
                    str(part),
                    quoted_atom(type_),
                    "nil" if position is None else str(position),
                    "nil" if extra is None else quoted_atom(extra),
                ]
            )
        )
        assert len(fact_arguments(repr(composition), "composition")) == 6


def test_composition_part_and_whole_are_code_components_of_its_trial(
    connected_two_trials,
):
    """A composition's trial, part and whole are those of its row, and a
    code component lists the compositions it is the whole or the part of
    """
    trial_id = connected_two_trials.trials()[-1]["id"]
    id_, part, whole = composition_rows(
        connected_two_trials, trial_id, "AND whole_id != ?", SCRIPT, limit=1
    )[0][:3]
    composition = Composition((trial_id, id_))
    assert composition.trial.id == trial_id
    assert (composition.part.trial_id, composition.part.id) == (trial_id, part)
    assert (composition.whole.trial_id, composition.whole.id) == (trial_id, whole)
    as_whole = [
        row[0]
        for row in composition_rows(
            connected_two_trials, trial_id, "AND whole_id = ?", whole
        )
    ]
    as_part = [
        row[0]
        for row in composition_rows(
            connected_two_trials, trial_id, "AND part_id = ?", part
        )
    ]
    component = CodeComponent((trial_id, whole))
    assert sorted(each.id for each in component.compositions_as_whole) == (as_whole)
    assert (
        sorted(each.id for each in CodeComponent((trial_id, part)).compositions_as_part)
        == as_part
    )


def test_code_component_children_and_parents_stay_in_their_trial(connected_two_trials):
    """``children`` lists the parts of a component and ``parents`` the
    wholes, within its trial: the other trial has the same numbering, and
    its rows must not double them
    """
    for trial in connected_two_trials.trials():
        trial_id = trial["id"]
        parts = sorted(
            row[1]
            for row in composition_rows(
                connected_two_trials, trial_id, "AND whole_id = ?", SCRIPT
            )
        )
        assert parts, "the script has no top-level statement"
        children = CodeComponent((trial_id, SCRIPT)).children
        assert sorted(child.id for child in children) == parts
        _, part, whole = composition_rows(
            connected_two_trials, trial_id, "AND whole_id != ?", SCRIPT, limit=1
        )[0][:3]
        parents = CodeComponent((trial_id, part)).parents
        assert [(parent.trial_id, parent.id) for parent in parents] == [
            (trial_id, whole)
        ]


# --- user -------------------------------------------------------------------


def test_the_trial_user_is_the_synthetic_user_of_the_run(connected_two_trials):
    """Both trials name the harness's user, which lists both and belongs
    to no group; neither trial is in an experiment

    Booleans with fixed messages: the user id holds the hostname.
    """
    trials = connected_two_trials.trials()
    users = {row["user_id"] for row in trials}
    one_user = len(users) == 1
    assert one_user, "the trials name different users"
    for row in trials:
        user = Trial(row["id"]).user
        same_id = user.id == row["user_id"]
        assert same_id, "Trial.user is not the user of the trial row"
        synthetic = user.userLogin == USER
        assert synthetic, "the user's login is not the harness's user"
        assert row["experiment_id"] is None
        assert Trial(row["id"]).experiment is None
    user = Trial(trials[0]["id"]).user
    assert sorted(trial.id for trial in user.trials) == sorted(
        row["id"] for row in trials
    )
    assert list(user.groups) == []
    assert list(user.member_of_groups) == []


# --- stage tags -------------------------------------------------------------


@pytest.fixture(scope="module")
def _tagged_store(tmp_path_factory):
    project = NowProject(tmp_path_factory.mktemp("stage_tags"))
    project.write("tagged.py", TAGGED)
    result = project.run("run", "tagged.py")
    assert result.stdout.strip().endswith("6"), str(result)
    return project


@pytest.fixture
def tagged(_tagged_store):
    """The store of ``tagged.py``, connected in-process, read-only"""
    before = _tagged_store.fingerprint()
    with connected_to(_tagged_store.path):
        yield _tagged_store
    assert _tagged_store.fingerprint() == before, (
        "the test changed the store of tagged.py"
    )


def stage_tag_rows(project):
    return project.query("SELECT * FROM stage_tags ORDER BY id")


def script_activation(project, trial_id):
    """The id of the activation of the script itself, by SQL"""
    rows = project.query(
        "SELECT activation.id FROM activation JOIN trial "
        "ON activation.trial_id = trial.id "
        "AND activation.code_block_id = trial.main_id "
        "WHERE trial.id = ?",
        trial_id,
    )
    assert len(rows) == 1
    return rows[0]["id"]


def test_stage_tags_are_loaded_by_trial_and_id(tagged):
    """Each tag loads by ``(trial id, id)`` with the columns of its row,
    in the order the script made them: the variable tag holds the name
    given and the value, ``double(3)``; the cell tag the tag given

    The name a cell tag records, and how its fact writes the id (see
    ``test_prolog_predicates_of_the_models``), are not asserted here: the
    script does not say what they should be.
    """
    rows = stage_tag_rows(tagged)
    assert [(row["id"], row["tag_name"]) for row in rows] == [
        (1, "6"),
        (2, "stage_one"),
    ]
    assert rows[0]["name"] == "result"
    for row in rows:
        tag = StageTags((row["trial_id"], row["id"]))
        assert dict(tag.to_dict()) == row
        arguments = fact_arguments(repr(tag), StageTags.prolog_description.name)
        assert len(arguments) == 7
        assert [arguments[0]] + arguments[2:4] == [
            quoted_atom(row["trial_id"]),
            quoted_atom(row["name"]),
            quoted_atom(row["tag_name"]),
        ]


def test_stage_tags_of_a_tagged_script(tagged):
    """Today both tags are stored without the activation that made them,
    and without the variable's name and value

    Characterization of a defect.
    """
    rows = stage_tag_rows(tagged)
    assert len(rows) == 2
    unstored = [
        (row["activation_id"], row["variable_name"], row["variable_value"])
        for row in rows
    ]
    assert unstored == [(None, None, None)] * 2


@known_defects(LOST_ACTIVATION)
def test_stage_tags_of_a_tagged_script_desired(tagged):
    """Both tags record the activation of the script, where the tagging
    functions ran"""
    rows = stage_tag_rows(tagged)
    expected = script_activation(tagged, rows[0]["trial_id"])
    wrong = [
        "{}: activation_id={}".format(row["name"], row["activation_id"])
        for row in rows
        if row["activation_id"] != expected
    ]
    assert not wrong, "; ".join(wrong)


def test_stage_tag_relationships(tagged):
    """Today a stage tag has no ``trial`` or ``activation``, and a trial no
    ``stage_tags``

    Characterization of a defect.
    """
    trial_id = stage_tag_rows(tagged)[0]["trial_id"]
    tag = StageTags((trial_id, 1))
    for name in ("trial", "activation"):
        with pytest.raises(AttributeError, match=name):
            getattr(tag, name)
    assert not hasattr(Trial(trial_id), "stage_tags")


@known_defects(NO_RELATIONSHIPS)
def test_stage_tag_relationships_desired(tagged):
    """A stage tag reaches its trial and the activation its row names, and
    a trial lists its stage tags, as ``stage_tags.py`` announces

    The activation is compared with the row, not with the script's: the
    row loses it today (``test_stage_tags_of_a_tagged_script``).
    """
    rows = stage_tag_rows(tagged)
    trial_id = rows[0]["trial_id"]
    tag = StageTags((trial_id, 1))
    assert tag.trial.id == trial_id
    activation = tag.activation
    assert getattr(activation, "id", None) == rows[0]["activation_id"]
    assert sorted(each.id for each in Trial(trial_id).stage_tags) == [
        row["id"] for row in rows
    ]
