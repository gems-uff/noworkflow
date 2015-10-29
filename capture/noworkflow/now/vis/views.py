# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import functools
from flask import render_template, jsonify, request
from ..persistence import persistence
from ..models.history import History
from ..models.trial import Trial
from ..models.diff import Diff

class WebServer(object):

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(WebServer, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        from flask import Flask

        self.app = Flask(__name__)

app = WebServer().app

def connection(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        persistence.connect_existing(app.dir)
        return func(*args, **kwargs)
    return inner

@app.route('/<path:path>')
def static_proxy(path):
    return app.send_static_file(path)

@app.route('/trials')
@connection
def trials():
    history = History()
    return jsonify(**history.graph_data(request.args.get('script'),
                                        request.args.get('execution')))

@app.route('/')
@connection
def index():
    history = History()
    return render_template("index.html",
        cwd = os.getcwd(),
        scripts = history.scripts()
    )

@app.route('/<tid>-<graph_mode>')
@connection
def index2(tid, graph_mode):
    history = History()
    return render_template("index.html",
        cwd = os.getcwd(),
        scripts = history.scripts()
    )

@app.route('/trials/<tid>/<graph_mode>/<cache>.json')
@connection
def trial_graph(tid, graph_mode, cache):
    trial = Trial(tid)
    graph = trial.graph
    graph.use_cache &= bool(int(cache))
    finished, g = getattr(graph, graph_mode)(trial)
    return jsonify(**g)

@app.route('/trials/<tid>/dependencies')
@connection
def dependencies(tid):
    trial = Trial(tid)
    local, result = trial.modules()
    return jsonify(local=local, all=result)

@app.route('/trials/<tid>/all_modules')
@connection
def all_modules(tid):
    trial = Trial(tid)
    local, result = trial.modules()
    result = sorted(result, key=lambda x:x not in local)
    return render_template("trial.html",
        cwd = os.getcwd(),
        trial = trial.info(),
        modules = result,
        info = "modules.html",
    )

@app.route('/trials/<tid>/environment')
@connection
def environment(tid):
    trial = Trial(tid)
    return jsonify(env=trial.environment())


@app.route('/trials/<tid>/all_environment')
@connection
def all_environment(tid):
    trial = Trial(tid)
    return render_template("trial.html",
        cwd = os.getcwd(),
        trial = trial.info(),
        env = trial.environment(),
        info = "environment.html",
    )

@app.route('/trials/<tid>/file_accesses')
@connection
def file_accesses(tid):
    trial = Trial(tid)
    return jsonify(file_accesses=trial.file_accesses())

@app.route('/trials/<tid>/all_file_accesses')
@connection
def all_file_accesses(tid):
    trial = Trial(tid)
    return render_template("trial.html",
        cwd = os.getcwd(),
        trial = trial.info(),
        file_accesses = trial.file_accesses(),
        info = "file_accesses.html",
    )


@app.route('/diff/<trial1>/<trial2>/<tl>-<nh>-<graph_mode>')
@app.route('/diff/<trial1>/<trial2>')
@connection
def diff(trial1, trial2, tl=None, nh=None, graph_mode=None):
    diff = Diff(trial1, trial2)
    modules_added, modules_removed, modules_replaced = diff.modules()
    env_added, env_removed, env_replaced = diff.environment()
    fa_added, fa_removed, fa_replaced = diff.file_accesses()
    return render_template("diff.html",
        cwd = os.getcwd(),
        trial1 = diff.trial1.info(),
        trial2 = diff.trial2.info(),
        trial = diff.trial(),
        modules_added = modules_added,
        modules_removed = modules_removed,
        modules_replaced = modules_replaced,
        env_added = env_added,
        env_removed = env_removed,
        env_replaced = env_replaced,
        fa_added = fa_added,
        fa_removed = fa_removed,
        fa_replaced = fa_replaced,
    )

@app.route('/diff/<trial1>/<trial2>/<graph_mode>/<tl>-<nh>-<cache>.json')
@connection
def diff_graph(trial1, trial2, graph_mode, tl, nh, cache):
    diff = Diff(trial1, trial2)
    graph = diff.graph
    graph.use_cache &= bool(int(cache))
    finished, d, t1, t2 = getattr(graph, graph_mode)(
        diff, time_limit=int(tl), neighborhoods=int(nh))
    return jsonify(
        diff=d,
        trial1=t1,
        trial2=t2,
    )
