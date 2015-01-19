from pkg_resources import resource_string
from IPython.display import (
    display_html, display_javascript
)

def init():
	js_files = [
		'vis/static/d3-v3.4.11/d3.min.js',
		'vis/static/trial_graph.js',
		'vis/static/external/jquery-1.11.1.min.js',
	]
	for js_file in js_files:
		display_javascript(resource_string(__name__,
			js_file).decode(encoding='UTF-8'))

	#css_files = [
	#	'vis/static/'
	#]
