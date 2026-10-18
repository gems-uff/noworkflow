# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The collaboration models, which have no doctests

``Experiment``, ``User``, ``Group``, ``MemberOfGroup`` and
``ExtendedAnnotation`` hold what ``now vis`` records about who ran a trial
and why. Their ``create``, ``delete`` and query methods, and the
relationships ``relationships.py`` declares between them and ``Trial``,
run here on the in-memory store: every value is one the test wrote, and
the rows are read back with SQL on the same store. Their Prolog facts are
in ``test_prolog_facts.py``; this module only adds the uniqueness of the
predicate names. Trials are linked to a user or an experiment by an
update of the trial row, never through ``Trial.set_user_based_on_env``,
which would record the real login and hostname.

Known defects have a characterization of today's behavior and a
``_desired`` twin marked through ``known_defects``. Their mechanisms are
plain Python and SQLite's defaults, the same on every system (measured on
macOS with Python 3.11 to 3.15).
"""
import collections
import contextlib
import re
import sqlite3
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm.exc import NoResultFound

from noworkflow.now.persistence import relational
from noworkflow.now.persistence.models import (
    ORDER, Experiment, ExtendedAnnotation, FileAccess, Group, MemberOfGroup,
    Remote, StageTags, Trial, User,
)
from noworkflow.tests.helpers.defects import Defect, known_defects
from noworkflow.tests.helpers.models import (
    TrialConfig, erase_database, new_trial,
)

UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# A synthetic user id in the form noWorkflow records (host\login).
USER_ID = "h\\alice"


def foreign_keys_off():
    """Whether a new sqlite3 connection starts with foreign keys off

    That is SQLite's default, and noWorkflow's connections never change
    it: no ``ON DELETE CASCADE`` runs.
    """
    with contextlib.closing(sqlite3.connect(":memory:")) as connection:
        return connection.execute("PRAGMA foreign_keys").fetchone()[0] == 0


FOREIGN_KEYS_OFF = foreign_keys_off()

GROUP_DELETE = Defect(
    reason="#353: Group.delete deletes only "
           "the group row and relies on the ON DELETE CASCADE that "
           "memberOfGroup declares on groupId, but noWorkflow never enables "
           "SQLite's foreign keys, so the memberships stay",
    signature="memberships left for the deleted group: 1",
    condition=FOREIGN_KEYS_OFF,
)
SHARED_PREDICATE = Defect(
    reason="#353: StageTags.prolog_description "
           "was copied from FileAccess: it is named access, the predicate "
           "of file accesses, and writes its id as f<id>",
    signature="access: FileAccess, StageTags",
)


def sql(statement, **params):
    """Rows of a query on the in-memory store, as dicts"""
    result = relational.session.execute(sa.text(statement), params)
    return [dict(row) for row in result.mappings()]


def link_trial(trial_id, **columns):
    """Set columns of a trial row (``user_id``, ``experiment_id``)"""
    relational.session.query(Trial.m).filter(
        Trial.m.id == trial_id).update(columns)
    relational.session.commit()


def memberships_of(group_id):
    return sql('SELECT id FROM "memberOfGroup" WHERE "groupId" = :group',
               group=group_id)


def shared_predicates():
    """``{predicate: [model, ...]}`` of the names that several models use"""
    owners = collections.defaultdict(list)
    for model in list(ORDER) + [Remote]:
        description = getattr(model, "prolog_description", None)
        if description is not None:
            owners[description.name].append(model.__name__)
    return {name: sorted(models) for name, models in owners.items()
            if len(models) > 1}


@pytest.fixture
def clean_store():
    """The in-memory store, empty before the test and after it"""
    erase_database()
    yield
    erase_database()


@pytest.fixture
def member(clean_store):
    """``(user id, group id, membership id)`` of a user in group ``g1``"""
    User.create(USER_ID, "alice")
    group = Group.create(SimpleNamespace(name="g1"))
    membership = MemberOfGroup.create(
        SimpleNamespace(userId=USER_ID, groupId=group.id))
    return USER_ID, group.id, membership.id


# --- experiment -------------------------------------------------------------


def test_experiment_is_loaded_by_its_id_and_reprs_as_a_fact(clean_store):
    """``Experiment.create`` gives the experiment a UUID; the proxy loads
    it by that id, ``load_experiment`` by its name, and the repr is its
    fact
    """
    created = Experiment.create(
        SimpleNamespace(name="exp1", description="first"))
    assert UUID.fullmatch(created.id), created.id
    experiment = Experiment(created.id)
    assert repr(experiment) == "experiment('{}', 'exp1', 'first').".format(
        created.id)
    assert dict(experiment.to_dict()) == sql("SELECT * FROM experiment")[0]
    assert Experiment.load_experiment("exp1").id == created.id
    assert Experiment.load_experiment("missing") is None
    assert [each.id for each in Experiment.all()] == [created.id]


def test_experiment_names_are_unique(clean_store):
    """A second experiment with the same name raises ``IntegrityError``,
    and the store keeps the first one
    """
    Experiment.create(SimpleNamespace(name="exp1", description="first"))
    with pytest.raises(sa.exc.IntegrityError, match="experiment.name"):
        Experiment.create(SimpleNamespace(name="exp1", description="second"))
    relational.session.rollback()
    assert [row["description"] for row in sql(
        "SELECT description FROM experiment")] == ["first"]


def test_trial_and_experiment_navigate_to_each_other(clean_store):
    """``Trial.experiment`` and ``Experiment.trials`` follow the trial's
    ``experiment_id``
    """
    trial_id = new_trial(TrialConfig("unfinished"))
    other = new_trial(TrialConfig("unfinished", script="other.py"))
    experiment_id = Experiment.create(
        SimpleNamespace(name="exp1", description="first")).id
    link_trial(trial_id, experiment_id=experiment_id)
    assert Trial(trial_id).experiment.id == experiment_id
    assert Trial(other).experiment is None
    assert [trial.id for trial in Experiment(experiment_id).trials] == [
        trial_id]


# --- user, group and membership ---------------------------------------------


def test_user_is_loaded_by_its_id_and_reprs_as_a_fact(clean_store):
    """A user is loaded by the id it was created with, and its fact doubles
    the backslash of ``host\\login``, as a quoted Prolog atom must
    """
    User.create(USER_ID, "alice")
    assert repr(User(USER_ID)) == "user('h\\\\alice', 'alice')."
    assert User.get_user(USER_ID).userLogin == "alice"
    assert User.get_user("nobody") is None


def test_trial_and_user_navigate_to_each_other(clean_store):
    """``Trial.user`` and ``User.trials`` follow the trial's ``user_id``"""
    trial_id = new_trial(TrialConfig("unfinished"))
    User.create(USER_ID, "alice")
    link_trial(trial_id, user_id=USER_ID)
    assert Trial(trial_id).user.id == USER_ID
    assert [trial.id for trial in User(USER_ID).trials] == [trial_id]


