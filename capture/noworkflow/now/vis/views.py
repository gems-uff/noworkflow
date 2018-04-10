# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define views for 'now vis'"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from flask import render_template, jsonify, request

from ..persistence.models import Trial
from ..persistence.models.history import History
from ..persistence.models.diff import Diff
from ..persistence import relational


class WebServer(object):
    """Flask WebServer"""
    # pylint: disable=too-few-public-methods
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(WebServer, cls).__new__(
                cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        from flask import Flask

        self.app = Flask(__name__)


app = WebServer().app  # pylint: disable=invalid-name


@app.after_request
def add_header(req):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req


@app.route("/<path:path>")
def static_proxy(path):
    """Serve static files"""
    return app.send_static_file(path)


@app.route("/")
@app.route("/<tid>-<graph_mode>")  # todo
def index(tid=None, graph_mode=None):
    """Respond history scripts and index page as HTML"""
    # pylint: disable=unused-argument
    history = History()
    return render_template(
        "index.html",
        cwd=os.getcwd(),
        scripts=history.scripts
    )


@app.route("/trials.json")
@app.route("/trials") # remove
def trials():
    """Respond history graph as JSON"""
    history = History(script=request.args.get("script"),
                      status=request.args.get("execution"),
                      summarize=bool(int(request.args.get("summarize"))))
    return jsonify(**history.graph.graph())


@app.route("/trials/<tid>/<graph_mode>/<cache>.json")
def trial_graph(tid, graph_mode, cache):
    """Respond trial graph as JSON"""
    trial = Trial(tid)
    graph = trial.graph
    graph.use_cache &= bool(int(cache))
    _, tgraph, _ = getattr(graph, graph_mode)()
    return jsonify(**tgraph)


@app.route("/trials/<tid>/dependencies.json")
@app.route("/trials/<tid>/dependencies")  # remove
def dependencies(tid):
    """Respond trial module dependencies as JSON"""
    # pylint: disable=not-an-iterable
    trial = Trial(tid)
    result = [x.to_dict(extra=("code_hash",)) for x in trial.modules]
    trial_path = trial.environment.get("PWD", "")
    return jsonify(all=result, trial_path=trial_path)


@app.route("/trials/<tid>/environment.json")
@app.route("/trials/<tid>/environment")  # remove
def environment(tid):
    """Respond trial environment variables as JSON"""
    trial = Trial(tid)
    result = {x.name: x.to_dict() for x in trial.environment_attrs}
    return jsonify(all=list(result.values()))


@app.route("/trials/<tid>/file_accesses.json")
@app.route("/trials/<tid>/file_accesses")  # remove
def file_accesses(tid):
    """Respond trial file accesses as JSON"""
    trial = Trial(tid)
    trial_path = trial.environment.get("PWD", "")
    return jsonify(file_accesses=[x.to_dict(extra=("stack",))
                                  for x in trial.file_accesses],
                   trial_path=trial_path)


@app.route("/diff/<trial1>/<trial2>/info.json")
def diff(trial1, trial2):
    """Respond trial diff as JSON"""
    diff_object = Diff(trial1, trial2)
    return jsonify(
        trial1=diff_object.trial1.to_dict(extra=("duration_text",)),
        trial2=diff_object.trial2.to_dict(extra=("duration_text",)),
        trial=diff_object.trial,
    )

@app.route("/diff/<trial1>/<trial2>/dependencies.json")
def diff_modules(trial1, trial2):
    """Respond modules diff as JSON"""
    diff_object = Diff(trial1, trial2)
    modules_added, modules_removed, modules_replaced = diff_object.modules
    t1_path = diff_object.trial1.environment.get("PWD", "")
    t2_path = diff_object.trial2.environment.get("PWD", "")
    return jsonify(
        modules_added=[x.to_dict(extra=("code_hash",)) for x in modules_added],
        modules_removed=[x.to_dict(extra=("code_hash",)) for x in modules_removed],
        modules_replaced=[[y.to_dict(extra=("code_hash",)) for y in x] for x in modules_replaced],
        t1_path=t1_path,
        t2_path=t2_path,
    )

@app.route("/diff/<trial1>/<trial2>/environment.json")
def diff_environment(trial1, trial2):
    """Respond environment diff as JSON"""
    diff_object = Diff(trial1, trial2)
    env_added, env_removed, env_replaced = diff_object.environment
    return jsonify(
        env_added=[x.to_dict() for x in env_added],
        env_removed=[x.to_dict() for x in env_removed],
        env_replaced=[[y.to_dict() for y in x] for x in env_replaced],
    )

@app.route("/diff/<trial1>/<trial2>/file_accesses.json")
def diff_accesses(trial1, trial2):
    """Respond trial diff as JSON"""
    diff_object = Diff(trial1, trial2)
    fa_added, fa_removed, fa_replaced = diff_object.file_accesses
    t1_path = diff_object.trial1.environment.get("PWD", "")
    t2_path = diff_object.trial2.environment.get("PWD", "")
    return jsonify(
        fa_added=[x.to_dict() for x in fa_added],
        fa_removed=[x.to_dict() for x in fa_removed],
        fa_replaced=[[y.to_dict() for y in x] for x in fa_replaced],
        t1_path=t1_path,
        t2_path=t2_path,
    )


@app.route("/diff/<trial1>/<trial2>/<graph_mode>-<cache>.json")
def diff_graph(trial1, trial2, graph_mode, cache):
    """Respond trial diff as JSON"""
    diff_object = Diff(trial1, trial2)
    graph = diff_object.graph
    graph.use_cache &= bool(int(cache))

    _, diff_result, _ = getattr(graph, graph_mode)()
    return jsonify(**diff_result)


@app.teardown_appcontext
def shutdown_session(exception=None):
    """Shutdown SQLAlchemy session"""
    # pylint: disable=unused-argument
    relational.session.remove()
