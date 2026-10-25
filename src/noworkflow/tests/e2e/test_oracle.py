# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The oracle: a script traced by ``now run`` behaves as under plain Python

Collecting provenance rewrites the script's AST, routes every call through
the collector and replaces the ``open`` functions, and none of that may
change what the script does. Each script of ``corpus/oracle`` runs twice
(``oracle.run_both``): with the interpreter that ``now`` runs on, then with
``now run``; the return code, stdout, stderr and the SHA-1 of every file
left in the project must be equal (``oracle.differences``), with nothing
normalized. ``oracle.assert_traced`` then requires that the store holds one
trial with evaluations, so a script that ran without the transformer
cannot pass. The scripts are realistic programs, each focused on one theme
of Python semantics that rewriting or wrapping could change: file I/O
through every wrapped entry point, argument passing, evaluation order,
generators, classes, exceptions, scopes, local packages, the command line
and the standard streams, containers, numbers and text, and Python
functions called back by builtins. A second group of themes
(``PROCESS_THEMES``) starts external processes, one way each:
``subprocess.run`` with and without ``capture_output``,
``run(check=True)`` and ``check_call`` with a failing child,
``check_output``, ``Popen``, ``shell=True``, ``os.system``, ``os.popen``,
``os.posix_spawn`` and ``os.posix_spawnp`` (with file actions, reaped by
``os.waitpid``), and ``multiprocessing`` with the fork start method.
Each one starts a child, ``children/child.py`` (a plain script) run by
``sys.executable`` or, with fork, a function of the script, once writing
a file that the script reads back and once not; flushes stdout before
every child that inherits it, so that the order of the lines does not
depend on buffering; quotes the command lines it hands to a shell for
the platform's shell, with an argument and a file name that have a
space, and stops when a shell did not run the child; and decodes exit
statuses by ``os.name``. A forked child inherits whatever the collector
installed in the process (audit hooks, once #202 adds them), so the
waits on a child that runs code of the script after a fork have a
timeout, after which the script kills the child and fails: the Queue's
get and the joins of ``multiprocessing`` (``Pool.join``, which takes
none, runs in a helper thread that the script waits for), every
``os.waitpid`` of a script (``os.fork()``, ``os.posix_spawn``), polled,
and the run of the ``preexec_fn`` child once it started. Two waits have
no bound: inside ``Popen``, the read of the pipe through which a
``preexec_fn`` child reports a failure before its exec, and, after the
Pool's helper thread timed out, the join of the workers that leaving the
Pool's ``with`` block terminates; there only the timeout with which the
harness runs the whole script (``NowProject.run``,
``oracle.run_plain``) remains. Elsewhere a child that hangs, or dies
before it answers, fails the case within the script's timeout instead
of hanging the run. The other children, which ``subprocess``,
``os.system`` and ``os.popen`` start through exec, run only
``children/child.py``, which never blocks (its stdin is a pipe, a file
or the null device the harness gives), and are waited for without one
(``os.system`` and ``os.popen`` take none). The
scripts that need what Windows lacks (``os.fork()``, ``preexec_fn``,
``os.posix_spawn``) are skipped there with the reason (``case`` takes
``marks``). Each theme also runs under coarse granularity (``-cg``, ids
``<theme>-cg``), under the depth limits that the noWorkflow 2 paper's
evaluation measures (``-d 2``, ``-d 3``, ``-cg -d 2``, ``-cg -d 3``, ids
``<theme>-d2`` and so on, #467), and ``modules.py`` also with ``-c
package`` (``modules-package``), so that the local package is rewritten
too; that case also requires the package's classes among the trial's
code components, since the main script alone records evaluations. A
depth limit only reduces what is collected (#243), so a case under one
carries no defect of its own; a coarse-grained limit carries the theme's
``-cg`` defects.

Both runs use the harness's synthetic environment (UTF-8 mode, a fixed
hash seed, terminal width and no colors), so the oracle compares what
noWorkflow changes under UTF-8 mode only: an ``open()`` without
``encoding=`` that behaves differently under a legacy locale (Windows
before Python 3.15) is out of its reach.

Layout of ``corpus/oracle``: every ``*.py`` at its top level is a script
that ``CASES`` runs; what the scripts import, read or start is either a
subdirectory (the ``toolkit`` package, the ``children`` the process themes
start) or a file that is not ``*.py`` (``inventory.txt``), and is declared
in ``SUPPORT``.
``test_oracle_lists_every_script`` enforces both, so a script added
without a case, or a file a script left in the corpus, fails it (it skips
hidden files and the clutter of file managers, ``Thumbs.db`` and
``desktop.ini``).

Every script must run identically on each supported Python under plain
Python, print nothing that changes between two runs (no ``id()``, times,
addresses or default reprs), write only relative paths inside the project
and never list the project directory itself, which the traced run fills
with its store.

Where noWorkflow changes the outcome, the construct is split out of its
theme script into a script of its own, so that the rest of the theme keeps
being compared, and that script is the evidence of the defect; a theme
docstring names the scripts its constructs were moved to, and the defects
its ``-cg`` run shows. The case of a defect script carries
``oracle.Defect`` entries: the reason starts with the issue (``#NNN``,
which the script's docstring repeats) and
states the mechanism, citing product code by file and function, and the
signature is a piece of text that the failing run prints today. The mark
is ``xfail(strict=True)``, and a run that differs without the signature of
a defect that applies fails outright, so a second defect or a new
regression cannot hide behind the mark. Each defect script holds one
mechanism, so that a fix flips exactly the cases that cite it, and a
script that two code sites break runs each trigger in its own ``try``, so
that both show. Where one mechanism inherently hides another, the reason
names both and says that the case flips only when both are fixed, and the
script's docstring says "(#<first>, with #<second> behind it)"; a theme under
``-cg`` with two crashes lists both defects. Unlike ``test_run.py``
there is no characterization twin that pins today's behavior: the reason
records the mechanism and the signature pins today's failure.

The map of marks is measured, never guessed: run this module with
``--runxfail`` on every Python of the matrix (it was measured on macOS
with Python 3.11 to 3.15 and on Linux with 3.15, the reference
container; the other Linux versions are the CI legs) and give each
``Defect`` ``since``/``before`` covering exactly the
versions where its case fails, and ``systems`` when a mark differs by
platform. A fix that turns a case green fails it with XPASS(strict) until
its ``Defect`` leaves ``CASES`` in the same change. The marks
(``since``/``before``) follow the Python that runs pytest, so every corpus
test first calls ``oracle.skip_unless_same_python``: under a
``NOW_E2E_CMD`` that traces with another version they would be wrong.

The control, ``test_oracle_detects_difference``, runs end to end a script
that differs only when it is traced, on stdout, on stderr and in a file it
writes, and requires the comparator to report exactly those three
differences. A comparator that always answered "equal", or a run that lost
a stream or the files, would keep every theme case green whatever the
scripts did; the control turns red then (so do the strict marks of the
defect cases, but only while defects remain).
``test_differences_between_outcomes`` checks the same comparator on
outcomes that differ in a single field, the return code included.

An idea not done here: a property-based generator of small programs
(Hypothesis), drawing statements and expressions from a grammar and
feeding each program to the same comparator, would search the space of
constructs instead of sampling it by hand; the corpus above is the
regression suite such a search would add to.
"""

import os

import pytest

from .harness import CORPUS
from .oracle import (
    STDLIB_ON_ANOTHER_DRIVE,
    Defect,
    Outcome,
    assert_same_outcome,
    assert_traced,
    defect_marks,
    differences,
    run_both,
    run_plain,
    run_traced,
    skip_unless_same_python,
)

ORACLE = CORPUS / "oracle"
# What the scripts read, import or start, next to them: the data file of
# file_io.py, the package of modules.py, open_wrapper_warning.py and
# open_files_kept_alive.py, the child of the process themes, and the
# distribution that duplicate_distributions.py counts.
SUPPORT = ("inventory.txt", "toolkit", "children", "oracle_marker-1.0.dist-info")
# Clutter that the file manager of a system leaves, not a script.
IGNORED = ("Thumbs.db", "desktop.ini")
# What the scripts that start processes use and Windows lacks: os.fork(),
# called directly or by the fork start method of multiprocessing, the
# preexec_fn of subprocess, and os.posix_spawn.
NEEDS_FORK = pytest.mark.skipif(
    os.name == "nt",
    reason="os.fork() and the fork start method do not exist on Windows",
)
NEEDS_PREEXEC_FN = pytest.mark.skipif(
    os.name == "nt", reason="subprocess does not support preexec_fn on Windows"
)
NEEDS_POSIX_SPAWN = pytest.mark.skipif(
    os.name == "nt", reason="os.posix_spawn and os.posix_spawnp do not exist on Windows"
)

# The arguments command_line.py receives: positionals, options, a repeated
# flag and a value with a space.
COMMAND_LINE_ARGS = (
    "data.csv",
    "--count",
    "3",
    "-vv",
    "--tag",
    "a",
    "--tag",
    "two words",
)


# Known defects. Each reason starts with its issue and states the mechanism;
# each signature is printed by the failing run today, on every version its
# mark covers.

CALLER_FRAME = Defect(
    "#271: every call the script makes goes through "
    "Collector._call (collector.py), so the builtins that read the frame "
    "of their caller see _call's frame: eval and exec without namespaces "
    "raise NameError, globals() lacks the script's names, locals() and "
    "vars() return _call's locals, dir() lists none of the script's "
    "names, sys._getframe() is _call, and the stacklevel of warnings.warn "
    "points one frame short, into the function that warned",
    signature="frame: _call",
)
SUPER_CALL = Defect(
    "#162: zero-argument super() is called from Collector._call "
    "(collector.py), a frame without the __class__ cell, so it raises "
    "RuntimeError('super(): __class__ cell not found') in any class, with "
    "or without bases. #274 is a second layer behind "
    "it: Collector._class_def (collector.py) binds the name to a second "
    "class, while the __class__ cell holds the first, and a zero-argument "
    "super() run in the right frame would still raise TypeError, so the "
    "case flips only when both are fixed",
    signature="super(): __class__ cell not found",
)
DEF_RUNS_TWICE = Defect(
    "#282: process_body (transformer_stmt.py) emits an "
    "untransformed copy of each def as __now_original_<name>, so its "
    "decorators and default expressions run twice, the first time on a "
    "function named __now_original_<name>",
    signature="wrap __now_original_greet",
)
ABSTRACT_METHOD_COPY = Defect(
    "#282: process_body (transformer_stmt.py) emits an "
    "untransformed copy of each def as __now_original_<name>; in a class "
    "body the copy stays in the class as _<Class>__now_original_<name>, "
    "with the decorators applied, so the copy of an @abstractmethod is "
    "abstract, listed in __abstractmethods__, and no subclass overrides it "
    "under that name: ABCMeta refuses to instantiate any subclass "
    "(TypeError)",
    signature="_Shape__now_original_area",
)
DOCSTRINGS_LOST = Defect(
    "#283: process_script (transformer_stmt.py) starts the "
    "rewritten module with noWorkflow's assignments, so the module's "
    "__doc__ is never set and resolves to the builtins module's docstring",
    signature="Built-in functions, types, exceptions, and other objects.",
)
FUNCTION_DOCSTRINGS_LOST = Defect(
    "#283: visit_FunctionDef (transformer_stmt.py) puts "
    "the match_arguments call first in every function body, so the "
    "docstring is no longer the body's first statement and __doc__ is None "
    "for functions and methods alike; a class keeps its docstring",
    signature="list - (no help)",
)
FUNCTION_SIGNATURE = Defect(
    "#285: visit_FunctionDef (transformer_stmt.py) "
    "prepends six __now_* parameters to every function, and "
    "Collector._function_def (collector.py) wraps the rewritten function "
    "with functools.wraps, whose __wrapped__ points to it: "
    "inspect.signature follows __wrapped__ and shows the six parameters, "
    "so Signature.bind of the script's arguments fails, and a call with "
    "too many positional arguments is reported with six more expected and "
    "given",
    signature="takes 8 positional arguments but 9 were given",
)
FUNCTION_DEFAULTS = Defect(
    "#285: Collector._function_def (collector.py) "
    "replaces each function with new_function_def(*args, **kwargs), and "
    "functools.wraps copies the function's name, docstring and "
    "__wrapped__ to it but not __defaults__ or __kwdefaults__, so the "
    "script reads the wrapper's: None",
    signature="defaults: None None",
)
CALL_ERROR_NAMES_COLLECTOR = Defect(
    "#270: visit_Call (transformer_expr.py) "
    "turns f(...) into __noworkflow__.call(...)(...), and Collector.call "
    "(collector.py) returns the bound method Collector._call as the "
    "callable, so an error that Python raises at the call site, before "
    "the callee runs, names Collector._call instead of the function: a "
    "keyword given twice through two ** unpackings. Not the same issue as "
    "#271: a callable that carried the callee's __module__ "
    "and __qualname__ would fix this message and keep _call's frame, and "
    "handing the frame-reading builtins the script's frame would fix those "
    "and keep this message",
    signature="Collector._call() got multiple values for keyword argument",
)
KEYWORD_NAMED_SELF = Defect(
    "#289: Collector.call (collector.py) returns the "
    "bound method Collector._call(self, *args, **kwargs) as the callable "
    "of every call site, and its self is not positional-only, so a keyword "
    "argument named self collides with it: TypeError before the callee "
    "runs, for builtins (dict, str.format) and the script's own functions "
    "alike. The white-box path of new_function_def (Collector._function_def) "
    "calls _call the same way",
    signature="Collector._call() got multiple values for argument 'self'",
)
RENAMED_FUNCTION_RECURSION = Defect(
    "#306: new_function_def "
    "(Collector._function_def, collector.py) tells a callback from a "
    "direct call by comparing the activation's name, which Collector.call "
    "(collector.py) takes from the called object's __name__, with the "
    "__name__ of the rewritten function; when a traced function's "
    "__name__ changes after the def (functools.wraps does it to every "
    "wrapper), the two never match, and the call takes the "
    "white-box-after-black-box path, which calls the same renamed function "
    "through Collector.call and re-enters it until RecursionError, "
    "before the wrapper's body ever runs",
    signature="calls failed: RecursionError\narea area []",
)
CLASS_CREATED_TWICE = Defect(
    "#274: Collector._class_def (collector.py) builds "
    "a second class from the namespace of the one the class statement "
    "created, with metaclass(name, bases, namespace), so the metaclass, "
    "__init_subclass__ and __set_name__ run twice per class statement, "
    "and the __class__ cell of the methods holds the discarded first "
    "class: __class__ is not the class bound to the name, and "
    "super(__class__, self) raises TypeError",
    signature="[('Exporter', 'output'), ('Exporter', 'output')",
)
DECORATED_OBJECT_WITHOUT_DICT = Defect(
    "#281: Collector.collect_function_def "
    "(collector.py) sets original_def on whatever the decorators returned, "
    "and a result that rejects attribute assignment (a property here, any "
    "object without a __dict__ alike) raises AttributeError",
    signature="'property' object has no attribute 'original_def'",
)
REPR_SERIALIZER = Defect(
    "#307: the default serializer, repr_serializer "
    "(persistence/serializers.py), records values with their class's own "
    "__repr__, including self when match_arguments (collector.py) binds "
    "it at the start of __init__, before the attributes exist",
    signature="'Money' object has no attribute 'currency'",
)
CLASS_REPR_UNDER_A_METACLASS = Defect(
    "#340: the default serializer, "
    "repr_serializer (persistence/serializers.py), skips the script's "
    "__repr__ only for a class whose metaclass is type; for an ABC, or "
    "any other metaclass, object.__getattribute__ finds the __repr__ that "
    "the class defines for its instances in its own namespace, and "
    "repr_serializer calls that function's original_def with the class as "
    "self when the collector records the class statement: AttributeError "
    "before any instance exists. Not #307, whose trigger is self before "
    "__init__ sets its attributes; a fix of #307 that falls back to repr() "
    "only when the script's __repr__ raises flips this case too, while a "
    "class on which that __repr__ succeeds is still recorded with it (the "
    "_desired twin in persistence/test_serializers.py)",
    signature="type object 'Shape' has no attribute 'side'",
)
COLLECTOR_COMPARES_VALUES = Defect(
    "#276: the collector compares the script's "
    "values with its own sentinels, key == -1 in Collector._item "
    "(collector.py) for an element of a set display and value != "
    "'<<<noWorkflow>>>' in Collector.ifexp for the value of a conditional "
    "expression, calling the script's __eq__ with an int or a str",
    signature="object has no attribute 'parts'",
)
POSITIONAL_ONLY_PARAMETERS = Defect(
    "#297: visit_FunctionDef "
    "(transformer_stmt.py) and visit_Lambda (transformer_expr.py) prepend "
    "their six __now_* parameters to args.args, after the positional-only "
    "ones, and process_parameters (transformer_stmt.py), which both call, "
    "never reads arguments.posonlyargs, so a call binds the collector's "
    "arguments to the script's positional-only parameters, and "
    "match_arguments (collector.py) reads .active from one of the script's "
    "values: AttributeError",
    signature="object has no attribute 'active'",
)
LAMBDA_IN_COLLECTION = Defect(
    "#290: the decorator that Collector._function_def "
    "(collector.py) returns pushes a DependencyAware on the enclosing "
    "activation, after _function_def popped the one that function_def "
    "pushed for the defaults, and only collect_function_def pops it, "
    "which a lambda never reaches; a lambda evaluated while an element of "
    "a list, tuple, set or dict display, or of a list or dict "
    "comprehension, is collected leaves that entry where Collector._item "
    "or after_dict_item expect the collection's, and they raise "
    "AttributeError",
    signature="'DependencyAware' object has no attribute 'items'",
)
CLASS_BODY_COMPREHENSION = Defect(
    "#272: the rewritten comprehension reads "
    "__now_activation__ inside its own scope, which does not see the "
    "class body's binding, so loop() pushes on the class activation and "
    "Collector.pop_assign (collector.py) pops the module's: IndexError",
    signature="in pop_assign",
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
    signature="activation.assignments[-1].dependency",
)
CALLBACK_ARGUMENTS = Defect(
    "#266: a Python callback called by a C builtin (re.sub, iter with a "
    "sentinel, print and str.format calling __str__, print calling "
    "__repr__ among other arguments, zip calling __iter__, a dict display "
    "calling keys of a mapping inside a function of two parameters) takes "
    "the white-box-after-black-box path of new_function_def "
    "(Collector._function_def, collector.py), which hands it the "
    "enclosing call's argument dependencies; when they outnumber its "
    "parameters, match_arguments (collector.py) raises IndexError",
    signature="failed: IndexError('list index out of range')",
)
YIELD_FROM_CALLBACK = Defect(
    "#266: the operand of yield from is not rewritten (visit_YieldFrom, "
    "transformer_expr.py, #161), so a parameterless generator function "
    "called there reaches new_function_def (Collector._function_def, "
    "collector.py) while list(), next() or sum() is the last activation, "
    "and gets that call's argument dependencies: IndexError in "
    "match_arguments (collector.py)",
    signature="param = parameter_order[last_unfilled]",
)
ASYNC_CALLBACK = Defect(
    "#266: through #157, a coroutine's body runs after the activation of "
    "its call closed, under the activation of asyncio.run, so "
    "new_function_def (Collector._function_def, collector.py) takes each "
    "traced function it calls for a callback of asyncio.run and hands it "
    "that call's argument dependencies: IndexError in match_arguments "
    "(collector.py)",
    signature="param = parameter_order[last_unfilled]",
)
VALUES_KEPT_ALIVE = Defect(
    "#309: Collector.activations (collector.py) keeps "
    "every closed ActivationLW until Collector.store, and with it the "
    "Dependency and Assign objects (prov_execution/structures.py) that "
    "hold the values recorded as dependencies or assignments, call "
    "arguments included: an object created inside a function or passed to "
    "a call outlives the script's last reference to it, so its __del__ "
    "never runs, and a weakref.finalize callback runs only at exit, "
    "through its atexit hook",
    signature="start\nTEMPORARY\nafter rebind\n",
)
LAST_ASSIGN_KEPT_ALIVE = Defect(
    "#291: visit_assign (transformer_stmt.py) "
    "rewrites each assignment to bind __now__assign__, in the script's "
    "namespace, to the Assign that Collector.pop_assign (collector.py) "
    "returns, and that Assign (prov_execution/structures.py) holds the "
    "assigned value until the next assignment rebinds the name: an object "
    "deleted right after its assignment stays alive, and its __del__ does "
    "not run at del",
    signature="creating a handle\nafter del\n",
)
ATTRIBUTE_CONTAINER_KEPT_ALIVE = Defect(
    "#267: Collector.__setitem__ and "
    "Collector.__getitem__ (collector.py) keep the object of each "
    "attribute access in Collector.current_attr, for Collector._func to "
    "bind to a method call that follows, and nothing clears it: the "
    "object stays alive until the next attribute or subscript access "
    "replaces it, so del does not release an object whose attribute the "
    "script set last",
    signature="creating a record\nafter del, saved: False\n",
)
GENERATOR_ACTIVATION_CYCLE = Defect(
    "#286: new_function_def "
    "(Collector._function_def, collector.py) keeps the generator that a "
    "traced generator function returns in activation.generator, a "
    "Generator (prov_execution/structures.py) whose value and dependency "
    "(set by Collector._call) hold it, while the generator's frame holds "
    "that activation as __now_activation__: the cycle keeps a generator "
    "the script dropped alive until the cyclic garbage collector runs "
    "(and as long as Collector.activations keeps the activation, "
    "#309), so its finally does not run when break "
    "leaves it. Holding the generator weakly there turns the case green "
    "on its own",
    signature="read first\nafter loop\n",
)
OPEN_FILES_KEPT_ALIVE = Defect(
    "#295: the open wrapper (Collector.new_open, "
    "collector.py) keeps every file opened for writing in "
    "Collector.open_write_files until it is closed, and the final sweep "
    "of Collector.store flushes it but never closes it, so a file object "
    "the script drops without close() is neither released nor flushed, "
    "and reading the file back at once sees it empty (related to #250)",
    signature="read back: ''",
)
RECURSION_DEPTH = Defect(
    "#305: each call of a traced function adds the frames "
    "of Collector._call and new_function_def (collector.py), so the "
    "default recursion limit of 1000 stops a recursion 400 levels deep "
    "with RecursionError",
    signature="400 levels: RecursionError",
)
BUILTINS_IS_A_DICT = Defect(
    "#269: Metascript.clear_namespace "
    "(collection/metadata.py) sets the script's __builtins__ to the "
    "__builtins__ of metadata.py, which in an imported module is the dict "
    "of the builtins module, not the module that `python script.py` "
    "gives: attribute access on it fails",
    signature="'dict' object has no attribute 'len'",
)
GENEXP_LAZY_FIRST_ITERABLE = Defect(
    "#288: visit_generator "
    "(transformer_expr.py) wraps the first iterable of a generator "
    "expression in __noworkflow__.loop, and Collector._loop "
    "(collector.py) returns _loop_generator, a generator function, so "
    "enumerate_generator's enumerate(value) runs only at the first next(): "
    "the __iter__ of the first iterable, and whatever it reads or raises, "
    "moves from the line that creates the generator expression to its "
    "first use",
    signature="pending: ['HELLO', 'LATE']",
)
GENEXP_FIRST_ITERABLE_ERROR = Defect(
    "#287: the finally of Collector.genexp "
    "(collector.py) assumes the generator expression was created: when "
    "evaluating its first iterable raises, collect_exception has already "
    "removed the expression's DependencyAware and the enclosing "
    "assignment's, and the finally pops one more and reads value, which "
    "was never bound, so the UnboundLocalError replaces the script's "
    "exception, which its except clause no longer catches; with value "
    "bound, the IndexError of activation.dependencies[-1] would replace it "
    "instead",
    signature="cannot access local variable 'value'",
)
CLASS_BODY_GENEXP_SCOPE = Defect(
    "#273: Python evaluates the first iterable of a "
    "generator expression in the enclosing scope, and the rewritten "
    "expression (visit_generator, transformer_expr.py) evaluates it inside "
    "Collector.genexp's call, where a class body's names are not visible: "
    "NameError. #287 then replaces that "
    "NameError with its UnboundLocalError; the case flips with this fix "
    "alone",
    signature="context: NameError: name 'size' is not defined",
)
MODULE_ON_ANOTHER_DRIVE = Defect(
    "#294: noWorkflow's module finder "
    "(prov_deployment/py3module.py, the loaders' exec_module) records each "
    "module the script imports with create_code_block (definition.py), "
    "which stores the module's path relative to the script's directory "
    "with os.path.relpath; on Windows, for a module on another drive than "
    "the project (the standard library of a Python installed on another "
    "drive), relpath raises ValueError and the import fails in the script, "
    "here the import of colorsys and of the latin-1 codec",
    signature="path is on mount",
    systems=("win32",),
    condition=STDLIB_ON_ANOTHER_DRIVE,
)
TEMPORARY_FILE_READ_AT_STORE = Defect(
    "#407: the final sweep of Collector.store (collector.py) reopens by "
    "name every write-mode access whose content_hash_after is unset and "
    "whose name os.path.isfile accepts, with no error handling; on "
    "Windows a file of tempfile is delete-on-close (O_TEMPORARY) and "
    "still exists under its name while open, so the second open is "
    "denied, the store fails after the script ran and `now run` exits "
    "with 1 (measured on every Windows leg of pre-release.yml and on "
    "main without #202; the script runs and stores on Linux and macOS)",
    signature="PermissionError: [Errno 13] Permission denied",
    systems=("win32",),
)
YIELD_IN_CALL_ARGUMENT = Defect(
    "#311: Collector.call (collector.py) pushes a "
    "FutureActivation on "
    "Collector.future_activation, one stack for the whole run, and "
    "Collector._call pops whichever entry is on top, not the one its call "
    "pushed. A generator paused by a yield inside a call's arguments "
    "leaves that call's entry on the stack, and when the script advances "
    "it while another call's arguments are being evaluated (advanced on a "
    "line of its own, it runs fine), that call pops the generator's entry "
    "and runs the generator's pending callee (list.append) with the "
    "arguments of the call that popped it (print's): "
    "print('first', next(accumulator)) runs list.append with two "
    "arguments. The yield's operand is a plain name",
    signature="list.append() takes exactly one argument (2 given)",
)
EXCEPTION_IN_CALL_ARGUMENTS = Defect(
    "#311: the same stack of pending calls "
    "(Collector.call, collector.py): an exception raised "
    "while a call's arguments are evaluated leaves that call's "
    "FutureActivation on Collector.future_activation, because "
    "Collector._call never runs to pop it; when the exception is caught "
    "inside a function that runs in another call's arguments, that call "
    "pops the stale entry and runs results.append with print's arguments",
    signature="list.append() takes exactly one argument (2 given)",
)
CONDITIONAL_EXPRESSION_EXCEPTION = Defect(
    "#280: the finally of Collector.ifexp "
    "(collector.py) assumes the conditional expression finished its "
    "bookkeeping: when the condition raises, remove_condition pops a "
    "condition that _condition never pushed, and when a branch raises, "
    "collect_exception, called with the expression's own handler, has "
    "already popped the expression's entries and the enclosing "
    "statement's, and the finally pops one more (at module level the "
    "activation's base entry), until none is left; either way "
    "IndexError('pop from empty list') replaces the script's exception",
    signature="failed: IndexError('pop from empty list')",
)
CONDITION_TEST_EXCEPTION = Defect(
    "#279: visit_If and visit_While "
    "(transformer_stmt.py) wrap the statement in a try whose finally calls "
    "Collector.remove_condition (collector.py), which pops "
    "activation.conditions on the assumption that Collector._condition "
    "pushed the statement's condition; when the test raises, _condition "
    "never runs (and the test of a while has already popped the condition "
    "of the previous iteration, or the one Collector.prepare_while pushed, "
    "before it runs), so the finally pops a condition that was never "
    "pushed, an enclosing statement's when one is left (whose own finally "
    "then finds none), and popping the empty list raises "
    "IndexError('pop from empty list'), which replaces the script's "
    "exception, or its result, beyond the reach of its except clause. "
    "visit_If evaluates the test in a conditional expression it builds "
    "itself, which never reaches Collector.ifexp, so a fix confined to "
    "Collector.ifexp (#280) does not "
    "repair it. The signature names remove_condition, which "
    "conditional_expression_errors.py does not print",
    signature="IndexError('pop from empty list') in remove_condition",
)
FILE_PROXY_TYPE = Defect(
    "#284: the open wrapper (Collector.new_open, "
    "collector.py) returns every file opened by path with a mode that "
    "writes (w, a, x or +, is_write_mode) inside a FileAccessProxy "
    "subclass (wrap_file_access), so type() of the file object is "
    "TextFileProxy, BufferedFileProxy or RawFileProxy instead of "
    "TextIOWrapper, BufferedWriter or FileIO; isinstance against the io "
    "base classes still holds, against those concrete classes it does "
    "not, and a file opened for reading is not wrapped",
    signature="TextFileProxy",
)
OPEN_WRAPPER_FRAME = Defect(
    "#296: the open wrapper (Collector.new_open, "
    "collector.py) runs between the code that calls open and the real "
    "open, so a warning that open raises for its caller names collector.py "
    "instead of the caller's file: here the RuntimeWarning for line "
    "buffering in binary mode (the DeprecationWarning of codecs.open from "
    "Python 3.14 goes the same way, not exercised here). Under a traced "
    "caller the frame of Collector._call (#271) stands "
    "between them as well, so the script calls open from a module that "
    "the default context does not rewrite",
    signature="('collector.py', 'RuntimeWarning')",
)
COARSE_DECORATOR = Defect(
    "#236: under -cg, RewriteDependencies.visit (transformer_expr.py) "
    "captures a decorator that is a name or an attribute without creating "
    "a component, so process_decorator reaches the fallback of "
    "RewriteAST._ast_num_from_component_id (transformer_stmt.py), whose "
    "create_code_component reads node.name: AttributeError in the "
    "transformer, and the script never runs",
    signature="in _ast_num_from_component_id\n    id_ = self.create_code_component(",
)
COARSE_AUGASSIGN_TARGET = Defect(
    "#275: under -cg, visit_augassign and "
    "visit_annassign (transformer_stmt.py) take the coarse path only for "
    "a name target; an augmented assignment, or an annotated assignment "
    "with a value, to an attribute or subscript target goes through "
    "capture, which under coarse granularity (RewriteDependencies.visit, "
    "transformer_expr.py) leaves it without target_expr: AttributeError "
    "in the transformer, and the script never runs",
    signature="assign\n    new_target.target_expr,",
)
FORK_EPILOGUE = Defect(
    "#375: a child that os.fork() makes in the traced script, "
    "unless it leaves through os._exit, leaves the exec() of the script "
    "in Execution.collect_provenance (prov_execution/execution.py) as the "
    "parent does and runs the rest of run (cmd/cmd_run.py) as `now`: "
    "collect_provenance catches its SystemExit; the store_provenance of "
    "deployment, definition and execution store the trial again from the "
    "child (Execution.store_provenance stores it through Collector.store "
    "first, and only then prints '[now] the execution exited via "
    "sys.exit(). Exit status: 3' on stderr; a child that exits with 0 "
    "stores just the same, silently); Tag.create_automatic_tag adds one "
    "more automatic tag per child; and the child exits as `now`, with the "
    "status it passed to sys.exit, so the parent's waitpid reads the same "
    "codes as under plain Python. The parent stores last, and the INSERT OR "
    "REPLACE of Model.store (persistence/models/base.py) replaces only the "
    "rows whose keys it reaches: the rows of the child's branch (its exit "
    "activation) stay in the parent's trial, which mixes two processes. The "
    "oracle sees only the [now] line on stderr: the case flips once the "
    "child no longer prints it, whatever becomes of the extra tags and "
    "rows, which the oracle does not compare",
    signature="[now] the execution exited via sys.exit(). Exit status: 3",
)
IF_BODY_CONTEXT = Defect(
    "#376: visit_If (transformer_stmt.py), which has no "
    "branch for coarse granularity, rewrites an if statement into a try "
    "that raises a ConditionException (the classes of "
    "ConditionExceptions, prov_execution/structures.py) and runs each "
    "branch, elif and else included, in the except clause that catches it, "
    "so the branch runs while noWorkflow's exception is being handled: an "
    "exception raised there gets it as __context__ (instead of None, or of "
    "the exception the script is handling, which becomes the "
    "ConditionException's own __context__, one link further), "
    "sys.exc_info() returns it, a bare raise re-raises it instead of the "
    "script's exception, which an except clause for that exception no "
    "longer catches, and a bare raise where the script handles no "
    "exception re-raises it instead of raising RuntimeError('No active "
    "exception to reraise')",
    signature="handling: ConditionException",
)
FORK_WARNING_FRAME = Defect(
    "#271: the script calls os.fork() through Collector._call "
    "(collector.py), like every other call, and the DeprecationWarning "
    "that os.fork() raises from Python 3.12 in a process with more than "
    "one thread is attributed to the nearest Python frame, the line of "
    "Collector._call that calls future.func: collector.py, where the "
    "default filters, which show a DeprecationWarning only for __main__, "
    "drop it (the mechanism of caller_frame.py; -cg loses it the same "
    "way, although no case runs this script with -cg)",
    signature="shown: []",
    since=(3, 12),
)
PREEXEC_FN_CALLBACK = Defect(
    "#266: subprocess.Popen calls preexec_fn in the child from "
    "_posixsubprocess.fork_exec, a C function, so a function of the script "
    "there takes the white-box-after-black-box path of new_function_def "
    "(Collector._function_def, collector.py) and gets the argument "
    "dependencies of the script's call to subprocess.run: IndexError in "
    "match_arguments (collector.py) in the child, which fork_exec never "
    "prints and Popen reports in the parent only as "
    "SubprocessError('Exception occurred in preexec_fn.'), and the program "
    "never runs. A preexec_fn that takes *args and **kwargs, or one "
    "parameter with a default, absorbs those arguments and works",
    signature="Exception occurred in preexec_fn",
)
DISTRIBUTION_LOOKUP = Defect(
    "#417: the loaders of prov_deployment/py3module.py call "
    "Deployment.get_version (prov_deployment/deployment.py) for every "
    "module the script imports for the first time, and get_version looks "
    "the module's distribution up through importlib.metadata.distribution, "
    "which asks every finder in sys.meta_path that has "
    "find_distributions, the script's own among them: the script's finder "
    "answers a question per module that plain Python never asks, and its "
    "code runs traced",
    signature="asked for: ['sched'",
)
DISTRIBUTIONS_LISTED_TWICE = Defect(
    "#420: Execution.collect_provenance (prov_execution/execution.py) puts "
    "the Finder that finder(metascript) builds in "
    "prov_deployment/py3module.py first in sys.meta_path around the exec of "
    "the script; Finder subclasses PathFinder for its find_spec and so "
    "inherits find_distributions, and importlib.metadata.Distribution."
    "discover asks every finder of sys.meta_path that has it: Finder and "
    "the standard PathFinder each walk sys.path, and every distribution "
    "comes back twice",
    signature="oracle-marker listed: 2",
)


def case(script, *args, flags=(), defects=(), suffix="", marks=()):
    """One oracle script run with ``args`` and the ``now run`` flags

    The id is the script's stem plus ``suffix``; ``defects`` are its known
    defects, whose marks apply where they show; ``marks`` are other marks
    of the case, such as the skip of a script that a system cannot run.
    """
    return pytest.param(
        script,
        args,
        flags,
        defects,
        id=script[:-3] + suffix,
        marks=list(marks) + defect_marks(defects),
    )


# Themes: each compares equal on every supported version, and under -cg
# except where a Defect says otherwise.
THEMES = (
    ("file_io.py", ()),
    ("arguments.py", ()),
    ("evaluation_order.py", ()),
    ("generators.py", ()),
    ("classes.py", ()),
    ("exceptions.py", ()),
    ("scopes.py", ()),
    ("modules.py", ()),
    ("command_line.py", COMMAND_LINE_ARGS),
    ("data_structures.py", ()),
    ("numbers_text.py", ()),
    ("callback_functions.py", ()),
)
# Themes that start external processes: children/child.py run by
# sys.executable, or a function of the script in a forked process.
PROCESS_THEMES = (
    ("subprocess_run.py", ()),
    ("subprocess_check.py", ()),
    ("subprocess_check_output.py", ()),
    ("subprocess_popen.py", ()),
    ("subprocess_shell.py", ()),
    ("os_system.py", ()),
    ("os_popen.py", ()),
    ("os_posix_spawn.py", ()),
    ("multiprocessing_fork.py", ()),
)
ALL_THEMES = THEMES + PROCESS_THEMES
# The marks of a theme, under every set of flags.
THEME_MARKS = {
    "os_posix_spawn.py": (NEEDS_POSIX_SPAWN,),
    "multiprocessing_fork.py": (NEEDS_FORK,),
}
# The themes that -cg does not run like plain Python. classes.py holds both
# a decorator that is a name and an augmented assignment to an attribute:
# the transformer stops at the first, so the run shows #236's signature
# only, and the case flips only when both defects are fixed.
COARSE_DEFECTS = {
    "evaluation_order.py": (COARSE_AUGASSIGN_TARGET,),
    "generators.py": (COARSE_AUGASSIGN_TARGET,),
    "classes.py": (COARSE_DECORATOR, COARSE_AUGASSIGN_TARGET),
    "exceptions.py": (COARSE_DECORATOR,),
    "scopes.py": (COARSE_AUGASSIGN_TARGET,),
    "callback_functions.py": (COARSE_AUGASSIGN_TARGET,),
}
# The classes that toolkit/shapes.py defines: class_def components of the
# trial only when -c package rewrites the package.
PACKAGE_CLASSES = ("Circle", "Square")

# The depth limits of the paper's evaluation (#467), fine- and
# coarse-grained, with the suffix of their ids. A depth limit only reduces
# what is collected (#243), so a case under one carries no defect of its
# own; under -cg -d 2 and -cg -d 3 the themes of COARSE_DEFECTS stop in
# the transformer as under -cg (depth_defects).
DEPTH_LIMITS = (
    (("-d", "2"), "-d2"),
    (("-d", "3"), "-d3"),
    (("-cg", "-d", "2"), "-cg-d2"),
    (("-cg", "-d", "3"), "-cg-d3"),
)


def depth_defects(script, flags):
    """The known defects of a theme under a depth limit: those of -cg when
    the limit is coarse-grained, none otherwise"""
    return COARSE_DEFECTS.get(script, ()) if "-cg" in flags else ()


CASES = (
    [
        case(script, *args, marks=THEME_MARKS.get(script, ()))
        for script, args in ALL_THEMES
    ]
    + [
        case(
            script,
            *args,
            flags=("-cg",),
            suffix="-cg",
            defects=COARSE_DEFECTS.get(script, ()),
            marks=THEME_MARKS.get(script, ()),
        )
        for script, args in ALL_THEMES
    ]
    + [
        case(
            script,
            *args,
            flags=flags,
            suffix=suffix,
            defects=depth_defects(script, flags),
            marks=THEME_MARKS.get(script, ()),
        )
        for flags, suffix in DEPTH_LIMITS
        for script, args in ALL_THEMES
    ]
    + [case("modules.py", flags=("-c", "package"), suffix="-package")]
    + [
        # Constructs split out of the themes: one mechanism each.
        case("caller_frame.py", defects=(CALLER_FRAME,)),
        case("super_call.py", defects=(SUPER_CALL,)),
        case("definitions_run_once.py", defects=(DEF_RUNS_TWICE,)),
        case("abstract_methods.py", defects=(ABSTRACT_METHOD_COPY,)),
        case("docstrings.py", defects=(DOCSTRINGS_LOST,)),
        case("function_docstrings.py", defects=(FUNCTION_DOCSTRINGS_LOST,)),
        case("function_introspection.py", defects=(FUNCTION_SIGNATURE,)),
        case("function_defaults.py", defects=(FUNCTION_DEFAULTS,)),
        case("call_site_errors.py", defects=(CALL_ERROR_NAMES_COLLECTOR,)),
        case("keyword_named_self.py", defects=(KEYWORD_NAMED_SELF,)),
        case("wraps_decorator.py", defects=(RENAMED_FUNCTION_RECURSION,)),
        case("class_hooks.py", defects=(CLASS_CREATED_TWICE,)),
        case("decorated_property.py", defects=(DECORATED_OBJECT_WITHOUT_DICT,)),
        case("repr_during_init.py", defects=(REPR_SERIALIZER,)),
        case("abc_class_repr.py", defects=(CLASS_REPR_UNDER_A_METACLASS,)),
        case("value_comparisons.py", defects=(COLLECTOR_COMPARES_VALUES,)),
        case("positional_only.py", defects=(POSITIONAL_ONLY_PARAMETERS,)),
        case("positional_only_defaults.py"),
        case("lambda_in_collection.py", defects=(LAMBDA_IN_COLLECTION,)),
        case("class_body_comprehension.py", defects=(CLASS_BODY_COMPREHENSION,)),
        case("with_without_as.py", defects=(WITH_WITHOUT_AS,)),
        case("callbacks.py", defects=(CALLBACK_ARGUMENTS,)),
        case("yield_from_builtin.py", defects=(YIELD_FROM_CALLBACK,)),
        case("async_tasks.py", defects=(ASYNC_CALLBACK,)),
        case("values_kept_alive.py", defects=(VALUES_KEPT_ALIVE,)),
        case("last_assign_kept_alive.py", defects=(LAST_ASSIGN_KEPT_ALIVE,)),
        case("attribute_kept_alive.py", defects=(ATTRIBUTE_CONTAINER_KEPT_ALIVE,)),
        case("dropped_generator.py", defects=(GENERATOR_ACTIVATION_CYCLE,)),
        case("open_files_kept_alive.py", defects=(OPEN_FILES_KEPT_ALIVE,)),
        case("deep_recursion.py", defects=(RECURSION_DEPTH,)),
        case("fstring_braces.py"),
        case("builtins_module.py", defects=(BUILTINS_IS_A_DICT,)),
        case("genexp_iterable_snapshot.py", defects=(GENEXP_LAZY_FIRST_ITERABLE,)),
        case("genexp_iterable_raises.py", defects=(GENEXP_FIRST_ITERABLE_ERROR,)),
        case("yield_in_call_argument.py", defects=(YIELD_IN_CALL_ARGUMENT,)),
        case("exception_in_call_arguments.py", defects=(EXCEPTION_IN_CALL_ARGUMENTS,)),
        case(
            "conditional_expression_errors.py",
            defects=(CONDITIONAL_EXPRESSION_EXCEPTION,),
        ),
        case("condition_test_errors.py", defects=(CONDITION_TEST_EXCEPTION,)),
        case("file_object_type.py", defects=(FILE_PROXY_TYPE,)),
        case("open_wrapper_warning.py", defects=(OPEN_WRAPPER_FRAME,)),
        case("class_body_genexp.py", defects=(CLASS_BODY_GENEXP_SCOPE,)),
        case("codec_import.py", defects=(MODULE_ON_ANOTHER_DRIVE,)),
        case("if_body_exception_context.py", defects=(IF_BODY_CONTEXT,)),
        case(
            "fork_child_exit_status.py", defects=(FORK_EPILOGUE,), marks=(NEEDS_FORK,)
        ),
        case(
            "fork_with_threads_warning.py",
            defects=(FORK_WARNING_FRAME,),
            marks=(NEEDS_FORK,),
        ),
        case(
            "subprocess_preexec_fn.py",
            defects=(PREEXEC_FN_CALLBACK,),
            marks=(NEEDS_PREEXEC_FN,),
        ),
        case("distribution_finder.py", defects=(DISTRIBUTION_LOOKUP,)),
        case("duplicate_distributions.py", defects=(DISTRIBUTIONS_LISTED_TWICE,)),
        case("setuptools_vendor_path.py"),
        case(
            "directories_and_temporary_files.py",
            defects=(TEMPORARY_FILE_READ_AT_STORE,),
        ),
    ]
)


def assert_package_rewritten(project):
    """Fail outright unless the trial holds the classes of ``toolkit``

    The main script alone records evaluations, so ``assert_traced`` would
    still pass if ``-c package`` left the package unrewritten (a context
    ignored, a ``SyntaxError`` swallowed); only the rewritten package adds
    a ``class_def`` component for each class of toolkit/shapes.py.
    """
    trial = project.trials()[0]
    found = {
        row["name"]
        for row in project.query(
            "SELECT name FROM code_component WHERE trial_id = ? AND type = 'class_def'",
            trial["id"],
        )
    }
    missing = sorted(set(PACKAGE_CLASSES) - found)
    if missing:
        pytest.fail(
            "-c package did not rewrite toolkit: no class_def component for {}".format(
                ", ".join(missing)
            ),
            pytrace=False,
        )


@pytest.mark.parametrize("script, args, flags, defects", CASES)
def test_oracle_script_runs_like_plain_python(project, script, args, flags, defects):
    """The script leaves the same return code, outputs and files when
    ``now run`` traces it, and the run was traced"""
    skip_unless_same_python(project)
    plain, traced = run_both(project, "oracle", script, *args, flags=flags)
    if plain.returncode != 0 or not plain.stdout:
        # Not an AssertionError: a broken script must never pass for the
        # known defect of its case.
        pytest.fail(
            "the script itself fails under plain Python; fix the script\n{}".format(
                plain
            ),
            pytrace=False,
        )
    assert_same_outcome(plain, traced, defects)
    assert_traced(project, " ".join(("run", *flags, script, *args)))
    if "package" in flags:
        assert_package_rewritten(project)


def test_oracle_lists_every_script():
    """Every top-level script of corpus/oracle is a case run without flags,
    every case names an existing script, and nothing else lies next to them
    but what the scripts read, import or start"""
    ids = [param.id for param in CASES]
    assert len(ids) == len(set(ids)), "two cases share an id"
    on_disk = sorted(path.name for path in ORACLE.glob("*.py"))
    unflagged = sorted(param.values[0] for param in CASES if not param.values[2])
    assert unflagged == on_disk
    themes = {script for script, _ in ALL_THEMES}
    flagged = {param.values[0] for param in CASES if param.values[2]}
    assert flagged <= themes, "flags only rerun a theme"
    others = sorted(
        path.name
        for path in ORACLE.iterdir()
        if path.suffix != ".py"
        and path.name != "__pycache__"
        and not path.name.startswith(".")
        and path.name not in IGNORED
    )
    assert others == sorted(SUPPORT), (
        "a file a script left behind, or support not declared in SUPPORT"
    )
    collected = [
        name
        for name in on_disk
        if name.startswith("test_") or name.endswith("_test.py")
    ]
    assert not collected, "pytest would collect {}".format(collected)


CONTROL = """\
import builtins
import sys

traced = "__noworkflow__" in vars(builtins)
print("oracle control" + ("!" if traced else ""))
print("same in both runs")
if traced:
    sys.stderr.write("traced\\n")
with open("control.txt", "w", encoding="utf-8") as control:
    control.write("traced\\n" if traced else "plain\\n")
"""


def test_oracle_detects_difference(project):
    """A script that differs only under ``now run``, by one character on
    stdout, one line on stderr and the content of a file, yields exactly
    those three differences (the control of the oracle)

    The return code is covered by ``test_differences_between_outcomes`` and
    by the cases that end through ``sys.exit`` or an uncaught exception,
    whose status ``now run`` passes on.
    """
    project.write("control.py", CONTROL)
    plain = run_plain(project, "control.py")
    traced = run_traced(project, "control.py")
    assert plain.stdout == "oracle control\nsame in both runs\n", str(plain)
    assert plain.stderr == "", str(plain)
    assert "control.txt" in plain.files, str(plain)
    found = differences(plain, traced)
    assert len(found) == 3, "\n".join(found)
    assert found[0].startswith("stdout differs"), found[0]
    assert "+'oracle control!\\n'" in found[0], found[0]
    assert found[1].startswith("stderr differs"), found[1]
    assert "+'traced\\n'" in found[1], found[1]
    assert found[2].startswith("file control.txt: content differs"), found[2]


BASE = Outcome("python", 0, "total: 3\n", "", {"out.txt": "a" * 40})
VARIANTS = {
    "stdout": (dict(stdout="total: 3!\n"), "stdout differs"),
    "stderr": (dict(stderr="warning\n"), "stderr differs"),
    "return code": (dict(returncode=1), "return code: python 0, now run 1"),
    "file content": (
        dict(files={"out.txt": "b" * 40}),
        "file out.txt: content differs",
    ),
    "file missing": (dict(files={}), "file out.txt: only python wrote it"),
    "file extra": (
        dict(files={"out.txt": "a" * 40, "new.txt": "c" * 40}),
        "file new.txt: only now run wrote it",
    ),
}


@pytest.mark.parametrize("field", sorted(VARIANTS))
def test_differences_between_outcomes(field):
    """Two outcomes that differ in one field yield one difference that
    names it; identical outcomes yield none"""
    changes, expected = VARIANTS[field]
    fields = dict(vars(BASE), label="now run", **changes)
    traced = Outcome(**fields)
    same = Outcome(**dict(vars(BASE), label="now run"))
    assert differences(BASE, same) == []
    found = differences(BASE, traced)
    assert len(found) == 1, found
    assert found[0].startswith(expected), found[0]
