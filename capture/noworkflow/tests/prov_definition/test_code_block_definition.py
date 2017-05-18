# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test Code Block collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ..collection_testcase import CollectionTestCase

from ...now.utils.cross_version import PY35, only


class TestCodeBlockDefinition(CollectionTestCase):
    """Test Code Block collection"""

    def test_script(self):
        """Test script collection. Do not ignore comments."""
        self.script("# script.py\n"
                    "a = 2\n"
                    "# other")
        self.compile()

        script = self.find_code_component(name="script.py")
        self.assertEqual(script.type, "script")
        self.assertEqual(script.mode, "w")
        self.assertEqual(script.first_char_line, 1)
        self.assertEqual(script.first_char_column, 0)
        self.assertEqual(script.last_char_line, 3)
        self.assertEqual(script.last_char_column, 7)
        self.assertEqual(script.container_id, -1)

        script_block = self.metascript.code_blocks_store[script.id]
        self.assertEqual(script_block.code, "# script.py\na = 2\n# other")
        self.assertEqual(script_block.docstring, "")
        self.assertTrue(bool(script_block.code_hash))

    def test_script_with_docstring(self):
        """Test script collection with docstring"""
        self.script("# script.py\n"
                    "'doc'\n"
                    "a = 2")
        self.compile()

        script = self.find_code_component(name="script.py")
        self.assertEqual(script.type, "script")
        self.assertEqual(script.mode, "w")
        self.assertEqual(script.first_char_line, 1)
        self.assertEqual(script.first_char_column, 0)
        self.assertEqual(script.last_char_line, 3)
        self.assertEqual(script.last_char_column, 5)
        self.assertEqual(script.container_id, -1)

        script_block = self.metascript.code_blocks_store[script.id]
        self.assertEqual(script_block.code, "# script.py\n'doc'\na = 2")
        self.assertEqual(script_block.docstring, "doc")
        self.assertTrue(bool(script_block.code_hash))

    def test_function_definition(self):
        """Test function definition collection"""
        self.script("# script.py\n"
                    "def f():\n"
                    "    'fdoc'\n"
                    "    pass\n")
        self.compile()

        script = self.find_code_component(name="script.py")
        function_def = self.find_code_component(name="f")

        self.assertEqual(function_def.type, "function_def")
        self.assertEqual(function_def.mode, "w")
        self.assertEqual(function_def.first_char_line, 2)
        self.assertEqual(function_def.first_char_column, 0)
        self.assertEqual(function_def.last_char_line, 4)
        self.assertEqual(function_def.last_char_column, 8)
        self.assertEqual(function_def.container_id, script.id)

        function_def_block = self.metascript.code_blocks_store[function_def.id]
        self.assertEqual(function_def_block.code,
                         "def f():\n"
                         "    'fdoc'\n"
                         "    pass")
        self.assertEqual(function_def_block.docstring, "fdoc")
        self.assertTrue(bool(function_def_block.code_hash))

    def test_function_definition_with_args(self):
        """Test function definition collection with arguments"""
        self.script("# script.py\n"
                    "def f(x, y=False):\n"
                    "    'fdoc'\n"
                    "    pass\n")
        self.compile()

        script = self.find_code_component(name="script.py")
        function_def = self.find_code_component(name="f")
        var_x = self.find_code_component(name="x")
        var_y = self.find_code_component(name="y")
        false = self.find_code_component(name="False")

        self.assertEqual(function_def.type, "function_def")
        self.assertEqual(function_def.mode, "w")
        self.assertEqual(function_def.first_char_line, 2)
        self.assertEqual(function_def.first_char_column, 0)
        self.assertEqual(function_def.last_char_line, 4)
        self.assertEqual(function_def.last_char_column, 8)
        self.assertEqual(function_def.container_id, script.id)

        self.assertEqual(var_x.type, "param")
        self.assertEqual(var_x.mode, "w")
        self.assertEqual(var_x.first_char_line, 2)
        self.assertEqual(var_x.first_char_column, 6)
        self.assertEqual(var_x.last_char_line, 2)
        self.assertEqual(var_x.last_char_column, 7)
        self.assertEqual(var_x.container_id, function_def.id)

        self.assertEqual(var_y.type, "param")
        self.assertEqual(var_y.mode, "w")
        self.assertEqual(var_y.first_char_line, 2)
        self.assertEqual(var_y.first_char_column, 9)
        self.assertEqual(var_y.last_char_line, 2)
        self.assertEqual(var_y.last_char_column, 10)
        self.assertEqual(var_y.container_id, function_def.id)

        #self.assertEqual(false.type, "literal")
        self.assertEqual(false.mode, "r")
        self.assertEqual(false.first_char_line, 2)
        self.assertEqual(false.first_char_column, 11)
        self.assertEqual(false.last_char_line, 2)
        self.assertEqual(false.last_char_column, 16)
        self.assertEqual(false.container_id, function_def.id)

        function_def_block = self.metascript.code_blocks_store[function_def.id]
        self.assertEqual(function_def_block.code,
                         "def f(x, y=False):\n"
                         "    'fdoc'\n"
                         "    pass")
        self.assertEqual(function_def_block.docstring, "fdoc")
        self.assertTrue(bool(function_def_block.code_hash))

    def test_function_definition_with_decorator(self):
        """Test function definition collection with decorator"""
        self.script("# script.py\n"
                    "def g(x):\n"
                    "    return x\n"
                    "@g\n"
                    "def f():\n"
                    "    'fdoc'\n"
                    "    pass\n")
        self.compile()

        script = self.find_code_component(name="script.py")
        function_def = self.find_code_component(name="f")

        self.assertEqual(function_def.type, "function_def")
        self.assertEqual(function_def.mode, "w")
        self.assertEqual(function_def.first_char_line, 4)
        self.assertEqual(function_def.first_char_column, 0)
        self.assertEqual(function_def.last_char_line, 7)
        self.assertEqual(function_def.last_char_column, 8)
        self.assertEqual(function_def.container_id, script.id)

        function_def_block = self.metascript.code_blocks_store[function_def.id]
        self.assertEqual(function_def_block.code,
                         "@g\n"
                         "def f():\n"
                         "    'fdoc'\n"
                         "    pass")
        self.assertEqual(function_def_block.docstring, "fdoc")
        self.assertTrue(bool(function_def_block.code_hash))

    @only(PY35)
    def test_async_function_definition(self):
        """Test async function definition collection"""
        self.script("# script.py\n"
                    "async def f():\n"
                    "    'fdoc'\n"
                    "    pass\n")
        self.compile()

        script = self.find_code_component(name="script.py")
        function_def = self.find_code_component(name="f")

        self.assertEqual(function_def.type, "function_def")
        self.assertEqual(function_def.mode, "w")
        self.assertEqual(function_def.first_char_line, 2)
        self.assertEqual(function_def.first_char_column, 0)
        self.assertEqual(function_def.last_char_line, 4)
        self.assertEqual(function_def.last_char_column, 8)
        self.assertEqual(function_def.container_id, script.id)

        function_def_block = self.metascript.code_blocks_store[function_def.id]
        self.assertEqual(function_def_block.code,
                         "async def f():\n"
                         "    'fdoc'\n"
                         "    pass")
        self.assertEqual(function_def_block.docstring, "fdoc")
        self.assertTrue(bool(function_def_block.code_hash))

    def test_class_definition(self):
        """Test class definition collection"""
        self.script("# script.py\n"
                    "class C():\n"
                    "    'cdoc'\n"
                    "    pass\n")
        self.compile()

        script = self.find_code_component(name="script.py")
        class_def = self.find_code_component(name="C")

        self.assertEqual(class_def.type, "class_def")
        self.assertEqual(class_def.mode, "w")
        self.assertEqual(class_def.first_char_line, 2)
        self.assertEqual(class_def.first_char_column, 0)
        self.assertEqual(class_def.last_char_line, 4)
        self.assertEqual(class_def.last_char_column, 8)
        self.assertEqual(class_def.container_id, script.id)

        class_def_block = self.metascript.code_blocks_store[class_def.id]
        self.assertEqual(class_def_block.code,
                         "class C():\n"
                         "    'cdoc'\n"
                         "    pass")
        self.assertEqual(class_def_block.docstring, "cdoc")
        self.assertTrue(bool(class_def_block.code_hash))

    def test_method_definition(self):
        """Test method definition collection"""
        self.script("# script.py\n"
                    "class C():\n"
                    "    'cdoc'\n"
                    "    def f(self):\n"
                    "        'mdoc'\n"
                    "        pass")
        self.compile()

        class_def = self.find_code_component(name="C")
        method_def = self.find_code_component(name="f")

        self.assertEqual(method_def.type, "function_def")
        self.assertEqual(method_def.mode, "w")
        self.assertEqual(method_def.first_char_line, 4)
        self.assertEqual(method_def.first_char_column, 4)
        self.assertEqual(method_def.last_char_line, 6)
        self.assertEqual(method_def.last_char_column, 12)
        self.assertEqual(method_def.container_id, class_def.id)

        method_def_block = self.metascript.code_blocks_store[method_def.id]
        self.assertEqual(method_def_block.code,
                         "def f(self):\n"
                         "        'mdoc'\n"
                         "        pass")
        self.assertEqual(method_def_block.docstring, "mdoc")
        self.assertTrue(bool(method_def_block.code_hash))

    def test_closure_definition(self):
        """Test closure definition collection"""
        self.script("# script.py\n"
                    "def f():\n"
                    "    'fdoc'\n"
                    "    def c():\n"
                    "        'cdoc'\n"
                    "        pass")
        self.compile()

        function_def = self.find_code_component(name="f")
        closure_def = self.find_code_component(name="c")

        self.assertEqual(closure_def.type, "function_def")
        self.assertEqual(closure_def.mode, "w")
        self.assertEqual(closure_def.first_char_line, 4)
        self.assertEqual(closure_def.first_char_column, 4)
        self.assertEqual(closure_def.last_char_line, 6)
        self.assertEqual(closure_def.last_char_column, 12)
        self.assertEqual(closure_def.container_id, function_def.id)

        closure_def_block = self.metascript.code_blocks_store[closure_def.id]
        self.assertEqual(closure_def_block.code,
                         "def c():\n"
                         "        'cdoc'\n"
                         "        pass")
        self.assertEqual(closure_def_block.docstring, "cdoc")
        self.assertTrue(bool(closure_def_block.code_hash))
