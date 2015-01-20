from pkg_resources import resource_string
from IPython.display import (
    display_html, display_javascript
)

def resource(filename):
	return resource_string(__name__, filename).decode(encoding='UTF-8')

def init():

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
		'vis/static/font-awesome-4.2.0/css/font-awesome.min.css',
		'vis/static/shared_graph.css',
		'vis/static/trial_graph.css',
		'vis/static/history_graph.css',
	]

	css_lines = ['<style>']
	for css_file in css_files:
		css_lines.append(resource(css_file))
	css_lines.append('</style>')
	display_html('\n'.join(css_lines), raw=True)
