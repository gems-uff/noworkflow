import os
from noworkflow import persistence
from flask import render_template, jsonify
from app import app

def load_trials(cwd):
	persistence.connect_existing(cwd)
	return persistence.load('trial')

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
	main = None
	activations = []
	for activation in persistence.load('function_activation', trial_id=tid):
		activations.append({
			'id': activation[0],
			'name': activation[1],
			'line': activation[2],
			'return': activation[3],
			'start': activation[4],
			'finish': activation[5],
			'caller_id': activation[6],
		})
		if not activation[6]:
			main = activations[-1]

	return jsonify(
		main=main,
		activations=activations
	)

@app.route('/')
def index():
	cwd = os.getcwd()
	return render_template("index.html", 
		cwd = cwd
	)