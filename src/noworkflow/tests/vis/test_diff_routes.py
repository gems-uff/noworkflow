# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The diff routes of ``now vis``: info, dependencies, environment, accesses

``/diff/<trial1>/<trial2>/{info,dependencies,environment,file_accesses}.json``
(and the same paths under ``/experiments/<expCode>/``) feed the Diff Info
panel that the history opens when two trials are compared
(``src/frontend/packages/nowvis/src/info/diff_info.ts``). Each view builds
``models.diff.Diff``: ``info.json`` serves both trials and the attributes
that differ (``diff_dict``), the other three the added, removed and
replaced modules, environment attributes and file accesses (``diff_set``,
which pairs a removed element with an added one of the same name, one to
one, the same mode first, in the order of the trial, #360).

Expected values come from the store (SQL on the trial, module,
code_block, environment_attr and file_access tables) and from the weather
corpus, never from literals. The shared two-trial store (``vis``) answers
the read-only cases: the second trial changed the last row of
``data2.dat``. ``changed`` is a store of this module's own, read-only too,
with the trials the shared one lacks: a local module edited between two
runs, and a script that writes a file and reads it back. Environment
values are compared with the store, and the trials' ``user_id`` (the
hostname) checked by type, through a name (``same = a == b; assert same,
...``), so pytest never prints them; messages name the attribute, never
its value. ``diff_set`` builds sets, which the routes serve in their
iteration order, so lists are compared without their order.

Known defects, each with a characterization and a ``_desired`` twin:

- ``#363``: ``trial1`` and ``trial2`` carry no
  ``code_hash``, which the panel shows when both trials ran the same code.
- ``#363``: the accesses carry neither ``stack`` nor
  ``timestamp``, which the panel shows.
- ``#366``: start and finish are the local
  wall-clock times labeled GMT; the twin's mark applies only where the
  local time ``now run`` records is not UTC.

An unknown trial id raises ``RuntimeError`` (a 500): characterized only,
since the frontend builds these URLs from the trials of the history.
Nothing here depends on the Python version (measured on macOS arm64 with
Python 3.11 to 3.15).
"""

import uuid
from datetime import datetime

import pytest
from werkzeug.http import http_date

from noworkflow.tests.e2e.harness import CORPUS, WEATHER_ARGS, NowProject

from .support import (
    LOCAL_TIME_AS_GMT,
    NOW_RUN_UTC_OFFSET,
    NOW_RUN_ZONE,
    Defect,
    known_defects,
    served_instant,
)

KINDS = ("info", "dependencies", "environment", "file_accesses")
# The lists of each route that serves a diff_set: (added, removed, replaced).
LISTS = {
    "dependencies": ("modules_added", "modules_removed", "modules_replaced"),
    "environment": ("env_added", "env_removed", "env_replaced"),
    "file_accesses": ("fa_added", "fa_removed", "fa_replaced"),
}
# What the Diff Info panel shows of each access (FileAccessData).
ACCESS_FIELDS_SHOWN = ("stack", "timestamp")

# The `changed` store: simulator.py gains a line between its trials 1 and 2;
# rw.py writes its argument to out.txt and reads it back (trials 3 and 4).
SIMULATOR_CHANGE = "\n\nVERSION = 2\n"
RW_SCRIPT = (
    "import sys\n"
    "with open('out.txt', 'w') as handle:\n"
    "    handle.write(sys.argv[1])\n"
    "with open('out.txt') as handle:\n"
    "    print(handle.read())\n"
)


INFO_CODE_HASH = Defect(
    reason="#363: the info.json view serializes trial1 "
    "and trial2 with extra=('duration_text',) only, so they carry no "
    "code_hash, which diff_info.ts shows when both trials ran the "
    "same code",
    signature="code_hash missing from ['trial1', 'trial2']",
)
ACCESS_FIELDS = Defect(
    reason="#363: the file_accesses.json view of a "
    "diff serializes each access with to_dict() alone, so the items "
    "carry neither the stack (which trials/<tid>/file_accesses.json "
    "sends) nor the timestamp that diff_info.ts shows",
    signature="accesses without the fields the Diff panel shows: "
    "['stack', 'timestamp']",
)


def diff_route(kind, trial1, trial2):
    return "/diff/{}/{}/{}.json".format(trial1, trial2, kind)


def stored_time(text):
    """A TIMESTAMP of the store as the naive datetime the model reads"""
    return datetime.fromisoformat(text)


def duration(row):
    return stored_time(row["finish"]) - stored_time(row["start"])


def trial_rows(project, *ids):
    rows = {row["id"]: row for row in project.trials()}
    return [rows[trial_id] for trial_id in ids]


def main_code_hash(project, row):
    """The code hash of a trial's main block, as Trial.code_hash gives it"""
    found = project.query(
        "SELECT code_hash FROM code_block WHERE trial_id = ? AND id = ?",
        row["id"],
        row["main_id"],
    )
    return found[0]["code_hash"] if found else ""


