# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Execution provenance collector"""

import sys
import weakref

from datetime import datetime, timedelta

from ...persistence.models import Trial
from ...utils.cross_version import IMMUTABLE

from .structures import Assign, DependencyAware, Dependency


class Collector(object):
    """Collector called by the transformed AST. __noworkflow__ object"""

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)

        self.evaluations = self.metascript.evaluations_store
        self.activations = self.metascript.activations_store
        self.dependencies = self.metascript.dependencies_store
        self.values = self.metascript.values_store

        self.exceptions = self.metascript.exceptions_store
        # Partial save
        self.partial_save_frequency = None
        if metascript.save_frequency:
            self.partial_save_frequency = timedelta(
                milliseconds=metascript.save_frequency
            )
        self.last_partial_save = datetime.now()

        self.first_activation = self.activations.dry_add(
            self.evaluations.dry_add(-1, -1, None, None), "<now>", None, None
        )
        self.last_activation = self.first_activation
        self.shared_types = {}

    def time(self):
        """Return time at this moment
        Also check whether or not it should invoke time related methods
        """
        # ToDo #76: Processor load. Should be collected from time to time
        #                         (there are static and dynamic metadata)
        # print os.getloadavg()
        now = datetime.now()
        if (self.partial_save_frequency and
                (now - self.last_partial_save > self.partial_save_frequency)):
            self.store(partial=True)

        return now

    def start_activation(self, name, code_component_id, definition_id, act):
        """Start new activation. Return activation object"""
        activation = self.activations.add_object(self.evaluations.add_object(
            code_component_id, act.id, None, None
        ), name, self.time(), definition_id)
        self.last_activation = activation
        return activation

    def close_activation(self, activation, value):
        """Close activation. Set moment and value"""
        evaluation = activation.evaluation
        evaluation.moment = self.time()
        evaluation.value_id = self.add_value(value)
        self.last_activation = self.activations.store.get(
            evaluation.activation_id, self.first_activation
        )


    def add_value(self, value):
        """Add value. Create type value recursively. Return value id"""
        if value is type:
            value_object = self.values.add_object(repr(value), -1)
            value_object.type_id = value_object.id
            self.shared_types[value] = value_object.id
            return value_object.id

        value_type = type(value)
        if value_type not in self.shared_types:
            self.shared_types[value_type] = self.add_value(value_type)
        type_id = self.shared_types[value_type]
        return self.values.add(repr(value), type_id)

    def start_script(self, module_name, code_component_id):
        """Start script collection. Create new activation"""
        return self.start_activation(
            module_name, code_component_id, code_component_id,
            self.last_activation
        )

    def close_script(self, now_activation):
        """Close script activation"""
        self.close_activation(now_activation, sys.modules[now_activation.name])

    def collect_exception(self, now_activation):
        """Collect activation exceptions"""
        exc = sys.exc_info()
        self.exceptions.add(exc, now_activation.id)

    def capture_single(self, activation, code_tuple, value, mode="dependency"):
        """Capture single value"""
        if code_tuple[0]:
            # Capture only if there is a code component id
            code_id, name = code_tuple[0]
            old_eval = activation.context.get(name, None)
            value_id = old_eval.value_id if old_eval else self.add_value(value)

            evaluation_id = self.evaluations.add(
                code_id, activation.id, self.time(), value_id
            )
            activation.dependencies[-1].add(Dependency(
                activation.id, evaluation_id, value, value_id, mode
            ))

            if old_eval:
                self.dependencies.add(
                    activation.id, evaluation_id,
                    old_eval.activation_id, old_eval.id, "assignment"
                )

        return value

    def assign_value(self, activation):
        """Capture assignment before"""
        activation.dependencies.append(DependencyAware())
        return self._assign_value

    def _assign_value(self, activation, value):
        """Capture assignment after"""
        dependency = activation.dependencies.pop()
        activation.assignments.append(Assign(self.time(), value, dependency))
        return value

    def pop_assign(self, activation):                                            # pylint: disable=no-self-use
        """Pop assignment from activation"""
        return activation.assignments.pop()

    def assign(self, activation, assign, code_component_tuple):                                # pylint: disable=no-self-use
        """Create dependencies"""
        moment, value, dependency = assign

        if code_component_tuple[1] == 'single':
            value_id = None
            if dependency and not isinstance(value, IMMUTABLE):
                for dep in dependency.dependencies:
                    if dep.value is value:
                        value_id = dep.value_id
                        dep.mode = "bind"
                        break
            if not value_id:
                value_id = self.add_value(value)
            code, name = code_component_tuple[0]
            evaluation = self.evaluations.add_object(
                code, activation.id, moment, value_id
            )
            if name:
                activation.context[name] = evaluation
            for dep in dependency.dependencies:
                self.dependencies.add(
                    activation.id, evaluation.id,
                    dep.activation_id, dep.evaluation_id,
                    dep.mode
                )

    def store(self, partial, status="running"):
        """Store execution provenance"""
        metascript = self.metascript
        tid = metascript.trial_id

        metascript.evaluations_store.fast_store(tid, partial=partial)
        metascript.activations_store.fast_store(tid, partial=partial)
        metascript.dependencies_store.fast_store(tid, partial=partial)
        metascript.values_store.fast_store(tid, partial=partial)
        metascript.compartments_store.fast_store(tid, partial=partial)
        metascript.file_accesses_store.fast_store(tid, partial=partial)

        now = datetime.now()
        if not partial:
            Trial.fast_update(tid, metascript.main_id, now, status)

        self.last_partial_save = now
