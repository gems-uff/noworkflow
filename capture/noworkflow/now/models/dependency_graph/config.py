# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Dependency graph configuration"""

from collections import defaultdict

from future.utils import viewvalues

from ...utils.data import OrderedDefaultDict

from .synonymers import Synonymer
from .filters import FilterValuesOut


class DataflowConfig(object):
    """Configure dependency graph"""

    # pylint: disable=too-many-instance-attributes
    # This is a configuration class. It is expected to have many attributes

    def __init__(self):
        self.rank_option = 0
        self.show_accesses = True
        self.show_values = True
        self.combine_accesses = True
        self.show_external_files = False
        self.max_depth = float("inf")
        self.show_internal_use = True
        self.mode = "simulation"

    @classmethod
    def create_arguments(cls, add_arg, mode="prospective"):
        """Create arguments

        Arguments:
        add_arg -- add argument function
        """
        add_arg("-a", "--accesses", type=int, default=1, metavar="A",
                help="R|show file accesses (default: 1)\n"
                     "0 hides file accesses\n"
                     "1 shows each file once (hide external accesses)\n"
                     "2 shows each file once (show external accesses)\n"
                     "3 shows all accesses (except external accesses)\n"
                     "4 shows all accesses (including external accesses)")
        add_arg("-v", "--values", action="store_true",
                help="R|show values as individual nodes.")
        add_arg("-d", "--depth", type=int, default=0, metavar="D",
                help="R|visualization depth (default: 0)\n"
                     "0 represents infinity")
        add_arg("-u", "--show-internal-use", action="store_false",
                help="show variables and functions which name starts with a "
                     "leading underscore")
        add_arg("-r", "--rank", type=int, default=0, metavar="R",
                help="R|align evalutions in the same column (default: 0)\n"
                     "0 does no align\n"
                     "1 aligns by line\n"
                     "2 aligns by line and column\n"
                     "With this option, all variables in a loop appear\n"
                     "grouped, reducing the width of the graph.\n"
                     "It may affect the graph legibility.\n"
                     "The alignment is independent for each activation.\n")
        add_arg("-m", "--mode", type=str, default=mode,
                choices=["simulation", "group", "prospective"],
                help=("R|Graph mode (default: {})\n"
                      "'simulation' presents a dataflow graph with all\n"
                      "relevant evaluations.\n"
                      "'group' presents a dataflow graph that combines\n"
                      "evaluations with the same values.\n"
                      "'prospective' presents only parameters, calls, and\n"
                      "assignments to calls."
                      .format(mode)))

    def read_args(self, args):
        """Read config from args"""
        self.show_accesses = bool(args.accesses)
        self.show_values = bool(args.values)
        self.combine_accesses = args.accesses in {1, 2}
        self.show_external_files = args.accesses in {2, 4}
        self.max_depth = args.depth or float("inf")
        self.show_internal_use = not bool(args.show_internal_use)
        self.rank_option = bool(args.rank_line)
        self.mode = args.mode

    def rank(self, cluster, new_nodes):
        """Group cluster evaluations"""
        if self.rank_option == 0:
            return
        by_line = OrderedDefaultDict(list)
        for node in new_nodes:
            if node is None:
                continue
            if self.rank_option == 1:
                line = node.evaluation.code_component.first_char_line
            else:
                line = (
                    node.evaluation.code_component.first_char_line,
                    node.evaluation.code_component.first_char_column,
                )

            by_line[line].append(node)

        for eva_nids in viewvalues(by_line):
            cluster.ranks.append(eva_nids)

    def synonymer(self):
        """Return synonymer based on config"""
        return Synonymer()

    def filter(self):
        """Return filter based on config"""
        return FilterValuesOut()
