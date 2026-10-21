# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The page of ``now vis``, the static files and the hooks of every response

Routes: ``index`` (``/``, ``/experiments/<expcode>/`` and
``/<tid>-<graph_mode>``), which renders ``templates/index.html`` with three
hidden inputs the frontend reads on load (``experimentsIn``, the JSON of
the store's experiments; ``selectedExperiment``, the code in the URL;
``server``, ``True`` on ``/`` when the store has an experiment or no trial
outside one, which shows the experiment list instead of the history);
``static_proxy``
(``/<path:path>``) and Flask's own ``/static/<path:filename>``, which serve
``now/vis/static``; and the two ``after_request`` hooks, ``add_header``
(cache headers) and ``zipper`` (gzip when the client accepts it).

Expected values come from the store (SQL) and from the files on disk next
to ``views.py`` (the template names the stylesheet and the bundle). The
page never carries the environment or the hostname;
the JSON bodies compared here may (a trial's ``user_id``), so they are
compared into a boolean before the assertion.

Known defects: #263 (the hashed ``.png`` files that ``bundle.js`` names hold
a line of webpack module text, not an image), with a characterization and a
``_desired`` twin. Characterized without a twin, because the frontend never
builds such a request: a missing file at the root whose name has a hyphen
answers the page (``/<tid>-<graph_mode>`` catches it), and the zipper also
compresses a client that refuses gzip (``gzip;q=0``) and a ``206`` range.
"""

import contextlib
import gzip
import html.parser
import json
import re
import sqlite3
import urllib.parse
import uuid
from pathlib import Path

import pytest

from noworkflow.now.vis import views
from noworkflow.tests.e2e.harness import NowProject, build_weather

from .support import EXPERIMENT, Defect, known_defects

STATIC = Path(views.__file__).resolve().parent / "static"
BUNDLE_ROUTE = "/dist/bundle.js"
JS_TYPES = ("text/javascript", "application/javascript")
GZIP = {"Accept-Encoding": "gzip"}
# The JSON the history widget loads first (HistoryWidget.url).
HISTORY = "/trials.json?script=*&execution=*&summarize=0"
MISSING = "/dist/no_such_file.js"

# The files webpack emits next to the bundle under a content hash, and the
# first bytes each kind of file starts with.
ASSET = re.compile(rb"\b[0-9a-f]{20,32}\.(?:png|svg|gif|jpe?g|woff2?|ttf|eot)\b")
MAGIC = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".woff": (b"wOFF",),
    ".woff2": (b"wOF2",),
    ".ttf": (b"\x00\x01\x00\x00", b"true", b"OTTO"),
}
# What each 20-hex asset holds today: the line webpack writes for an asset
# module, naming the real image.
WEBPACK_LINE = re.compile(
    rb'^export default __webpack_public_path__ \+ "([0-9a-f]{32}\.png)";\s*$'
)

SCROLLBAR_ICONS = Defect(
    reason="#263: the file-loader rule of the nowvis webpack config "
    "processes again the asset modules that css-loader emits, so "
    "bundle.js names 20-hex .png files whose content is the line "
    "'export default __webpack_public_path__ + \"<32-hex>.png\"' "
    "instead of the image",
    signature="export default __webpack_public_path__",
)


class Page(html.parser.HTMLParser):
    """What the browser reads from the page: inputs, stylesheets, scripts"""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.text = text
        self.inputs = {}
        self.input_attributes = {}
        self.stylesheets = []
        self.scripts = []
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input":
            self.inputs[values.get("id")] = values.get("value")
            self.input_attributes[values.get("id")] = sorted(name for name, _ in attrs)
        elif tag == "link" and values.get("rel") == "stylesheet":
            self.stylesheets.append(values.get("href"))
        elif tag == "script" and "src" in values:
            self.scripts.append(values["src"])


# The stylesheet the template links (font-awesome, under the static folder).
STYLESHEET = Page(
    (STATIC.parent / "templates" / "index.html").read_text(encoding="utf-8")
).stylesheets[0]


def page(vis, route):
    """GET ``route``, check that it is the HTML page, and parse it"""
    response = vis.get(route)
    assert response.status_code == 200, "GET {}: status {}".format(
        route, response.status_code
    )
    assert response.mimetype == "text/html", "GET {}: {}".format(
        route, response.mimetype
    )
    return Page(response.get_data(as_text=True))


def experiment_path(code):
    """The page of an experiment, its code quoted as a browser would"""
    return "/experiments/{}/".format(urllib.parse.quote(code, safe=""))


def static_file(relative):
    """The bytes of a file under ``now/vis/static``"""
    return (STATIC / relative).read_bytes()


def experiments_of(project):
    """The store's experiments as the page lists them, ordered by id"""
    return sorted(
        project.query("SELECT id, name, description FROM experiment"),
        key=lambda row: row["id"],
    )


