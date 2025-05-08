# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from collections import defaultdict
from ....patterns import var
from ....patterns.rules import name as name_
from .querier_options import PreloadedQuerierOptions


class Arrow(object):
    """Represent an arrow with a label"""
    # pylint: disable=too-few-public-methods
    def __init__(self, mode, checkpoint=None):
        self.mode = mode
        self.checkpoint = checkpoint
        self.marked = False

    def __repr__(self):
        label = self.mode
        if self.checkpoint is not None:
            label = "{}\n{}".format(label, self.checkpoint)
        if not self.marked:
            return '[label="{}"]'.format(label)
        return '[label="{}" color="blue"]'.format(label)


class StaticDebugOptions(PreloadedQuerierOptions):
    """Creates all possible arrows before, and gets them during search"""
    
    def __init__(self, *args, **kwargs):
        super(StaticDebugOptions, self).__init__(*args, **kwargs)
        self.arrows = {}
        self.visited_nodes = set()
        self.format = "png"
        
    def add_static_arrow(self, from_, to_, mode, checkpoint=None):
        """Add static arrow *name* *from_* node *to_* another node
        at a given checkpoint.
        Only add in debug mode
        """
        self.arrows[(from_, to_, mode, checkpoint)] = Arrow(mode, checkpoint)

    def visit_arrow(self, from_context, to_context):
        """Visit arrow"""
        mode, checkpoint = to_context.arrow, to_context.checkpoint
        tup = (
            from_context.evaluation, to_context.evaluation,
            to_context.arrow, to_context.checkpoint
        )
        arrow = self.arrows.get(tup, None)
        if arrow is None:
            arrow = self.arrows[tup] = Arrow(mode, checkpoint)
        arrow.marked = True
        
    def visit_context(self, context):
        """Visit context"""
        self.visited_nodes.add(context.evaluation)
        return context

    def reset_arrows(self):
        """Reset marks on static arrows"""
        self.visited = set()
        for tup, arrow in self.arrows.items():
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
        for tup, arrow in self.arrows.items():
            include(tup[0])
            include(tup[1])
            edges.append('  {} -> {} {};'.format(
                self._get_id(tup[0]),
                self._get_id(tup[1]),
                arrow,
            ))
        result.extend(nodes.values())
        result.extend(edges)
        result.append("}")
        return "\n".join(result)
    
    def _ipython_display_(self):
        from IPython.display import display
        from IPython import get_ipython
        ipython = get_ipython()
        obj = ipython.run_cell_magic(
            "dot", "--format {}".format(self.format), self.arrows_to_dot()
        )
        display(obj)
    

class DynamicDebugOptions(StaticDebugOptions):
    
    def add_static_arrow(self, from_, to_, mode, checkpoint=None):
        """Do Nothing"""

    def reset_arrows(self):
        """Erase all arroes"""
        self.arrows.clear()
