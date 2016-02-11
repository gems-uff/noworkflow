# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now show' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from ..ipython.converter import create_ipynb
from ..persistence.models import Trial
from ..persistence import persistence_config
from ..utils.functions import wrap
from ..utils.io import print_msg

from .command import NotebookCommand


def print_trial_relationship(relation, breakline="\n\n", other="\n    "):
    """Print trial relationship"""
    output = []
    for obj in relation:
        obj.show(_print=lambda x: output.append(wrap(x, other=other)))
    print(breakline.join(output))


def print_function_activation(trial, activation, level=1):
    """Print function activation recursively"""
    text = wrap(
        "{0.line}: {0.name} ({0.start} - {0.finish})".format(activation),
        initial="  " * level)
    indent = text.index(": ") + 2
    print(text)
    activation.show(_print=lambda x, offset=0: print(
        wrap(x, initial=" " * (indent + offset))))

    for inner_activation in activation.children:
        print_function_activation(trial, inner_activation, level + 1)


class Show(NotebookCommand):
    """Show the collected provenance of a trial"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial")
        add_arg("-m", "--modules", action="store_true",
                help="shows module dependencies")
        add_arg("-d", "--function-defs", action="store_true",
                help="shows the user-defined functions")
        add_arg("-e", "--environment", action="store_true",
                help="shows the environment conditions")
        add_arg("-a", "--function-activations", action="store_true",
                help="shows function activations")
        add_arg("-f", "--file-accesses", action="store_true",
                help="shows read/write access to files")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

    def execute(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
        trial = Trial(trial_ref=args.trial)

        print_msg("trial information:", True)
        trial.show(_print=lambda x: print(wrap(x)))

        if args.modules:
            print_msg("this trial depends on the following modules:", True)
            print_trial_relationship(trial.modules)

        if args.function_defs:
            print_msg("this trial has the following functions:", True)
            print_trial_relationship(trial.function_defs)

        if args.environment:
            print_msg("this trial has been executed under the following"
                      " environment conditions", True)
            print_trial_relationship(trial.environment_attrs, breakline="\n",
                                     other="\n  ")

        if args.function_activations:
            print_msg("this trial has the following function activation "
                      "graphF:", True)
            for act in trial.initial_activations:                                # pylint: disable=not-an-iterable
                print_function_activation(trial, act)

        if args.file_accesses:
            print_msg("this trial accessed the following files:", True)
            print_trial_relationship(trial.file_accesses)

    def execute_export(self, args):
        persistence_config.connect_existing(args.dir or os.getcwd())
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
                "trial").format(repr(args.trial) if args.trial else '')
        if not args.trial:
            name = "Current Trial.ipynb"
            code += (
                "\n"
                "# <codecell>\n"
                "%now_ls_magic\n"
                "# <codecell>\n"
                "%%now_prolog {trial.id}\n"
                "activation({trial.id}, 1, X, _, _, _)"
            )

        create_ipynb(name, code)
