# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now run`` over the Python grammar: one script per construct

The collector rewrites the AST of the script it runs, and each Python
version adds syntax. Each script of ``corpus/syntax`` uses one construct in
the ways that matter and prints what it computed; ``CASES`` names the
script, the oldest Python that parses it (``min_py``; the case is skipped
below it, before anything runs) and the flags of ``now run``. A case that
reruns a script under coarse granularity has the id ``<script>-cg``. Two
tests run for every case, each first skipped unless ``now`` traces with the
Python that runs pytest (``skip_unless_same_python``: the gates and the
marks follow the runner's version, which a ``NOW_E2E_CMD`` on another
Python would contradict):

- ``test_syntax_runs_like_plain_python`` runs the script with Python and
  with ``now run``, requires the same return code, stdout, stderr and
  written files (``oracle.py``), and then that the store holds one trial
  with evaluations (``oracle.assert_traced``), so a script that ran
  without the transformer cannot pass. The control of that comparator is
  ``test_oracle_detects_difference`` in ``test_oracle.py``.
- ``test_syntax_transformer_applies`` runs it with ``now run -v`` and
  requires that the transformer rewrote it and that the rewritten script
  ran. A green run is not enough: a ``SyntaxError`` from pyposast is
  swallowed (``Skipping transformer.``, printed only under ``-v``) and the
  script runs without its definition provenance; any other exception in
  pyposast or in the transformer prints a traceback, the script never runs,
  and the components created before it are stored all the same. So the
  test requires no ``Skipping transformer``, one trial, more than the
  script's own code component, at least one evaluation (only the rewritten
  script records one) and every component that ``components`` lists, as
  ``(type, line)`` or ``(type, line, name)``: a code component of that type
  (and name) whose first line is that line of the script, the construct's
  own line. The name of a component is its source text, the span pyposast
  gave it, so a name also catches a component recorded on the right line
  with the wrong span. A component recorded elsewhere is a wrong position,
  which the message shows with the lines where it was recorded.

