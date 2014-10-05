import os
from noworkflow import persistence
from flask import render_template, jsonify, request
from app import app
from models.trials import load_trials, row_to_dict
from models.trial import load_trial_activation_tree, get_modules, get_environment
from trial_visitors.trial_graph import TrialGraphVisitor, TrialGraphCombineVisitor



@app.route('/<path:path>')
def static_proxy(path):
    return app.send_static_file(path)

@app.route('/trials')
def trials():
    cwd = os.getcwd()
    persistence.connect_existing(cwd)
    return jsonify(**load_trials(request.args.get('script'), 
                                 request.args.get('execution')))

@app.route('/trials/<tid>/independent')
def independent_trial_graph(tid):
    cwd = os.getcwd()
    persistence.connect_existing(cwd)
    tree = load_trial_activation_tree(tid)
    visitor = TrialGraphVisitor()
    tree.visit(visitor)
    return jsonify(**visitor.to_dict())

@app.route('/trials/<tid>/combined')
def combined_trial_graph(tid):
    cwd = os.getcwd()
    persistence.connect_existing(cwd)
    tree = load_trial_activation_tree(tid)
    visitor = TrialGraphCombineVisitor()
    tree.visit(visitor)
    return jsonify(**visitor.to_dict())


@app.route('/')
def index():
    cwd = os.getcwd()
    persistence.connect_existing(cwd)
    
    scripts = {s[0].rsplit('/',1)[-1] for s in persistence.distinct_scripts()}
    return render_template("index.html", 
        cwd = cwd,
        scripts = scripts
    )

@app.route('/trials/<tid>/dependencies')
def dependencies(tid):
    cwd = os.getcwd()
    persistence.connect_existing(cwd)
    trial, local, result = get_modules(cwd, tid)
    return jsonify(local=local, all=result)

@app.route('/trials/<tid>/all_modules')
def all_modules(tid):
    cwd = os.getcwd()
    persistence.connect_existing(cwd)
    trial, local, result = get_modules(cwd, tid)
    result = sorted(result, key=lambda x:x not in local)
    return render_template("trial.html", 
        cwd = cwd,
        trial = trial,
        modules = result,
        info = "modules.html",
    )

@app.route('/trials/<tid>/environment')
def environment(tid):
    cwd = os.getcwd()
    persistence.connect_existing(cwd)
    env = get_environment(tid)
    return jsonify(env=env)


@app.route('/trials/<tid>/all_environment')
def all_environment(tid):
    cwd = os.getcwd()
    persistence.connect_existing(cwd)
    trial = persistence.load_trial(tid).fetchone()
    env = get_environment(tid)
    return render_template("trial.html", 
        cwd = cwd,
        trial = trial,
        env = env,
        info = "environment.html",
    )
