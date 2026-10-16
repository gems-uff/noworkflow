# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The collaboration routes of ``now vis`` that only read: GETs

The group widget lists ``/groups`` and ``/users``; the annotation widget
lists ``/experiments/<expCode>/extendedAnnotation`` or
``/trials/<trialCode>/extendedAnnotation`` and downloads
``/extendedAnnotation/<id>/annotation``; the history widget lists
``/collab/remotes/getall``; ``now pull`` reads
``/experiments/<expCode>/collab/{files,trialsids,usersids,bundle}`` from
the server. The routes that write (POST, DELETE, and the remote GETs that
change state) are #256's.

Two stores serve them:

- the shared two-trial weather store (``vis``), which has no experiment,
  group, annotation or remote: the empty answers, and the 400 of the
  ``collab`` routes for an experiment the store does not have;
- a two-trial store of this module (``collab``), where the fixture adds,
  through the models and never through the routes, an experiment that owns
  the first trial, an annotation of the experiment and one of that trial,
  a group with the store's user, and two remotes, one hidden. The tests
  only read it; its fingerprint is checked after each one.

The ``user`` table's id holds the hostname, and the bundle carries the
environment: they are compared into a boolean first, or counted, so that no
value reaches an assertion message. No known defect here; the download of
an unknown annotation crashes, which the frontend never asks for
(robustness, characterized).
"""
import email.message
import types

import pytest
from sqlalchemy.orm.exc import NoResultFound

from noworkflow.now.persistence import relational
from noworkflow.now.persistence.lightweight import (
    ExperimentLW, ExtendedAnnotationLW, GroupLW, MemberOfGroupLW,
)
from noworkflow.now.persistence.models import (
    Experiment, ExtendedAnnotation, Group, MemberOfGroup, Remote, Trial,
)
from noworkflow.tests.e2e.harness import NowProject, build_weather
from noworkflow.tests.helpers.persistence import connected_to

from .support import EXPERIMENT

INVALID_EXPERIMENT = "Invalid experiment ID"
COLLAB_ROUTES = ["collab/files", "collab/trialsids", "collab/usersids",
                 "collab/bundle?id={trial}"]
# What each list of a bundle holds, by the table it comes from.
BUNDLE_TABLES = {
    "activations": "activation",
    "arguments": "argument",
    "codeBlocks": "code_block",
    "codeComponents": "code_component",
    "compositions": "composition",
    "dependencies": "dependency",
    "environmentAttrs": "environment_attr",
    "evaluations": "evaluation",
    "fileAccesses": "file_access",
    "members": "member",
    "modules": "module",
}
VISIBLE_REMOTE = "http://remote.invalid/experiments/visible"
HIDDEN_REMOTE = "http://remote.invalid/experiments/hidden"


@pytest.fixture(scope="module")
def _collab_store(tmp_path_factory):
    """A two-trial store with collaboration rows, added through the models

    Returns the project and the ids the tests look for.
    """
    project = build_weather(
        NowProject(tmp_path_factory.mktemp("vis_collab")), trials=2)
    first, _ = [row["id"] for row in project.trials()]
    user = project.query("SELECT id FROM user")[0]["id"]
    with connected_to(project.path):
        experiment = Experiment.create(
            ExperimentLW("weather", "", "the weather corpus"))
        experiment_note = ExtendedAnnotation.create(ExtendedAnnotationLW(
            None, "a note on the experiment", "experiment note",
            "plainText", "prospective", "Experiment", experiment.id, None))
        trial_note = ExtendedAnnotation.create(ExtendedAnnotationLW(
            None, '{"checked": true}', "trial note", "json",
            "retrospective", "Trial", None, first))
        group = Group.create(GroupLW(None, "weather team", None))
        MemberOfGroup.create(MemberOfGroupLW(None, group.id, user))
        Remote.create(VISIBLE_REMOTE, "visible")
        Remote.create(HIDDEN_REMOTE, "hidden")
        session = relational.session
        # Remote.create ignores ``hide``; the trial of an experiment comes
        # from ``now pull`` or ``now import`` (#247), not from ``now run``.
        session.query(Remote.m).filter(
            Remote.m.server_url == HIDDEN_REMOTE).update({"hide": True})
        session.query(Trial.m).filter(Trial.m.id == first).update(
            {"experiment_id": experiment.id})
        session.commit()
    return types.SimpleNamespace(
        project=project, experiment=experiment.id, trial=first,
        experiment_note=experiment_note.id, trial_note=trial_note.id,
        group=group.id)


@pytest.fixture
def collab(_collab_store, vis_for):
    """The vis of the module's collaboration store: read-only

    ``ids`` holds what the fixture added.
    """
    project = _collab_store.project
    before = project.fingerprint()
    vis = vis_for(project)
    vis.ids = _collab_store
    yield vis
    same = project.fingerprint() == before
    assert same, "the test changed the module's collaboration store"


def attachment_name(response):
    """The file name of a ``Content-Disposition: attachment`` header"""
    header = email.message.Message()
    header["Content-Disposition"] = response.headers["Content-Disposition"]
    assert header.get_content_disposition() == "attachment"
    return header.get_filename()


def annotation_listing(project, column, value, related):
    """What the annotation listings give for the rows where ``column`` is
    ``value``: the row without its content, and only the ``related`` side
    """
    rows = project.query(
        'SELECT * FROM "extendedAnnotation" WHERE "{}" = ?'.format(column),
        value)
    return [{
        "id": row["id"],
        "annotation": "",
        "description": row["description"],
        "annotationFormat": row["annotationFormat"],
        "provenanceType": row["provenanceType"],
        "annotationLevel": row["annotationLevel"],
        "relatedExperiment": (row["relatedExperiment"]
                              if related == "relatedExperiment" else ""),
        "relatedTrial": (row["relatedTrial"]
                         if related == "relatedTrial" else ""),
    } for row in rows]


# --- the weather store: nothing to collaborate on ---------------------------


def test_groups_is_empty_without_groups(vis):
    """``/groups`` answers an empty JSON list on a store without groups"""
    assert vis.project.query('SELECT * FROM "group"') == []
    assert vis.json("/groups") == []


def test_users_lists_the_user_table(vis):
    """``/users`` gives the id and the login of each row of ``user``"""
    users = vis.json("/users")
    rows = vis.project.query('SELECT id, userLogin FROM "user"')
    assert rows, "now run records the user who ran the trial"
    assert all(set(user) == {"id", "userLogin"} for user in users)
    same = sorted((user["id"], user["userLogin"]) for user in users) == sorted(
        (row["id"], row["userLogin"]) for row in rows)
    assert same, "/users differs from the user table"


def test_users_include_the_user_of_every_trial(vis):
    """Every trial's ``user_id`` is the id of a user ``/users`` lists"""
    listed = {user["id"] for user in vis.json("/users")}
    recorded = {row["user_id"] for row in vis.project.trials()}
    same = recorded <= listed
    assert same, "a trial's user is not listed"


