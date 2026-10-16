# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Mask what differs between two identical runs of ``now``

Two runs of the same script on the same machine differ in trial ids, clock
readings, checkpoints, memory addresses, the PID and the directories they ran
in; on another machine also in the hostname and the install paths; in
another environment also in the ids of file accesses, which count the files
the imported libraries read there. Everything else is the output under test
and stays: content hashes (SHA-1), sequence keys, automatic tags, code
component and evaluation ids, line numbers.

The rules come from measuring two stores built identically in two fresh
directories, and ``test_normalize.py`` pins them. They mask by shape, not by
position: a float with seven or more decimals is a checkpoint wherever it
appears, so a corpus script must not compute such values (``1 / 3``); its
results would be masked too.
"""
import json
import os
import platform
import re
import socket
import sys
from pathlib import Path

import noworkflow

# Values that change between runs of the same script on the same machine,
# as ``Name: value`` lines (``now show -e``) or attribute names in
# ``now diff -e``.
VOLATILE_KEYS = ("PID", "OS_RELEASE", "OS_VERSION", "PROCESSOR")

# Path separators as they appear in output: native, doubled by ``repr`` and
# JSON, doubled again by the Prolog writer (``utils/prolog.py``).
SEP = r"[\\/]+"
# What may follow a path inside a longer path component. A path followed by
# one of these is a different path (``/tmp/project2`` is not ``/tmp/project``).
NOT_END = r"(?![\w.-])"

UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)
# ``now export ast -d`` names nodes after ``id()`` of the AST node.
AST_NODE = re.compile(r"\bnode\d{5,}\b")
# ``now export dataflow`` names a file access ``a_<id>``, and the id counts
# every access of the trial, the ones the graph leaves out included: the
# files the libraries the script imports read from the environment, such as
# the ``entry_points.txt`` of every installed distribution. Only in the dot
# syntax (``a_1 [``, ``a_1 ->``, ``-> a_1``), so a script's ``a_1`` stays.
ACCESS_NODE = re.compile(r"\ba_\d+(?= \[| ->)|(?<=-> )a_\d+\b")
# ``str(datetime)``: the fraction is omitted when the microsecond is zero.
TIMESTAMP = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\b"
)
# ``str(timedelta)``. Applied after TIMESTAMP, which contains this shape.
DURATION = re.compile(r"(?<![\d:])\d+:\d{2}:\d{2}(?:\.\d{1,6})?(?![\d:])")
# Seconds since 1970 of the Prolog timestamps (``now export prolog``
# without ``-t``).
EPOCH = re.compile(r"(?<![\w.])1\d{9}\.\d{1,6}(?![\w.])")
# Checkpoints: seconds since the trial started, as ``repr(float)``. They
# never have fewer than seven decimals unless the float is exact, and below
# 1e-4 they use the exponent form.
CHECKPOINT = re.compile(
    r"(?<![\w.])\d+\.\d{7,}(?:e[-+]?\d+)?(?![\w.])"
    r"|(?<![\w.])\d+(?:\.\d+)?e-\d+(?![\w.])"
)
# Where a checkpoint is printed, whatever its length: the 0-based argument
# of the Prolog facts (also inside the access tuples that `now diff -fa`
# prints) and `now diff -f`. The shape rule above misses a short repr, which
# is common on Windows, where perf_counter() ticks every 100 ns.
CHECKPOINT_ARGUMENT = {"evaluation": 2, "activation": 3, "access": 6,
                       "member": 6}
FACT_START = re.compile(r"\b({})\(".format("|".join(CHECKPOINT_ARGUMENT)))
CHECKPOINT_CHANGE = re.compile(
    r"(Checkpoint changed from )\S+( to )\S+$", re.MULTILINE)
NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?")
ADDRESS = re.compile(r"\b0x[0-9a-fA-F]+\b")
# The duration of an activation in ``now diff -fa``, ``round(x, 2)``.
MICROSECONDS = re.compile(r"\b\d+(?:\.\d+)? microseconds\b")
# A path into an installed package, up to its ``site-packages``. Bounded by
# path characters, so the text before the path stays (``  File "``).
SITE_PACKAGES = re.compile(r"""[^\s'"(),=]*?[\\/]+site-packages[\\/]+""")
# ``[ \t]``, not ``\s``: an empty value must not swallow the next line.
VOLATILE_LINE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<key>{})(?P<sep>[ \t]*:[ \t]*).*$".format(
        "|".join(VOLATILE_KEYS)
    ),
    re.MULTILINE,
)
VOLATILE_CHANGE = re.compile(
    r"^(?P<head>[ \t]*Environment attribute (?:{}) changed from ).*$".format(
        "|".join(VOLATILE_KEYS)
    ),
    re.MULTILINE,
)
# ``now -v`` and anything else that names the running noWorkflow: compared
# across versions by the golden-run.
NOWORKFLOW_VERSION = re.compile(r"\bnoWorkflow \d+(?:\.\d+)+\S*")
# Masks that replace values of varying width. A difflib hint line (``? ^``)
# under a line that contained one of them points at characters that the
# mask replaced, so its columns vary from run to run.
MASKS = ("<ADDRESS>", "<N> microseconds", "<CHECKPOINT>", "<TIMESTAMP>",
         "<DURATION>")


