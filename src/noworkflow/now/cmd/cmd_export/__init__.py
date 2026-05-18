from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from argparse import Namespace

from noworkflow.now.models.ast.trial_ast import TrialAst
from noworkflow.now.models.prov.export import export_prov

from ..command import Command

from .cmd_prolog import Prolog
from .cmd_ast import Ast
from .cmd_prov import Prov
from .cmd_dataflow import Dataflow
from .cmd_ipynb import Ipynb
from .cmd_prospective import Prospective

class Export(Command):
    """Export the collected provenance of a trial to different formats"""
    def add_arguments(self):
        export_sub = self.parser.add_subparsers(dest="what", required=True)
        commands = [
            Prolog(),
            Prov(),
            Dataflow(),
            Ast(),
            Ipynb(),
            Prospective(),
        ]
        for cmd in commands:
            cmd.create_parser(export_sub)
            
    def execute(self, args):
        print("Please select an export type")
