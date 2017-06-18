# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial dependency querier"""

from collections import defaultdict
from itertools import chain
from future.utils import viewitems
from ...persistence.models import Evaluation, Value
from .helpers import Arrow, Context, ValueState

class DependencyQuerier(object):
    """Represent a dependency graph for a trial"""
    # pylint: disable=too-many-instance-attributes
    def __init__(self, trial):
        # Trial
        self.trial = trial
        # Cache all trial evaluations
        self.evaluations = {}
        # Cache all trial activations
        self.activations = {}
        # Cache all trial values
        self.values = {}
        # ValueState Map: M[Value][Compartment.name][Moment] = Part
        self.compartments = defaultdict(lambda: defaultdict(ValueState))
        # Map part to evaluation that created it
        self.part_to_evaluation = {}
        # Map evaluation to its value
        self.evaluation_to_value = {}
        # Map evaluation to its parent activation
        self.evaluation_to_activation = {}
        # Map influenced -> influencer to dependency
        self.dependencies = defaultdict(dict)

        # Last search input
        self.last_search = set()
        # Visited nodes in last search
        self.visited_nodes = set()
        # Visited contexts in last search
        self.visited_context = set()
        # Stack of last search
        self.search_stack = []

    def add_static_arrow(self, from_, to_, name, moment=None, part=None):
        """Do nothing by default. Override for debugging"""
        # pylint: disable=unused-argument, no-self-use, too-many-arguments
        pass

    def get_arrow(self, from_, to_, name, moment=None, part=None):
        """Get arrow used to go from a node to another"""
        # pylint: disable=unused-argument, no-self-use, too-many-arguments
        return Arrow(name, moment, part)

    def visit_arrow(self, arrow, index, new_context):
        """Do nothing by default. Override for debugging"""
        # pylint: disable=unused-argument, no-self-use

    def reset_arrows(self):
        """Do nothing by default. Override for debugging"""
        # pylint: disable=unused-argument, no-self-use

    def initialize_compartments(self):
        """Initialize compartments.
        Return parts map
        -- parts map compartment moments to parts
        -- use it to identify evaluations that create compartments"""
        parts = {}
        self.values = {val.id: val for val in self.trial.values}
        for compartment in self.trial.compartments:
            whole = self.values[compartment.whole_id]
            part = self.values[compartment.part_id]
            moment = compartment.moment
            # Dependency to compartments
            self.add_static_arrow(whole, part, "<C>", moment, compartment.name)
            self.compartments[whole][compartment.name][moment] = part
            parts[moment] = part
        return parts

    def initialize_evaluations(self, parts):
        """Initialize evaluations"""
        self.activations = {act.id: act for act in self.trial.activations}
        for evaluation in self.trial.evaluations:
            self.evaluations[evaluation.id] = evaluation
            value = self.values[evaluation.value_id]
            moment = evaluation.moment
            # Dependency to value
            self.add_static_arrow(evaluation, value, "<V>", moment)
            self.evaluation_to_value[evaluation] = value

            if evaluation.activation_id is not None:
                # Dependency to caller
                activation = self.evaluations[evaluation.activation_id]
                self.add_static_arrow(evaluation, activation, "<A>")
                self.evaluation_to_activation[evaluation] = activation

            if moment in parts:
                # Dependency from part created by this evaluation
                self.add_static_arrow(value, evaluation, "<P>", moment)
                self.part_to_evaluation[value] = evaluation

    def initialize_dependencies(self):
        """Initialize dependencies"""
        for dependency in self.trial.dependencies:
            # Dependency between evaluations
            influenced = self.evaluations[dependency.dependent_id]
            influencer = self.evaluations[dependency.dependency_id]
            self.add_static_arrow(influenced, influencer, dependency.type)
            self.dependencies[influenced][influencer] = dependency

    def initialize(self):
        """Initialize graph"""
        self.__init__(self.trial)

        parts = self.initialize_compartments()
        self.initialize_evaluations(parts)
        self.initialize_dependencies()
        return self

    def _value_neighborhood(self, context):
        """If the context is in a value, find its neighborhoods"""
        from_ = context.element
        # Value to parts
        for name, value_state in viewitems(self.compartments[from_]):
            if (from_, name) in context.block_set:
                continue  # This part is being altered. Thus, it is blocked
            if (from_, "<C>") in context.block_set:
                continue  # Going to compartments is blocked
            to_, moment = value_state.current_pair(context.moment)
            if to_ is None:
                continue  # Value were created after the explored node
            arrow = self.get_arrow(from_, to_, "<C>", moment, name)
            # Keep the context moment and the block_set
            yield Context(to_, context.moment, context.block_set), arrow

        # Part to evaluation that created it
        to_ = self.part_to_evaluation.get(from_)
        if to_ is None:
            return  # Part is just an access
        if (from_, "<P>") in context.block_set:
            return  # Moving from part to evaluation is blocked
        if context.moment < to_.moment:
            return  # Part were accessed before definition (?)
        arrow = self.get_arrow(from_, to_, "<P>", to_.moment)
        # Going to evaluation, reset moment restriction. Keep block_set
        yield Context(to_, None, context.block_set), arrow

    def _evaluation_to_evaluations_neighborhood(self, context):
        """Visit evaluation dependencies"""
        from_ = context.element
        for to_, dependency in viewitems(self.dependencies[from_]):
            if (from_, dependency.type) in context.block_set:
                # Moviment from evaluation to evaluation is blocked
                continue
            new_block_set = context.block_set
            if from_.id in self.activations and dependency.type.startswith("argument"):
                continue  # Ignore this type
            if dependency.type.startswith("value"):
                # Block going to parts in a access
                whole_value = self.values[to_.value_id]
                new_block_set = frozenset(chain(
                    new_block_set, {(whole_value, "<C>")}
                ))
            arrow = self.get_arrow(from_, to_, dependency.type)
            # Moment is always None, when going to a evaluation
            yield Context(to_, None, new_block_set), arrow

    def _evaluation_to_activation_neighborhood(self, context):
        """Visit evaluation parent activation"""
        from_ = context.element
        to_ = self.evaluation_to_activation.get(from_)
        if to_ is None:
            return  # Main activation
        if (from_, "<A>") in context.block_set:
            return  # Moving from evaluation to activation is blocked
        arrow = self.get_arrow(from_, to_, "<A>")
        # Add restriction: to_ to return dependencies
        new_block_set = frozenset(chain(
            context.block_set, {(to_, "use"), (to_, "use-bind")}
        ))
        # Moment is always None, when going to a evaluation
        yield Context(to_, None, new_block_set), arrow

    def _evaluation_to_value_neighborhood(self, context):
        """Visit evaluation value"""
        from_ = context.element
        to_ = self.evaluation_to_value.get(from_)
        if (from_, "<V>") in context.block_set:
            # Moving from evaluation to value is blocked
            return
        # Going to value, set moment restriction as the evaluation moment
        moment = from_.moment
        arrow = self.get_arrow(from_, to_, "<V>", moment)
        yield Context(to_, moment, context.block_set), arrow

    def neighborhood(self, context):
        """Get neighborhood of context"""
        if isinstance(context.element, Value):
            for result in self._value_neighborhood(context):
                yield result
        elif isinstance(context.element, Evaluation):
            neighborhood = chain(
                self._evaluation_to_evaluations_neighborhood(context),
                self._evaluation_to_activation_neighborhood(context),
                self._evaluation_to_value_neighborhood(context),
            )
            for result in neighborhood:
                yield result

    def search(self, elements, stop=None):
        """Search a path from elements to stop (optional)"""
        if self.last_search != elements:
            self.reset_arrows()
            self.visited_nodes = set()
            self.visited_context = set()
            self.search_stack = []

            for element in elements:
                context = Context(element, None, frozenset())
                self.visited_nodes.add(element)
                self.visited_context.add(context)
                self.search_stack.append((context, 0))
            self.last_search = elements

        if stop in self.visited_nodes:
            return True

        while self.search_stack:
            context, index = self.search_stack.pop()
            for new_context, arrow in self.neighborhood(context):
                if new_context not in self.visited_context:
                    self.visit_arrow(arrow, index, new_context)
                    self.search_stack.append((new_context, index + 1))
                    self.visited_context.add(new_context)
                    node = new_context.element
                    self.visited_nodes.add(node)
                    if node == stop:
                        return True

        if stop is None:
            return self.visited_nodes
        return False

    def mark_code(self, elements, block=None):
        """Display code with dependencies"""
        block = block or self.trial.main
        visited = self.search(elements)
        return block.content([
            block.content.get_mark(
                node.code_component, {'className': 'mark-text'}
            )
            for node in visited
            if isinstance(node, Evaluation)
            if node.code_component_id in block.content.all_components
        ])