def test_group_is_created_loaded_and_deleted(clean_store):
    """``Group.create`` gives the group a UUID and ``Group.delete`` removes
    its row
    """
    group_id = Group.create(SimpleNamespace(name="g1")).id
    assert UUID.fullmatch(group_id), group_id
    assert repr(Group(group_id)) == "group('{}', 'g1').".format(group_id)
    Group.delete(group_id)
    assert sql('SELECT COUNT(*) AS n FROM "group"') == [{"n": 0}]
    assert list(Group.all()) == []


def test_member_of_group_links_a_user_to_a_group(member):
    """A membership reaches its user and its group, and both reach it and
    each other; ``list_members_Of_Group`` lists the users of one group
    """
    user_id, group_id, membership_id = member
    empty = Group.create(SimpleNamespace(name="g2")).id
    membership = MemberOfGroup(membership_id)
    assert repr(membership) == (
        "memberOfGroup('{}', 'h\\\\alice', '{}').".format(
            membership_id, group_id))
    assert membership.user.id == user_id
    assert membership.group.id == group_id
    assert [group.id for group in User(user_id).groups] == [group_id]
    assert [user.id for user in Group(group_id).users] == [user_id]
    assert [each.id for each in User(user_id).member_of_groups] == [
        membership_id]
    assert [each.id for each in Group(group_id).member_of_groups] == [
        membership_id]
    assert [user.id for user in User.list_members_Of_Group(group_id)] == [
        user_id]
    assert User.list_members_Of_Group(empty) == []


@pytest.mark.skipif(not FOREIGN_KEYS_OFF,
                    reason="this SQLite enforces foreign keys by default")
