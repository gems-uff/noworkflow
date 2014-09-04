import os
from noworkflow import persistence
from flask import render_template, jsonify
from app import app
from models.trials import load_trials
from models.trial import load_trial_activation_tree
from trial_visitors.trial_graph import TrialGraphVisitor

@app.route('/<path:path>')
def static_proxy(path):
	return app.send_static_file(path)

@app.route('/trials')
def trials():
	cwd = os.getcwd()
	persistence.connect_existing(cwd)
	return jsonify(**load_trials())

@app.route('/trials/<tid>')
def trial(tid):
	cwd = os.getcwd()
	persistence.connect_existing(cwd)
	tree = load_trial_activation_tree(tid)
	visitor = TrialGraphVisitor()
	tree.visit(visitor)
	return jsonify(**visitor.to_dict())

@app.route('/')
def index():
	cwd = os.getcwd()
	return render_template("index.html", 
		cwd = cwd
	)