def path_pattern(path):
    """Regex that matches ``path`` with any separator spelling

    The components are joined by ``[\\/]+``, so the same pattern matches
    the native path, its ``repr`` (doubled backslashes on Windows) and the
    Prolog escape of that ``repr`` (doubled again).

    >>> bool(re.fullmatch(path_pattern("/tmp/x/proj"), "/tmp/x/proj"))
    True
    >>> bool(re.fullmatch(path_pattern("C:\\\\a\\\\b"), "C:\\\\\\\\a\\\\\\\\b"))
    True
    >>> bool(re.match(path_pattern("/tmp/x/proj"), "/tmp/x/project"))
    False
    """
    parts = [part for part in re.split(r"[\\/]+", str(path))]
    while len(parts) > 1 and parts[-1] == "":
        parts.pop()
    return SEP.join(re.escape(part) for part in parts) + NOT_END


def path_variants(path):
    """The spellings of ``path`` that may reach the output

    noWorkflow stores ``realpath`` for the script, its directory and its
    modules, but keeps what was typed for the command line and the
    environment. On macOS the temporary directories are symlinks
    (``/var`` -> ``/private/var``), so both spellings occur.
    """
    path = str(path)
    variants = {path, os.path.realpath(path)}
    return sorted(variants, key=len, reverse=True)


def install_paths():
    """Directories of the interpreter and of noWorkflow, with placeholders

    Tracebacks and module paths point into them. ``<NOWORKFLOW>`` is the
    directory that contains the ``noworkflow`` package: ``src`` in an
    editable install, ``site-packages`` in a wheel.
    """
    package_root = Path(noworkflow.__file__).resolve().parent.parent
    return [
        ("<NOWORKFLOW>", package_root),
        ("<PREFIX>", sys.prefix),
        ("<PREFIX>", sys.exec_prefix),
        ("<BASE_PREFIX>", sys.base_prefix),
        ("<BASE_PREFIX>", sys.base_exec_prefix),
    ]


def usable_hostname(name):
    """A hostname long and specific enough to be replaced as a word"""
    return bool(name) and len(name) >= 4 and name.lower() != "localhost"