def ident(item):
    """What names a serialized row: its trial and its id in the trial"""
    return item["trial_id"], item["id"]


def idents(items):
    return sorted(ident(item) for item in items)


def pair_idents(pairs):
    return sorted((ident(first), ident(second)) for first, second in pairs)


def served_items(kind, data):
    """Every row a diff_set route lists: added, removed and both sides of
    each replaced pair
    """
    added, removed, replaced = LISTS[kind]
    return (
        data[added] + data[removed] + [item for pair in data[replaced] for item in pair]
    )


def canonical(kind, data):
    """``data`` with the lists of a diff_set in a fixed order"""
    if kind not in LISTS:
        return data
    added, removed, replaced = LISTS[kind]
    result = dict(data)
    result[added] = sorted(data[added], key=ident)
    result[removed] = sorted(data[removed], key=ident)
    result[replaced] = sorted(
        data[replaced], key=lambda pair: (ident(pair[0]), ident(pair[1]))
    )
    return result


def without_user(item):
    return {key: value for key, value in item.items() if key != "user_id"}


def access_rows(project, trial_id):
    return project.query(
        "SELECT * FROM file_access WHERE trial_id = ? ORDER BY id", trial_id
    )


def env_pairs(project, trial_id):
    """``{(name, value)}`` of a trial's environment: never print it"""
    return {
        (row["name"], row["value"])
        for row in project.query(
            "SELECT name, value FROM environment_attr WHERE trial_id = ?", trial_id
        )
    }


def module_rows(project, trial_id):
    """A trial's modules with the code hash of their code block"""
    return project.query(
        "SELECT module.*, code_block.code_hash AS code_hash FROM module "
        "LEFT JOIN code_block ON code_block.trial_id = module.trial_id "
        "AND code_block.id = CAST(module.code_block_id AS INTEGER) "
        "WHERE module.trial_id = ? ORDER BY module.id",
        trial_id,
    )


@pytest.fixture(scope="module")
def _changed_store(tmp_path_factory):
    """Four trials: the weather corpus before and after simulator.py
    changes (1, 2), then rw.py with two arguments (3, 4)
    """
    project = NowProject(tmp_path_factory.mktemp("diff_changed"))
    project.copy_corpus("weather")
    project.run(*WEATHER_ARGS)
    simulator = (CORPUS / "weather" / "simulator.py").read_text(encoding="utf-8")
    project.write("simulator.py", simulator + SIMULATOR_CHANGE)
    project.run(*WEATHER_ARGS)
    project.write("rw.py", RW_SCRIPT)
    project.run("run", "rw.py", "first")
    project.run("run", "rw.py", "second")
    return project


@pytest.fixture
def changed(_changed_store, vis_for):
    """The vis of ``_changed_store``, which no test may change"""
    before = _changed_store.fingerprint()
    yield vis_for(_changed_store)
    assert _changed_store.fingerprint() == before, (
        "a diff route changed the store of test_diff_routes"
    )


# --- info.json ---------------------------------------------------------------


def test_info_serves_both_trials_as_the_store_records_them(vis):
    """``trial1`` and ``trial2`` hold every column of their trial row, with
    the store's values, and ``duration_text`` is finish minus start
    (``user_id`` by type; start and finish in the format test below)
    """
    id1, id2 = vis.trial_ids
    data = vis.json(diff_route("info", id1, id2))
    assert set(data) == {"trial1", "trial2", "trial"}
    for name, row in zip(("trial1", "trial2"), trial_rows(vis.project, id1, id2)):
        served = data[name]
        assert set(row) <= set(served), "{}: columns missing".format(name)
        # Through a name: pytest would print the argument of isinstance().
        user_is_text = isinstance(served["user_id"], str)
        assert user_is_text, "{}: user_id is not text".format(name)
        expected = without_user(row)
        expected.pop("start")
        expected.pop("finish")
        # The names of the columns that differ, never the values: the path
        # names the user's temporary directory.
        differ = sorted(key for key in expected if served[key] != expected[key])
        assert not differ, "{}: {} differ from the store".format(name, differ)
        assert served["duration_text"] == str(duration(row)), name
        assert isinstance(served["start"], str), name
        assert isinstance(served["finish"], str), name


