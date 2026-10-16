# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The client of the vis route tests, and what several modules share

``Vis`` wraps Flask's test client with the project whose store it serves:
``get`` returns a response whose body is already read and closed (a file
the view opened is never left open), and ``json`` also checks the status
and the media type. Assertion messages name the route and the status,
never the body: several routes serve the machine's environment, and the
trial's ``user_id`` holds the hostname.

A route that crashes raises in the test (the fixtures propagate
exceptions). ``Vis`` raises that same exception again from its own frame,
with the traceback it had attached as a note: the note names every file,
line and source line, but pytest's report of a failure prints the
arguments of the frame that raised, and in the views and the models those
are trials, whose repr carries ``user_id``.

``Vis.routes(path)`` yields a route under each prefix the app declares for
it: the frontend builds most URLs relative to the page, so a view answers
both at ``/<path>`` and, when the page is ``/experiments/<code>/``, at
``/experiments/<code>/<path>``.

The times a route serves are compared with the store in the zone ``now
run`` records them in: ``NOW_RUN_UTC_OFFSET`` and ``served_instant``. Never
put the offset, or a served and a stored time side by side, in a message:
together they tell the machine's zone.
"""
import dataclasses
import email.utils
import json
import subprocess
import sys
import tempfile
import traceback
import uuid
from datetime import datetime, timedelta, timezone

from noworkflow.tests.e2e.harness import clean_env
from noworkflow.tests.helpers.defects import (  # noqa: F401  (re-exported)
    Defect, known_defects,
)

# The code of an experiment the two-trial store does not have: the prefixed
# routes that do not look the experiment up ignore it.
EXPERIMENT = "no-such-experiment"


def _now_run_utc_offset():
    """Seconds east of UTC of the local time ``now run`` records

    The harness runs ``now`` without TZ (``clean_env``), so the store holds
    naive times of the system zone, which this process does not use when
    its own environment sets TZ.
    """
    tmp = tempfile.gettempdir()
    completed = subprocess.run(
        [sys.executable, "-c",
         "import time; print(time.localtime().tm_gmtoff)"],
        env=clean_env(tmp, tmp), capture_output=True, text=True, check=True,
        timeout=60)
    return int(completed.stdout)


NOW_RUN_UTC_OFFSET = _now_run_utc_offset()
NOW_RUN_ZONE = timezone(timedelta(seconds=NOW_RUN_UTC_OFFSET))

# Every view behind ``/experiments/<expCode>/...`` receives ``expCode`` as
# a keyword argument; these take no such parameter, so Flask's call fails
# before the view runs.
EXPERIMENT_PREFIX = Defect(
    reason="#355: views.py declares an "
           "/experiments/<expCode>/ route for views whose signature has no "
           "expCode parameter, so Flask's call raises TypeError and the "
           "route answers 500",
    signature="got an unexpected keyword argument 'expCode'",
)
# The twins assert through booleans with this signature in the message.
LOCAL_TIME_AS_GMT = Defect(
    reason="#366: the store records times as naive "
           "local times (datetime.now()), and Flask's JSON provider formats "
           "a naive datetime with http_date, which reads it as UTC, so the "
           "trials of diff/<t1>/<t2>/info.json, the start and finish of an "
           "activation and the access timestamps of the function diff label "
           "the local wall-clock time GMT",
    signature="off by the UTC offset of now run's zone",
    condition=NOW_RUN_UTC_OFFSET != 0,
)


def served_instant(text):
    """The instant a served time names, read as a client would

    An HTTP date (today's format) or an ISO string; a time without a zone
    is read in the zone ``now run`` records in.
    """
    try:
        moment = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=NOW_RUN_ZONE)
    return moment


def unknown_trial_id(vis):
    """A trial id the store does not have"""
    trial_id = str(uuid.uuid4())
    assert trial_id not in vis.trial_ids, "a fresh uuid names a trial"
    return trial_id


@dataclasses.dataclass
class Vis:
    """The test client of the vis app and the project whose store it serves"""

    client: object
    project: object

    @property
    def trial_ids(self):
        """The ids of the project's trials, in the order they ran"""
        return [row["id"] for row in self.project.trials()]

    def get(self, route, **kwargs):
        """GET ``route``: the response, its body read and the file closed"""
        return self._request(self.client.get, route, kwargs)

    def post(self, route, **kwargs):
        """POST ``route``: the response, its body read and closed"""
        return self._request(self.client.post, route, kwargs)

    @staticmethod
    def _request(method, route, kwargs):
        try:
            response = method(route, **kwargs)
        except Exception as error:  # pylint: disable=broad-except
            raise _without_arguments(error) from None
        response.get_data()
        response.close()
        return response

    def json(self, route, status=200, **kwargs):
        """GET ``route`` and return its JSON, checking status and type"""
        response = self.get(route, **kwargs)
        assert response.status_code == status, (
            "GET {}: status {}, expected {}".format(
                route, response.status_code, status))
        assert response.mimetype == "application/json", (
            "GET {}: {}, expected JSON".format(route, response.mimetype))
        return json.loads(response.get_data(as_text=True))

    @staticmethod
    def routes(path):
        """``path`` (no leading slash) under the root and an experiment"""
        return ["/" + path, "/experiments/{}/{}".format(EXPERIMENT, path)]


def _without_arguments(error):
    """``error`` without its frames, their text kept in a note

    ``traceback.format_exception`` prints files, lines and source, never
    the values of arguments or locals; the chained exceptions go into the
    note too, and the caller raises ``from None``.
    """
    error.add_note("Raised in the route:\n" + "".join(
        traceback.format_exception(error)).rstrip())
    return error.with_traceback(None)
