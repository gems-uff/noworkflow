# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import argparse
import json

from .. import utils
from ..persistence import persistence
from ..models.trial import Trial
from ..models.trial_prolog import TrialProlog
from .command import Command


def int_or_type(string):
    try:
        return int(string)
    except ValueError:
        if "diff" in string:
            splitted = string.split(':')
            if len(splitted) < 3:
                raise argparse.ArgumentTypeError("you must diff two trials")
            return splitted
        return string


def nbconvert(code):
    cells = []
    for cell in code.split('\n# <codecell>\n'):
        cells.append({
            'cell_type': 'code',
            'execution_count': None,
            'metadata': {
                'collapsed': True,
            },
            'outputs': [],
            'source': [cell]
        })
    result = {
        'cells': cells,
        'nbformat': 4,
        'nbformat_minor': 0,
        'metadata': {
            "kernelspec": {
                "display_name": "Python 2",
                "language": "python",
                "name": "python2"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 2
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython2",
                "version": "2.7.6"
            }
        }
    }
    return result


class Export(Command):

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg('-r', '--rules', action='store_true',
                help='also exports inference rules')
        add_arg('-i', '--ipython', action='store_true',
                help='export ipython notebook file')
        add_arg('trial', type=int_or_type, nargs='?',
                help='trial id or none for last trial. If you are generation '
                     'ipython notebook files, it is also possible to use "history"'
                     'or "diff:<trial_id_1>:<trial_id_2>"')
        add_arg('--dir', type=str,
                help='set project path where is the database. Default to '
                     'current directory')

    def execute(self, args):
        persistence.connect_existing(args.dir or os.getcwd())
        if not args.ipython:
            trial = Trial(trial_id=args.trial, exit=True)
            trial_prolog = TrialProlog(trial)
            print(trial_prolog.export_text_facts())
            if args.rules:
                print(trial_prolog.export_rules())
        else:
            if args.trial == "history":
                nb = nbconvert((u"%load_ext noworkflow\n"
                                u"import noworkflow.now.ipython as nip\n"
                                u"# <codecell>\n"
                                u"history = nip.History()\n"
                                u"# history.graph_width = 700\n"
                                u"# history.graph_height = 300\n"
                                u"# history.script = '*'\n"
                                u"# history.execution = '*'\n"
                                u"# <codecell>\n"
                                u"history").format(args.trial))
                with open('History.ipynb'.format(args.trial),'w') as ipynb:
                    json.dump(nb, ipynb)
            elif isinstance(args.trial, list):
                nb = nbconvert((u"%load_ext noworkflow\n"
                                u"import noworkflow.now.ipython as nip\n"
                                u"# <codecell>\n"
                                u"diff = nip.Diff({1}, {2})\n"
                                u"# diff.graph_type = 0\n"
                                u"# diff.display_mode = 0\n"
                                u"# diff.graph_width = 500\n"
                                u"# diff.graph_height = 500\n"
                                u"# <codecell>\n"
                                u"diff").format(*args.trial))
                with open('Diff-{1}-{2}.ipynb'.format(*args.trial),'w') as ipynb:
                    json.dump(nb, ipynb)
            else:
                nb = nbconvert((u"%load_ext noworkflow\n"
                                u"import noworkflow.now.ipython as nip\n"
                                u"# <codecell>\n"
                                u"trial = nip.Trial({})\n"
                                u"# trial.graph_type = 0\n"
                                u"# trial.graph_width = 500\n"
                                u"# trial.graph_height = 500\n"
                                u"# <codecell>\n"
                                u"trial").format(args.trial))
                with open('Trial-{}.ipynb'.format(args.trial),'w') as ipynb:
                    json.dump(nb, ipynb)
