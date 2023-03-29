# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from .querier_options import QuerierOptions

class NodeContext(object):

    def __init__(self, evaluation, checkpoint, is_activation=False, arrow=None, steps=0, options=None):
        self.evaluation = evaluation
        self.checkpoint = checkpoint
        self.is_activation = is_activation
        self.options = options or QuerierOptions()
        self.steps = 0
        self.arrow = arrow

    def __eq__(self, other):
        if isinstance(other, NodeContext):
            return (
                self.evaluation, self.checkpoint, self.is_activation
            ) == (
                other.evaluation, other.checkpoint, other.is_activation
            )
        return False

    def __hash__(self):
        return hash((self.evaluation.trial_id, self.evaluation.id, self.checkpoint, self.is_activation))

    def dependencies(self):
        """Context dependencies"""
        if self.is_activation:
            return
        evaluation = self.evaluation
        # If time is not in the context, get it from the entity
        checkpoint = self.checkpoint or evaluation.checkpoint

        # Follow default derivations
        for dep in self.options.dependencies(evaluation):
            dependency = dep.dependency
            checkpoint = checkpoint or dependency.checkpoint
            if dep.type == 'argument' and not self.options.visit_arguments:
                continue
            yield NodeContext(
                dependency, None,
                arrow=dep.type, steps=self.steps + 1, options=self.options
            )

        # Yield non-navigatable activation
        if self.options.visit_activations and evaluation.activation:
            yield NodeContext(
                evaluation.activation.this_evaluation, None, True, 
                arrow="<A>", steps=self.steps + 1, options=self.options
            )

        if checkpoint and self.options.visit_members:
            if not self.options.visit_out and evaluation.code_component.name == "Out":
                return
            # Get initial reference to value
            original = self.options.member_container(evaluation)

            # Move to all parts of the structure
            # Reconstruct state
            member_dict = self.options.members(original)
            state = {}
            for key, checkpoints in member_dict.items():
                value = max(
                    (
                        (member_checkpoint, member)
                        for member_checkpoint, member in checkpoints.items()
                        if member_checkpoint <= checkpoint
                    ),
                    key=lambda tup: tup[0],
                    default=None 
                )
                if value is not None:
                    state[key] = value

            # Move to parts of the state
            for key, (member_checkpoint, member) in state.items():
                yield NodeContext(
                    member, checkpoint, 
                    arrow="<{}>".format(key), steps=self.steps + 1, options=self.options
                )
