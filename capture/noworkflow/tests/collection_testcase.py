# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Code Block collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import unittest

from future.utils import viewvalues, viewitems

from ..now.collection.metadata import Metascript
from ..now.utils.cross_version import PY3


NAME = "noworkflow/tests/examples/script.py"


class CollectionTestCase(unittest.TestCase):
    """Helpers to test noWorkflow collection"""

    def find(self, store, **kwargs):                                             # pylint: disable=no-self-use
        """Find object in object store by kwargs attributes"""
        for component in viewvalues(store):
            found = True
            for key, value in viewitems(kwargs):
                if getattr(component, key) != value:
                    found = False
                    break
            if found:
                return component
        return None

    def find_code_component(self, **kwargs):
        """Find code component by attributes in kwargs"""
        return self.find(self.metascript.code_components_store.store, **kwargs)

    def find_evaluation(self, **kwargs):
        """Find evaluation by attributes in kwargs"""
        return self.find(self.metascript.evaluations_store.store, **kwargs)

    def find_value(self, **kwargs):
        """Find value by attributes in kwargs"""
        return self.find(self.metascript.values_store.store, **kwargs)

    def find_dependency(self, **kwargs):
        """Find dependency by attributes in kwargs"""
        return self.find(self.metascript.dependencies_store.store, **kwargs)

    def find_compartment(self, **kwargs):
        """Find compartment by attributes in kwargs"""
        return self.find(self.metascript.compartments_store.store, **kwargs)

    def get_evaluation(self, **kwargs):
        """Execute and get evaluation"""
        if not hasattr(self, 'executed'):
            self.metascript.definition.collect_provenance()
            self.metascript.execution.collect_provenance()
            self.assertEqual(self.metascript.execution.msg,
                             "the execution of trial -1 finished successfully")
            self.executed = True

        var = self.find_code_component(**kwargs)
        if not var:
            return None
        return self.find_evaluation(code_component_id=var.id)

    def get_compartment_value(self, whole, name, **kwargs):
        compartment = self.find_compartment(
            whole_id=whole.id, name=name, **kwargs)
        if not compartment:
            return None
        return self.metascript.values_store[compartment.part_id]

    def evaluation_repr(self, evaluation):
        """Get evaluation friendly representation"""
        return "{}({})".format(self.metascript.code_components_store[
            evaluation.code_component_id
        ].name, evaluation.id)

    def assert_dependency(self, dependent, dependency, type_=None):
        """Check if dependency exists"""
        dep = self.find_dependency(dependent_id=dependent.id,
                                   dependency_id=dependency.id)
        if not dep:
            self.fail("Dependency not found {} -> {}".format(
                self.evaluation_repr(dependent),
                self.evaluation_repr(dependency),
            ))
        if type_ is not None:
            full_dep = self.find_dependency(
                dependent_id=dependent.id, dependency_id=dependency.id,
                type=type_)
            if not full_dep:
                self.fail(
                    "Dependency not found {} -({})> {}. "
                    "Found dependency with type '{}'".format(
                        self.evaluation_repr(dependent), type_,
                        self.evaluation_repr(dependency), dep.type
                    )
                )

    def assert_no_dependency(self, dependent, dependency, type_=None):
        """Check if dependency exists"""
        params = {'dependent_id': dependent.id, 'dependency_id': dependency}
        if type_ is not None:
            params['type'] = type_
        dep = self.find_dependency(**params)
        self.assertIsNone(dep)


    def rtype(self, name):                                                       # pylint: disable=no-self-use
        """Create type repr according to python version"""
        keyword = "class" if PY3 else "type"
        return "<{} '{}'>".format(keyword, name)


    def script(self, code, name=NAME, **kwargs):
        """Create metascript with the desired code"""
        self.maxDiff = None
        self.metascript = Metascript(
            path=name,
            dir=os.path.dirname(name),
            code=code,
            **kwargs
        )
        self.metascript.clear_namespace()