def test_info_trial_holds_the_attributes_that_differ(vis):
    """``trial`` maps each attribute whose value differs between the two
    trial rows (``id`` aside), the duration and the main code hash included,
    to ``[first, second]``; the weather pair runs the same code. Start and
    finish are served as ``trial1`` and ``trial2`` serve them (their format
    is the subject of the time tests below)
    """
    id1, id2 = vis.trial_ids
    row1, row2 = trial_rows(vis.project, id1, id2)
    hash1, hash2 = (
        main_code_hash(vis.project, row1),
        main_code_hash(vis.project, row2),
    )
    assert hash1 and hash1 == hash2, "the weather pair runs the same code"
    data = vis.json(diff_route("info", id1, id2))
    expected_keys = {key for key in row1 if key != "id" and row1[key] != row2[key]}
    if duration(row1) != duration(row2):
        expected_keys.add("duration_text")
    trial = data["trial"]
    assert set(trial) == expected_keys
    assert "start" in trial and "finish" in trial, "two runs, two times"
    for key, pair in trial.items():
        assert isinstance(pair, list) and len(pair) == 2, key
        if key == "user_id":
            # Through a name: pytest would print the values.
            both_text = all(isinstance(value, str) for value in pair)
            assert both_text, "user_id is not text"
        elif key == "duration_text":
            assert pair == [str(duration(row1)), str(duration(row2))], key
        elif key in ("start", "finish"):
            assert pair == [data["trial1"][key], data["trial2"][key]], key
        else:
            assert pair == [row1[key], row2[key]], key


def test_info_trials_carry_no_code_hash(vis):
    """Characterization (#363): ``trial1`` and
    ``trial2`` hold the trial's columns and ``duration_text``, nothing else
    """
    id1, id2 = vis.trial_ids
    data = vis.json(diff_route("info", id1, id2))
    columns = set(vis.project.trials()[0])
    for name in ("trial1", "trial2"):
        assert set(data[name]) == columns | {"duration_text"}, name


@known_defects(INFO_CODE_HASH)
def test_info_trials_carry_no_code_hash_desired(vis):
    """``trial1`` and ``trial2`` carry the code hash of their main block,
    which the panel shows as the header of a diff between equal codes
    """
    id1, id2 = vis.trial_ids
    data = vis.json(diff_route("info", id1, id2))
    missing = [name for name in ("trial1", "trial2") if "code_hash" not in data[name]]
    assert not missing, "code_hash missing from {}".format(missing)
    for name, row in zip(("trial1", "trial2"), trial_rows(vis.project, id1, id2)):
        assert data[name]["code_hash"] == main_code_hash(vis.project, row), name


def test_info_times_are_local_times_labeled_gmt(vis):
    """Characterization (#366): start and finish
    are the naive times of the store formatted as HTTP dates, which say
    GMT whatever zone ``now run`` recorded them in
    """
    id1, id2 = vis.trial_ids
    data = vis.json(diff_route("info", id1, id2))
    for name, row in zip(("trial1", "trial2"), trial_rows(vis.project, id1, id2)):
        for key in ("start", "finish"):
            served = data[name][key]
            # A boolean: both sides together would tell the machine's zone.
            naive = served == http_date(stored_time(row[key]))
            assert naive, "{} {}: not the store's naive time as an HTTP date".format(
                name, key
            )
            assert served.endswith(" GMT"), (name, key)


@known_defects(LOCAL_TIME_AS_GMT)
def test_info_times_are_local_times_labeled_gmt_desired(vis):
    """Read as a client reads them, start and finish name the instants the
    trial started and finished (to the second)
    """
    id1, id2 = vis.trial_ids
    data = vis.json(diff_route("info", id1, id2))
    for name, row in zip(("trial1", "trial2"), trial_rows(vis.project, id1, id2)):
        for key in ("start", "finish"):
            recorded = stored_time(row[key]).replace(tzinfo=NOW_RUN_ZONE)
            gap = (served_instant(data[name][key]) - recorded).total_seconds()
            # Today's gap is the zone's offset (the local clock read as
            # UTC), give or take the truncation to the second. Booleans
            # only: the gap would tell the machine's zone.
            on_time = abs(gap) < 1
            shifted = abs(gap - NOW_RUN_UTC_OFFSET) < 1
            assert on_time, "{} {}: not the recorded instant{}".format(
                name,
                key,
                ", off by the UTC offset of now run's zone" if shifted else "",
            )


