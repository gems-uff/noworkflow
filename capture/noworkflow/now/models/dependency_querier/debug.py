# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Classes for helping debugging the querier"""

from collections import defaultdict
from future.utils import viewvalues

from ....patterns import var
from ....patterns.rules import name as name_
from ...utils.functions import run_dot

from .graph import DependencyQuerier
from .helpers import Arrow


class StaticDebugDependencyQuerier(DependencyQuerier):
    """Creates all possible arrows before, and gets them during search"""
    def __init__(self, trial):
        super(StaticDebugDependencyQuerier, self).__init__(trial)
        self.arrows = defaultdict(dict)
        initial_activation = self.trial.initial_activation
        if not initial_activation:
            # There is no activation in this trial
            return
        self.start = initial_activation.start

    def _elapsed_time(self, current):
        """Get elapsed time in microseconds from start to current moment
        Use for debug
        """
        if current is None:
            return ""
        return str((current - self.start).microseconds)

    def add_static_arrow(self, from_, to_, name, moment=None, part=None):
        """Add static arrow *name* *from_* node *to_* another node
        at a given moment.
        Only add in debug mode
        """
        # pylint: disable=too-many-arguments
        arrow = self.arrows[from_][to_] = Arrow(name, moment, part)
        if moment is not None:
            arrow.label += "\n" + self._elapsed_time(moment)

    def get_arrow(self, from_, to_, name, moment=None, part=None):
        """Get arrow used to go from a node to another"""
        # pylint: disable=unused-argument, too-many-arguments
        #arrow = Arrow(name, moment)
        #if moment is not None:
        #    arrow.label += "\n" + self._elapsed_time(moment)
        return self.arrows[from_][to_]

    def visit_arrow(self, arrow, index, new_context):
        """Visit arrow"""
        arrow.marked = True
        arrow.label += "\n{} {} {}".format(
            index,
            self._elapsed_time(new_context.moment),
            {(x[0].id, x[1]) for x in new_context.block_set}
        )

    def reset_arrows(self):
        """Reset marks on static arrows"""
        for influenced in viewvalues(self.arrows):
            for arrow in viewvalues(influenced):
                arrow.marked = False

    def _get_name(self, element):
        """Get element name"""
        # pylint: disable=no-self-use
        the_name = var("the_name")
        type_name = type(element).__name__
        return "{}({}, {})".format(
            type_name[0],
            element.id,
            next(iter(name_(
                element.trial_id, type_name.lower(), element.id, the_name
            )))[1][the_name]
        )

    def _get_id(self, element):
        """Get element id"""
        # pylint: disable=no-self-use
        return "{}{}".format(
            type(element).__name__,
            element.id
        )

    def arrows_to_dot(self):
        """Convert arrows to dot"""
        result = []
        result.append("digraph G {")
        result.append("  rankdir=BT")
        nodes = {}

        def include(element):
            """Include node"""
            if element not in nodes:
                nodes[element] = '  {} [label="{}" color="{}"];'.format(
                    self._get_id(element),
                    self._get_name(element),
                    "blue" if element in self.visited_nodes else "black"
                )
        edges = []
        for influenced, influencers in self.arrows.items():
            include(influenced)
            for influencer, arrow in influencers.items():
                include(influencer)
                edges.append('  {} -> {} {};'.format(
                    self._get_id(influenced),
                    self._get_id(influencer),
                    arrow,
                ))
        result.extend(nodes.values())
        result.extend(edges)
        result.append("}")
        return "\n".join(result)

    def draw_arrows(self, format_="png"):
        """Draw arrows"""
        from IPython.display import display_png, display_svg
        {'SVG': display_svg, 'PNG': display_png}[format_.upper()](
            run_dot(self.arrows_to_dot(), format_),
            raw=True
        )


class DynamicDebugDependencyQuerier(StaticDebugDependencyQuerier):
    """Creates arrows during search"""

    def add_static_arrow(self, from_, to_, name, moment=None, part=None):
        """Do Nothing"""
        # pylint: disable=too-many-arguments, no-self-use
        pass

    def get_arrow(self, from_, to_, name, moment=None, part=None):
        """Get arrow used to go from a node to another or create a new one"""
        # pylint: disable=too-many-arguments
        arrow = self.arrows[from_].get(to_)
        if arrow is None:
            arrow = self.arrows[from_][to_] = Arrow(name, moment, part)
            if moment is not None:
                arrow.label += "\n" + self._elapsed_time(moment)
        return arrow

    def reset_arrows(self):
        """Erase all arroes"""
        self.arrows.clear()
