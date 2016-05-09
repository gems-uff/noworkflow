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

    def find(self, store, **kwargs):
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

    def get_evaluation(self, **kwargs):
        """Execute and get evaluation"""
        if not hasattr(self, 'executed'):
            self.metascript.definition.collect_provenance()
            self.metascript.execution.collect_provenance()
            self.assertEqual(self.metascript.execution.msg,
                             "the execution of trial -1 finished successfully")
            self.executed = True

        var = self.find_code_component(**kwargs)
        return self.find_evaluation(code_component_id=var.id)

    def rtype(self, name):
        """Create type repr according to python version"""
        keyword = "class" if PY3 else "type"
        return "<{} '{}'>".format(keyword, name)


    def script(self, code, name=NAME):
        """Create metascript with the desired code"""
        self.maxDiff = None
        self.metascript = Metascript(
            path=name,
            dir=os.path.dirname(name),
            code=code
        )
        self.metascript.clear_namespace()