# --- dependencies.json --------------------------------------------------------


def test_dependencies_of_the_weather_pair(vis):
    """Both runs import the same simulator.py: no module added, removed or
    replaced, and ``t1_path``/``t2_path`` are the trials' paths
    """
    id1, id2 = vis.trial_ids
    row1, row2 = trial_rows(vis.project, id1, id2)
    modules1, modules2 = (
        [
            (row["name"], row["version"], row["code_hash"])
            for row in module_rows(vis.project, trial_id)
        ]
        for trial_id in (id1, id2)
    )
    assert modules1 and modules1 == modules2, "the same modules"
    data = vis.json(diff_route("dependencies", id1, id2))
    assert data == {
        "modules_added": [],
        "modules_removed": [],
        "modules_replaced": [],
        "t1_path": row1["path"],
        "t2_path": row2["path"],
    }


def test_dependencies_replace_a_local_module_that_changed(changed):
    """A local module whose code changed between two trials is one
    replaced pair, [first trial's module, second's], each with the code
    hash of its code block
    """
    id1, id2 = changed.trial_ids[:2]
    modules1 = module_rows(changed.project, id1)
    modules2 = module_rows(changed.project, id2)
    assert [row["name"] for row in modules1] == ["simulator"]
    assert [row["name"] for row in modules2] == ["simulator"]
    assert modules1[0]["code_hash"] != modules2[0]["code_hash"]
    data = changed.json(diff_route("dependencies", id1, id2))
    assert data["modules_added"] == []
    assert data["modules_removed"] == []
    assert len(data["modules_replaced"]) == 1
    for served, row in zip(data["modules_replaced"][0], (modules1[0], modules2[0])):
        assert ident(served) == ident(row)
        assert served["name"] == row["name"]
        assert served["path"] == row["path"]
        assert served["code_hash"] == row["code_hash"]


# --- environment.json ---------------------------------------------------------


def test_environment_replaced_names_are_the_attributes_that_changed(vis):
    """``env_replaced`` holds the attributes whose value differs between
    the trials, ``env_added``/``env_removed`` those of one trial only
    (names compared, never values)
    """
    id1, id2 = vis.trial_ids
    pairs1 = env_pairs(vis.project, id1)
    pairs2 = env_pairs(vis.project, id2)
    removed = {name for name, _ in pairs1 - pairs2}
    added = {name for name, _ in pairs2 - pairs1}
    data = vis.json(diff_route("environment", id1, id2))
    served = {
        "replaced": sorted(first["name"] for first, _ in data["env_replaced"]),
        "added": sorted(item["name"] for item in data["env_added"]),
        "removed": sorted(item["name"] for item in data["env_removed"]),
    }
    assert served == {
        "replaced": sorted(added & removed),
        "added": sorted(added - removed),
        "removed": sorted(removed - added),
    }
    assert served["replaced"], "two runs differ at least in the pid"


def test_environment_items_are_the_stored_rows(vis):
    """Every item is an environment_attr row (id, name, trial_id, value),
    each pair [first trial's, second's] of one name with two values;
    compared without printing a value
    """
    id1, id2 = vis.trial_ids
    data = vis.json(diff_route("environment", id1, id2))
    rows = {
        ident(row): row
        for row in vis.project.query(
            "SELECT * FROM environment_attr WHERE trial_id IN (?, ?)", id1, id2
        )
    }
    items = served_items("environment", data)
    assert items, "two runs differ at least in the pid"
    for item in items:
        assert set(item) == {"id", "name", "trial_id", "value"}, item["name"]
        # Through a name: pytest would print the argument of isinstance().
        value_is_text = isinstance(item["value"], str)
        assert value_is_text, "{}: value is not text".format(item["name"])
        same = item == rows.get(ident(item))
        assert same, "{}: not its stored row".format(item["name"])
    for first, second in data["env_replaced"]:
        assert (first["trial_id"], second["trial_id"]) == (id1, id2)
        assert first["name"] == second["name"]
        differ = first["value"] != second["value"]
        assert differ, "{}: replaced by an equal value".format(first["name"])


# --- file_accesses.json -------------------------------------------------------


