# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The routes of ``now vis`` that serve stored content, and ``/files``

The content routes read the content store by hash:

- ``trials/<tid>/<script_hash>/<name>`` (``get_script``): the link of the
  trial's script, which ``nowvis/src/info/trial_info.ts`` builds relative
  to the page from the history node's ``code_hash`` and ``script``;
- ``trials/files/<file_hash>/<file_ext>`` (``get_file``): the links of the
  file accesses (``nowvis/src/info/file_accesses_info.ts``, which passes
  the accessed file's base name as ``file_ext``) and of an activation's
  code block in the trial graph's tooltip (``trial/src/graph.ts``, which
  passes the activation's name);
- ``getFileContent/<file_hash>``: the content decoded, as JSON;
- ``/downloadFile/<fid>`` and its two experiment forms (the function diff
  window and ``now pull``): the bytes as ``application/octet-stream``.

Bytes are compared with the store's content directory
(``NowProject.content``), the hashes come from its tables. ``/files/<id>``
fills the "restore file" dialog: the names of the trial's file accesses,
its script and its modules' files, compared with the store as multisets.

Known defects, each with a characterization and a ``_desired`` twin:
``EXPERIMENT_PREFIX`` (``get_script`` and ``get_file`` take no
``expCode``; the script link is relative, so on an experiment's page it is
the one the frontend builds), ``SCRIPT_NAME``, ``FILE_NAME`` (the names a
browser offers when saving a script, a file access or an activation's
source) and #224 (a ``..`` hash reads the store's ``db.sqlite`` through
every content route). A hash the store does not hold raises
``FileNotFoundError`` (characterized only). The frontend links hashes it
read from the store, with one exception: the function diff window
(``nowvis/src/graph/function_diff.ts``) makes "Content hash before: null"
clickable for an added or removed write of a new file, which requests
``/downloadFile/null``. Measured on macOS with Python 3.11 to 3.15: none
of it depends on the version.
"""
import collections
import hashlib
import ntpath
import sqlite3

import pytest
from werkzeug.http import parse_options_header

from noworkflow.tests.e2e.harness import (
    WEATHER_ARGS,
    WEATHER_DATA2_TRIAL2,
    build_weather,
)

from .support import EXPERIMENT, EXPERIMENT_PREFIX, Defect, known_defects

SCRIPT_NAME = Defect(
    reason="#366: get_script (vis/views.py) names the "
           "download f\"{name}.py\", while the link the frontend builds "
           "(nowvis info/trial_info.ts) already ends in the trial's script "
           "with its extension, so simulation.py is offered as "
           "simulation.py.py",
    signature="'.py' appended to the script name",
)
FILE_NAME = Defect(
    reason="#366: get_file (vis/views.py) names the "
           "download file_hash + file_ext with no separator, while the "
           "frontend passes a name as file_ext (the accessed file's base "
           "name in nowvis info/file_accesses_info.ts, the activation's "
           "name in trial/src/graph.ts), so data1.dat is offered as "
           "<hash>data1.dat and run_simulation as <hash>run_simulation",
    signature="the content hash glued to the file name",
)
CONTENT_PATH = Defect(
    reason="#224: PlainEngine.get joins the content directory with hash[:2] "
           "and hash[2:] without validating the hash, so every content "
           "route of now vis serves .noworkflow/db.sqlite, the machine's "
           "environment included, for the hash '..db.sqlite'",
    signature="served the store's db.sqlite",
)

# The hash that resolves to ``.noworkflow/db.sqlite``:
# join(content, "..", "db.sqlite").
DB_HASH = "..db.sqlite"


def disposition(response):
    """``(type, filename)`` of the response's Content-Disposition"""
    value, options = parse_options_header(
        response.headers.get("Content-Disposition", ""))
    return value, options.get("filename")


def main_code_hash(project, trial):
    """The code hash of the trial's script: its main code block's"""
    rows = project.query(
        "SELECT code_hash FROM code_block WHERE trial_id = ? AND id = ?",
        trial["id"], trial["main_id"])
    assert len(rows) == 1, "no main code block"
    return rows[0]["code_hash"]


def script_link(project, trial):
    """The script link of the trial, as trial_info.ts builds it"""
    return "trials/{}/{}/{}".format(
        trial["id"], main_code_hash(project, trial), trial["script"])


def stored_hashes(project):
    """Every content hash the file accesses of the store name, sorted"""
    hashes = set()
    for row in project.query(
            "SELECT content_hash_before, content_hash_after "
            "FROM file_access"):
        hashes.update(value for value in row.values() if value)
    return sorted(hashes)


