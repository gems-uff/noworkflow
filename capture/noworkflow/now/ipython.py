# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
						division, unicode_literals)

import os

from pkg_resources import resource_string
from IPython.display import (
    display_html, display_javascript
)
from .models.trial import Trial
from .models.diff import Diff
from .models.history import History
from .persistence import persistence

def resource(filename):
	return resource_string(__name__, filename).decode(encoding='UTF-8')

def init(path=None):
	if path is None:
		path = os.getcwd()
	persistence.connect_existing(path)

	js_files = [
		'vis/static/d3-v3.4.11/d3.min.js',
		#'vis/static/external/jquery-1.11.1.min.js',
		'vis/static/trial_graph.js',
		'vis/static/history_graph.js',
	]

	require_js = '''
		<!DOCTYPE html>
		<meta charset="utf-8">
		<body>
			<script charset="utf-8">
			{0}
			</script>
		</body
	'''
	js_text = [resource(js_file) for js_file in js_files]

	display_html(
		require_js.format(';\n'.join(js_text)),
		raw=True
		)

	css_files = [
		'vis/static/font-awesome-4.3.0/css/font-awesome-ip.css',
		'vis/static/shared_graph.css',
		'vis/static/trial_graph.css',
		'vis/static/history_graph.css',
	]

	css_lines = ['<style>']
	for css_file in css_files:
		css_lines.append(resource(css_file))
	css_lines.append('</style>')
	display_html('\n'.join(css_lines), raw=True)

	return "ok"