def test_file_accesses_replaced_are_the_files_whose_content_changed(vis):
    """The accesses of a file whose hashes differ between the two trials'
    file_access rows are replaced, [first trial's row, second's]; those
    with the same hashes are left out (the second trial changed data2.dat,
    and with it output.csv)
    """
    id1, id2 = vis.trial_ids
    rows1 = {row["name"]: row for row in access_rows(vis.project, id1)}
    rows2 = {row["name"]: row for row in access_rows(vis.project, id2)}
    assert len(rows1) == len(access_rows(vis.project, id1)), "one per file"
    assert len(rows2) == len(access_rows(vis.project, id2)), "one per file"
    hashes = ("content_hash_before", "content_hash_after")
    replaced = sorted(
        (ident(rows1[name]), ident(rows2[name]))
        for name in set(rows1) & set(rows2)
        if any(rows1[name][key] != rows2[name][key] for key in hashes)
    )
    assert set(rows1) >= {"data1.dat", "data2.dat"}
    data = vis.json(diff_route("file_accesses", id1, id2))
    assert idents(data["fa_added"]) == sorted(
        ident(rows2[name]) for name in set(rows2) - set(rows1)
    )
    assert idents(data["fa_removed"]) == sorted(
        ident(rows1[name]) for name in set(rows1) - set(rows2)
    )
    assert pair_idents(data["fa_replaced"]) == replaced
    names = {first["name"] for first, _ in data["fa_replaced"]}
    assert "data2.dat" in names and "data1.dat" not in names


def test_file_access_items_are_the_stored_rows(vis):
    """Each served access holds its file_access row, and ``t1_path``/
    ``t2_path`` are the trials' paths
    """
    id1, id2 = vis.trial_ids
    row1, row2 = trial_rows(vis.project, id1, id2)
    rows = {
        ident(row): row
        for trial_id in (id1, id2)
        for row in access_rows(vis.project, trial_id)
    }
    data = vis.json(diff_route("file_accesses", id1, id2))
    assert (data["t1_path"], data["t2_path"]) == (row1["path"], row2["path"])
    items = served_items("file_accesses", data)
    assert items, "the weather pair has replaced accesses"
    for item in items:
        row = rows[ident(item)]
        assert {key: item[key] for key in row} == row


def test_file_access_items_carry_only_the_columns(vis):
    """Characterization (#363): an access is its
    file_access columns, without the stack and the timestamp
    """
    id1, id2 = vis.trial_ids
    columns = set(access_rows(vis.project, id1)[0])
    items = served_items(
        "file_accesses", vis.json(diff_route("file_accesses", id1, id2))
    )
    assert items, "the weather pair has replaced accesses"
    for item in items:
        assert set(item) == columns, item["name"]


@known_defects(ACCESS_FIELDS)
def test_file_access_items_carry_only_the_columns_desired(vis):
    """Each access carries what the Diff panel shows of it: the stack that
    the trial's own file_accesses.json serves for it, and a timestamp that
    lies the stored checkpoint after the trial's start as info.json serves
    it, to the second (the zone the times are served in cancels out)
    """
    id1, id2 = vis.trial_ids
    items = served_items(
        "file_accesses", vis.json(diff_route("file_accesses", id1, id2))
    )
    assert items, "the weather pair has replaced accesses"
    missing = sorted(
        {field for item in items for field in ACCESS_FIELDS_SHOWN if field not in item}
    )
    assert not missing, "accesses without the fields the Diff panel shows: {}".format(
        missing
    )
    rows = {
        ident(row): row
        for trial_id in (id1, id2)
        for row in access_rows(vis.project, trial_id)
    }
    info = vis.json(diff_route("info", id1, id2))
    starts = {
        info[name]["id"]: served_instant(info[name]["start"])
        for name in ("trial1", "trial2")
    }
    stacks = {}
    for trial_id in (id1, id2):
        for access in vis.json("/trials/{}/file_accesses.json".format(trial_id))[
            "file_accesses"
        ]:
            stacks[ident(access)] = access["stack"]
    for item in items:
        assert item["stack"] == stacks[ident(item)], item["name"]
        after_start = (
            served_instant(item["timestamp"]) - starts[item["trial_id"]]
        ).total_seconds()
        checkpoint = rows[ident(item)]["checkpoint"]
        assert abs(after_start - checkpoint) < 1, item["name"]


def rw_accesses(project, trial_id):
    """``{mode: row}`` of the out.txt accesses of an rw.py trial"""
    rows = access_rows(project, trial_id)
    assert [row["name"] for row in rows] == ["out.txt", "out.txt"]
    by_mode = {row["mode"]: row for row in rows}
    assert set(by_mode) == {"w", "r"}
    return by_mode


