# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Code Block collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ..collection_testcase import CollectionTestCase


class TestScript(CollectionTestCase):
    """Test Script activation"""

    def test_script(self):
        """Test script collection"""
        self.script("# script.py\n"
                    "# other")
        self.metascript.execution.collect_provenance()
        self.assertEqual(self.metascript.execution.msg,
                         "the execution of trial -1 finished successfully")

        script = self.find_code_component(name="script.py")
        script_evaluation = self.find_evaluation(code_component_id=script.id)
        script_activation = self.metascript.activations_store[
            script_evaluation.id
        ]

        self.assertEqual(script_evaluation.activation_id, -1)
        self.assertTrue(script_activation.start < script_evaluation.moment)
        self.assertEqual(script_activation.code_block_id, script.id)
        self.assertEqual(script_activation.name, "__main__")

        script_value = self.metascript.values_store[script_evaluation.value_id]
        script_type = self.metascript.values_store[script_value.type_id]
        type_type = self.metascript.values_store[script_type.type_id]

        self.assertEqual(script_value.value[:19], "<module '__main__' ")
        self.assertEqual(script_type.value, self.rtype("module"))
        self.assertEqual(type_type.value, self.rtype("type"))
        self.assertEqual(type_type.type_id, type_type.id)

        self.assertEqual(len(self.metascript.exceptions_store.store), 0)

    def test_script_with_error(self):
        """Test script collection with exception"""
        self.script("# script.py\n"
                    "1 / 0\n"
                    "# other")
        self.metascript.execution.collect_provenance()
        self.assertNotEqual(self.metascript.execution.msg,
                            "the execution of trial -1 finished successfully")

        script = self.find_code_component(name="script.py")
        script_evaluation = self.find_evaluation(code_component_id=script.id)
        script_activation = self.metascript.activations_store[
            script_evaluation.id
        ]

        self.assertEqual(script_evaluation.activation_id, -1)
        self.assertTrue(script_activation.start < script_evaluation.moment)
        self.assertEqual(script_activation.code_block_id, script.id)
        self.assertEqual(script_activation.name, "__main__")

        script_value = self.metascript.values_store[script_evaluation.value_id]
        script_type = self.metascript.values_store[script_value.type_id]
        type_type = self.metascript.values_store[script_type.type_id]

        self.assertEqual(script_value.value[:19], "<module '__main__' ")
        self.assertEqual(script_type.value, self.rtype("module"))
        self.assertEqual(type_type.value, self.rtype("type"))
        self.assertEqual(type_type.type_id, type_type.id)

        self.assertEqual(len(self.metascript.exceptions_store.store), 1)

        # ToDo #77: check exception
