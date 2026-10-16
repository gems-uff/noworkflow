# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Compare the solutions of a rule with what the store holds

A pattern query yields ``(result, binds)`` pairs whose binds are keyed by
``Variable`` objects and reuse the variables between solutions.
``bindings`` turns a query into plain rows, iterating it to the end: a query
left early keeps its variables bound, which silently filters the next query
that uses them. ``assert_rows`` compares rows as multisets (the order of a
rule follows SQLite's, the order of rules.pl its clauses) and words each
difference on its own line, so that a ``Defect`` signature can name one
kind of difference:

- ``raises <Type>: <message>``: the rule raised instead of answering;
- ``unbound in <n> solutions``: solutions left a variable unbound (BLANK,
  ABSENT or the Prolog UNBOUND) where the store has a value;
- ``repeats <n> solutions``: copies of a solution beyond the store's count;
- ``only in the rule (<n>): ...`` and ``only in the store (<n>): ...``: the
  rows the other side lacks, counted with repetition.

The rules.pl side reads ``now export prolog -r`` through
``helpers/swipl.py``; ``normalize_prolog`` maps its conventions back to the
store's. The defect helpers are re-exported for the test modules.

Two traps of the machinery. Create each variable with ``var("X")``: the
factory's ``var.X`` hands out one shared object per name for the whole
process. And never bind a model rule (``activation``, ``trial``...) to a
global name of a test module (``from noworkflow.patterns import
activation``): the suite runs with ``--doctest-modules``, whose finder asks
every global for ``__wrapped__``, and a model rule raises KeyError instead
of AttributeError, which fails the collection of the whole module (the
defect ``model-rule-getattr-keyerror``). Import the package (``from
noworkflow import patterns``) and write ``patterns.activation``.
"""
import collections
import re

from noworkflow.patterns.machinery import BLANK, Variable
from noworkflow.tests.helpers.defects import (  # noqa: F401  (re-exported)
    Defect, defect_marks, expect_known_failure, known_defects,
)
from noworkflow.tests.helpers.swipl import UNBOUND, Compound

# Rows listed per line of a difference; the count in the line is complete.
SHOWN_ROWS = 10
ACCESS_ID = re.compile(r"f(\d+)\Z")


class _Absent:
    """The value of a variable that a solution does not bind at all"""

    def __repr__(self):
        return "<absent>"


ABSENT = _Absent()
UNBOUND_MARKERS = (BLANK, ABSENT, UNBOUND)


def bindings(query, *variables):
    """Every solution of ``query``, as a tuple of the values of ``variables``

    Each variable is a ``Variable`` (looked up by identity) or a name (the
    one variable of the binds with that name; ValueError when two distinct
    variables share it). A variable the solution does not bind is
    ``ABSENT``; one bound to ``BLANK`` (``_``, a lost binding) stays
    ``BLANK``. Lists become tuples, so rows can be counted. The query is
    iterated to the end, which unbinds its variables again.
    """
    rows = []
    for _, binds in query:
        rows.append(tuple(_plain(_lookup(binds, variable))
                          for variable in variables))
    return rows


def _lookup(binds, variable):
    if isinstance(variable, Variable):
        return binds.get(variable, ABSENT)
    found = [(key, value) for key, value in binds.items()
             if key.name == variable]
    if len({id(key) for key, _ in found}) > 1:
        raise ValueError("two variables are named {!r}; pass the Variable "
                         "itself".format(variable))
    return found[0][1] if found else ABSENT


def _plain(value):
    if isinstance(value, (list, tuple)) and not isinstance(value, Compound):
        return tuple(_plain(item) for item in value)
    return value


def outcome(thunk):
    """``thunk()``, or ``"<Type>: <message>"`` when it raises an Exception

    A skip or a ``pytest.fail`` is not an Exception and goes through.
    """
    try:
        return thunk()
    except Exception as error:  # pylint: disable=broad-except
        return "{}: {}".format(type(error).__name__, error)


def differences(actual, expected):
    """The categorized lines of how ``actual`` differs from ``expected``

    Both are iterables of hashable rows; the result is empty when they are
    equal as multisets. ``actual`` is the rule's, ``expected`` the store's.
    """
    actual = collections.Counter(actual)
    expected = collections.Counter(expected)
    if actual == expected:
        return ""
    extra, missing = actual - expected, expected - actual
    lines = ["{} solutions in the rule, {} in the store".format(
        sum(actual.values()), sum(expected.values()))]
    unbound = sum(count for row, count in extra.items() if _unbound(row))
    if unbound:
        lines.append("unbound in {} solutions".format(unbound))
    repeats = sum(count - max(expected[row], 1)
                  for row, count in actual.items()
                  if count > max(expected[row], 1))
    if repeats:
        lines.append("repeats {} solutions".format(repeats))
    for label, rows in (("only in the rule", extra),
                        ("only in the store", missing)):
        if rows:
            lines.append("{} ({}): {}".format(
                label, sum(rows.values()), _show(rows)))
    return "\n".join(lines)


def _unbound(row):
    values = row if isinstance(row, tuple) else (row,)
    return any(value is marker for value in values
               for marker in UNBOUND_MARKERS)


def _show(rows):
    shown = sorted(rows.items(), key=lambda item: repr(item[0]))
    text = ", ".join(
        repr(row) if count == 1 else "{!r} x{}".format(row, count)
        for row, count in shown[:SHOWN_ROWS])
    if len(shown) > SHOWN_ROWS:
        text += ", ... ({} more distinct)".format(len(shown) - SHOWN_ROWS)
    return text


def assert_rows(actual_thunk, expected_rows, defects=()):
    """Assert that ``actual_thunk()`` answers ``expected_rows``, as multisets

    Returns the rows when they match. Otherwise the message is ``raises
    <Type>: <message>`` or the lines of ``differences``; a known defect that
    applies must carry a signature found in it (``expect_known_failure``,
    which fails the test outright otherwise), and the AssertionError that
    follows is what the ``xfail(raises=AssertionError)`` mark absorbs.
    """
    actual = outcome(actual_thunk)
    if isinstance(actual, str):
        message = "raises " + actual
    else:
        message = differences(actual, expected_rows)
        if not message:
            return actual
    expect_known_failure(defects, message)
    raise AssertionError(message)


def normalize_prolog(value):
    """A value of a rules.pl solution in the store's terms

    The export writes an access id as the atom ``f<id>`` and None as
    ``nil``; both come back here as the int and None. Tuples (rows, lists)
    and the arguments of a ``Compound`` are mapped item by item. Apply it to
    the columns that hold ids or nullable values: a name that happens to be
    ``nil`` or ``f1`` would be mapped too.
    """
    if isinstance(value, Compound):
        return Compound(value.name, normalize_prolog(value.args))
    if isinstance(value, tuple):
        return tuple(normalize_prolog(item) for item in value)
    if isinstance(value, str):
        if value == "nil":
            return None
        match = ACCESS_ID.match(value)
        if match:
            return int(match.group(1))
    return value
