# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Dependency graph configuration"""

from collections import defaultdict

from future.utils import viewvalues

from ...utils.data import OrderedDefaultDict

from .synonymers import SameSynonymer, ValueSynonymer
from .synonymers import AccessNameSynonymer, JoinedSynonymer
from .filters import FilterValuesOut, FilterAccessesOut, FilterInternalsOut
from .filters import FilterExternalAccessesOut
from .filters import JoinedFilter, AcceptAllNodesFilter
from .node_types import ClusterNode, EvaluationNode


class DependencyConfig(object):
    """Configure dependency graph"""

    # pylint: disable=too-many-instance-attributes
    # This is a configuration class. It is expected to have many attributes

    def __init__(self):
        self.rank_option = 0
        self.show_accesses = True
        self.show_values = False
        self.show_internals = False
        self.show_external_files = False
        self.combine_accesses = True
        self.combine_assignments = True
        self.combine_values = False
        self.max_depth = float("inf")
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
        add_arg("-H", "--hide-internals", action="store_false",
                help="show variables and functions which name starts with a "
                     "leading underscore")
        add_arg("-e", "--evaluations", type=int, default=1, metavar="E",
                help="R|combine evaluation nodes (default: 1)\n"
                     "0 does not combine evaluation nodes\n"
                     "1 combines evaluation nodes by assignment\n"
                     "2 combines evaluation nodes by value")
        add_arg("-d", "--depth", type=int, default=0, metavar="D",
                help="R|visualization depth (default: 0)\n"
                     "0 represents infinity")
        add_arg("-g", "--group", type=int, default=0, metavar="R",
                help="R|align evalutions in the same column (default: 0)\n"
                     "0 does no align\n"
                     "1 aligns by line\n"
                     "2 aligns by line and column\n"
                     "With this option, all variables in a loop appear\n"
                     "grouped, reducing the width of the graph.\n"
                     "It may affect the graph legibility.\n"
                     "The alignment is independent for each activation.\n")
        add_arg("-m", "--mode", type=str, default=mode,
                choices=[
                    "simulation", "activation", "dependency", "prospective"
                ],
                help=("R|Graph mode (default: {})\n"
                      "'simulation' presents a dataflow graph with all\n"
                      "relevant evaluations.\n"
                      "'activation' presents only activations.\n"
                      "'dependency' presents a graph with a single cluster,\n"
                      "with all evaluations and activations.\n"
                      "'prospective' presents only parameters, calls, and\n"
                      "assignments to calls."
                      .format(mode)))

    def read_args(self, args):
        """Read config from args"""
        self.show_accesses = bool(args.accesses)
        self.show_values = bool(args.values)
        self.show_internals = not bool(args.hide_internals)
        self.show_external_files = args.accesses in {2, 4}

        self.combine_accesses = args.accesses in {1, 2}
        self.combine_assignments = args.evaluations == 1
        self.combine_values = args.evaluations == 2

        self.max_depth = args.depth or float("inf")
        self.rank_option = args.group
        self.mode = args.mode

    def rank(self, cluster):
        """Group cluster evaluations"""
        if self.rank_option == 0:
            return
        by_line = OrderedDefaultDict(list)
        for node in cluster.elements:
            if not isinstance(node, EvaluationNode):
                continue
            #if isinstance(node, ClusterNode):
            #    continue
            if self.rank_option == 1:
                line = node.line
            else:
                line = (node.line, node.column)

            by_line[line].append(node)

        for eva_nids in viewvalues(by_line):
            cluster.ranks.append(eva_nids)

    def synonymer(self, extra=None):
        """Return synonymer based on config"""
        synonymers = []
        if self.combine_accesses:
            synonymers.append(AccessNameSynonymer())
        if self.combine_assignments:
            synonymers.append(SameSynonymer())
        if self.combine_values:
            synonymers.append(ValueSynonymer())
        synonymers.extend(extra or [])
        return JoinedSynonymer.create(*synonymers)

    def filter(self, extra=None):
        """Return filter based on config"""
        filters = []
        if not self.show_values:
            filters.append(FilterValuesOut())
        if not self.show_accesses:
            filters.append(FilterAccessesOut())
        elif not self.show_external_files:
            filters.append(FilterExternalAccessesOut())
        if not self.show_internals:
            filters.append(FilterInternalsOut())
        filters.extend(extra or [])
        if not filters:
            return AcceptAllNodesFilter()
        return JoinedFilter.create(*filters)

    def clusterizer(self, trial, filter_=None, synonymer=None):
        """Return clusterizer based on config"""
        from .clusterizer import Clusterizer
        from .clusterizer import ActivationClusterizer
        from .clusterizer import DependencyClusterizer
        from .clusterizer import ProspectiveClusterizer
        cls = {
            "simulation": Clusterizer,
            "activation": ActivationClusterizer,
            "dependency": DependencyClusterizer,
            "prospective": ProspectiveClusterizer,
        }[self.mode]
        return cls(
            trial,
            config=self,
            filter_=filter_,
            synonymer=synonymer
        )
