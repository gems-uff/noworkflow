# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now export ipynb'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from argparse import Namespace

from ...persistence.models import Trial
from ...persistence import persistence_config


from ...models.ast.trial_ast import TrialAst
from ...models.diff import Diff as DiffModel
from ...ipython.converter import create_ipynb

from ..command import Command

class Ipynb(Command):
    """Create a notebook file for analysis"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial", type=str, nargs="?",
                help="Options: (i) 'trial_id' or empty for last trial; "
                     "(ii) 'history' for history graph; "
                     "(iii) 'diff:<trial_id_1>:<trial_id_2>' for the difference between two trials.")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")
        add_arg("--content-engine", type=str,
                help="set the content database engine")

    def execute(self, args):
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        
        if args.trial and args.trial.startswith("diff:"):
            splitted = dict(enumerate(args.trial.split(":")))
            trial1 = splitted[1]
            trial2 = splitted[2]
            DiffModel(trial1, trial2)
            name = "Diff-{0}-{1}.ipynb".format(trial1, trial2)
            code = ("%load_ext noworkflow\n"
                    "import noworkflow.now.ipython as nip\n"
                    "# <codecell>\n"
                    "diff = nip.Diff('{0}', '{1}')\n"
                    "# diff.graph.view = 0\n"
                    "# diff.graph.mode = 3\n"
                    "# diff.graph.width = 500\n"
                    "# diff.graph.height = 500\n"
                    "# <codecell>\n"
                    "diff").format(trial1, trial2)
        elif args.trial == "history":
            name = "History.ipynb"
            code = ("%load_ext noworkflow\n"
                    "import noworkflow.now.ipython as nip\n"
                    "# <codecell>\n"
                    "history = nip.History()\n"
                    "# history.graph.width = 700\n"
                    "# history.graph.height = 300\n"
                    "# history.script = '*'\n"
                    "# history.status = '*'\n"
                    "# <codecell>\n"
                    "history")
        elif not args.trial or args.trial == "current":
            name = "Current Trial.ipynb"
            code = ("%load_ext noworkflow\n"
                    "import noworkflow.now.ipython as nip\n"
                    "# <codecell>\n"
                    "trial = nip.Trial()\n"
                    "# trial.graph.mode = 3\n"
                    "# trial.graph.width = 500\n"
                    "# trial.graph.height = 500\n"
                    "# <codecell>\n"
                    "trial"
                    "\n"
                    "# <codecell>\n"
                    "%now_ls_magic\n"
                    "# <codecell>\n"
                    "%%now_prolog {trial.id}\n"
                    "activation({trial.id}, 1, X, _, _, _)")
        else:
            Trial(trial_ref=args.trial)
            name = "Trial-{}.ipynb".format(args.trial)
            code = ("%load_ext noworkflow\n"
                    "import noworkflow.now.ipython as nip\n"
                    "# <codecell>\n"
                    "trial = nip.Trial({})\n"
                    "# trial.graph.mode = 3\n"
                    "# trial.graph.width = 500\n"
                    "# trial.graph.height = 500\n"
                    "# <codecell>\n"
                    "trial").format(repr(args.trial))
        create_ipynb(name, code)
