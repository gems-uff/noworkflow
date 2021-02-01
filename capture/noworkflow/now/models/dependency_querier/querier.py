# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from .querier_options import QuerierOptions
from .node_context import NodeContext

class DependencyQuerier(object):

    def __init__(self, options=None):
        self.options = options or QuerierOptions()
        self.last_search = (None, None)

    def navigate_dependencies(self, initial_evaluations, visited=None, stop_on=None):
        self.options.reset_arrows()    
        nodes_to_visit = []
        visited = visited or set()
        for evaluation in initial_evaluations:
            context = NodeContext(evaluation, None, options=self.options)
            if context not in visited:
                nodes_to_visit.append(context)
                visited.add(self.options.visit_context(context))

        found = set()
        while nodes_to_visit:
            context = nodes_to_visit.pop()
            for neighbor in context.dependencies():
                if neighbor not in visited:
                    self.options.visit_arrow(context, neighbor)
                    visited.add(self.options.visit_context(neighbor))
                    nodes_to_visit.append(neighbor)
                    if stop_on and neighbor.evaluation in stop_on:
                        found.add(neighbor.evaluation)
                        if len(found) == len(stop_on):
                            return nodes_to_visit, visited, found
        return nodes_to_visit, visited, found

    