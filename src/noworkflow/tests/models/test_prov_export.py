# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``export_prov``: the user, groups, memberships and annotations of a trial

``now export prov`` ends with the entities of the collaboration models: the
trial's user, the user's groups and memberships, and the annotations of the
trial. On a store made by ``now run`` the user has no group and the trial
no annotation (only ``now vis`` creates them), so the e2e tests never reach
those lines. Here they are built on the in-memory store, with a synthetic
user id, around a trial without evaluations (an unfinished ``new_trial``),
so the output holds only the prefixes and these entities. The store is
erased before and after each test.

``SaveOutput``, which collects the lines, is checked writing its
``.provn`` file under ``tmp_path``.
"""

from types import SimpleNamespace

import pytest

from noworkflow.now.models.prov.export import export_prov
from noworkflow.now.models.prov.save_output import SaveOutput
from noworkflow.now.persistence import relational
from noworkflow.now.persistence.models import (
    Experiment,
    ExtendedAnnotation,
    Group,
    MemberOfGroup,
    Trial,
    User,
)
from noworkflow.tests.helpers.models import (
    TrialConfig,
    erase_database,
    new_trial,
)

USER_ID = "h\\alice"
PREFIXES = [
    "prefix script <https://dew-uff.github.io/versioned-prov/ns/script#>",
    "prefix version <https://dew-uff.github.io/versioned-prov/ns#>",
]
ANNOTATION = (
    'entity(extendedAnnotation_{id}, [type="script:extendedAnnotation", '
    'annotation="{annotation}", description="{description}", '
    'annotationFormat="{format}", provenanceType="{type}", '
    'annotationLevel="{level}", relatedExperiment="{experiment}", '
    'relatedTrial="{trial}"])'
)


@pytest.fixture
def clean_store():
    """The in-memory store, empty before the test and after it"""
    erase_database()
    yield
    erase_database()


def annotate(annotation, trial_id=None, experiment_id=None, **fields):
    """Create an annotation; the fields not given are NULL"""
    values = dict(
        annotation=annotation,
        description=None,
        annotationFormat=None,
        provenanceType=None,
        annotationLevel=None,
        relatedExperiment=experiment_id,
        relatedTrial=trial_id,
    )
    values.update(fields)
    return ExtendedAnnotation.create(SimpleNamespace(**values)).id


def entity_lines(text):
    return [line for line in text.splitlines() if line.startswith("entity(")]


def test_export_prov_declares_the_collaboration_entities_of_the_trial(clean_store):
    """The trial's user, each of the user's groups and memberships, and the
    trial's annotation become one entity each, with the values the store
    holds

    The order of the groups is not fixed, so the lines compare as a set.
    """
    trial_id = new_trial(TrialConfig("unfinished"))
    User.create(USER_ID, "alice")
    groups = {
        name: Group.create(SimpleNamespace(name=name)).id for name in ("g1", "g2")
    }
    memberships = {
        MemberOfGroup.create(
            SimpleNamespace(userId=USER_ID, groupId=group_id)
        ).id: group_id
        for group_id in groups.values()
    }
    experiment_id = Experiment.create(SimpleNamespace(name="exp", description="d")).id
    annotation_id = annotate(
        "note",
        trial_id,
        experiment_id,
        description="why",
        annotationFormat="text",
        provenanceType="retrospective",
        annotationLevel="trial",
    )
    relational.session.query(Trial.m).filter(Trial.m.id == trial_id).update(
        {"user_id": USER_ID, "experiment_id": experiment_id}
    )
    relational.session.commit()

    text = export_prov(Trial(trial_id)).text
    assert text.splitlines()[:2] == PREFIXES
    expected = {'entity(user_h\\alice, [type="script:user", label="alice"])'}
    expected |= {
        'entity(group_{}, [type="script:group", label="{}"])'.format(group_id, name)
        for name, group_id in groups.items()
    }
    expected |= {
        'entity(memberOfGroup_{}, [type="script:memberOfGroup", '
        'userId="h\\alice", groupId="{}"])'.format(membership_id, group_id)
        for membership_id, group_id in memberships.items()
    }
    expected.add(
        ANNOTATION.format(
            id=annotation_id,
            annotation="note",
            description="why",
            format="text",
            type="retrospective",
            level="trial",
            experiment=experiment_id,
            trial=trial_id,
        )
    )
    lines = entity_lines(text)
    assert len(lines) == len(expected)
    assert set(lines) == expected


def test_export_prov_declares_only_the_annotations_of_the_trial(clean_store):
    """Of three annotations, only the one related to the exported trial is
    an entity, its NULL fields written as empty strings; a trial without a
    user has no user entity
    """
    trial_id = new_trial(TrialConfig("unfinished"))
    other = new_trial(TrialConfig("unfinished", script="other.py"))
    experiment_id = Experiment.create(SimpleNamespace(name="exp", description="d")).id
    mine = annotate("mine", trial_id)
    annotate("other", other)
    annotate("experiment only", experiment_id=experiment_id)
    lines = entity_lines(export_prov(Trial(trial_id)).text)
    assert lines == [
        ANNOTATION.format(
            id=mine,
            annotation="mine",
            description="",
            format="",
            type="",
            level="",
            experiment="",
            trial=trial_id,
        )
    ]


def test_save_output_writes_its_lines_to_a_provn_file(tmp_path):
    """Each call adds a line of its arguments joined by spaces; ``save``
    writes the lines, joined by newlines, to ``<name>.provn``"""
    output = SaveOutput(name=str(tmp_path / "trial"))
    output("a")
    output("b", 1)
    output()
    assert str(output) == "a\nb 1\n"
    output.save()
    assert (tmp_path / "trial.provn").read_text() == "a\nb 1\n"
