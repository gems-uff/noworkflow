# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define views for 'now vis'"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from flask import render_template, jsonify, request

from ..persistence.models import History, Diff, Trial
from ..persistence import relational


class WebServer(object):                                                         # pylint: disable=too-few-public-methods
    """Flask WebServer"""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(WebServer, cls).__new__(
                cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        from flask import Flask

        self.app = Flask(__name__)


app = WebServer().app                                                            # pylint: disable=invalid-name


@app.route("/<path:path>")
def static_proxy(path):
    """Serve static files"""
    return app.send_static_file(path)


@app.route("/trials")
def trials():
    """Respond history graph as JSON"""
    history = History(script=request.args.get("script"),
                      status=request.args.get("execution"))
    graph = history.graph.graph()
    return jsonify(**graph)


@app.route("/")
@app.route("/<tid>-<graph_mode>")
def index(tid=None, graph_mode=None):                                           # pylint: disable=unused-argument
    """Respond history scripts and index page as HTML"""
    history = History()
    return render_template(
        "index.html",
        cwd=os.getcwd(),
        scripts=history.scripts
    )


@app.route("/trials/<tid>/<graph_mode>/<cache>.json")
def trial_graph(tid, graph_mode, cache):
    """Respond trial graph as JSON"""
    trial = Trial(tid)
    graph = trial.graph
    graph.use_cache &= bool(int(cache))
    _, tgraph = getattr(graph, graph_mode)()
    return jsonify(**tgraph)


@app.route("/trials/<tid>/dependencies")
def dependencies(tid):
    """Respond trial module dependencies as JSON"""
    trial = Trial(tid)
    local = [x.to_dict() for x in trial.local_modules]                           # pylint: disable=not-an-iterable
    result = [x.to_dict() for x in trial.modules]                                # pylint: disable=not-an-iterable
    return jsonify(local=local, all=result)


@app.route("/trials/<tid>/all_modules")
def all_modules(tid):
    """Respond trial module dependencies as HTML"""
    trial = Trial(tid)
    local = trial.local_modules
    result = trial.modules
    result = sorted(result, key=lambda x: x not in local)                        # pylint: disable=unsupported-membership-test
    return render_template(
        "trial.html",
        cwd=os.getcwd(),
        trial=trial.to_dict(extra=("duration_text",)),
        modules=result,
        info="modules.html",
    )


@app.route("/trials/<tid>/environment")
def environment(tid):
    """Respond trial environment variables as JSON"""
    trial = Trial(tid)
    return jsonify(env=trial.environment)


@app.route("/trials/<tid>/all_environment")
def all_environment(tid):
    """Respond trial environment variables as HTML"""
    trial = Trial(tid)
    return render_template(
        "trial.html",
        cwd=os.getcwd(),
        trial=trial.to_dict(extra=("duration_text",)),
        env=trial.environment,
        info="environment.html",
    )


@app.route("/trials/<tid>/file_accesses")
def file_accesses(tid):
    """Respond trial file accesses as JSON"""
    trial = Trial(tid)
    return jsonify(file_accesses=[x.to_dict(extra=("stack",))
                                  for x in trial.file_accesses])


@app.route("/trials/<tid>/all_file_accesses")
def all_file_accesses(tid):
    """Respond trial file accesses as HTML"""
    trial = Trial(tid)
    return render_template(
        "trial.html",
        cwd=os.getcwd(),
        trial=trial.to_dict(extra=("duration_text",)),
        file_accesses=[x.to_dict(extra=("stack",))
                       for x in trial.file_accesses],
        info="file_accesses.html",
    )


@app.route("/diff/<trial1>/<trial2>")
@app.route("/diff/<trial1>/<trial2>/<tlimit>-<neighborhoods>-<graph_mode>")
def diff(trial1, trial2, tlimit=None, neighborhoods=None, graph_mode=None):      # pylint: disable=unused-argument
    """Respond trial diff as HTML"""
    diff_object = Diff(trial1, trial2)

    modules_added, modules_removed, modules_replaced = diff_object.modules
    env_added, env_removed, env_replaced = diff_object.environment
    fa_added, fa_removed, fa_replaced = diff_object.file_accesses
    return render_template(
        "diff.html",
        cwd=os.getcwd(),
        trial1=diff_object.trial1.to_dict(extra=("duration_text",)),
        trial2=diff_object.trial2.to_dict(extra=("duration_text",)),
        trial=diff_object.trial,
        modules_added=modules_added,
        modules_removed=modules_removed,
        modules_replaced=modules_replaced,
        env_added=env_added,
        env_removed=env_removed,
        env_replaced=env_replaced,
        fa_added=fa_added,
        fa_removed=fa_removed,
        fa_replaced=fa_replaced,
    )


@app.route("/diff/<trial1>/<trial2>/<graph_mode>/"
           "<tlimit>-<neighborhoods>-<cache>.json")                              # pylint: disable=too-many-arguments
def diff_graph(trial1, trial2, graph_mode, tlimit, neighborhoods, cache):
    """Respond trial diff as JSON"""
    diff_object = Diff(trial1, trial2)
    graph = diff_object.graph
    graph.use_cache &= bool(int(cache))

    _, diff_result, trial1, trial2 = getattr(graph, graph_mode)(
        time_limit=int(tlimit), neighborhoods=int(neighborhoods)
    )
    return jsonify(
        diff=diff_result,
        trial1=trial1,
        trial2=trial2,
    )


@app.teardown_appcontext
def shutdown_session(exception=None):                                            # pylint: disable=unused-argument
    """Shutdown SQLAlchemy session"""
    relational.session.remove()
