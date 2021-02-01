# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from collections import defaultdict

class QuerierOptions(object):

    def __init__(self, visit_activations=False, visit_arguments=True, visit_members=True, visit_out=True):
        self.visit_activations = visit_activations
        self.visit_arguments = visit_arguments
        self.visit_members = visit_members
        self.visit_out = visit_out

    def dependencies(self, evaluation):
        """Get evaluation dependencies"""
        return evaluation.dependencies_as_dependent

    def member_container(self, evaluation):
        """Get original evaluation container"""
        return evaluation.member_container

    def members(self, evaluation):
        """Get evaluation members"""
        result = defaultdict(dict)
        for member in evaluation.memberships_as_collection:
            result[member.key][member.checkpoint] = member.member
        return result

    def visit_arrow(self, from_, to_):
        """Visit arrow"""

    def visit_context(self, context):
        """Visit context"""
        return context

    def reset_arrows(self):
        """Reset arrows"""


class PreloadedQuerierOptions(QuerierOptions):

    def __init__(self, trial, visit_activations=False, visit_arguments=True, visit_members=True, visit_out=True):
        super(PreloadedQuerierOptions, self).__init__(visit_activations, visit_arguments, visit_members, visit_out)
        self.trial = trial
        self._dependencies = defaultdict(list)
        self._members = defaultdict(lambda: defaultdict(dict))
        self._containers = {}
        self._activations = {}
        self._evaluations = {}
        self.gen_disabled_static = True
        self.initialize(initial=True)

    def add_static_arrow(self, from_, to_, mode, checkpoint=None):
        pass

    def initialize_evaluations(self):
        """Initialize evaluations"""
        self._activations = {act.id: act for act in self.trial.activations}
        self._evaluations = {eva.id: eva for eva in self.trial.evaluations}
        for _, evaluation in self._evaluations.items():
            if (self.visit_activations or self.gen_disabled_static) and evaluation.activation_id:
                activation = self._evaluations[evaluation.activation_id]
                self.add_static_arrow(evaluation, activation, "<A>")

            if evaluation.member_container_id is not None:
                self._containers[evaluation.id] = self._evaluations[evaluation.member_container_id]

    def initialize_dependencies(self):
        """Initialize dependencies"""
        for dependency in self.trial.dependencies:
            # Dependency between evaluations
            influenced = self._evaluations[dependency.dependent_id]
            influencer = self._evaluations[dependency.dependency_id]
            self._dependencies[influenced].append(dependency)
            if dependency.type == "argument" and not (self.visit_arguments or self.gen_disabled_static):
                continue
            self.add_static_arrow(influenced, influencer, dependency.type)
        
    def initialize_members(self):
        """Initialize members"""
        for member in self.trial.members:
            ecollection = self._evaluations[member.collection_id]
            emember = self._evaluations[member.member_id]
            self._members[ecollection][member.key][member.checkpoint] = emember
            if self.visit_members or self.gen_disabled_static:
                self.add_static_arrow(ecollection, emember, "<{}>".format(member.key), member.checkpoint)

    def initialize(self, initial=False):
        """Initialize graph"""
        if not initial:
            self.__init__(
                self.trial, self.visit_activations, self.visit_arguments, 
                self.visit_members, self.visit_out
            )

        self.initialize_evaluations()
        self.initialize_dependencies()
        self.initialize_members()
        return self

    def dependencies(self, evaluation):
        return self._dependencies[evaluation]

    def member_container(self, evaluation):
        return self._containers.get(evaluation.id, evaluation)

    def members(self, evaluation):
        return self._members[evaluation]
