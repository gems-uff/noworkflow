# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from IPython.display import display_html, display_javascript

from ..persistence import persistence
from ..utils import resource

from .models import set_default, update_all, Trial, Diff, History
from .magics import register_magics


def init(path=None, ipython=None):
    register_magics(ipython)

    if path is None:
        path = os.getcwd()
    persistence.connect(path)

    js_files = [
        'vis/static/d3-v3.4.11/d3.min.js',
        'vis/static/trial_graph.js',
        'vis/static/history_graph.js',
        'vis/static/ipython.js',
    ]

    require_js = '''
        <!DOCTYPE html>
        <meta charset="utf-8">
        <body>
            <script charset="utf-8">
            var now_temp = define;
            define = undefined;
            {0}
            define = now_temp;
            </script>
        </body
    '''
    js_text = [resource(js_file, 'utf-8') for js_file in js_files]

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
        css_lines.append(resource(css_file, 'utf-8'))
    css_lines.append('</style>')
    display_html('\n'.join(css_lines), raw=True)

    return "ok"
