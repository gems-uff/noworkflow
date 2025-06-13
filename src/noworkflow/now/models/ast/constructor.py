# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Operations to reconstruct AST trees"""
from .model import NowNode

def add_composition(node, composition, part=None):
    """Add composition to node"""
    if part is None:
        raise ValueError("'part' must be a function that returns a node")
    node.add_attr(
        composition.type,
        part(composition),
        position=composition.position,
        extra=composition.extra
    )

def create_trees(components_list, blocks_map, compositions_list):
    """Create all NowNode trees from a trial"""

    # Sort compositions by position
    sorted_compositions = sorted(
        compositions_list,
        key=lambda x: (x.position is None, x.position)
    )

    # Create map of components as NowNode
    nodes = {
        comp.id: NowNode(comp, blocks_map.get(comp.id))
        for comp in components_list
    }

    # Transform compositions into attributes
    function = lambda comp: nodes.get(comp.part_id)
    for composition in sorted_compositions:
        add_composition(nodes[composition.whole_id], composition, function)
    return nodes

def component_to_tree(component):
    """Convert CodeComponent to NowNode tree"""
    if component is None:
        return None
    node = NowNode(component, component.this_block)

    function = lambda comp: component_to_tree(comp.part)
    for composition in component.compositions_as_whole:
        add_composition(node, composition, function)
    return node