def test_deleting_a_group_with_a_member(member):
    """Today the membership survives its group: the row stays, the user
    still lists it, and it names a group that no longer exists

    Characterization of a defect. SQLite does not enforce foreign keys on
    this connection, so the ``ON DELETE CASCADE`` of ``memberOfGroup`` never
    runs.
    """
    user_id, group_id, membership_id = member
    Group.delete(group_id)
    assert sql("PRAGMA foreign_keys") == [{"foreign_keys": 0}]
    assert memberships_of(group_id) == [{"id": membership_id}]
    assert [each.id for each in User(user_id).member_of_groups] == [
        membership_id]
    assert MemberOfGroup(membership_id).group is None
    assert [user.id for user in User.list_members_Of_Group(group_id)] == [
        user_id]


@known_defects(GROUP_DELETE)
def test_deleting_a_group_with_a_member_desired(member):
    """Deleting a group deletes its memberships, as the ``ON DELETE
    CASCADE`` that ``memberOfGroup`` declares on ``groupId`` says"""
    user_id, group_id, _ = member
    Group.delete(group_id)
    left = memberships_of(group_id)
    assert not left, "memberships left for the deleted group: {}".format(
        len(left))
    assert list(User(user_id).member_of_groups) == []


# --- extended annotation ----------------------------------------------------


def test_extended_annotation_is_loaded_and_queried_by_trial_and_experiment(
        clean_store):
    """An annotation reprs its eight fields in declaration order, is found
    by its trial and by its experiment, and reaches both

    ``GetInfoByTrialId`` and ``GetInfoByExperimentId`` return the id, the
    format, the provenance type, the level, the related id and the
    description, in that order (their select lists). ``GetById`` uses
    ``.one()``: an unknown id raises ``NoResultFound``.
    """
    trial_id = new_trial(TrialConfig("unfinished"))
    experiment_id = Experiment.create(
        SimpleNamespace(name="exp1", description="first")).id
    fields = dict(
        annotation="note", description="why", annotationFormat="text",
        provenanceType="retrospective", annotationLevel="trial",
        relatedExperiment=experiment_id, relatedTrial=trial_id)
    annotation_id = ExtendedAnnotation.create(
        SimpleNamespace(**fields)).id
    annotation = ExtendedAnnotation(annotation_id)
    assert repr(annotation) == (
        "extendedAnnotation('{}', 'note', 'why', 'text', 'retrospective', "
        "'trial', '{}', '{}').".format(annotation_id, experiment_id,
                                       trial_id))
    assert ExtendedAnnotation.GetById(annotation_id).annotation == "note"
    info = (annotation_id, "text", "retrospective", "trial")
    assert [tuple(row) for row in ExtendedAnnotation.GetInfoByExperimentId(
        experiment_id)] == [info + (experiment_id, "why")]
    assert [tuple(row) for row in ExtendedAnnotation.GetInfoByTrialId(
        trial_id)] == [info + (trial_id, "why")]
    assert annotation.experiment.id == experiment_id
    assert annotation.trial.id == trial_id
    assert [each.id for each in Experiment(
        experiment_id).extended_annotations] == [annotation_id]
    assert [each.id for each in Trial(trial_id).extended_annotations] == [
        annotation_id]
    with pytest.raises(NoResultFound):
        ExtendedAnnotation.GetById("missing")


# --- Prolog predicates ------------------------------------------------------


def test_prolog_predicates_of_the_models(clean_store):
    """Today ``StageTags`` and ``FileAccess`` both describe their facts as
    ``access``, the only predicate name that two models share, and a stage
    tag's fact writes its id as a file access does, ``f<id>``

    Characterization of a defect: the stage tag's description was copied
    from the file access. The row is inserted through the table, since
    nothing outside ``now run`` creates a stage tag.
    """
    assert shared_predicates() == {"access": ["FileAccess", "StageTags"]}
    assert StageTags.prolog_description.name == "access"
    assert FileAccess.prolog_description.name == "access"
    relational.session.execute(StageTags.t.insert(), {
        "trial_id": "t1", "id": 1, "name": "result", "tag_name": "6"})
    relational.session.commit()
    assert repr(StageTags(("t1", 1))).startswith("access('t1', f1, ")


@known_defects(SHARED_PREDICATE)
def test_prolog_predicates_of_the_models_desired():
    """Each model's facts have a predicate of their own"""
    shared = shared_predicates()
    assert not shared, "; ".join(
        "{}: {}".format(name, ", ".join(models))
        for name, models in sorted(shared.items()))
