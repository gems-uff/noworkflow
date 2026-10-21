# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""What the collector records for constructs with known defects

The e2e corpora pin how these constructs change what a script does under
``now run``; this module pins what the store records for them, in
process: the parts of an f-string (#160), ``yield from`` (#161) and the
arguments of a call made in a generator body that ``list()`` resumes, the
bases and keywords of a class statement and ``super()`` (#162, with the
keyword that reaches ``__init_subclass__``, #266, and the ``self`` of a
method reached through ``super()``), and the read of an inherited class
attribute through an object without ``__dict__``, the case of the quick
fix of #149 in ``Collector.full_member_lookup``.

Each characterization pins today's facts, and its ``_desired`` twin states
the behavior the issue asks for, marked with ``known_defects``: it is an
``xfail(strict=True)`` whose failure must carry the signature of its
defect. The twins live in the sibling ``Test<Subject>Desired`` classes.
Every mechanism is pure Python and gives the same facts on every supported
version, so no mark is limited by version or system.

The expected values never come from the collector: the spans come from the
script's text, the parts from Python's own ``ast``, and the values from
plain Python semantics, read back from the script's namespace where an
object is involved (reprs carry addresses). The f-strings avoid the
constructs that the syntax corpus pins on their own (no ``{{``, no
``F``/``rf`` prefix, no string inside a field, no f-string as a call's
only argument), so that only #160 shows.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import ast

from ..collection_testcase import CollectionTestCase
from ..helpers.defects import Defect, known_defects

SUCCESS = "the execution of trial -1 finished successfully"


def span(component):
    """Where a code component is: first and last line and column"""
    return (
        component.first_char_line,
        component.first_char_column,
        component.last_char_line,
        component.last_char_column,
    )


def span_of(code, lineno, text):
    """Where the first ``text`` of line ``lineno`` (1-based) of ``code`` is"""
    line = code.splitlines()[lineno - 1]
    column = line.index(text)
    return (lineno, column, lineno, column + len(text))


class ConstructCase(CollectionTestCase):
    """Reads compositions and dependencies of the collected script"""

    def parts(self, whole):
        """(composition type, position, part) of ``whole``, in order

        Compositions without a position (a format spec) come last; those
        without a part (the conversion of an fvalue) are left out.
        """
        store = self.metascript.code_components_store.store
        found = [
            (comp.type, comp.position, store[comp.part_id])
            for comp in self.metascript.compositions_store.store.values()
            if comp.whole_id == whole.id and comp.part_id is not None
        ]
        return sorted(
            found, key=lambda item: (item[1] is None, item[1] or 0, item[2].id)
        )

    def dependencies_of(self, evaluation):
        """Every dependency whose dependent is ``evaluation``"""
        store = self.metascript.dependencies_store.store
        return [dep for dep in store.values() if dep.dependent_id == evaluation.id]


# ---------------------------------------------------------------- #160
FSTRINGS = (
    "# script.py\n"
    'name = "nw"\n'
    "age = 10\n"
    'greeting = f"Hello, my name is {name} and I am {age} years old."\n'
    'spec = f"{name!s:>12}|{age:04d}"\n'
    'debug = f"{age=}"\n'
)
GREETING = 'f"Hello, my name is {name} and I am {age} years old."'
SPEC = 'f"{name!s:>12}|{age:04d}"'
DEBUG = 'f"{age=}"'
FSTRING_PARTS = (
    "#160: pyposast's visit_Str (pyposast/visitor.py) places every string "
    "constant on the next string token (ElementDict.find_next, "
    "pyposast/parser.py), and a literal part of an f-string, a format "
    "spec (a JoinedStr, placed by visit_JoinedStr the same way) and the "
    "text of an = specifier are no token of their own: each takes the span "
    "of the whole f-string, and visit_JoinedStr and visit_FormattedValue "
    "(transformer_expr.py) name the component after that span"
)


def joined_str(code, lineno):
    """The outermost JoinedStr on ``lineno``, according to Python's ast"""
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.JoinedStr) and node.lineno == lineno:
            return node
    raise AssertionError("no f-string on line {}".format(lineno))


def literal_texts(code, lineno):
    """The literal parts of the f-string on ``lineno``, by Python's ast

    They hold no escape, so each value is its source text.
    """
    return [
        value.value
        for value in joined_str(code, lineno).values
        if isinstance(value, ast.Constant)
    ]


class FStringCase(ConstructCase):
    """Finds the f-strings of FSTRINGS and their parts"""

    def fstring(self, lineno):
        """The outer f-string on ``lineno``

        On line 5 the two format specs are f-strings too, with the same
        name and span; the outer one is the f-string that is no format
        spec.
        """
        self.script(FSTRINGS)
        self.execute()
        specs = {
            comp.part_id
            for comp in self.metascript.compositions_store.store.values()
            if comp.type == "format_spec"
        }
        return [
            component
            for component in self.metascript.code_components_store.store.values()
            if component.type == "fstring"
            and component.first_char_line == lineno
            and component.id not in specs
        ][0]

    def literals(self, whole):
        """(name, span) of each literal part of ``whole``, in order"""
        return [
            (part.name, span(part))
            for _, _, part in self.parts(whole)
            if part.type == "literal"
        ]

    def spec(self):
        """The fvalue {name!s:>12} of line 5 and its format spec"""
        self.script(FSTRINGS)
        self.execute()
        fvalue = self.find_code_component(type="fvalue", name="{name!s:>12}")
        return fvalue, [
            part for kind, _, part in self.parts(fvalue) if kind == "format_spec"
        ][0]


class TestFStringParts(FStringCase):
    """The parts of an f-string"""

    def test_fstring_parts_are_composed_in_source_order(self):
        """The literals and fvalues are the f-string's *values, in order

        The kinds follow Python's own JoinedStr.values; the fvalues are
        named after their text and take its span.
        """
        whole = self.fstring(4)
        kinds = {"Constant": "literal", "FormattedValue": "fvalue"}
        expected = [
            kinds[type(value).__name__] for value in joined_str(FSTRINGS, 4).values
        ]
        parts = self.parts(whole)
        self.assertEqual([part.type for _, _, part in parts], expected)
        self.assertEqual(
            [(kind, pos) for kind, pos, _ in parts],
            [("*values", pos) for pos in range(len(expected))],
        )
        self.assertEqual(
            [(part.name, span(part)) for _, _, part in parts if part.type == "fvalue"],
            [(text, span_of(FSTRINGS, 4, text)) for text in ("{name}", "{age}")],
        )

    def test_fstring_literal_parts_take_the_span_of_the_whole_fstring(self):
        """Each literal part is named and placed as the f-string (#160)"""
        self.assertEqual(
            self.literals(self.fstring(4)),
            [(GREETING, span_of(FSTRINGS, 4, GREETING))]
            * len(literal_texts(FSTRINGS, 4)),
        )

    def test_format_spec_takes_the_span_of_the_whole_fstring(self):
        """A format spec is an f-string named and placed as the outer one

        Its literal part too (#160). Its evaluation, '>12', is the one the
        fvalue uses.
        """
        fvalue, spec = self.spec()
        self.assertEqual(
            (spec.type, spec.name, span(spec)),
            ("fstring", SPEC, span_of(FSTRINGS, 5, SPEC)),
        )
        self.assertEqual(self.literals(spec), [(SPEC, span_of(FSTRINGS, 5, SPEC))])
        fvalue_eval = self.find_evaluation(code_component_id=fvalue.id)
        spec_eval = self.find_evaluation(code_component_id=spec.id)
        self.assertEqual(spec_eval.repr, repr(">12"))
        self.assert_dependency(fvalue_eval, spec_eval, "use")

    def test_debug_specifier_text_takes_the_span_of_the_whole_fstring(self):
        """The text of an = specifier is named and placed as the f-string"""
        self.assertEqual(
            self.literals(self.fstring(6)), [(DEBUG, span_of(FSTRINGS, 6, DEBUG))]
        )


class TestFStringPartsDesired(FStringCase):
    """What #160 asks for the parts of an f-string"""

    @known_defects(Defect(FSTRING_PARTS, GREETING))
    def test_fstring_literal_parts_take_the_span_of_the_whole_fstring_desired(self):
        """Desired (#160): each literal part is named and placed as its text

        The literals are the Constants of Python's JoinedStr.
        """
        self.assertEqual(
            self.literals(self.fstring(4)),
            [(text, span_of(FSTRINGS, 4, text)) for text in literal_texts(FSTRINGS, 4)],
        )

    @known_defects(Defect(FSTRING_PARTS, SPEC))
    def test_format_spec_takes_the_span_of_the_whole_fstring_desired(self):
        """Desired (#160): the literal of a format spec is its own text

        The span of the spec f-string itself is left open: Python 3.12+
        places it at ':>12', colon included.
        """
        _, spec = self.spec()
        self.assertEqual(self.literals(spec), [(">12", span_of(FSTRINGS, 5, ">12"))])

    @known_defects(Defect(FSTRING_PARTS, DEBUG))
    def test_debug_specifier_text_takes_the_span_of_the_whole_fstring_desired(self):
        """Desired (#160): the text of an = specifier is 'age='"""
        self.assertEqual(
            self.literals(self.fstring(6)), [("age=", span_of(FSTRINGS, 6, "age="))]
        )


# ---------------------------------------------------------------- #161
YIELD_FROM = (
    "# script.py\n"
    "def inner(k):\n"
    "    yield k\n"
    "    return k + 1\n"
    "def outer(m):\n"
    "    result = yield from inner(m)\n"
    "    yield result\n"
    "values = list(outer(5))\n"
)
GENERATOR = "# script.py\ndef inner(k):\n    yield k\nvalues = list(inner(5))\n"
CALL_IN_BODY = (
    "# script.py\n"
    "def f(k):\n"
    "    return k + 1\n"
    "def outer(m):\n"
    "    result = f(m)\n"
    "    {}\n"
    "values = {}\n"
)
PLAIN_CALL = CALL_IN_BODY.format("return result", "outer(5)")
RESUMED_CALL = CALL_IN_BODY.format("yield result", "list(outer(5))")
YIELD_FROM_OPERAND = (
    "#161: visit_YieldFrom (transformer_expr.py) creates the yield_from "
    "component and returns the node unvisited, so its operand gets no code "
    "component, no composition and no evaluation, and the yield from "
    "itself is never evaluated"
)
YIELD_FROM_BINDING = (
    "#161: the operand of yield from is not rewritten (visit_YieldFrom, "
    "transformer_expr.py), so inner(m) never goes through Collector.call; "
    "its body starts under the activation of list() and takes the "
    "white-box-after-black-box path of new_function_def "
    "(Collector._function_def, collector.py, #266), where match_arguments "
    "binds k to list()'s argument. #324 is "
    "a second layer behind it: with the operand rewritten (measured in "
    "memory), k is 5 but depends on nothing, because the call inner(m) is "
    "made in the body of outer, which list() resumes, and its argument "
    "goes to list(); so the case flips only when both are fixed"
)
RESUMED_CALL_ARGUMENTS = (
    "#324: Collector._argument "
    "(collector.py) adds the argument of a call to "
    "Collector.last_activation, not to the activation it receives; while "
    "list() resumes a generator, last_activation is the activation of "
    "list(), so a call made in the generator body hands its arguments to "
    "list(), and match_arguments (collector.py) finds none for the "
    "parameters of the callee"
)


class YieldFromCase(ConstructCase):
    """Reads what YIELD_FROM records"""

    def yield_from_parts(self):
        """(type, name, composition type) of each part of the yield from"""
        self.script(YIELD_FROM)
        self.execute()
        whole = self.find_code_component(type="yield_from")
        return [(part.type, part.name, kind) for kind, _, part in self.parts(whole)]

    def line_six(self):
        """(type, name, repr) of the evaluations of line 6, in order"""
        self.script(YIELD_FROM)
        self.execute()
        store = self.metascript.code_components_store.store
        return [
            (
                store[evaluation.code_component_id].type,
                store[evaluation.code_component_id].name,
                evaluation.repr,
            )
            for evaluation in self.metascript.evaluations_store.store.values()
            if store[evaluation.code_component_id].first_char_line == 6
        ]

    def arguments_of(self, call):
        """The names of the 'argument' dependencies of ``call``, sorted"""
        store = self.metascript.code_components_store.store
        evaluations = self.metascript.evaluations_store.store
        return sorted(
            store[evaluations[dep.dependency_id].code_component_id].name
            for dep in self.dependencies_of(self.get_evaluation(name=call))
            if dep.type == "argument"
        )


class TestYieldFrom(YieldFromCase):
    """yield from, its subgenerator, and the calls a generator body makes"""

    def test_generator_called_directly_binds_the_parameter_to_its_argument(self):
        """Control: a generator called directly binds k to its argument

        Even when list() consumes it: the call inner(5) goes through
        Collector.call, and the body makes no call of its own.
        """
        self.script(GENERATOR)
        param_k = self.get_evaluation(name="k", type="param")
        self.assertEqual(param_k.repr, "5")
        self.assert_dependency(param_k, self.get_evaluation(name="5"), "argument", True)
        self.assertEqual(self.metascript.namespace["values"], [5])

    def test_call_in_a_function_binds_the_parameter_to_its_argument(self):
        """Control: f(m) made in a plain function binds k to the read of m"""
        self.script(PLAIN_CALL)
        param_k = self.get_evaluation(name="k", type="param")
        self.assertEqual(param_k.repr, "5")
        self.assert_dependency(
            param_k, self.get_evaluation(name="m", mode="r"), "argument", True
        )
        self.assertEqual(self.metascript.namespace["values"], 6)

    def test_call_in_a_resumed_generator_gives_its_argument_to_list(self):
        """f(m) made in a generator body that list() resumes loses m

        Python passes m, which is 5, to f, and list() receives only the
        generator; the store gives k no dependency and records the read
        of m as an argument of list(outer(5)).
        """
        self.script(RESUMED_CALL)
        param_k = self.get_evaluation(name="k", type="param")
        self.assertEqual(param_k.repr, "5")
        self.assertEqual(self.dependencies_of(param_k), [])
        self.assertEqual(self.arguments_of("list(outer(5))"), ["m", "outer(5)"])
        self.assertEqual(self.metascript.namespace["values"], [6])

    def test_yield_from_operand_has_no_code_component(self):
        """The yield from has only its keyword part (#161)

        Python's ast has the call inner(m) as its operand, and no code
        component holds it.
        """
        self.assertEqual(self.yield_from_parts(), [("syntax", "yield from", "*op_pos")])
        self.assertIsNone(self.find_code_component(name="inner(m)"))

    def test_yield_from_is_not_evaluated(self):
        """Line 6 records only the write of result, which depends on nothing

        Its value is right: inner returns k + 1 = 6, and plain Python
        gives values == [5, 6] (#161).
        """
        self.assertEqual(self.line_six(), [("name", "result", "6")])
        self.assertEqual(self.metascript.namespace["values"], [5, 6])
        result = self.get_evaluation(name="result", mode="w")
        self.assertEqual(self.dependencies_of(result), [])

    def test_yield_from_binds_the_parameter_to_the_builtin_argument(self):
        """The subgenerator's k is recorded as the argument of list()

        Python binds k to m, which is 5; the store records the outer
        generator, with a reference to the call outer(5) (#161, through
        the path of #266).
        """
        self.script(YIELD_FROM)
        param_k = self.get_evaluation(name="k", type="param")
        self.assertTrue(
            param_k.repr.startswith("<generator object outer"), param_k.repr
        )
        self.assert_dependency(
            param_k, self.get_evaluation(name="outer(5)"), "argument", True
        )


class TestYieldFromDesired(YieldFromCase):
    """What #161 and the resumed generator defect ask for"""

    @known_defects(Defect(YIELD_FROM_OPERAND, "[('syntax', 'yield from', '*op_pos')]"))
    def test_yield_from_operand_has_no_code_component_desired(self):
        """Desired (#161): the operand is a part of the yield from

        Composed as 'value', as the operand of a yield is.
        """
        self.assertIn(("call", "inner(m)", "value"), self.yield_from_parts())

    @known_defects(Defect(YIELD_FROM_OPERAND, "[('name', 'result', '6')]"))
    def test_yield_from_is_not_evaluated_desired(self):
        """Desired (#161): the yield from is evaluated, and result uses it

        Its value is the subgenerator's return value, 6.
        """
        line_six = self.line_six()
        self.assertIn(
            ("yield_from", "yield from inner(m)", "6"),
            line_six,
            "evaluations on line 6: {}".format(line_six),
        )
        result = self.get_evaluation(name="result", mode="w")
        self.assert_dependency(result, self.get_evaluation(type="yield_from"))

    @known_defects(Defect(YIELD_FROM_BINDING, "<generator object outer"))
    def test_yield_from_binds_the_parameter_to_the_builtin_argument_desired(self):
        """Desired (#161): k is 5, bound to the read of m

        As the controls bind a parameter to its argument. It also needs
        the call inner(m), made in the body of outer, to keep its argument
        (the next twin).
        """
        self.script(YIELD_FROM)
        param_k = self.get_evaluation(name="k", type="param")
        self.assertEqual(param_k.repr, "5")
        self.assert_dependency(
            param_k, self.get_evaluation(name="m", mode="r"), "argument", True
        )

    @known_defects(Defect(RESUMED_CALL_ARGUMENTS, "['m', 'outer(5)']"))
    def test_call_in_a_resumed_generator_gives_its_argument_to_list_desired(self):
        """Desired: list() receives only the generator, and k is bound to m

        As in the control, where f(m) is made in a plain function.
        """
        self.script(RESUMED_CALL)
        self.assertEqual(self.arguments_of("list(outer(5))"), ["outer(5)"])
        self.assert_dependency(
            self.get_evaluation(name="k", type="param"),
            self.get_evaluation(name="m", mode="r"),
            "argument",
            True,
        )


# ---------------------------------------------------------------- #162
CLASS_KEYWORD = (
    "# script.py\n"
    "class Base:\n"
    '    def __init_subclass__(cls, label="none"):\n'
    "        cls.label = label\n"
    'tag = "derived"\n'
    "class Derived(Base, label=tag):\n"
    "    pass\n"
    "result = Derived.label\n"
)
SUPER = (
    "# script.py\n"
    "class Base:\n"
    "    def __init__(self, value):\n"
    "        self.value = value\n"
    "class Derived(Base):\n"
    "    def __init__(self, value):\n"
    "        {}.__init__(value)\n"
    "item = Derived(7)\n"
    "result = item.value\n"
)
EXPLICIT_SUPER = SUPER.format("super(Derived, self)")
ZERO_ARGUMENT_SUPER = SUPER.format("super()")
CLASSMETHOD = (
    "# script.py\n"
    "class C:\n"
    "    @classmethod\n"
    "    def make(cls):\n"
    "        return cls\n"
    "inst = C()\n"
    "k = inst.make()\n"
)
KEYWORD_TO_CALLBACK = (
    "#266: type.__new__ calls __init_subclass__ from C, so its body takes "
    "the white-box-after-black-box path of new_function_def "
    "(Collector._function_def, collector.py), where match_arguments "
    "(collector.py) matches the parameters only against the argument "
    "dependencies of the enclosing activation, finds none for label and "
    "records its default (value and dependency) instead of the keyword the "
    "class statement passed"
)
SUPER_ZERO = (
    "#162: zero-argument super() is called from Collector._call "
    "(collector.py), a frame without the __class__ cell, so it raises "
    "RuntimeError; #274 is a second layer behind it (the __class__ cell "
    "holds the discarded first class, and super() would raise TypeError), "
    "so the case flips only when both are fixed"
)
BOUND_SELF = (
    "#323: Collector.func (collector.py) sets "
    "the bound dependency of a call to Collector.current_attr, the "
    "evaluation of the object before the dot, whenever the callee has "
    "__self__, and match_arguments (collector.py) binds the first "
    "parameter to it; Python binds it to __self__, which is the instance "
    "behind super() and the class of a classmethod reached through an "
    "instance"
)


class ClassStatementCase(ConstructCase):
    """Reads what the class statements record"""

    def labels(self):
        """The param evaluations of label, once the script ran

        __init_subclass__ runs twice per class statement today (#274), so
        callers never count them.
        """
        self.script(CLASS_KEYWORD)
        self.execute()
        self.assertEqual(self.metascript.namespace["result"], "derived")
        return self.get_evaluations(name="label", type="param")

    def assert_explicit_store(self):
        """Base.__init__ receives 7 from Derived.__init__, and result is 7"""
        value = self.get_evaluation(name="value", type="param", first_char_line=3)
        self.assertEqual(value.repr, "7")
        self.assert_dependency(
            value,
            self.get_evaluation(name="value", mode="r", first_char_line=7),
            "argument",
            True,
        )
        self.assertEqual(self.get_evaluation(name="result").repr, "7")
        self.assertEqual(self.metascript.namespace["result"], 7)

    def self_param(self):
        """The self param of Base.__init__, reached through super()"""
        self.script(EXPLICIT_SUPER)
        return self.get_evaluation(name="self", type="param", first_char_line=3)


class TestClassStatement(ClassStatementCase):
    """Bases, keywords and methods of a class statement"""

    def test_class_bases_and_keywords_are_dependencies_of_the_class(self):
        """The class depends on its base and on the value of its keyword

        Both are parts of the class_def, as *bases and *keywords. This
        refutes the part of #162 that says they are lost.
        """
        self.script(CLASS_KEYWORD)
        derived = self.get_evaluation(name="Derived", type="class_def")
        self.assert_dependency(
            derived, self.get_evaluation(name="Base", mode="r"), "base"
        )
        self.assert_dependency(
            derived, self.get_evaluation(name="tag", mode="r"), "argument"
        )
        whole = self.find_code_component(name="Derived", type="class_def")
        self.assertEqual(
            [
                (part.type, part.name, kind, pos)
                for kind, pos, part in self.parts(whole)
                if kind in ("*bases", "*keywords")
            ],
            [("name", "Base", "*bases", 0), ("name", "tag", "*keywords", 0)],
        )

    def test_class_keyword_reaches_init_subclass_as_the_default(self):
        """__init_subclass__ records label as its default, 'none'

        The class statement passes label='derived', and the reads of label
        inside see it; the param depends on the literal "none" (#266).
        """
        labels = self.labels()
        default = self.get_evaluation(name='"none"')
        self.assertTrue(labels)
        for label in labels:
            self.assertEqual(label.repr, repr("none"))
            self.assert_dependency(label, default, "argument", True)
        reads = self.get_evaluations(name="label", mode="r")
        self.assertTrue(reads)
        for read in reads:
            self.assertEqual(read.repr, repr("derived"))

    def test_explicit_super_call_is_collected(self):
        """Control: super(Derived, self).__init__(value) passes 7 along"""
        self.script(EXPLICIT_SUPER)
        self.assert_explicit_store()

    def test_zero_argument_super_stops_the_collection(self):
        """super() raises RuntimeError and the script stops there (#162)

        Plain Python runs it and sets result to 7.
        """
        msg = self.collect(ZERO_ARGUMENT_SUPER)
        self.assertEqual(
            msg.splitlines()[0], "RuntimeError('super(): __class__ cell not found')"
        )
        self.assertIsNone(
            self.get_evaluation(name="value", type="param", first_char_line=3)
        )
        self.assertNotIn("result", self.metascript.namespace)

    def test_method_through_super_binds_self_to_the_super_object(self):
        """The self of Base.__init__ is recorded as the super() proxy

        Python binds it to the Derived instance; the store records the
        proxy, with a reference to the call super(Derived, self).
        """
        param = self.self_param()
        self.assertTrue(param.repr.startswith("<super: <class 'Derived'>"), param.repr)
        self.assert_dependency(
            param, self.get_evaluation(name="super(Derived, self)"), "argument", True
        )

    def test_classmethod_through_instance_binds_cls_to_the_instance(self):
        """The cls of a classmethod called on an instance is the instance

        Python binds it to the class (k is C); the store records the
        instance, with a reference to the read of inst.
        """
        self.script(CLASSMETHOD)
        param = self.get_evaluation(name="cls", type="param")
        self.assertTrue(param.repr.startswith("<__main__.C object at"), param.repr)
        self.assert_dependency(
            param, self.get_evaluation(name="inst", mode="r"), "argument", True
        )
        namespace = self.metascript.namespace
        self.assertIs(namespace["k"], namespace["C"])


class TestClassStatementDesired(ClassStatementCase):
    """What #162, #266 and the bound self defect ask for"""

    # The list of the label reprs, which starts with 'none' today
    @known_defects(Defect(KEYWORD_TO_CALLBACK, "[\"'none'\""))
    def test_class_keyword_reaches_init_subclass_as_the_default_desired(self):
        """Desired (#266): label is 'derived', from the read of tag"""
        labels = self.labels()
        tag = self.get_evaluation(name="tag", mode="r")
        self.assertTrue(labels)
        self.assertEqual(
            [label.repr for label in labels], [repr("derived")] * len(labels)
        )
        for label in labels:
            self.assert_dependency(label, tag)

    @known_defects(Defect(SUPER_ZERO, "super(): __class__ cell not found"))
    def test_zero_argument_super_stops_the_collection_desired(self):
        """Desired (#162): super() works as super(Derived, self) does"""
        msg = self.collect(ZERO_ARGUMENT_SUPER)
        self.assertEqual(msg, SUCCESS)
        self.assert_explicit_store()

    @known_defects(Defect(BOUND_SELF, "<super: <class 'Derived'>"))
    def test_method_through_super_binds_self_to_the_super_object_desired(self):
        """Desired: the self of Base.__init__ is the Derived instance"""
        param = self.self_param()
        self.assertEqual(param.repr, repr(self.metascript.namespace["item"]))

    @known_defects(Defect(BOUND_SELF, "<__main__.C object at"))
    def test_classmethod_through_instance_binds_cls_to_the_instance_desired(self):
        """Desired: the cls of a classmethod is the class, even via inst"""
        self.script(CLASSMETHOD)
        param = self.get_evaluation(name="cls", type="param")
        self.assertEqual(param.repr, repr(self.metascript.namespace["C"]))


# ---------------------------------------------------------------- #149
SLOTS_CLASS_ATTRIBUTE = (
    "# script.py\n"
    "class Base:\n"
    "    __slots__ = ()\n"
    '    kind = "f"\n'
    "class Point(Base):\n"
    '    __slots__ = ("x",)\n'
    "    def __init__(self, x):\n"
    "        self.x = x\n"
    "p = Point(3)\n"
    "b = p.kind\n"
)
GETATTR_COUNTS = (
    "# script.py\n"
    "class Base:\n"
    "    __slots__ = ()\n"
    '    kind = "f"\n'
    "class Counting(Base):\n"
    "    __slots__ = ()\n"
    "    misses = []\n"
    "    def __getattr__(self, name):\n"
    "        Counting.misses.append(name)\n"
    "        raise AttributeError(name)\n"
    "p = Counting()\n"
    "b = p.kind\n"
    "seen = list(Counting.misses)\n"
)
GETATTR_RAISES = (
    "# script.py\n"
    "class Base:\n"
    "    __slots__ = ()\n"
    '    kind = "f"\n'
    "class Proxy(Base):\n"
    "    __slots__ = ()\n"
    "    def __getattr__(self, name):\n"
    "        raise KeyError(name)\n"
    "p = Proxy()\n"
    "b = p.kind\n"
)
DICT_PROBE = (
    "#149: full_member_lookup (collector.py) tests "
    "hasattr(vcontainer, '__dict__'), which on an object without __dict__ "
    "calls the script's __getattr__('__dict__'): the call is recorded, its "
    "side effects happen, and an exception other than AttributeError "
    "escapes into the script"
)


class TestMemberLookupWithoutDict(CollectionTestCase):
    """Reading an inherited class attribute through __slots__ instances

    In all three scripts kind is found on Base, so plain Python never
    calls __getattr__ and b is 'f'.
    """

    def test_class_attribute_of_an_object_without_dict_is_read(self):
        """p.kind is 'f', read from p, on an object without __dict__

        Guards the quick fix of #149: without it the collector raises
        AttributeError("'Point' object has no attribute '__dict__'").
        """
        self.script(SLOTS_CLASS_ATTRIBUTE)
        kind = self.get_evaluation(name="p.kind")
        self.assertEqual(kind.repr, repr("f"))
        self.assertEqual(self.get_evaluation(name="b").repr, repr("f"))
        self.assert_dependency(
            kind, self.get_evaluation(name="p", mode="r", first_char_line=10), "value"
        )
        self.assertEqual(self.metascript.namespace["b"], "f")

    def test_member_lookup_calls_the_script_getattr_with_dict(self):
        """The collector calls the script's __getattr__('__dict__') (#149)

        The call is recorded too: its name param is '__dict__'.
        """
        self.script(GETATTR_COUNTS)
        self.execute()
        self.assertEqual(self.metascript.namespace["seen"], ["__dict__"])
        self.assertEqual(self.metascript.namespace["b"], "f")
        self.assertEqual(
            self.get_evaluation(name="name", type="param").repr, repr("__dict__")
        )

    def test_member_lookup_lets_a_getattr_error_escape(self):
        """A KeyError of the script's __getattr__ stops the script (#149)"""
        msg = self.collect(GETATTR_RAISES)
        self.assertEqual(msg.splitlines()[0], "KeyError('__dict__')")
        self.assertNotIn("b", self.metascript.namespace)


class TestMemberLookupWithoutDictDesired(CollectionTestCase):
    """What #149 asks for a member lookup without __dict__"""

    @known_defects(Defect(DICT_PROBE, "['__dict__']"))
    def test_member_lookup_calls_the_script_getattr_with_dict_desired(self):
        """Desired (#149): the script's __getattr__ is never called"""
        self.script(GETATTR_COUNTS)
        self.execute()
        self.assertEqual(self.metascript.namespace["seen"], [])

    @known_defects(Defect(DICT_PROBE, "KeyError('__dict__')"))
    def test_member_lookup_lets_a_getattr_error_escape_desired(self):
        """Desired (#149): the script runs to the end, with b == 'f'"""
        msg = self.collect(GETATTR_RAISES)
        self.assertEqual(msg, SUCCESS)
        self.assertEqual(self.metascript.namespace["b"], "f")
