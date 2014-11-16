from __future__ import absolute_import

import os
import functools
from ..persistence import persistence
from flask import render_template, jsonify, request
from . import app
from ..models.history import History
from ..models.trial import Trial


def connection(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        cwd = os.getcwd()
        persistence.connect_existing(cwd)
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

@app.route('/trials/<tid>/independent')
@connection
def independent_trial_graph(tid):
    trial = Trial(tid)
    return jsonify(**trial.independent_activation_graph())

@app.route('/trials/<tid>/combined')
@connection
def combined_trial_graph(tid):
    trial = Trial(tid)
    return jsonify(**trial.combined_activation_graph())

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