def test_experiment_annotations_are_empty_without_annotations(vis):
    """The annotations of an experiment the store does not have: ``[]``"""
    assert vis.project.query('SELECT * FROM "extendedAnnotation"') == []
    route = "/experiments/{}/extendedAnnotation".format(EXPERIMENT)
    assert vis.json(route) == []


def test_trial_annotations_are_empty_without_annotations(vis):
    """Each trial of the weather store lists no annotation"""
    for trial in vis.trial_ids:
        assert vis.json("/trials/{}/extendedAnnotation".format(trial)) == []


def test_annotations_url_of_a_page_without_experiment_answers_404(vis):
    """On the page of a store without experiments the annotation widget
    asks ``/experiments//extendedAnnotation`` (an empty code), which no
    route declares: 404, which the widget reads as "no annotation"
    """
    response = vis.get("/experiments//extendedAnnotation")
    assert response.status_code == 404


def test_annotation_content_of_an_unknown_id_crashes(vis):
    """Downloading an annotation that does not exist crashes in
    ``ExtendedAnnotation.GetById``, which uses ``one()`` (robustness: the
    widget only links the annotations it listed)
    """
    with pytest.raises(NoResultFound):
        vis.get("/extendedAnnotation/no-such-annotation/annotation")


def test_remotes_is_empty_without_remotes(vis):
    """``/collab/remotes/getall`` answers no remote on the weather store"""
    assert vis.project.query("SELECT * FROM remote") == []
    assert vis.json("/collab/remotes/getall") == {"remotes": []}