def access_links(project):
    """``(hash, base name)`` of every file access link of the store

    file_accesses_info.ts links each hash of an access to
    ``/trials/files/<hash>/<last path component of the name>``.
    """
    links = set()
    for row in project.query(
            "SELECT name, content_hash_before, content_hash_after "
            "FROM file_access"):
        base = row["name"].split("/")[-1]
        for content_hash in (row["content_hash_before"],
                             row["content_hash_after"]):
            if content_hash:
                links.add((content_hash, base))
    assert links, "the store has no file access with content"
    return sorted(links)


def activation_links(project):
    """``(code hash, name)`` of every activation link of the store

    The trial graph's tooltip (trial/src/graph.ts) links an activation that
    has a code block to ``/trials/files/<its code_hash>/<its name>``, both
    read from ``/trials/<tid>/activations/<aid>``.
    """
    links = {(row["code_hash"], row["name"]) for row in project.query(
        "SELECT activation.name, code_block.code_hash "
        "FROM activation JOIN code_block "
        "ON code_block.trial_id = activation.trial_id "
        "AND code_block.id = activation.code_block_id")}
    assert links, "no activation with a code block"
    return sorted(links)


def absent_hash(project):
    """A well-formed hash that the store's content directory lacks"""
    content_hash = hashlib.sha1(b"not in the store").hexdigest()
    path = project.store / "content" / content_hash[:2] / content_hash[2:]
    assert not path.exists(), "the absent hash is in the store"
    return content_hash


def expected_files(project, trial_id):
    """What ``/files/<trial_id>`` lists, from the store, as a multiset"""
    names = [row["name"] for row in project.query(
        "SELECT name FROM file_access WHERE trial_id = ? AND name != 'nul'",
        trial_id)]
    names += [row["script"] for row in project.query(
        "SELECT script FROM trial WHERE id = ?", trial_id)]
    names += [ntpath.basename(row["path"]) for row in project.query(
        "SELECT path FROM module WHERE trial_id = ?", trial_id)]
    return collections.Counter(names)


def build_renamed_input(project):
    """Weather twice, the second trial reading data3.dat for data2.dat"""
    project.copy_corpus("weather")
    project.run(*WEATHER_ARGS)
    project.write("data3.dat", WEATHER_DATA2_TRIAL2)
    project.run(*WEATHER_ARGS[:-1], "data3.dat")
    return project


# --- The script link ---------------------------------------------------------


def test_script_link_serves_the_trial_script(vis):
    """The script link of each trial serves the bytes stored under the
    trial's code hash, which are the script file of the project
    """
    for trial in vis.project.trials():
        response = vis.get("/" + script_link(vis.project, trial))
        assert response.status_code == 200, "script link: status {}".format(
            response.status_code)
        code_hash = main_code_hash(vis.project, trial)
        assert response.get_data() == vis.project.content(code_hash), (
            "the script link serves other bytes than its hash")
        script = (vis.project.path / trial["script"]).read_bytes()
        assert response.get_data() == script, (
            "the trial's code hash is not the project's script")


def test_script_link_offers_the_script_name_with_py_appended(vis):
    """Today the script link is served inline and the name a browser
    offers when saving it is the script's name with ``.py`` appended
    """
    trial = vis.project.trials()[0]
    response = vis.get("/" + script_link(vis.project, trial))
    kind, filename = disposition(response)
    assert kind == "inline"
    assert filename == trial["script"] + ".py"


@known_defects(SCRIPT_NAME)
def test_script_link_offers_the_script_name_desired(vis):
    """The name a browser offers for the script is the script's own"""
    trial = vis.project.trials()[0]
    response = vis.get("/" + script_link(vis.project, trial))
    _, filename = disposition(response)
    doubled = filename == trial["script"] + ".py"
    assert filename == trial["script"], (
        "'.py' appended to the script name" if doubled
        else "offered as {!r}".format(filename))


def test_script_link_under_an_experiment_raises_type_error(vis):
    """Today the script link under ``/experiments/<code>/``, the one the
    frontend builds on an experiment's page, raises ``TypeError``
    """
    trial = vis.project.trials()[0]
    _, prefixed = vis.routes(script_link(vis.project, trial))
    with pytest.raises(TypeError, match="unexpected keyword argument "
                                        "'expCode'"):
        vis.get(prefixed)


@known_defects(EXPERIMENT_PREFIX)
def test_script_link_under_an_experiment_desired(vis):
    """Under an experiment, the script link serves the same script"""
    trial = vis.project.trials()[0]
    plain, prefixed = vis.routes(script_link(vis.project, trial))
    response = vis.get(prefixed)
    assert response.status_code == 200
    assert response.get_data() == vis.get(plain).get_data()


# --- The file links ----------------------------------------------------------


def test_file_access_links_serve_the_stored_content(vis):
    """Each link of a file access serves the bytes stored under its hash"""
    for content_hash, base in access_links(vis.project):
        response = vis.get("/trials/files/{}/{}".format(content_hash, base))
        assert response.status_code == 200, "{}: status {}".format(
            base, response.status_code)
        assert response.get_data() == vis.project.content(content_hash), (
            "{}: other bytes than its hash".format(base))