def test_accesses_to_one_file_in_two_modes_pair_by_mode(changed):
    """When a write and a read of one file both change, the write of the
    first trial is paired with the write of the second and the read with
    the read; nothing is added or removed. Until #204 both accesses of the
    second trial were paired with one access of the first, by name alone,
    and the other was listed as removed (#360)
    """
    id3, id4 = changed.trial_ids[2:]
    rows3 = rw_accesses(changed.project, id3)
    rows4 = rw_accesses(changed.project, id4)
    expected = sorted((ident(rows3[mode]), ident(rows4[mode])) for mode in ("w", "r"))
    data = changed.json(diff_route("file_accesses", id3, id4))
    served = {
        "added": idents(data["fa_added"]),
        "removed": idents(data["fa_removed"]),
        "replaced": pair_idents(data["fa_replaced"]),
    }
    assert served == {"added": [], "removed": [], "replaced": expected}


# --- every route --------------------------------------------------------------


def test_a_trial_diffed_with_itself_has_no_difference(vis):
    """Comparing a trial with itself: no attribute differs, both sides are
    the same trial, and no module, attribute or access is listed
    """
    trial_id = vis.trial_ids[1]
    info = vis.json(diff_route("info", trial_id, trial_id))
    assert info["trial"] == {}
    same = info["trial1"] == info["trial2"]
    assert same, "trial1 and trial2 differ"
    assert info["trial1"]["id"] == trial_id
    for kind, names in LISTS.items():
        data = vis.json(diff_route(kind, trial_id, trial_id))
        assert {name: data[name] for name in names} == {name: [] for name in names}, (
            kind
        )


def test_the_reversed_pair_swaps_the_info(vis):
    """``diff/t2/t1``: trial1 and trial2 swap, and each differing
    attribute holds its two values in the other order
    """
    id1, id2 = vis.trial_ids
    forward = vis.json(diff_route("info", id1, id2))
    backward = vis.json(diff_route("info", id2, id1))
    swapped = (
        backward["trial1"] == forward["trial2"]
        and backward["trial2"] == forward["trial1"]
    )
    assert swapped, "trial1 and trial2 are not swapped"
    assert set(backward["trial"]) == set(forward["trial"])
    for key, pair in without_user(forward["trial"]).items():
        assert backward["trial"][key] == pair[::-1], key


@pytest.mark.parametrize("kind", sorted(LISTS))
def test_the_reversed_pair_swaps_each_list(vis, kind):
    """``diff/t2/t1``: what was added is removed and the reverse, each
    replaced pair is swapped, and so are the paths
    """
    id1, id2 = vis.trial_ids
    added, removed, replaced = LISTS[kind]
    forward = vis.json(diff_route(kind, id1, id2))
    backward = vis.json(diff_route(kind, id2, id1))
    assert idents(backward[added]) == idents(forward[removed])
    assert idents(backward[removed]) == idents(forward[added])
    assert pair_idents(backward[replaced]) == sorted(
        (second, first) for first, second in pair_idents(forward[replaced])
    )
    if "t1_path" in forward:
        assert (backward["t1_path"], backward["t2_path"]) == (
            forward["t2_path"],
            forward["t1_path"],
        )


@pytest.mark.parametrize("kind", KINDS)
def test_the_experiment_form_serves_the_same_json(vis, kind):
    """Under ``/experiments/<expCode>/`` each route answers what it answers
    at the root: these views ignore the experiment
    """
    id1, id2 = vis.trial_ids
    path = diff_route(kind, id1, id2).lstrip("/")
    root, experiment = (canonical(kind, vis.json(route)) for route in vis.routes(path))
    same = root == experiment
    assert same, "{}: the experiment form differs".format(kind)


@pytest.mark.parametrize("position", ["first", "second"])
@pytest.mark.parametrize("kind", KINDS)
def test_an_unknown_trial_raises_runtime_error(vis, kind, position):
    """Robustness: an id that names no trial raises ``RuntimeError`` in
    ``Trial`` (a 500 under ``now vis``), not a 404
    """
    known = vis.trial_ids[0]
    unknown = str(uuid.uuid4())
    assert unknown not in vis.trial_ids
    pair = (unknown, known) if position == "first" else (known, unknown)
    with pytest.raises(RuntimeError, match="Trial .+ not found"):
        vis.get(diff_route(kind, *pair))