@pytest.mark.parametrize("path", COLLAB_ROUTES)
def test_collab_route_of_an_unknown_experiment_answers_400(vis, path):
    """The ``collab`` GETs that ``now pull`` calls answer 400 with the JSON
    string that ``now pull`` and ``now push`` compare against
    """
    assert vis.project.query(
        "SELECT * FROM experiment WHERE id = ?", EXPERIMENT) == []
    route = "/experiments/{}/{}".format(
        EXPERIMENT, path.format(trial=vis.trial_ids[0]))
    assert vis.json(route, status=400) == INVALID_EXPERIMENT


# --- a store with an experiment, annotations, a group and remotes -----------


def test_experiment_annotations_list_the_experiments_rows(collab):
    """An experiment lists its annotations without their content and
    without a trial
    """
    ids = collab.ids
    route = "/experiments/{}/extendedAnnotation".format(ids.experiment)
    listing = collab.json(route)
    assert listing == annotation_listing(
        collab.project, "relatedExperiment", ids.experiment,
        "relatedExperiment")
    assert [note["id"] for note in listing] == [ids.experiment_note]


def test_trial_annotations_list_the_trials_rows(collab):
    """A trial lists its own annotations, without content or experiment;
    the other trial lists none
    """
    ids = collab.ids
    for trial in collab.trial_ids:
        listing = collab.json("/trials/{}/extendedAnnotation".format(trial))
        assert listing == annotation_listing(
            collab.project, "relatedTrial", trial, "relatedTrial")
        expected = [ids.trial_note] if trial == ids.trial else []
        assert [note["id"] for note in listing] == expected


@pytest.mark.parametrize("which, extension", [
    ("experiment_note", "txt"), ("trial_note", "json"),
])
def test_annotation_content_downloads_as_an_attachment(
        collab, which, extension):
    """The content of an annotation downloads as ``<id>.<format>``, with
    ``plainText`` saved as ``.txt``
    """
    note = getattr(collab.ids, which)
    response = collab.get("/extendedAnnotation/{}/annotation".format(note))
    assert response.status_code == 200
    assert response.mimetype == "application/octet-stream"
    assert attachment_name(response) == "{}.{}".format(note, extension)
    stored = collab.project.query(
        'SELECT annotation FROM "extendedAnnotation" WHERE id = ?', note)
    assert response.get_data(as_text=True) == stored[0]["annotation"]


def test_groups_lists_each_group_with_its_members(collab):
    """``/groups`` gives each group's id and name, and its members as
    ``/users`` gives them
    """
    groups = collab.json("/groups")
    rows = collab.project.query('SELECT id, name FROM "group"')
    assert [(group["id"], group["name"]) for group in groups] == [
        (row["id"], row["name"]) for row in rows]
    assert [group["id"] for group in groups] == [collab.ids.group]
    members = collab.project.query(
        'SELECT "user".id, "user".userLogin FROM "memberOfGroup" '
        'JOIN "user" ON "user".id = "memberOfGroup".userId '
        'WHERE "memberOfGroup".groupId = ?', collab.ids.group)
    assert members, "the fixture added the store's user"
    same = groups[0]["members"] == members
    assert same, "the members differ from memberOfGroup"