class Normalizer:
    """Replace the volatile parts of an output by stable placeholders

    ``paths`` is a list of ``(placeholder, path)`` pairs: the project
    directory, the temporary home and so on. The install directories of the
    interpreter and of noWorkflow are always added after them.
    """

    def __init__(self, paths=(), hostname=None):
        if hostname is None:
            hostname = socket.gethostname()
        flags = re.IGNORECASE if os.name == "nt" else 0
        pairs = []
        for placeholder, path in list(paths) + install_paths():
            for variant in path_variants(path):
                pairs.append((variant, placeholder))
        # Longest first: a path inside another one is replaced by the
        # placeholder of the outer one only when it is not more specific.
        pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
        self.path_rules = [
            (re.compile(path_pattern(path), flags), placeholder)
            for path, placeholder in pairs
        ]
        names = {hostname, hostname.split(".")[0]} if hostname else set()
        self.host_rules = [
            re.compile(
                r"(?<![A-Za-z0-9.-]){}(?![A-Za-z0-9-])".format(re.escape(name)),
                re.IGNORECASE,
            )
            for name in sorted(names, key=len, reverse=True)
            if usable_hostname(name)
        ]
        self.python_version = re.compile(
            r"(?<![\w.]){}(?![\w.])".format(re.escape(platform.python_version()))
        )

    def __call__(self, text):
        text = text.replace("\r\n", "\n")
        for pattern, placeholder in self.path_rules:
            text = pattern.sub(lambda match, value=placeholder: value, text)
        text = SITE_PACKAGES.sub("<SITE>/", text)
        for pattern in self.host_rules:
            text = pattern.sub("<HOSTNAME>", text)
        text = self.python_version.sub("<PYTHON_VERSION>", text)
        text = NOWORKFLOW_VERSION.sub("noWorkflow <NOWORKFLOW_VERSION>", text)
        text = number(UUID, "<UUID{}>", text)
        text = number(AST_NODE, "node<N{}>", text)
        text = number(ACCESS_NODE, "a_<A{}>", text)
        text = TIMESTAMP.sub("<TIMESTAMP>", text)
        text = DURATION.sub("<DURATION>", text)
        text = EPOCH.sub("<EPOCH>", text)
        text = mask_fact_checkpoints(text)
        text = CHECKPOINT_CHANGE.sub(r"\1<CHECKPOINT>\2<CHECKPOINT>", text)
        text = CHECKPOINT.sub("<CHECKPOINT>", text)
        text = ADDRESS.sub("<ADDRESS>", text)
        text = MICROSECONDS.sub("<N> microseconds", text)
        text = VOLATILE_LINE.sub(r"\g<indent>\g<key>\g<sep><MASKED>", text)
        text = VOLATILE_CHANGE.sub(r"\g<head><MASKED>", text)
        return tidy(text)

    def json(self, text):
        """Normalize a JSON document after sorting its keys

        Sorting first makes the numbering of the UUIDs independent of the
        order in which the producer wrote the keys.
        """
        data = json.loads(text)
        return self(json.dumps(data, sort_keys=True, indent=1,
                               ensure_ascii=False))


def number(pattern, template, text):
    """Replace each distinct match by ``template`` numbered by first use"""
    seen = {}

    def replace(match):
        value = match.group(0)
        if value not in seen:
            seen[value] = template.format(len(seen) + 1)
        return seen[value]

    return pattern.sub(replace, text)


def tidy(text):
    """Strip line ends and drop difflib hints over masked characters

    ``now diff -fa`` prints difflib's ``? `` lines under the lines that
    changed. Under a line that had an address or a duration, the hint marks
    the characters that the mask replaced, so it varies from run to run, and
    difflib omits it when the two values are too dissimilar. The hint ends
    with its own newline and ``cmd_diff.py`` joins difflib's lines with
    another, so the blank line it leaves goes with it.
    """
    lines = []
    dropped = False
    for line in text.split("\n"):
        line = line.rstrip()
        if (line.startswith("? ") and lines
                and any(mask in lines[-1] for mask in MASKS)):
            dropped = True
            continue
        if dropped and not line:
            dropped = False
            continue
        dropped = False
        lines.append(line)
    text = "\n".join(lines).strip("\n")
    return text + "\n" if text else ""


def prolog_statements(text):
    """Split Prolog text into ``(kind, text)``: comment, blank or clause

    A clause ends at a ``.`` that closes the line outside a quoted atom, so
    a fact whose value holds a newline stays one statement.

    >>> [kind for kind, _ in prolog_statements("% c\\n\\nf('a.\\nb').\\n")]
    ['comment', 'blank', 'clause']
    """
    statements = []
    index, size = 0, len(text)
    while index < size:
        char = text[index]
        if char == "\n":
            statements.append(("blank", "\n"))
            index += 1
            continue
        if char == "%":
            end = text.find("\n", index)
            end = size if end < 0 else end + 1
            statements.append(("comment", text[index:end]))
            index = end
            continue
        end, quoted = index, False
        while end < size:
            char = text[end]
            if quoted:
                if char == "'":
                    if text[end + 1:end + 2] == "'":
                        end += 2
                        continue
                    quoted = False
            elif char == "'":
                quoted = True
            elif char == "." and text[end + 1:end + 2] in ("\n", ""):
                end += 1
                break
            end += 1
        if text[end:end + 1] == "\n":
            end += 1
        statements.append(("clause", text[index:end]))
        index = end
    return statements