A known defect is a ``Defect`` of ``oracle.py``, in the ``runs`` and
``transforms`` entries of each case: the reason starts with the issue that
will fix it (``#NNN: ``) and states the mechanism
measured, and the signature is a piece of text the failing run prints
today. The mark is ``xfail(strict=True)`` on the versions (and, with
``systems``, the platforms) where it applies; a failure without the
signature of an applicable defect fails outright, so a second defect or a
new regression cannot hide behind the mark. Each script that shows a
defect holds one mechanism, so that a fix flips exactly the cases that cite
it; where one mechanism can only be reached behind another, the reason
names both and says that the case flips only when both are fixed. The
script's docstring names the issue of each defect it shows; a green script
may also name, as context, the issue of what these tests do not check
("not checked here").

The map is measured, never guessed: run this module with ``--runxfail`` on
every Python of the matrix (macOS locally first; the CI legs are recorded
by the lead of the change) and give each defect ``since``/``before``
covering exactly the versions where the unmarked test fails; a mark that
differs by platform uses ``systems``. A fix that turns a case green fails it
with XPASS(strict) until the defect leaves that case's ``runs`` or
``transforms``: flipping an xfail means editing ``CASES`` in the same
change.

Layout of ``corpus/syntax``: every entry is a script that a case runs;
``test_syntax_cases_and_corpus_scripts`` fails on a script without a case
and on anything else left there (it skips hidden files, ``__pycache__`` and
the clutter of file managers, ``Thumbs.db`` and ``desktop.ini``).
"""

import dataclasses
import sys

import pytest

from .harness import CORPUS
from .oracle import (
    Defect,
    assert_same_outcome,
    assert_traced,
    defect_marks,
    expect_known_failure,
    fresh_copy,
    run_both,
    run_traced,
    skip_unless_same_python,
)

SYNTAX = CORPUS / "syntax"
# Clutter that the file manager of a system leaves, not a script.
IGNORED = ("Thumbs.db", "desktop.ini")


@dataclasses.dataclass(frozen=True)
class Case:
    """One script of ``corpus/syntax`` and how ``now run`` runs it

    ``name`` is the test id and, unless ``script`` says otherwise, the
    script's stem; ``construct`` says what the script exercises and heads
    the failure messages. ``components`` are ``(type, line)`` or ``(type,
    line, name)`` code components the transformer records for the
    construct; empty when it has no visitor for it, when the failing run
    stores none of them to measure the list against, or when listing them
    would mix a second defect into the case. ``runs`` and ``transforms``
    are the ``Defect``s of each test.
    """

    name: str
    construct: str
    script: str = None
    min_py: tuple = (3, 11)
    flags: tuple = ()
    components: tuple = ()
    runs: tuple = ()
    transforms: tuple = ()

    @property
    def filename(self):
        return (self.script or self.name) + ".py"


def misplaced(kind, line, found=(), name=None):
    """The message of ``component_problems`` for one missing component

    ``found`` are the lines where components of that type (and name) were
    recorded. A signature built with it is the text the failing run prints.
    """
    label = kind if name is None else "{} {!r}".format(kind, name)
    return "no {} at line {}; {} at line(s): {}".format(
        label, line, label, ", ".join(str(item) for item in found) or "none"
    )


# Defects shared by more than one case.

WALRUS_FALLBACK = (
    "#236: an assignment expression as {} reaches the fallback of "
    "RewriteAST._ast_num_from_component_id (transformer_stmt.py), which "
    "reads node.name, never set on a NamedExpr: AttributeError in the "
    "transformer, and the script never runs"
)
TYPE_PARAMS = (
    "#158: function_def and class_def (ast_elements.py) rebuild the "
    "definitions without type_params, so the type parameters vanish: "
)
BLACK_BOX_FALLBACK = (
    "#266: {} returns the {} uninstrumented ({}), so {} enters through "
    "the white-box-after-black-box path of new_function_def "
    "(Collector._function_def, collector.py), which hands it the "
    "dependencies of the enclosing activation as arguments; {} "
    "match_arguments (collector.py) indexes past its parameter list: "
    "IndexError"
)
BLACK_BOX_SIGNATURE = "param = parameter_order[last_unfilled]"
POSITIONAL_ONLY = (
    "#297: visit_FunctionDef "
    "(transformer_stmt.py) and visit_Lambda (transformer_expr.py) prepend "
    "their six __now_* parameters to args.args, after the positional-only "
    "ones, and process_parameters (transformer_stmt.py), which both call, "
    "never reads arguments.posonlyargs: "
)
COARSE_TARGET = (
    "#275: under -cg, visit_augassign and "
    "visit_annassign (transformer_stmt.py) take the coarse shortcut only "
    "for a name target (and visit_annassign only with a value: an "
    "annotation without one returns before it captures its target); {} "
    "goes down the fine-grained path, whose capture of the target is a "
    "plain generic_visit under -cg (RewriteDependencies.visit, "
    "transformer_expr.py) that sets no target_expr: AttributeError in the "
    "transformer, and the script never runs"
)
COMPREHENSION_UNPACKING = (
    "#278: the comprehension visitors "
    "(transformer_expr.py) assume a plain element, and a PEP 798 unpacking "
    "is not one: "
)
WITH_WITHOUT_AS = Defect(
    "#310: Collector._withitem (collector.py) appends an "
    "Assign only for an item with 'as', and the script's __enter__, called "
    "from WithContext.__enter__ (prov_execution/structures.py), takes the "
    "white-box-after-black-box path of new_function_def "
    "(Collector._function_def, collector.py), which reads "
    "activation.assignments[-1] before the call (find_bound_self) and "
    "again after it (the extend that catches only AttributeError): with no "
    "Assign pending, IndexError before __enter__ runs; a fix needs both "
    "reads",
    "activation.assignments[-1].dependency",
)
DECORATOR_FALLBACK = Defect(
    "#236: under -cg, RewriteDependencies.visit (transformer_expr.py) "
    "captures a decorator that is a name or an attribute without creating "
    "a component, so process_decorator reaches the fallback of "
    "RewriteAST._ast_num_from_component_id (transformer_stmt.py), which "
    "reads node.name: AttributeError in the transformer, and the script "
    "never runs",
    "'Name' object has no attribute 'name'",
)
LAZY_IMPORT_IN_TRY = (
    "#292: process_script (transformer_stmt.py) wraps "
    "the module body in try/except/finally, and Python rejects a lazy "
    "import inside try (SyntaxError from the compile in "
    "Definition.collect, definition.py)"
)
LAZY_IMPORT_SIGNATURE = "lazy import not allowed inside try/except blocks"

# The source text of the f-strings of fstring_prefix.py.
PREFIXED = (
    'F"hello {name}"',
    r'rf"\d+ {count}"',
    r'Rf"\t{name}"',
    r'rF"{count}\n"',
    r'FR"\s{name}"',
    r'Fr"{count}\b"',
)
# The source text of the f-strings that hold a string in a field.
NESTED_FORMAT_SPEC = '''f"{f'{value:.{precision}f}':>{width}}|"'''
NESTED_JOIN = '''f"{', '.join(f'<{item}>' for item in items)}"'''
NESTED_TRIPLE = """f'''{f"{f'{width}'}"}'''"""
NESTED_MIDDLE = '''f"{f'{width}'}"'''
SAME_QUOTE = '''f"{f"{f"{1 + 1}"}"}"'''
SAME_QUOTE_MIDDLE = '''f"{f"{1 + 1}"}"'''
SAME_QUOTE_JOIN = '''f"{", ".join(names)}"'''
SPANNING = 'f"{\n    len(names)  # how many names\n}"'
BACKSLASH = r'''f"{'\n'.join(names)}"'''
GREETING = 'f"Hello, my name is {name} and I am {age} years old."'
TOTAL = 'f"total {count}"'

CASES = (
    Case(
        "match_statement",
        "match: literal, or, as, value, sequence, mapping, class, guard and "
        "wildcard patterns (no visitor)",
    ),
    Case(
        "walrus",
        "assignment expressions in an if, a while and a call (no visitor)",
    ),
    Case(
        "walrus_comprehension",
        "assignment expressions in a comprehension, binding in the enclosing scope",
        components=(("listcomp", 5), ("listcomp", 9)),
        runs=(
            Defect(
                WALRUS_FALLBACK.format("the element of a list comprehension"),
                "'NamedExpr' object has no attribute 'name'",
            ),
        ),
        transforms=(
            Defect(
                WALRUS_FALLBACK.format("the element of a list comprehension"),
                "'NamedExpr' object has no attribute 'name'",
            ),
        ),
    ),
    Case(
        "walrus_yield",
        "an assignment expression as the value of a yield",
        components=(("yield", 5),),
        runs=(
            Defect(
                WALRUS_FALLBACK.format("the value of a yield"),
                "'NamedExpr' object has no attribute 'name'",
            ),
        ),
        transforms=(
            Defect(
                WALRUS_FALLBACK.format("the value of a yield"),
                "'NamedExpr' object has no attribute 'name'",
            ),
        ),
    ),
    Case(
        "fstring_prefix",
        "f-strings whose prefix does not start with a lowercase f (such as "
        "F, rf, Rf, rF, FR, Fr), each with a field and assigned to a name",
        components=(
            ("fstring", 7, PREFIXED[0]),
            ("fvalue", 7, "{name}"),
            ("fstring", 8, PREFIXED[1]),
            ("fvalue", 8, "{count}"),
            ("fstring", 9, PREFIXED[2]),
            ("fvalue", 9, "{name}"),
            ("fstring", 10, PREFIXED[3]),
            ("fvalue", 10, "{count}"),
            ("fstring", 11, PREFIXED[4]),
            ("fvalue", 11, "{name}"),
            ("fstring", 12, PREFIXED[5]),
            ("fvalue", 12, "{count}"),
        ),
    ),
    # The outer f-string is named only on line 9: on lines 10 and 11 the
    # JoinedStr of each format spec is recorded with the span of the whole
    # f-string, so a name could not tell the two apart.
    Case(
        "fstring_formatted_value",
        "f-string literal parts, conversions, format specs and =, each "
        "f-string assigned to a name",
        components=(
            ("fstring", 9, GREETING),
            ("fvalue", 9, "{name}"),
            ("fvalue", 9, "{age}"),
            ("literal", 9, "Hello, my name is "),
            ("literal", 9, " and I am "),
            ("literal", 9, " years old."),
            ("fvalue", 10, "{name!r}"),
            ("fvalue", 10, "{name!s:>12}"),
            ("fvalue", 10, "{ratio:.2%}"),
            ("fvalue", 10, "{age:04d}"),
            ("fvalue", 11, "{age=}"),
            ("fvalue", 11, "{ratio = :.1f}"),
        ),
        transforms=(
            Defect(
                "#160: pyposast's visit_Str (pyposast/visitor.py) looks every "
                "string constant up among the string tokens "
                "(ElementDict.find_next, pyposast/parser.py), and a literal "
                "part of an f-string is no token of its own: each literal part "
                "takes the span of the whole f-string and is named after it, "
                "while the expected name is the part's own source text",
                misplaced("literal", 9, name="Hello, my name is "),
            ),
        ),
    ),
    Case(
        "fstring_call_argument",
        "an f-string as the only argument of a call, next to the same "
        "f-string assigned and passed with a second argument",
        components=(
            ("fstring", 6, TOTAL),
            ("fstring", 7, TOTAL),
            ("fstring", 8, TOTAL),
        ),
    ),
    Case(
        "fstring_braces",
        "doubled braces in f-strings, next to replacement fields",
        components=(
            ("fstring", 6, 'f"{{{name}}}"'),
            ("fvalue", 6, "{name}"),
            ("fstring", 7, """f'{{"{name}": {count}}}'"""),
            ("fvalue", 7, "{name}"),
            ("fvalue", 7, "{count}"),
            ("fstring", 8, 'f"{{}} placeholder and {count}"'),
            ("fvalue", 8, "{count}"),
        ),
    ),
    # Not named: the inner f-string of line 9, whose format spec is recorded
    # with its span, and {width}, the field of the outer format spec, which
    # takes the span of {value:.{precision}f} (#423).
    Case(
        "fstring_nested",
        "f-strings nested in a field and in a format spec, each assigned to a name",
        components=(
            ("fstring", 9, NESTED_FORMAT_SPEC),
            ("fvalue", 9, "{f'{value:.{precision}f}':>{width}}"),
            ("fvalue", 9, "{value:.{precision}f}"),
            ("fvalue", 9, "{precision}"),
            ("fstring", 10, NESTED_JOIN),
            ("fstring", 10, "f'<{item}>'"),
            ("fvalue", 10, "{', '.join(f'<{item}>' for item in items)}"),
            ("fvalue", 10, "{item}"),
            ("fstring", 11, NESTED_TRIPLE),
            ("fstring", 11, NESTED_MIDDLE),
            ("fvalue", 11, """{f"{f'{width}'}"}"""),
            ("fvalue", 11, "{f'{width}'}"),
            ("fvalue", 11, "{width}"),
        ),
    ),
    Case(
        "fstring_pep701",
        "PEP 701 f-strings: the same quote nested, multi-line fields with a "
        "comment, a backslash in a field, each assigned to a name",
        min_py=(3, 12),
        components=(
            ("fstring", 6, SAME_QUOTE),
            ("fstring", 6, SAME_QUOTE_MIDDLE),
            ("fvalue", 6, '{f"{f"{1 + 1}"}"}'),
            ("fvalue", 6, '{f"{1 + 1}"}'),
            ("fvalue", 6, "{1 + 1}"),
            ("fstring", 7, SAME_QUOTE_JOIN),
            ("fvalue", 7, '{", ".join(names)}'),
            ("fstring", 8, SPANNING),
            ("fvalue", 8, "{\n    len(names)  # how many names\n}"),
            ("fstring", 11, BACKSLASH),
            ("fvalue", 11, r"""{'\n'.join(names)}"""),
        ),
    ),
    Case(
        "fstring_spec_field",
        "a field in the format spec of a field whose expression holds a "
        "brace, a nested f-string's field or a dict display, next to the "
        "same spec after a plain name",
        components=(
            ("fvalue", 7, "{width}"),
            ("fvalue", 8, "{width}"),
            ("fvalue", 9, "{width}"),
        ),
        transforms=(
            Defect(
                "#423: pyposast's visit_FormattedValue "
                "(pyposast/visitor.py) looks the '{' of each field of the format "
                "spec up from just after the '{' of the field that holds the "
                "spec (visit_string_like, brackets.find_next, "
                "pyposast/parser.py), and the expression of that field comes "
                "first: a brace inside it, the field of a nested f-string or a "
                "dict display, is found before the spec's own, and the spec's "
                "field takes its span, while the same spec after a plain name "
                "is placed right",
                misplaced("fvalue", 8, (7,), name="{width}"),
            ),
        ),
    ),
    Case(
        "except_star",
        "except* over an exception group (TryStar, no visitor)",
    ),
    Case(
        "type_alias",
        "the type statement, plain and generic (TypeAlias, no visitor)",
        min_py=(3, 12),
    ),
    Case(
        "generic_class",
        "a PEP 695 generic class whose annotations use its parameter",
        min_py=(3, 12),
        components=(("class_def", 5, "Box"),),
        runs=(
            Defect(
                TYPE_PARAMS + "on 3.12 and 3.13 the annotations that name T "
                "raise NameError when the class is defined",
                "NameError(\"name 'T' is not defined\")",
                before=(3, 14),
            ),
            Defect(
                TYPE_PARAMS + "from 3.14, with deferred annotations, Box "
                "loses its __class_getitem__ and Box[int] raises TypeError",
                "is not subscriptable",
                since=(3, 14),
            ),
        ),
    ),
    Case(
        "generic_function",
        "PEP 695 generic functions: plain, bound, constrained, TypeVarTuple "
        "and ParamSpec",
        min_py=(3, 12),
        components=(
            ("function_def", 5, "first"),
            ("function_def", 9, "largest"),
            ("function_def", 13, "shaped"),
        ),
        runs=(
            Defect(
                TYPE_PARAMS + "the annotations that name T raise NameError, "
                "when the function is defined on 3.12 and 3.13 and when "
                "__annotations__ is read from 3.14",
                "NameError(\"name 'T' is not defined\")",
            ),
        ),
    ),
    Case(
        "type_param_defaults",
        "PEP 696 type parameter defaults on a class, a function and an alias",
        min_py=(3, 13),
        components=(("class_def", 5, "Box"), ("function_def", 9, "pick")),
        runs=(
            Defect(
                TYPE_PARAMS + "on 3.13 the annotations that name T raise "
                "NameError when the function is defined",
                "NameError(\"name 'T' is not defined\")",
                before=(3, 14),
            ),
            Defect(
                TYPE_PARAMS + "from 3.14 Box.__type_params__ is empty",
                "IndexError('tuple index out of range')",
                since=(3, 14),
            ),
        ),
    ),
    Case(
        "tstring",
        "PEP 750 template strings, with and without interpolations (no visitor)",
        min_py=(3, 14),
    ),
    Case(
        "async_await",
        "async def and await, with and without parameters, and gather",
        components=(
            ("await", 8),
            ("await", 13),
            ("await", 18),
            ("await", 19),
            ("await", 21),
        ),
        runs=(
            Defect(
                BLACK_BOX_FALLBACK.format(
                    "visit_Await (transformer_expr.py)",
                    "await",
                    "#157",
                    "a coroutine function it calls",
                    "double(value) absorbs them, but for the parameterless ready()",
                ),
                BLACK_BOX_SIGNATURE,
            ),
        ),
    ),
    Case(
        "async_for",
        "async for over an asynchronous generator, with else",
        components=(("async_for", 13),),
        runs=(
            Defect(
                "#157: _yielditem (collector.py) reads "
                "activation.generator.value, but new_function_def creates "
                "activation.generator only for a GeneratorType result, and an "
                "async generator is not one: AttributeError",
                "in _yielditem",
            ),
        ),
    ),
    Case(
        "async_for_iterator",
        "async for over an asynchronous iterator defined by a class, with else",
        components=(("async_for", 21),),
    ),
    Case(
        "async_with",
        "async with, two items in one statement",
        components=(("async_with", 20),),
        runs=(
            Defect(
                BLACK_BOX_FALLBACK.format(
                    "visit_AsyncWith (transformer_stmt.py)",
                    "statement",
                    "#157",
                    'the call Resource("b") of the second item',
                    "the traced __init__ receives them, and",
                )
                + "; the "
                "uninstrumented statement also calls the second item's "
                "__aenter__ through the same path, where the same IndexError "
                "shows once __init__ absorbs the extra arguments",
                BLACK_BOX_SIGNATURE,
            ),
        ),
    ),
    Case(
        "async_comprehension",
        "async for inside a list comprehension, over an asyncio.StreamReader",
        components=(("listcomp", 13),),
        runs=(
            Defect(
                "#157: visit_generator (transformer_expr.py, 'ToDo: consider "
                "node.is_async') wraps every comprehension iterable in "
                "Collector.loop, whose _loop returns the synchronous generator "
                "_loop_generator, so the async for of the comprehension gets a "
                "generator: TypeError. The iterable is a StreamReader, whose "
                "__aiter__ and __anext__ are not traced: with that mechanism "
                "fixed (simulated), the __aiter__ of an iterator of the script "
                "takes #266's white-box-after-black-box path under the "
                "activation of asyncio.run, and match_arguments (collector.py) "
                "raises IndexError",
                "'async for' requires an object with __aiter__ method",
            ),
        ),
    ),
    Case(
        "async_await_comprehension",
        "await inside a list comprehension",
        components=(("listcomp", 11), ("await", 11)),
        runs=(
            Defect(
                BLACK_BOX_FALLBACK.format(
                    "visit_Await (transformer_expr.py)",
                    "await",
                    "#157",
                    "square(value)",
                    "inside the comprehension",
                ),
                BLACK_BOX_SIGNATURE,
            ),
        ),
    ),
    Case(
        "ann_assign",
        "annotated assignments at module, class and function scope, and a "
        "local annotation that is never evaluated",
        components=(
            ("ann_assign", 12),
            ("ann_assign", 13),
            ("ann_assign", 17),
            ("ann_assign", 18),
            ("ann_assign", 22),
            ("ann_assign", 27),
        ),
    ),
    Case(
        "ann_assign-cg",
        "annotated assignments under coarse granularity, one of them to a "
        "subscript (coarse records no ann_assign for a name target, so no "
        "component is listed)",
        script="ann_assign",
        flags=("-cg",),
        runs=(
            Defect(
                COARSE_TARGET.format('the annotated assignment values["key"]: int = 5'),
                "'Subscript' object has no attribute 'target_expr'",
            ),
        ),
        transforms=(
            Defect(
                COARSE_TARGET.format('the annotated assignment values["key"]: int = 5'),
                "'Subscript' object has no attribute 'target_expr'",
            ),
        ),
    ),
    Case(
        "dataclass",
        "@dataclass with order, frozen, defaults and default_factory",
        components=(
            ("class_def", 6, "Item"),
            ("class_def", 13, "Point"),
            ("ann_assign", 8),
            ("ann_assign", 10),
            ("ann_assign", 16),
        ),
    ),
    Case(
        "decorator_with_args",
        "decorator factories with functools.wraps and keyword arguments, "
        "stacked on a function and on a class",
        components=(
            ("function_def", 8, "wrapper"),
            ("function_def", 22, "greet"),
            ("class_def", 28, "Thing"),
        ),
        runs=(
            Defect(
                "#306: Collector.call "
                "(collector.py) names each activation after the callee's "
                "__name__, including the internal one new_function_def opens "
                "for itself, so a wrapper that functools.wraps (or any "
                "assignment to __name__) renames never matches the rewritten "
                "function's __name__, takes the white-box-after-black-box path "
                "of new_function_def (Collector._function_def, collector.py) "
                "and re-enters itself through Collector._call until "
                "RecursionError",
                "RecursionError x-greeting greet thing",
            ),
        ),
    ),
    Case(
        "decorator",
        "decorators that are a name or an attribute: staticmethod, "
        "classmethod, functools.cache and a function of the script",
        components=(
            ("function_def", 19, "double"),
            ("function_def", 23, "make"),
            ("function_def", 29, "square"),
            ("function_def", 35, "plain"),
        ),
    ),
    Case(
        "decorator-cg",
        "decorators that are a name or an attribute under coarse "
        "granularity (only the first function_def is listed: the failing "
        "run stores none of the later ones)",
        script="decorator",
        flags=("-cg",),
        components=(("function_def", 19, "double"),),
        runs=(DECORATOR_FALLBACK,),
        transforms=(DECORATOR_FALLBACK,),
    ),
    Case(
        "decorator_property",
        "property as a decorator, for a getter and a setter",
        components=(("function_def", 9, "celsius"), ("function_def", 13, "celsius")),
        runs=(
            Defect(
                "#281: visit_FunctionDef "
                "(transformer_stmt.py) puts collect_function_def first in the "
                "decorator list, so it runs last and receives what the "
                "script's decorators returned; Collector.collect_function_def "
                "(collector.py) sets original_def on it, and a result without "
                "a __dict__ (a property here) rejects the assignment: "
                "AttributeError",
                "'property' object has no attribute 'original_def'",
            ),
        ),
    ),
    Case(
        "decorated_definitions",
        "consecutive decorated classes whose names are never used again",
        components=(("class_def", 12, "First"), ("class_def", 17, "Second")),
    ),
    Case(
        "starred_targets",
        "starred assignment and for targets, and starred names, attributes "
        "and subscripts in displays and in a call",
        components=(
            ("starred", 10),
            ("starred", 12),
            ("starred", 14),
            ("starred", 16),
            ("starred", 20),
            ("starred", 21),
            ("starred", 22),
        ),
    ),
    Case(
        "starred_display",
        "starred items whose operand is a literal, a display, a call, a "
        "binary operation or a conditional expression",
        components=(
            ("starred", 7),
            ("starred", 8),
            ("starred", 9),
            ("starred", 10),
            ("starred", 11),
        ),
        runs=(
            Defect(
                "#308: visit_Starred "
                "(transformer_expr.py) reads target_expr from the rewritten "
                "operand, which only a name, an attribute or a subscript "
                "carries; a string literal, a list display, a call, a binary "
                "operation and a conditional expression (each measured alone) "
                "raise AttributeError in the transformer, and the script never "
                "runs",
                "'Call' object has no attribute 'target_expr'",
            ),
        ),
        transforms=(
            Defect(
                "#308: visit_Starred "
                "(transformer_expr.py) raises AttributeError on a starred "
                "literal, display, call, operation or conditional expression: "
                "nothing is evaluated",
                "'Call' object has no attribute 'target_expr'",
            ),
        ),
    ),
    Case(
        "call_unpacking",
        "several * and ** unpackings in one call, a dict display into the "
        "parameters, an iterable into *args (recorded as arguments)",
        components=(("call", 22), ("call", 23), ("call", 24), ("call", 25)),
    ),
    Case(
        "dict_unpacking",
        "dictionary unpacking in a display",
        components=(("dict", 5), ("dict", 7)),
    ),
    Case(
        "class_bases",
        "classes with bases and keywords: zero-argument super() and "
        "__init_subclass__ with a class keyword",
        components=(("class_def", 6, "Base"), ("class_def", 18, "Derived")),
        runs=(
            Defect(
                "#162: the transformer instruments super() as a call, so super "
                "runs inside the frame of Collector._call (collector.py), where "
                "zero-argument super() finds no __class__ cell: RuntimeError; "
                "#274 is a second layer behind it "
                "(Collector._class_def (collector.py) builds a second class "
                "whose methods keep the first one in their __class__ cell, so "
                "super() would then raise TypeError), which test_oracle.py "
                "covers, so the case flips only when both are fixed",
                "super(): __class__ cell not found",
            ),
        ),
    ),
    Case(
        "metaclass_new",
        "a metaclass whose __new__ runs for a class statement",
        components=(("class_def", 5, "Meta"), ("class_def", 11, "WithMeta")),
        runs=(
            Defect(
                "#293: the class statement calls Meta.__new__ "
                "while the activation of the class body (Collector.start_class, "
                "collector.py) is the last one, and only Collector._call sets "
                "func_evaluation; new_function_def (Collector._function_def, "
                "collector.py) takes the white-box-after-black-box path, whose "
                "__new__/__call__ branch builds the bound Dependency from "
                "activation.func_evaluation, None here: AttributeError (a "
                "__call__ reached from a for loop over iter(callable, "
                "sentinel) fails through the same branch). "
                "#274 calls Meta.__new__ a second time "
                "through the same branch, which this script cannot observe",
                "'NoneType' object has no attribute 'activation_id'",
            ),
        ),
    ),
    Case(
        "class_in_function",
        "class statements inside a function and a method, one nested in "
        "another, and a class body that reads a parameter of its function",
        components=(
            ("class_def", 8, "Inner"),
            ("class_def", 19, "InMethod"),
            ("class_def", 26, "A"),
            ("class_def", 27, "B"),
        ),
        runs=(
            Defect(
                "#354: the transformer writes `__now_activation__ = "
                "start_class(__now_activation__, ...)` into the class body, "
                "and a name that a class body assigns is looked up in the "
                "class namespace and then in the globals, skipping the "
                "enclosing function, so Collector.start_class (collector.py) "
                "receives the module's activation; the class decorator then "
                "pops from the empty dependency list of the function's "
                "activation: IndexError, and the script never finishes",
                "pop from empty list",
            ),
        ),
    ),
    Case(
        "class_slots",
        "__slots__ as a tuple and as a single string",
        components=(
            ("class_def", 5, "Point"),
            ("class_def", 13, "Named"),
            ("assign", 6),
            ("assign", 14),
        ),
    ),
    Case(
        "yield_from",
        "yield from a subgenerator, with its return value, and from a range",
        components=(("yield_from", 12), ("yield_from", 14)),
        runs=(
            Defect(
                BLACK_BOX_FALLBACK.format(
                    "visit_YieldFrom (transformer_expr.py)",
                    "expression",
                    "#161",
                    "the parameterless generator inner()",
                    "when its body starts,",
                ),
                BLACK_BOX_SIGNATURE,
            ),
        ),
    ),
    Case(
        "yield_call_argument",
        "a yield expression as the argument of a call inside a generator",
        components=(("yield", 7), ("yield", 8)),
        runs=(
            Defect(
                "#311: Collector.call (collector.py) "
                "pushes the callee's FutureActivation on "
                "Collector.future_activation, one stack for the whole run, "
                "before the arguments are evaluated, and Collector._call pops "
                "whichever entry is on top, not the one its own call pushed; a "
                "yield in the arguments suspends the generator between the "
                "two, so the caller's pending print pops the generator's "
                "items.append, and each resume of the generator pops a pending "
                "print (the first resume the second print's, the second the "
                "first's): items.append receives the yielded values and print "
                "the sent ones",
                "collected ['first', 'second']",
            ),
        ),
    ),
    Case(
        "with_statement",
        "with: several items, parenthesized items, a tuple target, an item "
        "without a target after a bound one, an exception received and "
        "suppressed, a file (the outcome and the positions only: which "
        "item each target of a statement with several items depends on is "
        "not checked)",
        components=(
            ("with", 38),
            ("withitem", 38),
            ("with", 41),
            ("withitem", 42),
            ("withitem", 43),
            ("with", 47),
            ("withitem", 47),
            ("with", 50),
            ("withitem", 50),
            ("with", 55),
            ("with", 58),
            ("with", 62),
        ),
    ),
    Case(
        "with_statement-cg",
        "the with script under coarse granularity (the outcome and the positions only)",
        script="with_statement",
        flags=("-cg",),
        components=(
            ("with", 38),
            ("withitem", 38),
            ("with", 41),
            ("withitem", 42),
            ("withitem", 43),
            ("with", 47),
            ("withitem", 47),
            ("with", 50),
            ("withitem", 50),
            ("with", 55),
            ("with", 58),
            ("with", 62),
        ),
    ),
    Case(
        "with_no_target",
        "a with statement whose only item has no target",
        components=(("with", 18), ("withitem", 18)),
        runs=(WITH_WITHOUT_AS,),
    ),
    Case(
        "with_no_target-cg",
        "a with statement whose only item has no target, under coarse granularity",
        script="with_no_target",
        flags=("-cg",),
        components=(("with", 18), ("withitem", 18)),
        runs=(WITH_WITHOUT_AS,),
    ),
    Case(
        "for_multiple_targets",
        "for with tuple, nested tuple, enumerate and zip targets, and else",
        components=(("for", 5), ("for", 7), ("for", 9)),
    ),
    Case(
        "for_multiple_targets-cg",
        "for with several targets under coarse granularity, which records "
        "no for component, only the calls of the for lines",
        script="for_multiple_targets",
        flags=("-cg",),
        components=(("call", 7), ("call", 9)),
    ),
    Case(
        "if_elif_else",
        "if with elif and else, returning from each branch, and in a loop",
        components=(("if", 6), ("if", 8), ("if", 10), ("if", 17)),
    ),
    Case(
        "if_elif_else-cg",
        "if with elif and else under coarse granularity",
        script="if_elif_else",
        flags=("-cg",),
        components=(("if", 6), ("if", 8), ("if", 10), ("if", 17)),
    ),
    Case(
        "while_else",
        "while with else, break and continue",
        components=(("while", 4), ("continue", 7), ("break", 9), ("while", 15)),
    ),
    Case(
        "while_else-cg",
        "while with else, break and continue under coarse granularity, "
        "which records no while component",
        script="while_else",
        flags=("-cg",),
        components=(("continue", 7), ("break", 9)),
    ),
    Case(
        "sys_exit_no_code",
        "sys.exit() without a code, which ends the script with status 0",
        components=(("call", 5),),
    ),
    Case(
        "global_nonlocal",
        "global and nonlocal declarations",
        components=(("global", 8), ("nonlocal", 16)),
    ),
    Case(
        "lambda_expr",
        "lambda: defaults, *args, keyword-only, **kwargs, as a key, in a "
        "comprehension, called at once",
        components=(
            ("lambda_def", 5),
            ("lambda_def", 6),
            ("lambda_def", 8),
            ("lambda_def", 9),
            ("lambda_def", 11),
        ),
        runs=(
            Defect(
                "#290: the decorator that _function_def "
                "(collector.py) returns pushes a DependencyAware of its own on "
                "the enclosing activation, which only collect_function_def pops "
                "and a lambda never reaches; as the element of a list "
                "comprehension, _item pops that extra entry as the item's own "
                "and reads .items from the item's DependencyAware, left on top "
                "in place of the list's CollectionDependencyAware: "
                "AttributeError",
                "'DependencyAware' object has no attribute 'items'",
            ),
        ),
    ),
    Case(
        "chained_comparison",
        "chained comparisons with mixed operators and their short circuit",
        components=(
            ("lt.lte.lt", 12),
            ("lt.gt", 12),
            ("eq.noteq", 12),
            ("in.notin", 13),
            ("isnot.isnot", 13),
            ("lt.lt.lt", 14),
        ),
    ),
    Case(
        "conditional_expression",
        "conditional expressions: nested, short-circuiting, raising inside "
        "the branch taken",
        components=(("ifexp", 12), ("ifexp", 16), ("ifexp", 17), ("ifexp", 19)),
    ),
    Case(
        "del_statement",
        "del of a name, a subscript, a slice, an attribute, several targets",
        components=(("delete", 13), ("delete", 14), ("delete", 15), ("delete", 16)),
    ),
    Case(
        "assert_statement",
        "assert with and without a message, passing without evaluating the "
        "message, failing and caught",
        components=(("assert", 12), ("assert", 13), ("assert", 15)),
    ),
    Case(
        "positional_only",
        "positional-only parameters, with defaults and next to **kwargs",
        components=(
            ("param", 6, "a"),
            ("param", 6, "b"),
            ("param", 6, "c"),
            ("param", 10, "a"),
            ("param", 10, "rest"),
        ),
        runs=(
            Defect(
                POSITIONAL_ONLY + "a call binds the collector's values to the "
                "script's parameters and match_arguments (collector.py) gets a "
                "tuple as its activation: AttributeError",
                "'tuple' object has no attribute 'active'",
            ),
        ),
        transforms=(
            Defect(
                POSITIONAL_ONLY + "no param component is recorded for a "
                "positional-only parameter",
                misplaced("param", 6, name="a"),
            ),
        ),
    ),
    Case(
        "positional_only_defaults",
        "a default after '/' with no default before it, in a def and a "
        "lambda that are never called",
        components=(("param", 7, "factor"), ("param", 11, "factor")),
    ),
    Case(
        "keyword_only",
        "keyword-only parameters, required and with defaults",
        components=(
            ("param", 5, "factor"),
            ("param", 5, "offset"),
            ("param", 9, "start"),
        ),
    ),
    Case(
        "try_finally",
        "try with except, else and finally, around a return and a break",
        components=(("try", 6), ("exception", 8), ("try", 20)),
    ),
    Case(
        "bare_except",
        "a bare except catching SystemExit and KeyboardInterrupt",
        components=(("try", 6), ("exception", 8), ("try", 10), ("exception", 12)),
        runs=(
            Defect(
                "#268: visit_exchandler "
                "(transformer_stmt.py) gives a bare except the type Exception, "
                "so SystemExit and KeyboardInterrupt escape a handler that "
                "catches them under Python: sys.exit(3) ends the script before "
                "its first print",
                "the execution exited via sys.exit(). Exit status: 3",
            ),
        ),
    ),
    Case(
        "raise_from",
        "raise from an exception and from None",
        components=(("raise", 8), ("raise", 20)),
    ),
    Case(
        "assignment_targets",
        "chained, tuple, swap, nested, attribute and subscript targets, and "
        "augmented assignment",
        components=(
            ("assign", 10),
            ("assign", 11),
            ("assign", 12),
            ("assign", 13),
            ("assign", 15),
            ("assign", 17),
            ("aug_assign", 18),
            ("aug_assign", 19),
            ("aug_assign", 20),
        ),
    ),
    Case(
        "assignment_targets-cg",
        "augmented assignments to an attribute and a subscript under coarse "
        "granularity (coarse records no aug_assign for a name target, so no "
        "component is listed)",
        script="assignment_targets",
        flags=("-cg",),
        runs=(
            Defect(
                COARSE_TARGET.format("the augmented assignment holder.value += 1"),
                "'Attribute' object has no attribute 'target_expr'",
            ),
        ),
        transforms=(
            Defect(
                COARSE_TARGET.format("the augmented assignment holder.value += 1"),
                "'Attribute' object has no attribute 'target_expr'",
            ),
        ),
    ),
    Case(
        "except_no_parens",
        "PEP 758 except with several types and no parentheses",
        min_py=(3, 14),
        components=(("try", 5), ("exception", 7)),
    ),
    Case(
        "deferred_annotations",
        "PEP 649 annotations that name a class defined later",
        min_py=(3, 14),
        components=(
            ("function_def", 6, "build"),
            ("ann_assign", 11),
            ("annotation", 11),
        ),
    ),
    Case(
        "lazy_import",
        "PEP 810 lazy import and lazy from ... import, after two plain imports",
        min_py=(3, 15),
        components=(("import", 11), ("import_from", 12)),
        runs=(
            Defect(
                LAZY_IMPORT_IN_TRY + ", so the script never runs", LAZY_IMPORT_SIGNATURE
            ),
        ),
        transforms=(
            Defect(
                LAZY_IMPORT_IN_TRY + ": nothing is evaluated", LAZY_IMPORT_SIGNATURE
            ),
        ),
    ),
    Case(
        "lazy_import_alone",
        "a PEP 810 lazy import that is the only import statement of the script",
        min_py=(3, 15),
        components=(("import", 10),),
        runs=(
            Defect(
                LAZY_IMPORT_IN_TRY + ", so the script never runs", LAZY_IMPORT_SIGNATURE
            ),
        ),
        transforms=(
            Defect(
                LAZY_IMPORT_IN_TRY + ": nothing is evaluated", LAZY_IMPORT_SIGNATURE
            ),
        ),
    ),
    Case(
        "comprehension_filters",
        "comprehensions with two and three if clauses",
        components=(
            ("listcomp", 5),
            ("setcomp", 6),
            ("dictcomp", 7),
            ("genexpcomp", 8),
        ),
        runs=(
            Defect(
                "#277: visit_generator "
                "(transformer_expr.py) joins two or more if clauses into "
                "ast.BoolOp() built without its fields, which Python 3.15 "
                "rejects: TypeError in the transformer, and the script never "
                "runs",
                "BoolOp.__init__ missing 1 required positional argument: 'op'",
                since=(3, 15),
            ),
        ),
        transforms=(
            Defect(
                "#277: visit_generator "
                "(transformer_expr.py) builds ast.BoolOp() without op, which "
                "Python 3.15 rejects: nothing is evaluated",
                "BoolOp.__init__ missing 1 required positional argument: 'op'",
                since=(3, 15),
            ),
        ),
    ),
    Case(
        "comprehension_unpacking",
        "PEP 798 unpacking in list and set comprehensions",
        min_py=(3, 15),
        components=(("listcomp", 6), ("setcomp", 7)),
        runs=(
            Defect(
                COMPREHENSION_UNPACKING + "visit_ListComp spreads the starred "
                "element into Collector.comprehension_item(): TypeError",
                "comprehension_item() takes 4 positional arguments but 5 were given",
            ),
        ),
    ),
    Case(
        "comprehension_unpacking_dict",
        "PEP 798 unpacking in a dict comprehension",
        min_py=(3, 15),
        components=(("dictcomp", 5),),
        runs=(
            Defect(
                COMPREHENSION_UNPACKING + "{**d for d in ds} has a None value, "
                "and _dict_itemize raises AttributeError in the transformer; "
                "the script never runs",
                "in _dict_itemize",
            ),
        ),
        transforms=(
            Defect(
                COMPREHENSION_UNPACKING + "_dict_itemize raises AttributeError "
                "on the None value of {**d for d in ds}: nothing is evaluated",
                "in _dict_itemize",
            ),
        ),
    ),
    Case(
        "comprehension_unpacking_generator",
        "PEP 798 unpacking in a generator expression",
        min_py=(3, 15),
        components=(("genexpcomp", 5),),
        runs=(
            Defect(
                COMPREHENSION_UNPACKING + "visit_GeneratorExp passes starred= "
                "to Collector._genitem(): TypeError",
                "_genitem() got an unexpected keyword argument 'starred'",
            ),
        ),
    ),
)


def params(kind):
    """``CASES`` as pytest params with their skip and known-defect marks

    ``kind`` is ``runs`` or ``transforms``.
    """
    result = []
    for case in CASES:
        marks = [
            pytest.mark.skipif(
                sys.version_info[:2] < case.min_py,
                reason="{} needs Python {}.{}".format(case.filename, *case.min_py),
            )
        ]
        marks.extend(defect_marks(getattr(case, kind)))
        result.append(pytest.param(case, id=case.name, marks=marks))
    return result


@pytest.mark.parametrize("case", params("runs"))
def test_syntax_runs_like_plain_python(project, case):
    """The script prints, exits and writes what it does under Python, and
    the run was traced"""
    skip_unless_same_python(project)
    plain, traced = run_both(project, "syntax", case.filename, flags=case.flags)
    try:
        assert_same_outcome(plain, traced, case.runs)
    except AssertionError as error:
        raise AssertionError("{}: {}".format(case.construct, error)) from None
    assert_traced(project)


def component_problems(project, trial_id, expected):
    """Each component of ``expected`` missing from its line of the script"""
    rows = project.query(
        "SELECT type, name, first_char_line FROM code_component "
        "WHERE trial_id = ? AND first_char_line > 0",
        trial_id,
    )
    problems = []
    for component in expected:
        kind, line = component[:2]
        name = component[2] if len(component) > 2 else None
        lines = sorted(
            {
                row["first_char_line"]
                for row in rows
                if row["type"] == kind and name in (None, row["name"])
            }
        )
        if line not in lines:
            problems.append(misplaced(kind, line, lines, name))
    return problems


@pytest.mark.parametrize("case", params("transforms"))
def test_syntax_transformer_applies(project, case):
    """The transformer rewrites the script and the rewritten script runs"""
    skip_unless_same_python(project)
    fresh_copy(project, "syntax")
    traced = run_traced(project, case.filename, flags=("-v",) + case.flags)
    problems = []
    if "Skipping transformer" in traced.stdout:
        problems.append(
            "a SyntaxError from pyposast or the transformer was swallowed "
            "and the script ran without its definition provenance"
        )
    trials = project.trials()
    if len(trials) != 1:
        problems.append("expected one trial, found {}".format(len(trials)))
    else:
        trial_id = trials[0]["id"]
        components = project.count("code_component", trial_id)
        if components <= 1:
            problems.append(
                "{} code component(s): nothing beyond the script itself "
                "was recorded".format(components)
            )
        evaluations = project.count("evaluation", trial_id)
        if evaluations == 0:
            problems.append(
                "no evaluation: the rewritten script never ran ({} code "
                "components were stored before the failure)".format(components)
            )
        problems.extend(component_problems(project, trial_id, case.components))
    if problems:
        text = "{}: {}\n\n{}".format(case.construct, "\n".join(problems), traced)
        expect_known_failure(case.transforms, text)
        raise AssertionError(text)


def test_syntax_cases_and_corpus_scripts():
    """Every script of corpus/syntax has a case, every case a script, the
    names are unique, and nothing but scripts lies in the corpus"""
    scripts = {path.name for path in SYNTAX.glob("*.py")}
    used = {case.filename for case in CASES}
    assert not scripts - used, "scripts without a case: {}".format(
        sorted(scripts - used)
    )
    assert not used - scripts, "cases without a script: {}".format(
        sorted(used - scripts)
    )
    names = [case.name for case in CASES]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, "duplicate case names: {}".format(duplicates)
    others = sorted(
        path.name
        for path in SYNTAX.iterdir()
        if path.suffix != ".py"
        and path.name != "__pycache__"
        and not path.name.startswith(".")
        and path.name not in IGNORED
    )
    assert not others, "not a script of the corpus: {}".format(others)
    collected = sorted(
        name
        for name in scripts
        if name.startswith("test_") or name.endswith("_test.py")
    )
    assert not collected, "pytest would collect {}".format(collected)
