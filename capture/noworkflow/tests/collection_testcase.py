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
from ..now.models.ast import create_trees
from ..now.utils.cross_version import PY3
from .helpers import models


NAME = "noworkflow/tests/examples/script.py"


def cluster(evaluation_nid):
    """Get cluster id"""
    return "cluster_" + evaluation_nid.split("_")[-1]


class CollectionTestCase(unittest.TestCase):
    """Helpers to test noWorkflow collection"""

    def find_all(self, store, **kwargs):
        """Find objects in object store by kwargs attributes"""
        # pylint: disable=no-self-use
        for component in viewvalues(store):
            found = True
            for key, value in viewitems(kwargs):
                if getattr(component, key) != value:
                    found = False
                    break
            if found:
                yield component

    def find(self, store, **kwargs):
        """Find object in object store by kwargs attributes"""
        # pylint: disable=no-self-use
        for component in self.find_all(store, **kwargs):
            return component
        return None

    def find_code_component(self, **kwargs):
        """Find code component by attributes in kwargs"""
        return self.find(self.metascript.code_components_store.store, **kwargs)

    def find_all_evaluations(self, **kwargs):
        """Find evaluation by attributes in kwargs"""
        return self.find_all(self.metascript.evaluations_store.store, **kwargs)

    def find_evaluation(self, **kwargs):
        """Find evaluation by attributes in kwargs"""
        return self.find(self.metascript.evaluations_store.store, **kwargs)

    def find_dependency(self, **kwargs):
        """Find dependency by attributes in kwargs"""
        return self.find(self.metascript.dependencies_store.store, **kwargs)

    def find_member(self, **kwargs):
        """Find members by attributes in kwargs"""
        return self.find(self.metascript.members_store.store, **kwargs)

    def get_evaluations(self, **kwargs):
        """Execute and get evaluation"""
        self.execute()
        c_store = self.metascript.code_components_store.store
        result = []
        for var in self.find_all(c_store, **kwargs):
            result.extend(self.find_all_evaluations(code_component_id=var.id))
        return result

    def execute(self, set_max_diff=True):
        """Execute script"""
        # pylint: disable=attribute-defined-outside-init
        if not hasattr(self, 'executed'):
            if set_max_diff:
                self.maxDiff = None
            self.metascript.execution.collect_provenance()
            self.assertEqual(self.metascript.execution.msg,
                             "the execution of trial -1 finished successfully")
            self.executed = True

    def clean_execution(self):
        """Clear database and execute"""
        # pylint: disable=attribute-defined-outside-init
        models.meta = self.metascript
        models.erase_database()
        self.metascript.trial_id = models.Trial.create(**models.trial_params(
            script=self.metascript.code,
            path=self.metascript.path
        ))
        if not hasattr(self, 'executed'):
            self.metascript.execution.collect_provenance()
            self.assertEqual(self.metascript.execution.msg,
                             "the execution of trial 1 finished successfully")
            self.executed = True
        self.metascript.deployment.store_provenance()
        self.metascript.definition.store_provenance()
        self.metascript.execution.store_provenance()

    def get_evaluation(self, **kwargs):
        """Execute and get evaluation"""
        for evaluation in self.get_evaluations(**kwargs):
            return evaluation
        return None

    def evaluation_node(self, **kwargs):
        """Execute and get evaluation id"""
        evaluation = self.get_evaluation(**kwargs)
        if not evaluation:
            return self.fail("Evaluation not found for {}".format(kwargs))
        return "e_{}".format(evaluation.id)

    def evaluation_repr(self, evaluation):
        """Get evaluation friendly representation"""
        component = self.metascript.code_components_store[
            evaluation.code_component_id
        ]
        return "{}({}:l{})".format(
            component.name, evaluation.id, component.first_char_line
        )

    def assert_member(self, collection, member, key):
        result = self.find_member(
            collection_id=collection.id,
            member_id=member.id, key=key)
        if result is None:
            self.fail(
                "The collection {} does not have the member {} at {}".format(
                    self.evaluation_repr(collection),
                    self.evaluation_repr(member),
                    key
                )
            )
        return result

    def assert_no_member(self, collection, member, key):
        result = self.find_member(
            collection_id=collection.id,
            member_id=member.id, key=key)
        if result is not None:
            self.fail(
                "The collection {} has the member {} at {}".format(
                    self.evaluation_repr(collection),
                    self.evaluation_repr(member),
                    key
                )
            )
        return result

    def assert_type(self, evaluation, type_evaluation):
        original = evaluation
        eva_id = evaluation.id
        type_id = type_evaluation.id
        while eva_id is not None:
            member = self.find_member(
                collection_id=eva_id,
                member_id=type_id,
                key=".__class__")
            if member:
                return
            dep = self.find_dependency(
                dependent_id=eva_id,
                reference=True)
            eva_id = dep.dependency_id if dep else None

        self.fail("Evaluation {} does not have type {}".format(
            self.evaluation_repr(original),
            self.evaluation_repr(type_evaluation),
        ))

    def assert_dependency(self, dependent, dependency, type_=None,
                          reference=False, collection=None, key=None):
        """Check if dependency exists"""
        collection_id = getattr(collection, "id", None)
        dep = self.find_dependency(dependent_id=dependent.id,
                                   dependency_id=dependency.id,
                                   collection_id=collection_id,
                                   key=key)
        if not dep:
            self.fail("Dependency not found {} -> {}".format(
                self.evaluation_repr(dependent),
                self.evaluation_repr(dependency),
            ))
        if type_ is not None:
            full_dep = self.find_dependency(
                dependent_id=dependent.id, dependency_id=dependency.id,
                reference=reference, type=type_,
                collection_id=collection_id, key=key)
            if not full_dep:
                self.fail(
                    "Dependency not found {} -({})> {}. "
                    "Found {} with type '{}'".format(
                        self.evaluation_repr(dependent), type_,
                        self.evaluation_repr(dependency),
                        'reference' if dep.reference else 'dependency',
                        dep.type
                    )
                )

    def pdebug(self, members=False):
        """Print current dependencies"""
        from collections import defaultdict
        used_evals = set()
        print()
        print("Dependencies")
        for dep in viewvalues(self.metascript.dependencies_store.store):
            dependent, dependency = dep.dependent_id, dep.dependency_id
            edependent = self.metascript.evaluations_store[dependent]
            edependency = self.metascript.evaluations_store[dependency]
            used_evals.add(dependent)
            used_evals.add(dependency)
            extra = ""
            if dep.key is not None:
                col = self.metascript.evaluations_store[dep.collection_id]
                extra = " {}{}".format(self.evaluation_repr(col), dep.key)
            print("  {} -({})> {}{}{}".format(
                self.evaluation_repr(edependent), dep.type,
                self.evaluation_repr(edependency),
                " (R)" if dep.reference else "",
                extra
            ))
        print("Evaluations")
        for eva in viewvalues(self.metascript.evaluations_store.store):
            if not eva.id in used_evals:
                print("  {}".format(
                    self.evaluation_repr(eva),
                ))
        if members:
            print("Members")
            collections = defaultdict(list)
            for member in viewvalues(self.metascript.members_store.store):
                collections[member.collection_id].append((member.member_id, member.key, member.moment))
            for collection_id, members in viewitems(collections):
                collection = self.metascript.evaluations_store[collection_id]
                print("  {}".format(
                    self.evaluation_repr(collection),
                ))
                for member_id, key, moment in members:
                    member = self.metascript.evaluations_store[member_id]
                    print("    {} = {} ({})".format(
                        key,
                        self.evaluation_repr(member),
                        moment
                    ))

    def assert_no_dependency(self, dependent, dependency, type_=None):
        """Check if dependency exists"""
        params = {'dependent_id': dependent.id, 'dependency_id': dependency}
        if type_ is not None:
            params['type'] = type_
        dep = self.find_dependency(**params)
        self.assertIsNone(dep)


    def rtype(self, name):
        """Create type repr according to python version"""
        # pylint: disable=no-self-use
        keyword = "class" if PY3 else "type"
        return "<{} '{}'>".format(keyword, name)


    def script(self, code, name=NAME, **kwargs):
        """Create metascript with the desired code"""
        # pylint: disable=attribute-defined-outside-init
        self.metascript = Metascript(
            path=name,
            dir=os.path.dirname(name),
            code=code,
            **kwargs
        )
        self.metascript.clear_namespace()

    def compile(self):
        """Compile script to apply AST transformations"""
        self.metascript.definition.compile(
            self.metascript.code, self.metascript.path, "exec"
        )

    def compile_tree(self, id_=None):
        """Compile script and return trees
        Id limits to a unique tree"""
        self.compile()
        trees = create_trees(
            viewvalues(self.metascript.code_components_store.store),
            self.metascript.code_blocks_store.store,
            viewvalues(self.metascript.compositions_store.store),
        )
        if id_ is None:
            return trees
        return trees[id_]