def strip_prolog_predicate(text, name):
    """Remove a predicate from a Prolog export: its comment, declaration
    and facts

    ``now export prolog`` writes each predicate as a ``%`` comment block that
    starts with ``% FACT DEFINITION: name(...)``, a ``:- dynamic(name/N).``
    declaration and the facts.
    """
    statements = prolog_statements(text)
    definition = "% FACT DEFINITION: {}(".format(name)
    declaration = ":- dynamic({}/".format(name)
    fact = "{}(".format(name)
    keep = [True] * len(statements)
    for index, (kind, body) in enumerate(statements):
        if kind == "comment" and body.startswith(definition):
            start = index
            while start > 0 and statements[start - 1][0] == "comment":
                start -= 1
            stop = index
            while stop < len(statements) and statements[stop][0] == "comment":
                stop += 1
            for position in range(start, stop):
                keep[position] = False
        elif kind == "clause" and (body.startswith(declaration)
                                   or body.startswith(fact)):
            keep[index] = False
    return "".join(body for (kind, body), kept in zip(statements, keep)
                   if kept)


def prolog_facts(text):
    """Map each predicate to the arities of its facts and to its declared
    arity: ``{name: (declared, {arities})}``
    """
    result = {}
    for kind, body in prolog_statements(text):
        if kind != "clause":
            continue
        match = re.match(r":- dynamic\((\w+)/(\d+)\)\.", body)
        if match:
            declared, arities = result.get(match.group(1), (None, set()))
            result[match.group(1)] = (int(match.group(2)), arities)
            continue
        match = re.match(r"(\w+)\(", body)
        if match:
            declared, arities = result.get(match.group(1), (None, set()))
            arities.add(clause_arity(body[match.end():]))
            result[match.group(1)] = (declared, arities)
    return result


def mask_fact_checkpoints(text):
    """Mask the checkpoint argument of every activation, evaluation, access
    and member fact, by position

    >>> mask_fact_checkpoints("evaluation('<UUID1>', 7, 0.314076, 3, 2, 'x', 7).")
    "evaluation('<UUID1>', 7, <CHECKPOINT>, 3, 2, 'x', 7)."
    >>> mask_fact_checkpoints("member('<UUID1>', 0, 1, 0, 11, '.a, b', 0.5, 'Put').")
    "member('<UUID1>', 0, 1, 0, 11, '.a, b', <CHECKPOINT>, 'Put')."
    """
    pieces, position = [], 0
    for match in FACT_START.finditer(text):
        if match.start() < position:
            continue
        spans = argument_spans(text, match.end())
        index = CHECKPOINT_ARGUMENT[match.group(1)]
        if spans is None or index >= len(spans):
            continue
        start, end = spans[index]
        value = text[start:end].strip()
        if not NUMBER.fullmatch(value):
            continue
        offset = start + (len(text[start:end]) - len(text[start:end].lstrip()))
        pieces.append(text[position:offset])
        pieces.append("<CHECKPOINT>")
        position = offset + len(value)
    pieces.append(text[position:])
    return "".join(pieces)


def argument_spans(text, index):
    """``[(start, end)]`` of the top-level arguments of a call, from just
    after its ``(``; None when the call does not close"""
    spans, depth, quoted, start = [], 0, False, index
    while index < len(text):
        char = text[index]
        if quoted:
            if char == "'":
                if text[index + 1:index + 2] == "'":
                    index += 2
                    continue
                quoted = False
        elif char == "'":
            quoted = True
        elif char in "([":
            depth += 1
        elif char in ")]":
            if depth == 0:
                spans.append((start, index))
                return spans
            depth -= 1
        elif char == "," and depth == 0:
            spans.append((start, index))
            start = index + 1
        index += 1
    return None


def clause_arity(arguments):
    """Count the top-level arguments of a fact, from after its ``(``

    >>> clause_arity("'a', 'b,c', f(1, 2), nil).")
    4
    """
    depth, count, quoted, index = 0, 1, False, 0
    while index < len(arguments):
        char = arguments[index]
        if quoted:
            if char == "'":
                if arguments[index + 1:index + 2] == "'":
                    index += 2
                    continue
                quoted = False
        elif char == "'":
            quoted = True
        elif char in "([":
            depth += 1
        elif char in ")]":
            if depth == 0:
                return count
            depth -= 1
        elif char == "," and depth == 0:
            count += 1
        index += 1
    return count
