import os
from noworkflow import persistence
from flask import render_template, jsonify
from app import app
from models import load_trial, load_trials


@app.route('/<path:path>')
def static_proxy(path):
	return app.send_static_file(path)

@app.route('/trials')
def trials():
	cwd = os.getcwd()
	result = {
		'nodes': [],
		'edges': [],
	}
	tid = 0
	for trial in load_trials(cwd):
		result['nodes'].append({
			'id': trial[0],
			'start': trial[1],
			'finish': trial[2],
			'script': trial[3],
			'code_hash': trial[4],
			'arguments': trial[5],
			'inherited_id': trial[6],
		})
		if tid:
			result['edges'].append({
				'source': tid,
				'target': tid - 1,
				'level': 0
			})
		tid += 1
	return jsonify(**result)

@app.route('/trials/<tid>')
def trial(tid):
	cwd = os.getcwd()
	persistence.connect_existing(cwd)
	trial = load_trial(tid)
	print trial
	return jsonify(**trial)

@app.route('/')
def index():
	cwd = os.getcwd()
	return render_template("index.html", 
		cwd = cwd
	)