def server_flag(project):
    """``server`` as the store says: an experiment, or no trial outside one"""
    experiments = project.query("SELECT COUNT(*) AS n FROM experiment")[0]["n"]
    trials = project.query(
        "SELECT COUNT(*) AS n FROM trial WHERE experiment_id IS NULL"
    )[0]["n"]
    return str(bool(experiments) or not trials)


def add_experiment(project, name, description):
    """Insert an experiment as ``POST /experiments`` does; its id"""
    experiment_id = str(uuid.uuid4())
    path = str(project.store / "db.sqlite")
    with contextlib.closing(sqlite3.connect(path)) as connection:
        with connection:
            connection.execute(
                "INSERT INTO experiment (id, name, description) VALUES (?, ?, ?)",
                (experiment_id, name, description),
            )
    return experiment_id


def hashed_assets():
    """The hashed file names ``bundle.js`` names, as on disk"""
    return sorted(
        {match.decode() for match in ASSET.findall(static_file("dist/bundle.js"))}
    )


def magic_ok(name, body):
    """Whether ``body`` starts as a file of ``name``'s extension does"""
    extension = Path(name).suffix.lower()
    if extension == ".svg":
        return body.lstrip()[:5] in (b"<svg ", b"<svg>", b"<?xml")
    return body.startswith(MAGIC.get(extension, (b"",)))


@pytest.fixture(scope="module")
def _experiment_store(tmp_path_factory):
    project = build_weather(NowProject(tmp_path_factory.mktemp("vis_index_experiment")))
    add_experiment(project, "it's <b>one</b>", 'a "quoted" & <i>tagged</i>')
    return project


@pytest.fixture
def experiment_store(_experiment_store):
    """A one-trial weather store with one experiment and no trial in it:
    read-only"""
    before = _experiment_store.fingerprint()
    yield _experiment_store
    assert _experiment_store.fingerprint() == before, (
        "the test changed the module's experiment store"
    )


# --- index ------------------------------------------------------------------


def test_index_loads_the_bundle_and_the_stylesheet(vis):
    """The page loads ``/dist/bundle.js`` and the font-awesome stylesheet,
    and the app serves both"""
    root = page(vis, "/")
    assert root.scripts == [BUNDLE_ROUTE]
    assert root.stylesheets == [STYLESHEET]
    assert "font-awesome" in STYLESHEET
    for route in root.scripts + root.stylesheets:
        status = vis.get(route).status_code
        assert status == 200, "GET {}: status {}".format(route, status)


def test_index_of_a_store_with_trials_and_no_experiment(vis):
    """On the two-trial store the inputs say: no experiment, none selected,
    and ``server`` False, so the frontend shows the history"""
    assert vis.project.query("SELECT COUNT(*) AS n FROM experiment")[0]["n"] == 0, (
        "premise: the shared store has no experiment"
    )
    root = page(vis, "/")
    assert set(root.inputs) == {"experimentsIn", "selectedExperiment", "server"}
    assert root.inputs["experimentsIn"] is not None
    assert sorted(
        json.loads(root.inputs["experimentsIn"]), key=lambda row: row["id"]
    ) == experiments_of(vis.project)
    assert root.inputs["selectedExperiment"] == ""
    assert root.inputs["server"] == server_flag(vis.project) == "False"


