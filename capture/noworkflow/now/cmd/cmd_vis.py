# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now vis' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import threading
import webbrowser

from ..persistence import persistence_config

from .command import Command


def run(path=None, browser=False, port=5000, debug=False):
    """Open Flask server"""
    if browser:
        url = "http://127.0.0.1:{0}".format(port)
        print(url)
        threading.Timer(1.25, lambda: webbrowser.open(url)).start()
    from ..vis.views import app
    app.dir = path or os.getcwd()
    app.run(port=port, debug=debug, threaded=True)


class Vis(Command):
    """ Open visualization tool """

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("-p", "--port", nargs="?", type=int, default=5000,
                help="sets server port")
        add_arg("-d", "--debug", action="store_true",
                help="debug mode")
        add_arg("-b", "--browser", action="store_true",
                help="opens browser")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        run(path=args.dir, browser=args.browser, port=args.port,
            debug=args.debug)
