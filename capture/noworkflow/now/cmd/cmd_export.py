# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now export'command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import argparse
import json
import os


from ..persistence.models import Trial
from ..persistence import persistence_config

from .command import Command


def export_type(string):
    """Check if argument is an integer or a diff"""
    if "diff:" in string:
        splitted = string.split(":")
        if len(splitted) < 3:
            raise argparse.ArgumentTypeError("you must diff two trials")
        Trial(trial_ref=splitted[1])
        Trial(trial_ref=splitted[2])
        return splitted
    elif string in ("history", "current"):
        return string
    Trial(trial_ref=string)
    return string


def nbconvert(code):
    """Create Jupyter Notebook code"""
    cells = []
    for cell in code.split("\n# <codecell>\n"):
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {
                "collapsed": True,
            },
            "outputs": [],
            "source": [cell]
        })
    result = {
        "cells": cells,
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
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


def export_notebook(trial):
    """Create notebook in the desired format and save it"""
    if trial == "history":
        inb = nbconvert(("%load_ext noworkflow\n"
                         "import noworkflow.now.ipython as nip\n"
                         "# <codecell>\n"
                         "history = nip.History()\n"
                         "# history.graph.width = 700\n"
                         "# history.graph.height = 300\n"
                         "# history.script = '*'\n"
                         "# history.status = '*'\n"
                         "# <codecell>\n"
                         "history"))
        with open("History.ipynb", "w") as ipynb:
            json.dump(inb, ipynb)
    elif trial == "current":
        inb = nbconvert(("%load_ext noworkflow\n"
                         "import noworkflow.now.ipython as nip\n"
                         "# <codecell>\n"
                         "trial = nip.Trial()\n"
                         "trial\n"
                         "# <codecell>\n"
                         "%now_ls_magic\n"
                         "# <codecell>\n"
                         "%%now_prolog {trial.id}\n"
                         "activation({trial.id}, 1, X, _, _, _)"))
        with open("Current Trial.ipynb", "w") as ipynb:
            json.dump(inb, ipynb)
    elif isinstance(trial, list):
        inb = nbconvert(("%load_ext noworkflow\n"
                         "import noworkflow.now.ipython as nip\n"
                         "# <codecell>\n"
                         "diff = nip.Diff('{1}', '{2}')\n"
                         "# diff.graph.view = 0\n"
                         "# diff.graph.mode = 3\n"
                         "# diff.graph.width = 500\n"
                         "# diff.graph.height = 500\n"
                         "# <codecell>\n"
                         "diff").format(*trial))
        with open("Diff-{1}-{2}.ipynb".format(*trial), "w") as ipynb:
            json.dump(inb, ipynb)
    else:
        inb = nbconvert(("%load_ext noworkflow\n"
                         "import noworkflow.now.ipython as nip\n"
                         "# <codecell>\n"
                         "trial = nip.Trial('{}')\n"
                         "# trial.graph.mode = 3\n"
                         "# trial.graph.width = 500\n"
                         "# trial.graph.height = 500\n"
                         "# <codecell>\n"
                         "trial").format(trial))
        with open("Trial-{}.ipynb".format(trial), "w") as ipynb:
            json.dump(inb, ipynb)


class Export(Command):
    """Export the collected provenance of a trial to Prolog or Notebook"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("-r", "--rules", action="store_true",
                help="also exports inference rules")
        add_arg("-i", "--ipython", action="store_true",
                help="export ipython notebook file")
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial. If you are generation "
                     "ipython notebook files, it is also possible to use "
                     "'history' or 'diff:<trial_id_1>:<trial_id_2>'")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        args.trial = export_type(args.trial)
        if not args.ipython:
            trial = Trial(trial_ref=args.trial)
            print(trial.prolog.export_text_facts())
            if args.rules:
                print("\n".join(trial.prolog.rules()))
        else:
            export_notebook(args.trial)
