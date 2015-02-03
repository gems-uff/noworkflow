# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
from .. import utils
from ..persistence import persistence
from ..models.trial import Trial
from ..models.trial_prolog import TrialProlog
from .command import Command

def int_or_type(string):
    try:
        return int(string)
    except ValueError:
        return string


class Export(Command):

    def add_arguments(self):
        add_arg = self.parser.add_argument
        add_arg('trial', type=int_or_type, nargs='?',
                help='trial id or none for last trial. If you are generation '
                     'ipython notebook files, you can also use "history"')
        add_arg('-r', '--rules', action='store_true',
                help='also exports inference rules')
        add_arg('-i', '--ipython', action='store_true',
                help='export ipython notebook file')

    def execute(self, args):
        persistence.connect_existing(os.getcwd())
        if not args.ipython:
            trial = Trial(trial_id=args.trial, exit=True)
            trial_prolog = TrialProlog(trial)
            print(trial_prolog.export_text_facts())
            if args.rules:
                print(trial_prolog.export_rules())
        else:
            import IPython.nbformat.current as nbf
            if args.trial == "history":
                nb = nbf.reads((u"import noworkflow.now.ipython as nip\n"
                      u"nip.init()\n"
                      u"history = nip.History()\n"
                      u"# history.graph_width = 700\n"
                      u"# history.graph_height = 300\n"
                      u"# history.script = '*'\n"
                      u"# history.execution = '*'\n"
                      u"history").format(args.trial), 'py')
                with open('History.ipynb'.format(args.trial),'w') as ipynb:
                    nbf.write(nb, ipynb, 'ipynb')
            else:
                nb = nbf.reads((u"import noworkflow.now.ipython as nip\n"
                      u"nip.init()\n"
                      u"trial = nip.Trial({})\n"
                      u"# trial.display_mode = 0\n"
                      u"# trial.graph_width = 500\n"
                      u"# trial.graph_height = 500\n"
                      u"trial").format(args.trial), 'py')
                with open('Trial-{}.ipynb'.format(args.trial),'w') as ipynb:
                    nbf.write(nb, ipynb, 'ipynb')