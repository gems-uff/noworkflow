# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
from __future__ import absolute_import
from __future__ import print_function

import os
import webbrowser
import threading

from ..vis import app
from .command import Command
from ..persistence import persistence

class Vis(Command):

    def add_arguments(self):
        p = self.parser
        p.add_argument('-p', '--port', help='sets server port', nargs='?', type=int, default=5000)
        p.add_argument('-d', '--debug', help='debug mode', action='store_true')
        p.add_argument('-b', '--browser', help='opens browser', action='store_true')


    def execute(self, args):
        if args.browser:
            url = "http://127.0.0.1:{0}".format(args.port)
            print(url)
            threading.Timer(1.25, lambda: webbrowser.open(url)).start()
        app.run(port=args.port, debug=args.debug)
