# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""IPython Module"""
from __future__ import (absolute_import, print_function,
                        division)


from ..persistence.models import *                                               # pylint: disable=wildcard-import
from ..persistence import persistence_config, relational, content


def init(path=None, ipython=None):
    """Initiate noWorkflow extension.
    Load D3, IPython magics, and connect to database


    Keyword Arguments:
    path -- database path (default=current directory)
    ipython -- IPython object (default=None)
    """

    import os
    from IPython.display import display_html
    from ..utils.functions import resource
    from .magics import register_magics
    try:
        from .hierarchymagic import load_ipython_extension as load_hierarchy
        load_hierarchy(ipython)
    except ImportError:
        print("Warning: Sphinx is not installed. Dot "
              "graphs won't work")

    register_magics(ipython)

    if path is None:
        path = os.getcwd()
    persistence_config.connect(path)

    js_files = [
        u"vis/static/d3-v3.4.11/d3.min.js",
        u"vis/static/trial_graph.js",
        u"vis/static/history_graph.js",
        u"vis/static/ipython.js",
    ]

    require_js = u"""
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
    """
    js_text = [resource(js_file, u"utf-8") for js_file in js_files]

    display_html(
        require_js.format(";\n".join(js_text)),
        raw=True
    )

    css_files = [
        u"vis/static/font-awesome-4.3.0/css/font-awesome-ip.css",
        u"vis/static/shared_graph.css",
        u"vis/static/trial_graph.css",
        u"vis/static/history_graph.css",
    ]

    css_lines = [u"<style>"]
    for css_file in css_files:
        css_lines.append(resource(css_file, u"utf-8"))
    css_lines.append(u"</style>")
    display_html(u"\n".join(css_lines), raw=True)

    return u"ok"
