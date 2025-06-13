# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""""now list" command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
from bisect import bisect_left

from ..persistence.models import Trial
from ..persistence import persistence_config
from ..persistence.models.base import proxy_gen
from ..utils.io import print_msg

from .command import Command
from .cmd_evaluation import add_query_arguments, query_evaluations


class Clean(Command):
    """Clean jupyter notebook using the collected provenance"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial")
        add_arg("-o", "--output", type=str,
                help="Notebook output name. By default it is clean-notebook-[Trial].ipynb")
        add_arg("-j", "--notebook", type=str,
                help="Previous notebook for merging markdown cells")
        add_arg("--header", action="store_true",
                help="Create header")
        add_arg("--merge-last", action="store_true",
                help="Add cells from merged notebook after the clean notebook in ambiguous situations")
        add_arg("--merge-code", action="store_true",
                help="Also restore code cells from previous notebook during merge")
        add_arg("--add-empty", action="store_true",
                help="Add empty code cell in the end")
        add_query_arguments(add_arg)
                
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")
        add_arg("--content-engine", type=str,
                help="set the content database engine")

    def execute(self, args):
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        
        trial = Trial(trial_ref=args.trial)
        result = list(proxy_gen(query_evaluations(args)))

        from ..models.dependency_querier import PreloadedQuerierOptions
        from ..models.cleaning import get_cells, create_clean, create_merged_from_cells
        options = PreloadedQuerierOptions(trial, visit_out=False)
       
        cells = get_cells(result, options)
        if not cells:
            print("Trial {} is not a notebook trial".format(args.trial))
            return
        name = args.trial or "current"
        filename = args.output or "clean-notebook-{}.ipynb".format(name)
        merge = args.notebook is not None

        if not merge:
            create_clean(
                cells, filename, name, 
                args.header, args.add_empty,
            )
        else:
            create_merged_from_cells(
                cells, filename, args.notebook, name,
                args.header, args.add_empty,
                not args.merge_last, args.merge_code
            )
        print("Created clean notebook: {}".format(filename))