def test_remotes_lists_only_the_visible_remotes(collab):
    """``/collab/remotes/getall`` gives every remote that is not hidden"""
    rows = collab.project.query(
        "SELECT id, server_url, name, used, hide FROM remote "
        "WHERE NOT hide ORDER BY id")
    answer = collab.json("/collab/remotes/getall")["remotes"]
    assert answer == [dict(row, used=bool(row["used"]),
                           hide=bool(row["hide"])) for row in rows]
    assert [remote["server_url"] for remote in answer] == [VISIBLE_REMOTE]


def test_trialsids_lists_the_trials_of_the_experiment(collab):
    """``collab/trialsids`` gives the ids of the experiment's trials"""
    ids = collab.ids
    route = "/experiments/{}/collab/trialsids".format(ids.experiment)
    expected = [row["id"] for row in collab.project.query(
        "SELECT id FROM trial WHERE experiment_id = ?", ids.experiment)]
    assert collab.json(route) == expected == [ids.trial]


def test_usersids_lists_every_user(collab):
    """``collab/usersids`` gives the id of every user of the store"""
    route = "/experiments/{}/collab/usersids".format(collab.ids.experiment)
    answer = collab.json(route)
    rows = collab.project.query('SELECT id FROM "user"')
    same = sorted(answer) == sorted(row["id"] for row in rows)
    assert same, "collab/usersids differs from the user table"


def test_files_lists_every_content_hash(collab):
    """``collab/files`` gives the hash of every file of the content store"""
    content = collab.project.store / "content"
    if not content.is_dir():
        pytest.skip("the store does not use the plain content engine")
    stored = sorted(path.parent.name + path.name
                    for path in content.glob("*/*") if path.is_file())
    route = "/experiments/{}/collab/files".format(collab.ids.experiment)
    assert sorted(collab.json(route)) == stored


def test_bundle_carries_the_rows_of_the_requested_trial(collab):
    """``collab/bundle?id=<trial>`` gives that trial and, for each table of
    its provenance, as many rows as the store has for it

    Today it carries no user: ``getBundle`` never passes user ids to
    ``export_bundle``. A user's id holds the hostname, so the list is
    compared into a boolean.
    """
    ids = collab.ids
    route = "/experiments/{}/collab/bundle?id={}".format(
        ids.experiment, ids.trial)
    bundle = collab.json(route)
    assert set(bundle) == set(BUNDLE_TABLES) | {"trials", "users"}
    assert [trial["id"] for trial in bundle["trials"]] == [ids.trial]
    for key, table in BUNDLE_TABLES.items():
        assert {row["trial_id"] for row in bundle[key]} <= {ids.trial}, key
        assert len(bundle[key]) == collab.project.count(table, ids.trial), (
            key)
    assert bundle["activations"], "the trial has activations"
    no_user = bundle["users"] == []
    assert no_user, "the bundle carries {} users".format(
        len(bundle["users"]))


def test_bundle_ignores_ids_that_name_no_trial(collab):
    """``now pull`` asks ``?id=0&&id=<trial>...``: the ids that name no
    trial change nothing in the bundle
    """
    ids = collab.ids
    base = "/experiments/{}/collab/bundle?".format(ids.experiment)
    plain = collab.json(base + "id={}".format(ids.trial))
    pulled = collab.json(base + "id=0&&id={}".format(ids.trial))
    same = pulled == plain
    assert same, "the pull-shaped request gives another bundle"


def test_bundle_of_no_trial_is_empty(collab):
    """Without an id, every list of the bundle is empty"""
    route = "/experiments/{}/collab/bundle".format(collab.ids.experiment)
    bundle = collab.json(route)
    assert all(rows == [] for rows in bundle.values()), sorted(
        key for key, rows in bundle.items() if rows)

