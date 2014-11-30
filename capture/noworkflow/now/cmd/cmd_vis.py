# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import webbrowser
import threading

from ..persistence import persistence
from .command import Command

class Vis(Command):

    def add_arguments(self):
        add_arg = self.parser.add_argument
        add_arg('-p', '--port', nargs='?', type=int, default=5000,
                help='sets server port')
        add_arg('-d', '--debug', action='store_true',
                help='debug mode')
        add_arg('-b', '--browser', action='store_true',
                help='opens browser')

    def execute(self, args):
        if args.browser:
            url = "http://127.0.0.1:{0}".format(args.port)
            print(url)
            threading.Timer(1.25, lambda: webbrowser.open(url)).start()
        from ..vis.views import app
        app.run(port=args.port, debug=args.debug)
