# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Fixtures of the tests of the vis in a browser

The rest of the suite never runs the JavaScript of the vis: the route tests
(``tests/vis``) call Flask in this process, and the ``frontend`` job of CI
only rebuilds the bundle. These tests serve a two-trial weather store with
``now vis`` over a real port and drive the bundle that it serves, the
working tree's, in headless Chrome through Playwright, with real input
events: wheel, drag, click, right click, Shift+click, typing.

They need the ``browser`` dependency group (``uv sync --group browser``)
and Google Chrome, which Playwright drives in place (``channel="chrome"``,
or the executable named by ``CHROME``): its own browsers are never
downloaded. Without either they skip, unless ``NOW_BROWSER=require``, which
the ``vis-browser`` job of CI sets, makes that a failure. They bind a port,
so inside the Claude Code sandbox they fail at the server; run them outside.

- ``vis_url``: a ``now vis`` of its own for each test (``NowProject.serve``
  of the harness), started from inside the project with the harness's
  environment, whose ``PATH`` holds the ``now`` of this installation. Each
  test has its own server and browser because the leak detector blames a
  child process kept by a fixture of wider scope on the first test that
  uses it.
- ``vis``: a page on that server, the history loaded, with
  ``page_helpers.js`` installed (``window.__vis``) and what the page
  reported (console errors, uncaught exceptions, dialogs, responses of 400
  and above) collected in ``vis.problems``.

The store is built once per session and shared. Every graph route of the
vis writes a cache into it, so it is not the read-only
``two_trial_project`` of the other tests.
"""

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from noworkflow.tests.e2e.harness import NowProject, build_weather

HELPERS = Path(__file__).with_name("page_helpers.js")
VIEWPORT = {"width": 1400, "height": 900}
# What every page of the history asks for and does not get, in every run
# and with every bundle: the annotation widget fetches the extended
# annotation of the experiment, and the history page has none (an empty id
# in the URL); Chrome asks for a favicon the vis does not have.
KNOWN_PROBLEMS = (
    "http 404 /experiments//extendedAnnotation",
    "http 404 /favicon.ico",
)


def required():
    return os.environ.get("NOW_BROWSER") == "require"


def skip_or_fail(reason):
    if required():
        pytest.fail("{} (NOW_BROWSER=require)".format(reason), pytrace=False)
    pytest.skip(reason)


@pytest.fixture(scope="session")
def _browser_store(tmp_path_factory):
    return build_weather(NowProject(tmp_path_factory.mktemp("browser")), trials=2)


@pytest.fixture
def vis_url(_browser_store):
    """The URL of a ``now vis`` serving the two-trial store, for this test"""
    with _browser_store.serve() as server:
        yield server.url


class Vis:
    """A page of the vis and the input that a user would give it"""

    def __init__(self, page, problems):
        self.page = page
        self.problems = problems

    def js(self, expression, arg=None):
        return self.page.evaluate(expression, arg)

    def wait(self, expression, what, timeout=30000):
        """Wait for a JavaScript condition, or fail saying what never came"""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        try:
            self.page.wait_for_function(expression, timeout=timeout, polling=200)
        except PlaywrightTimeout:
            pytest.fail("never came: {}".format(what), pytrace=False)

    def settle(self):
        """Mark the end of the input, then wait until the page is quiet"""
        self.js("__vis.touch()")
        self.wait("__vis.quiet()", "a quiet page", timeout=60000)

    def at(self, target, empty=False):
        """Where input on ``target`` goes; fail when nothing is visible there

        ``target`` is a JavaScript expression for an element; ``empty`` asks
        for the background of that SVG instead.
        """
        helper = "emptyPoint" if empty else "point"
        point = self.js("__vis.{}({})".format(helper, target))
        assert point, "nothing visible {} {}".format(
            "behind" if empty else "at", target
        )
        return point

    def click(self, target, button="left", shift=False):
        point = self.at(target)
        mouse, keyboard = self.page.mouse, self.page.keyboard
        mouse.move(point["x"], point["y"])
        if shift:
            keyboard.down("Shift")
        mouse.click(point["x"], point["y"], button=button)
        if shift:
            keyboard.up("Shift")
        self.settle()
        return point

    def drag_from(self, point, dx, dy):
        mouse = self.page.mouse
        mouse.move(point["x"], point["y"])
        mouse.down()
        mouse.move(point["x"] + dx, point["y"] + dy, steps=6)
        mouse.up()
        self.settle()

    def drag(self, target, dx, dy, empty=False):
        self.drag_from(self.at(target, empty), dx, dy)

    def wheel(self, target, delta_y, empty=False):
        point = self.at(target, empty)
        self.page.mouse.move(point["x"], point["y"])
        self.page.mouse.wheel(0, delta_y)
        self.settle()

    def hover(self, target):
        """Move the pointer onto ``target`` and wait for what it reveals"""
        point = self.at(target)
        self.page.mouse.move(point["x"], point["y"], steps=4)
        self.settle()

    def type(self, text):
        self.page.keyboard.insert_text(text)

    def menu(self, option):
        """Run a command of the context menu of the first trial"""
        self.click("__vis.historyNodes()[0]", button="right")
        self.wait(
            "document.getElementById('context-menu').classList.contains('show')",
            "the context menu",
        )
        self.click("document.getElementById({!r})".format(option))

    def unexpected_problems(self):
        return [p for p in self.problems if p not in KNOWN_PROBLEMS]


def launch(playwright):
    from playwright.sync_api import Error

    chrome = os.environ.get("CHROME")
    try:
        if chrome:
            return playwright.chromium.launch(executable_path=chrome, headless=True)
        return playwright.chromium.launch(channel="chrome", headless=True)
    except Error as error:
        skip_or_fail("no Chrome to drive: {}".format(str(error).splitlines()[0]))


@pytest.fixture
def vis(vis_url):
    """A page of the vis with the history graph drawn"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        skip_or_fail("Playwright is not installed: uv sync --group browser")
    problems = []
    with sync_playwright() as playwright:
        browser = launch(playwright)
        try:
            page = browser.new_page(viewport=VIEWPORT, locale="en-US")
            page.add_init_script(path=str(HELPERS))

            def console(message):
                # A failed request is reported once, as its response.
                if message.type == "error" and not message.text.startswith(
                    "Failed to load resource"
                ):
                    problems.append("console error " + message.text[:300])

            def response(answer):
                if answer.status >= 400:
                    path = urlsplit(answer.url).path
                    problems.append("http {} {}".format(answer.status, path))

            def dialog(opened):
                problems.append("dialog " + opened.message)
                opened.accept()

            page.on("console", console)
            page.on(
                "pageerror", lambda error: problems.append("exception " + str(error))
            )
            page.on("response", response)
            page.on("dialog", dialog)
            page.goto(vis_url + "/")
            vis = Vis(page, problems)
            vis.wait("__vis.historyNodes().length >= 2", "the history graph")
            vis.settle()
            yield vis
        finally:
            browser.close()