def test_trial_and_graph_mode_route_renders_the_same_page(vis):
    """``/<tid>-<graph_mode>`` (a link the frontend does not build yet)
    answers the same page as ``/``"""
    first = vis.trial_ids[0]
    root = vis.get("/").get_data()
    for route in ("/{}-tree".format(first), "/{}-exact_match".format(first)):
        response = vis.get(route)
        assert response.status_code == 200, "GET {}: status {}".format(
            route, response.status_code
        )
        assert response.get_data() == root, route


def test_missing_root_file_with_a_hyphen_answers_the_page(vis):
    """Today a missing file at the root whose name has a hyphen answers the
    page with 200, because ``/<tid>-<graph_mode>`` matches it; without the
    hyphen, or under a directory, it answers 404

    Characterization (robustness): the frontend never requests such a file.
    """
    hyphen = vis.get("/no-such-file.js")
    assert hyphen.status_code == 200
    assert hyphen.mimetype == "text/html"
    assert hyphen.get_data() == vis.get("/").get_data()
    assert vis.get("/no_such_file.js").status_code == 404
    assert vis.get("/dist/no-such-file.js").status_code == 404


def test_experiment_page_selects_its_code(vis):
    """``/experiments/<code>/`` selects the code of the URL, lists the same
    experiments and keeps ``server`` False, so the history shows"""
    root = page(vis, "/")
    experiment = page(vis, experiment_path(EXPERIMENT))
    assert experiment.inputs["selectedExperiment"] == EXPERIMENT
    assert experiment.inputs["experimentsIn"] == root.inputs["experimentsIn"]
    assert experiment.inputs["server"] == "False"
    assert experiment.scripts == root.scripts


@pytest.mark.parametrize(
    "code",
    [
        "it's",
        'a"b<c>&d',
        "x' autofocus onfocus='alert(1)",
    ],
)
def test_experiment_code_is_escaped_in_the_page(vis, code):
    """A code with quotes or markup reaches ``selectedExperiment`` intact,
    as text: it adds no attribute and no element to the page"""
    root = page(vis, "/")
    experiment = page(vis, experiment_path(code))
    assert experiment.inputs["selectedExperiment"] == code
    assert experiment.input_attributes == root.input_attributes
    assert experiment.scripts == root.scripts
    assert code not in experiment.text, "the code is in the page unescaped"


def test_experiment_link_without_the_slash_redirects(vis):
    """The link the experiment list builds (``/experiments/<id>``, no
    trailing slash) redirects to the experiment page"""
    response = vis.get("/experiments/{}".format(EXPERIMENT))
    assert response.status_code == 308, response.status_code
    location = urllib.parse.urlsplit(response.headers["Location"]).path
    assert location == "/experiments/{}/".format(EXPERIMENT)


def test_index_of_a_store_with_an_experiment(experiment_store, vis_for):
    """With an experiment in the store, ``/`` lists it (its name and
    description escaped) and sets ``server`` True, so the frontend shows the
    experiment list; the experiment's page selects it with ``server``
    False"""
    vis = vis_for(experiment_store)
    expected = experiments_of(experiment_store)
    assert len(expected) == 1, "premise: one experiment"
    root = page(vis, "/")
    listed = json.loads(root.inputs["experimentsIn"])
    assert sorted(listed, key=lambda row: row["id"]) == expected
    assert root.inputs["server"] == server_flag(experiment_store) == "True"
    for text in (expected[0]["name"], expected[0]["description"]):
        assert text not in root.text, "experiment text unescaped in the page"
    experiment = page(vis, experiment_path(expected[0]["id"]))
    assert experiment.inputs["selectedExperiment"] == expected[0]["id"]
    assert experiment.inputs["server"] == "False"


# --- static files -----------------------------------------------------------


@pytest.mark.parametrize("route", [BUNDLE_ROUTE, "/static/dist/bundle.js"])
def test_bundle_is_served_byte_for_byte(vis, route):
    """``bundle.js`` comes back as JavaScript, equal to the file on disk,
    from ``/dist/`` (what the page loads) and from ``/static/dist/``"""
    response = vis.get(route)
    assert response.status_code == 200, response.status_code
    assert response.mimetype in JS_TYPES, response.mimetype
    same = response.get_data() == static_file("dist/bundle.js")
    assert same, "GET {} differs from dist/bundle.js".format(route)