def test_file_access_links_offer_the_hash_glued_to_the_name(vis):
    """Today a file access link is served inline and the name a browser
    offers when saving it is the hash followed by the file's name
    """
    for content_hash, base in access_links(vis.project):
        response = vis.get("/trials/files/{}/{}".format(content_hash, base))
        kind, filename = disposition(response)
        assert kind == "inline", base
        assert filename == content_hash + base, base


@known_defects(FILE_NAME)
def test_file_access_links_offer_the_file_name_desired(vis):
    """The name a browser offers for a file access is the file's name"""
    for content_hash, base in access_links(vis.project):
        response = vis.get("/trials/files/{}/{}".format(content_hash, base))
        _, filename = disposition(response)
        glued = filename == content_hash + base
        assert filename == base, (
            "the content hash glued to the file name" if glued
            else "{} offered as {!r}".format(base, filename))


def test_activation_links_serve_the_code_block_source(vis):
    """The link of an activation in the trial graph's tooltip serves the
    source stored under its code block's hash
    """
    for code_hash, name in activation_links(vis.project):
        response = vis.get("/trials/files/{}/{}".format(code_hash, name))
        assert response.status_code == 200, "{}: status {}".format(
            name, response.status_code)
        assert response.get_data() == vis.project.content(code_hash), (
            "{}: other bytes than its hash".format(name))


def test_activation_links_offer_the_hash_glued_to_the_name(vis):
    """Today the name a browser offers for an activation's source is the
    code hash followed by the activation's name
    """
    for code_hash, name in activation_links(vis.project):
        response = vis.get("/trials/files/{}/{}".format(code_hash, name))
        kind, filename = disposition(response)
        assert kind == "inline", name
        assert filename == code_hash + name, name


@known_defects(FILE_NAME)
def test_activation_links_offer_the_activation_name_desired(vis):
    """The name a browser offers for an activation's source is the name
    the link carries, the activation's
    """
    for code_hash, name in activation_links(vis.project):
        response = vis.get("/trials/files/{}/{}".format(code_hash, name))
        _, filename = disposition(response)
        glued = filename == code_hash + name
        assert filename == name, (
            "the content hash glued to the file name" if glued
            else "{} offered as {!r}".format(name, filename))


def test_file_link_under_an_experiment_raises_type_error(vis):
    """Today ``/experiments/<code>/trials/files/...`` raises ``TypeError``
    (the frontend builds absolute file links, never this form)
    """
    content_hash, base = access_links(vis.project)[0]
    _, prefixed = vis.routes("trials/files/{}/{}".format(content_hash, base))
    with pytest.raises(TypeError, match="unexpected keyword argument "
                                        "'expCode'"):
        vis.get(prefixed)


@known_defects(EXPERIMENT_PREFIX)
def test_file_link_under_an_experiment_desired(vis):
    """Under an experiment, a file link serves the same content"""
    content_hash, base = access_links(vis.project)[0]
    plain, prefixed = vis.routes("trials/files/{}/{}".format(
        content_hash, base))
    response = vis.get(prefixed)
    assert response.status_code == 200
    assert response.get_data() == vis.get(plain).get_data()


# --- getFileContent and the downloads ----------------------------------------


@pytest.mark.parametrize("prefixed", [False, True], ids=["root", "experiment"])
def test_get_file_content_is_the_decoded_content(vis, prefixed):
    """``getFileContent/<hash>`` answers the stored content decoded as
    text, at the root and under an experiment
    """
    for content_hash in stored_hashes(vis.project):
        route = vis.routes("getFileContent/" + content_hash)[prefixed]
        answer = vis.json(route)
        assert set(answer) == {"file_content"}
        expected = vis.project.content(content_hash).decode(errors="ignore")
        assert answer["file_content"] == expected, content_hash


@pytest.mark.parametrize("route", [
    "/downloadFile/{}",
    "/experiments/{}/downloadFile/{{}}".format(EXPERIMENT),
    "/experiments/{}/collab/files/{{}}".format(EXPERIMENT),
], ids=["root", "experiment", "collab"])
def test_download_routes_serve_the_bytes(vis, route):
    """The download routes serve the stored bytes as octet-stream, with no
    file name: the function diff window names the download with its link's
    ``download`` attribute, which a Content-Disposition file name would
    override
    """
    for content_hash in stored_hashes(vis.project):
        response = vis.get(route.format(content_hash))
        assert response.status_code == 200, "{}: status {}".format(
            content_hash, response.status_code)
        assert response.mimetype == "application/octet-stream"
        assert "Content-Disposition" not in response.headers
        assert response.get_data() == vis.project.content(content_hash), (
            content_hash)


