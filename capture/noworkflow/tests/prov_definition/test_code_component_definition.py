# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Code Block collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ..collection_testcase import CollectionTestCase


class TestCodeComponentDefinition(CollectionTestCase):
    """Test Stmt collection"""

    def test_assign_to_name(self):
        """Test assign to name"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "# other")
        self.metascript.definition.collect_provenance()

        script = self.find_code_component(name="script.py")
        variable = self.find_code_component(name="a")
        self.assertEqual(variable.type, "name")
        self.assertEqual(variable.mode, "w")
        self.assertEqual(variable.first_char_line, 2)
        self.assertEqual(variable.first_char_column, 0)
        self.assertEqual(variable.last_char_line, 2)
        self.assertEqual(variable.last_char_column, 1)
        self.assertEqual(variable.container_id, script.id)

    def test_assign_name_to_name(self):
        """Test assign to name"""
        self.script("# script.py\n"
                    "a = 2\n"
                    "b = a\n"
                    "# other")
        self.metascript.definition.collect_provenance()

        script = self.find_code_component(name="script.py")
        read_a = self.find_code_component(name="a", mode="r")
        write_b = self.find_code_component(name="b")

        self.assertEqual(read_a.type, "name")
        self.assertEqual(read_a.mode, "r")
        self.assertEqual(read_a.first_char_line, 3)
        self.assertEqual(read_a.first_char_column, 4)
        self.assertEqual(read_a.last_char_line, 3)
        self.assertEqual(read_a.last_char_column, 5)
        self.assertEqual(read_a.container_id, script.id)

        self.assertEqual(write_b.type, "name")
        self.assertEqual(write_b.mode, "w")
        self.assertEqual(write_b.first_char_line, 3)
        self.assertEqual(write_b.first_char_column, 0)
        self.assertEqual(write_b.last_char_line, 3)
        self.assertEqual(write_b.last_char_column, 1)
        self.assertEqual(write_b.container_id, script.id)

    def test_dict_definition(self):
        """Test dict definition"""
        self.script("# script.py\n"
                    "x = {'a': 1, 'b': 2}\n"
                    "# other")
        self.metascript.definition.collect_provenance()

        script = self.find_code_component(name="script.py")
        key_value_a = self.find_code_component(name="'a': 1", mode="r")
        key_value_b = self.find_code_component(name="'b': 2", mode="r")
        dict_comp = self.find_code_component(name="{'a': 1, 'b': 2}", mode="r")

        self.assertEqual(key_value_a.type, "key_value")
        self.assertEqual(key_value_a.mode, "r")
        self.assertEqual(key_value_a.first_char_line, 2)
        self.assertEqual(key_value_a.first_char_column, 5)
        self.assertEqual(key_value_a.last_char_line, 2)
        self.assertEqual(key_value_a.last_char_column, 11)
        self.assertEqual(key_value_a.container_id, script.id)

        self.assertEqual(key_value_b.type, "key_value")
        self.assertEqual(key_value_b.mode, "r")
        self.assertEqual(key_value_b.first_char_line, 2)
        self.assertEqual(key_value_b.first_char_column, 13)
        self.assertEqual(key_value_b.last_char_line, 2)
        self.assertEqual(key_value_b.last_char_column, 19)
        self.assertEqual(key_value_b.container_id, script.id)

        self.assertEqual(dict_comp.type, "dict")
        self.assertEqual(dict_comp.mode, "r")
        self.assertEqual(dict_comp.first_char_line, 2)
        self.assertEqual(dict_comp.first_char_column, 4)
        self.assertEqual(dict_comp.last_char_line, 2)
        self.assertEqual(dict_comp.last_char_column, 20)
        self.assertEqual(dict_comp.container_id, script.id)