def test_stylesheet_and_its_fonts_are_served(vis):
    """The stylesheet the page links comes back as CSS equal to its file,
    and every ``url()`` in it resolves to a served font equal to its file,
    whose first bytes match its extension"""
    href = page(vis, "/").stylesheets[0]
    response = vis.get(href)
    assert response.status_code == 200, response.status_code
    assert response.mimetype == "text/css", response.mimetype
    css = response.get_data()
    assert css == static_file(href.lstrip("/"))
    urls = re.findall(rb"url\(['\"]?([^'\")]+)['\"]?\)", css)
    assert urls, "premise: the stylesheet names fonts"
    for url in sorted({url.decode() for url in urls}):
        target = urllib.parse.urlsplit(urllib.parse.urljoin(href, url)).path
        font = vis.get(target)
        assert font.status_code == 200, "GET {}: status {}".format(
            target, font.status_code
        )
        body = font.get_data()
        assert body == static_file(target.lstrip("/")), target
        assert magic_ok(target, body), "GET {}: not a font".format(target)


@pytest.mark.parametrize(
    "route",
    [
        MISSING,
        "/static/dist/no_such_file.js",
        "/no_such_file.css",
        "/dist/",
        "/dist",
    ],
)
def test_missing_static_file_answers_404(vis, route):
    """A file the static folder does not have, or a directory, answers 404"""
    status = vis.get(route).status_code
    assert status == 404, "GET {}: status {}".format(route, status)


@pytest.mark.parametrize(
    "route",
    [
        "/%2e%2e/views.py",
        "/dist/%2e%2e/%2e%2e/views.py",
        "/static/%2e%2e/views.py",
        "/%2e%2e/templates/index.html",
        "/dist/../../views.py",
    ],
)
def test_path_out_of_the_static_folder_answers_404(vis, route):
    """A path that climbs out of ``now/vis/static`` answers 404, not the
    file next to it"""
    response = vis.get(route)
    assert response.status_code == 404, "GET {}: status {}".format(
        route, response.status_code
    )
    assert b"def static_proxy" not in response.get_data()


def test_hashed_assets_hold_webpack_module_text(vis):
    """Today every hashed file ``bundle.js`` names (served at ``/dist/``
    as ``image/png``) is one line of webpack module text naming a 32-hex
    file, which ``/dist/`` serves as a real PNG nobody requests

    Characterization of a defect.
    """
    names = hashed_assets()
    assert names, "premise: bundle.js names hashed assets"
    for name in names:
        response = vis.get("/dist/" + name)
        assert response.status_code == 200, name
        assert response.mimetype == "image/png", name
        line = WEBPACK_LINE.match(response.get_data())
        assert line, "{} is not the webpack line".format(name)
        image = vis.get("/dist/" + line.group(1).decode())
        assert image.status_code == 200, line.group(1)
        assert magic_ok(".png", image.get_data()), line.group(1)


@known_defects(SCROLLBAR_ICONS)
def test_hashed_assets_hold_webpack_module_text_desired(vis):
    """Every hashed file ``bundle.js`` names is served, and its body is
    what its extension says"""
    names = hashed_assets()
    assert names, "premise: bundle.js names hashed assets"
    bad = []
    for name in names:
        response = vis.get("/dist/" + name)
        assert response.status_code == 200, name
        body = response.get_data()
        if not magic_ok(name, body):
            bad.append("{} starts with {!r}".format(name, body[:38]))
    assert not bad, "BAD magic: {}".format("; ".join(bad))


# --- after_request hooks ----------------------------------------------------