CONTENT_ROUTES = {
    "script": "/trials/{tid}/{hash}/simulation.py",
    "file": "/trials/files/{hash}/data1.dat",
    "file_content": "/getFileContent/{hash}",
    "download": "/downloadFile/{hash}",
    "collab": "/experiments/" + EXPERIMENT + "/collab/files/{hash}",
}


@pytest.mark.parametrize("route", sorted(CONTENT_ROUTES))
def test_absent_hash_raises_file_not_found(vis, route):
    """A well-formed hash the store does not hold raises
    ``FileNotFoundError`` (``now vis`` answers 500) on every content route
    """
    url = CONTENT_ROUTES[route].format(
        tid=vis.trial_ids[0], hash=absent_hash(vis.project))
    with pytest.raises(FileNotFoundError):
        vis.get(url)


def test_download_of_the_null_hash_raises_file_not_found(vis):
    """``/downloadFile/null``, which the function diff window requests for
    the null before-hash of a new file's write, raises
    ``FileNotFoundError`` (``now vis`` answers 500)
    """
    with pytest.raises(FileNotFoundError):
        vis.get("/downloadFile/null")


def served_database(vis, route):
    """``(status, whether the body is the store's db.sqlite)``"""
    url = CONTENT_ROUTES[route].format(tid=vis.trial_ids[0], hash=DB_HASH)
    response = vis.get(url)
    database = (vis.project.store / "db.sqlite").read_bytes()
    if route == "file_content" and response.mimetype == "application/json":
        body = response.get_json().get("file_content")
        same = body == database.decode(errors="ignore")
    else:
        same = response.get_data() == database
    return response.status_code, same


@pytest.mark.parametrize("route", sorted(CONTENT_ROUTES))
def test_dot_dot_hash_serves_the_store_database(vis, route):
    """Today the hash ``..db.sqlite`` reaches ``.noworkflow/db.sqlite``
    through every content route, which serves the whole file
    """
    status, same = served_database(vis, route)
    assert status == 200, "status {}".format(status)
    assert same, "the route did not serve the store's db.sqlite"


@pytest.mark.parametrize("route", sorted(CONTENT_ROUTES))
@known_defects(CONTENT_PATH)
def test_rejects_a_content_hash_outside_the_content_directory_desired(
        vis, route):
    """A content route answers a client error, and no bytes, for a hash
    that names a file outside the content directory
    """
    status, same = served_database(vis, route)
    assert not same, "served the store's db.sqlite"
    assert 400 <= status < 500, "status {}".format(status)


# --- /files ------------------------------------------------------------------


def test_files_lists_the_accesses_script_and_modules(vis):
    """``/files/<id>`` lists each file access of the trial (``nul``
    excluded), its script and its modules' file names, once each
    """
    for trial_id in vis.trial_ids:
        answer = vis.json("/files/" + trial_id)
        assert set(answer) == {"files"}
        listed = collections.Counter(answer["files"])
        assert listed == expected_files(vis.project, trial_id)


def test_files_of_an_unknown_trial_is_empty(vis):
    """A trial id the store does not have lists no file"""
    assert vis.json("/files/no-such-trial") == {"files": []}


def test_files_names_a_module_recorded_with_backslashes(project, vis_for):
    """A module path recorded on Windows (``\\`` separators) is listed by
    its file name, as a POSIX one is
    """
    build_weather(project)
    with project.db() as connection:
        (row,) = connection.execute(
            "SELECT trial_id, id, path FROM module LIMIT 1").fetchall()
    name = ntpath.basename(row["path"])
    windows = "C:\\Users\\nowtest\\project\\" + name
    connection = sqlite3.connect(str(project.store / "db.sqlite"))
    try:
        with connection:
            connection.execute(
                "UPDATE module SET path = ? WHERE trial_id = ? AND id = ?",
                (windows, row["trial_id"], row["id"]))
    finally:
        connection.close()
    vis = vis_for(project)
    listed = collections.Counter(vis.json("/files/" + row["trial_id"])["files"])
    assert listed[name] == 1, "the module's file name"
    assert listed == expected_files(vis.project, row["trial_id"])


def test_files_lists_only_the_trial_own_files(project, vis_for):
    """Where the trials read different files, each trial lists its own:
    the first data2.dat, the second data3.dat
    """
    vis = vis_for(build_renamed_input(project))
    first, second = vis.trial_ids
    first_files = collections.Counter(vis.json("/files/" + first)["files"])
    second_files = collections.Counter(vis.json("/files/" + second)["files"])
    assert first_files == expected_files(vis.project, first)
    assert second_files == expected_files(vis.project, second)
    assert "data2.dat" in first_files and "data3.dat" not in first_files
    assert "data3.dat" in second_files and "data2.dat" not in second_files
