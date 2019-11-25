# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import unittest
import sys

from ...now.cmd.cmd_run import run
from ...now.collection.metadata import Metascript


NAME = "noworkflow/tests/examples/script.py"
PY3_PREFIX = "" if sys.version_info < (3, 0) else "module."


class Args(object):

    def __init__(self):
        self.verbose = False
        self.bypass_modules = False
        self.context = "main"
        self.depth = sys.getrecursionlimit()
        self.non_user_depth = 1
        self.execution_provenance = "Tracer"
        self.disasm = False
        self.dir = None
        self.script = NAME
        self.argv = ["-e", "Tracer", "__init__.py"]
        self.create_last = False
        self.name = None
        self.meta = False
        self.disasm0 = False
        self.disasm = False
        self.save_frequency = 0
        self.call_storage_frequency = 10000
        self.content_engine = "plain"
        self.message = "<empty>"


class TestCallSlicing(unittest.TestCase):

    def prepare(self, code):
        sys.argv = ["now", "run", "-e", "Tracer", "__init__.py"]
        metascript = Metascript().read_cmd_args(Args())
        metascript.fake_path(NAME, code.encode("utf-8"))

        # Set __main__ namespace
        import __main__
        metascript.namespace = __main__.__dict__

        # Clear boilerplate
        metascript.clear_sys()
        metascript.clear_namespace()

        return metascript

    def extract(self, metascript):
        result = set()
        for dep in metascript.variables_dependencies_store.values():
            source = metascript.variables_store[dep.source_id]
            target = metascript.variables_store[dep.target_id]
            result.add(((source.name, source.line),
                        (target.name, target.line)))
        return result

    def test_simple(self):
        metascript = self.prepare("def fn(a, b):\n"
                                  "    return a + b\n"
                                  "x = y = 1\n"
                                  "r = fn(x, y)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("b", 1), ("y", 3)),
            (("--graybox--", 0), ("x", 3)),
            (("--graybox--", 0), ("y", 3)),
            (("return", 2), ("a", 1)),
            (("return", 2), ("b", 1)),
            (("fn", 4), ("return", 2)),
            (("fn", 4), ("fn", 1)),
            (("r", 4), ("fn", 4)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_call_keyword(self):
        metascript = self.prepare("def fn(a, b, c=3):\n"
                                  "    return a + b + c\n"
                                  "x = y = 1\n"
                                  "r = fn(x, y, c=y)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("b", 1), ("y", 3)),
            (("--graybox--", 0), ("x", 3)),
            (("--graybox--", 0), ("y", 3)),
            (("c", 1), ("y", 3)),
            (("return", 2), ("a", 1)),
            (("return", 2), ("b", 1)),
            (("return", 2), ("c", 1)),
            (("fn", 4), ("return", 2)),
            (("fn", 4), ("fn", 1)),
            (("r", 4), ("fn", 4)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_call_keyword_kw(self):
        metascript = self.prepare("def fn(a, b, c=3):\n"
                                  "    return a + b + c\n"
                                  "x = y = 1\n"
                                  "z = {'b': 2}\n"
                                  "r = fn(x, c=y, **z)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("b", 1), ("z", 4)),
            (("c", 1), ("y", 3)),
            (("return", 2), ("a", 1)),
            (("return", 2), ("b", 1)),
            (("return", 2), ("c", 1)),
            (("fn", 5), ("return", 2)),
            (("fn", 5), ("fn", 1)),
            (("r", 5), ("fn", 5)),

            (("--graybox--", 0), ("x", 3)),
            (("--graybox--", 0), ("y", 3)),
            (("--graybox--", 0), ("z", 4)),
            (("z", 5), ("--graybox--", 0)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_call_args(self):
        metascript = self.prepare("def fn(a, b, c=3):\n"
                                  "    return a + b + c\n"
                                  "x = 1\n"
                                  "y = [2]\n"
                                  "r = fn(x, *y)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("b", 1), ("y", 4)),
            (("c", 1), ("y", 4)),  # ToDo #75: fix?
            (("return", 2), ("a", 1)),
            (("return", 2), ("b", 1)),
            (("return", 2), ("c", 1)),
            (("fn", 5), ("return", 2)),
            (("fn", 5), ("fn", 1)),
            (("r", 5), ("fn", 5)),

            (("--graybox--", 0), ("x", 3)),
            (("--graybox--", 0), ("y", 4)),
            (("y", 5), ("--graybox--", 0)),

        }
        self.assertEqual(result, self.extract(metascript))

    def test_def_args(self):
        metascript = self.prepare("def fn(a, *args):\n"
                                  "    return a + args[0]\n"
                                  "x, y, z = 1, 2, 3\n"
                                  "r = fn(x, y, z)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("args", 1), ("y", 3)),
            (("args", 1), ("z", 3)),  # ToDo #75: fix?
            (("return", 2), ("a", 1)),
            (("return", 2), ("args", 1)),
            (("fn", 4), ("return", 2)),
            (("fn", 4), ("fn", 1)),
            (("r", 4), ("fn", 4)),
            (("--graybox--", 0), ("x", 3)),
            (("--graybox--", 0), ("z", 3)),
            (("--graybox--", 0), ("y", 3)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_def_args_call_args(self):
        metascript = self.prepare("def fn(a, *args):\n"
                                  "    return a + args[0]\n"
                                  "x, y = 1, [2, 3]\n"
                                  "r = fn(x, *y)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("args", 1), ("y", 3)),
            (("return", 2), ("a", 1)),
            (("return", 2), ("args", 1)),
            (("fn", 4), ("return", 2)),
            (("fn", 4), ("fn", 1)),
            (("y", 4), ("--graybox--", 0)),
            (("--graybox--", 0), ("x", 3)),
            (("--graybox--", 0), ("y", 3)),
            (("r", 4), ("fn", 4)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_def_args_call_kw(self):
        metascript = self.prepare("def fn(a, *args):\n"
                                  "    return a\n"
                                  "x = {'a': 1}\n"
                                  "r = fn(**x)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("args", 1), ("x", 3)),  # ToDo #75: fix?
            (("return", 2), ("a", 1)),
            (("fn", 4), ("return", 2)),
            (("fn", 4), ("fn", 1)),
            (("x", 4), ("--graybox--", 0)),
            (("--graybox--", 0), ("x", 3)),
            (("r", 4), ("fn", 4)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_def_kwargs_call_keywords(self):
        metascript = self.prepare("def fn(a, **kwargs):\n"
                                  "    return a + kwargs['b']\n"
                                  "x, y = 1, 1\n"
                                  "r = fn(x, b=y)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("kwargs", 1), ("y", 3)),
            (("--graybox--", 0), ("x", 3)),
            (("--graybox--", 0), ("y", 3)),
            (("return", 2), ("a", 1)),
            (("return", 2), ("kwargs", 1)),
            (("fn", 4), ("return", 2)),
            (("fn", 4), ("fn", 1)),
            (("r", 4), ("fn", 4)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_def_kwargs_call_kwargs(self):
        metascript = self.prepare("def fn(a, **kwargs):\n"
                                  "    return a + kwargs['b']\n"
                                  "x = {'a': 1, 'b': 2}\n"
                                  "r = fn(**x)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("kwargs", 1), ("x", 3)),
            (("return", 2), ("a", 1)),
            (("return", 2), ("kwargs", 1)),
            (("fn", 4), ("return", 2)),
            (("fn", 4), ("fn", 1)),
            (("x", 4), ("--graybox--", 0)),
            (("--graybox--", 0), ("x", 3)),
            (("r", 4), ("fn", 4)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_complex(self):
        metascript = self.prepare("def fn(a, b, c, d, "
                                  "e=5, f=6, g=7, **kwargs):\n"
                                  "    return a\n"
                                  "x, y, z, w, u = 1, 2, [3, 4], 5, 7\n"
                                  "v = {'h': 8}\n"
                                  "r = fn(x, y, *z, e=w, g=u, **v)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("b", 1), ("y", 3)),
            (("c", 1), ("z", 3)),
            (("c", 1), ("v", 4)),  # ToDo #75: fix?
            (("d", 1), ("z", 3)),
            (("d", 1), ("v", 4)),  # ToDo #75: fix?
            (("e", 1), ("w", 3)),
            (("f", 1), ("z", 3)),  # ToDo #75: fix?
            (("f", 1), ("v", 4)),  # ToDo #75: fix?
            (("g", 1), ("u", 3)),
            (("kwargs", 1), ("z", 3)),  # ToDo #75: fix?
            (("kwargs", 1), ("v", 4)),
            (("return", 2), ("a", 1)),
            (("fn", 5), ("return", 2)),
            (("fn", 5), ("fn", 1)),
            (("r", 5), ("fn", 5)),

            (("--graybox--", 0), ("x", 3)),
            (("--graybox--", 0), ("v", 4)),
            (("--graybox--", 0), ("y", 3)),
            (("--graybox--", 0), ("u", 3)),
            (("--graybox--", 0), ("w", 3)),
            (("--graybox--", 0), ("z", 3)),
            (("z", 5), ("--graybox--", 0)),
            (("v", 5), ("--graybox--", 0)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_nested(self):
        metascript = self.prepare("def fn(a):\n"
                                  "    return a\n"
                                  "x = 1\n"
                                  "r = fn(fn(x))")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("a", 1), ("fn", 4)),
            (("--graybox--", 0), ("x", 3)),
            (("--graybox--", 0), ("fn", 4)),
            (("return", 2), ("a", 1)),
            (("fn", 4), ("return", 2)),
            (("fn", 4), ("fn", 4)),
            (("fn", 4), ("--graybox--", 0)),
            (("r", 4), ("fn", 4)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_ccall(self):
        metascript = self.prepare("a, b = 1, 2\n"
                                  "c = min(a, b)")
        run(metascript)
        result = {
            (("{}min".format(PY3_PREFIX), 2), ("return", 2)),
            (("{}min".format(PY3_PREFIX), 2), ("min", 0)),
            (("c", 2), ("{}min".format(PY3_PREFIX), 2)),

            (("--graybox--", 0), ("a", 1)),
            (("--graybox--", 0), ("b", 1)),
            (("return", 2), ("--graybox--", 0)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_noreturn(self):
        metascript = self.prepare("def fn(a):\n"
                                  "    a = 2\n"
                                  "x = 1\n"
                                  "r = fn(x)")
        run(metascript)
        result = {
            (("a", 1), ("x", 3)),
            (("--graybox--", 0), ("x", 3)),
            (("fn", 4), ("return", 2)),
            (("fn", 4), ("fn", 1)),
            (("r", 4), ("fn", 4)),
        }
        self.assertEqual(result, self.extract(metascript))

    def test_ccall_inter_params(self):
        metascript = self.prepare("a, b = [1, 2, 3], True\n"
                                  "c = sorted(a, reverse=b)")
        run(metascript)
        result = {
            (("{}sorted".format(PY3_PREFIX), 2), ("return", 2)),
            (("{}sorted".format(PY3_PREFIX), 2), ("sorted", 0)),
            (("c", 2), ("{}sorted".format(PY3_PREFIX), 2)),

            (("--graybox--", 0), ("a", 1)),
            (("--graybox--", 0), ("b", 1)),
            (("return", 2), ("--graybox--", 0)),
            (("a", 2), ("--graybox--", 0)),
        }
        if sys.version_info < (3, 0):
            result.add(
                (("b", 1), ("True", 0)),
            )
        self.assertEqual(result, self.extract(metascript))

    def test_import1(self):
        metascript = self.prepare("import csv")
        run(metascript)
        result = {
            (("csv", 1), ("import csv", 1)),
            (("import csv", 1), ("--blackbox--", 1)),
        }
        self.assertEqual(result, self.extract(metascript))