@pytest.mark.parametrize("route", ["/", HISTORY, STYLESHEET, MISSING])
def test_every_response_carries_the_cache_headers(vis, route):
    """Every response, a 404 included, tells the browser not to reuse it
    without revalidating: ``Cache-Control`` has ``max-age=0``,
    ``no-cache`` or ``no-store`` (``add_header`` assigns it twice; either
    value does), with ``Pragma: no-cache`` and ``Expires: 0``"""
    response = vis.get(route)
    cache_control = response.headers.get("Cache-Control", "")
    directives = {part.strip().lower() for part in cache_control.split(",")}
    assert directives & {"max-age=0", "no-cache", "no-store"}, directives
    assert response.headers.get("Pragma") == "no-cache"
    assert response.headers.get("Expires") == "0"


def test_static_file_revalidates_with_its_etag(vis):
    """The browser revalidates; the ETag of a static file answers 304
    without a body, with or without gzip"""
    route = STYLESHEET
    etag = vis.get(route).headers.get("ETag")
    assert etag, "no ETag"
    for headers in ({}, GZIP):
        response = vis.get(route, headers=dict(headers, **{"If-None-Match": etag}))
        assert response.status_code == 304, response.status_code
        assert response.get_data() == b""
        assert "Content-Encoding" not in response.headers


def test_json_response_is_gzipped_when_the_client_accepts_it(vis):
    """With ``Accept-Encoding: gzip`` a JSON answer comes back compressed,
    with ``Vary`` and the compressed length, and decompresses to the bytes
    of the answer without the header"""
    plain = vis.get(HISTORY)
    zipped = vis.get(HISTORY, headers=GZIP)
    assert plain.status_code == zipped.status_code == 200
    assert "Content-Encoding" not in plain.headers
    assert zipped.headers.get("Content-Encoding") == "gzip"
    assert zipped.headers.get("Vary") == "Accept-Encoding"
    assert zipped.mimetype == "application/json"
    body = zipped.get_data()
    assert int(zipped.headers["Content-Length"]) == len(body)
    same = gzip.decompress(body) == plain.get_data()
    assert same, "GET {}: the gzip body differs from the plain one".format(HISTORY)


def test_bundle_is_gzipped_when_the_client_accepts_it(vis):
    """The bundle, the largest response, comes back compressed and
    decompresses to the file on disk"""
    response = vis.get(BUNDLE_ROUTE, headers={"Accept-Encoding": "gzip, deflate, br"})
    assert response.status_code == 200, response.status_code
    assert response.headers.get("Content-Encoding") == "gzip"
    body = response.get_data()
    assert int(response.headers["Content-Length"]) == len(body)
    assert len(body) < len(static_file("dist/bundle.js"))
    same = gzip.decompress(body) == static_file("dist/bundle.js")
    assert same, "the gzip bundle differs from dist/bundle.js"


def test_error_response_is_not_gzipped(vis):
    """A 404 is not compressed, even when the client accepts gzip"""
    plain = vis.get(MISSING)
    zipped = vis.get(MISSING, headers=GZIP)
    assert plain.status_code == zipped.status_code == 404
    assert "Content-Encoding" not in zipped.headers
    assert zipped.get_data() == plain.get_data()


def test_gzip_refused_with_q0_is_still_sent(vis):
    """Today ``zipper`` looks for the word gzip in ``Accept-Encoding``, so a
    client that refuses it (``gzip;q=0``) gets gzip anyway

    Characterization (robustness): browsers do not send ``q=0`` for gzip.
    """
    response = vis.get(HISTORY, headers={"Accept-Encoding": "gzip;q=0, identity"})
    assert response.headers.get("Content-Encoding") == "gzip"


def test_range_request_is_gzipped_after_the_slice(vis):
    """Today a range request with gzip answers 206 with the slice of the
    file compressed, while ``Content-Range`` counts the uncompressed bytes

    Characterization (robustness): the frontend never asks for a range.
    """
    bundle = static_file("dist/bundle.js")
    response = vis.get(BUNDLE_ROUTE, headers=dict(GZIP, Range="bytes=0-9"))
    assert response.status_code == 206, response.status_code
    assert response.headers.get("Content-Encoding") == "gzip"
    assert response.headers.get("Content-Range") == "bytes 0-9/{}".format(len(bundle))
    assert gzip.decompress(response.get_data()) == bundle[:10]
