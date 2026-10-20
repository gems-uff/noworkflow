# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``patterns/support.py``: the comparison the rule tests rest on

Every rule test turns a query into rows with ``bindings`` and compares them
with SQL through ``assert_rows``; a comparator that hid a lost binding, a
repeated solution or a crash would let the defects it exists to catch pass.
The queries here need no store: the helper rule ``member`` answers from a
Python list, and a list of ``(result, binds)`` pairs stands in for a query
where the machinery cannot produce the case (a BLANK bind).
"""

import pytest

from noworkflow.patterns import BLANK, var
from noworkflow.patterns.rules import member
from noworkflow.tests.helpers.swipl import UNBOUND, Compound
from noworkflow.tests.patterns.support import (
    ABSENT,
    Defect,
    assert_rows,
    bindings,
    normalize_prolog,
    outcome,
)

MATCHES = Defect("#NNN: an example mechanism", "only in the store (1)")
OTHER = Defect("#NNN: an example mechanism", "repeats 1 solutions")


def test_bindings_lists_each_solution_and_turns_lists_into_tuples():
    """``member`` answers its list in order; X is unbound afterwards"""
    x = var("X")
    assert bindings(member(x, [1, [2, 3]]), x) == [(1,), ((2, 3),)]
    assert x.bound is BLANK


def test_bindings_finds_a_variable_by_name():
    assert bindings(member(var("X"), ["a", "b"]), "X") == [("a",), ("b",)]


def test_a_variable_the_solution_does_not_bind_is_absent():
    assert bindings(member(var("X"), [1]), "X", var("Y")) == [(1, ABSENT)]


def test_a_variable_bound_to_blank_stays_blank():
    """A lost binding is not confused with an absent variable"""
    x, y = var("X Y")
    query = [(None, {x: BLANK, y: 2})]
    assert bindings(query, x, "Y") == [(BLANK, 2)]


def test_two_variables_with_one_name_are_ambiguous():
    first, second = var("X"), var("X")
    with pytest.raises(ValueError, match="two variables are named 'X'"):
        bindings([(None, {first: 1, second: 2})], "X")


def test_outcome_returns_the_value_or_the_exception_text():
    assert outcome(lambda: [(1,)]) == [(1,)]
    assert outcome(lambda: {}["_"]) == "KeyError: '_'"


def test_assert_rows_compares_multisets_and_returns_the_rows():
    assert assert_rows(lambda: [(2,), (1,), (1,)], [(1,), (2,), (1,)]) == [
        (2,),
        (1,),
        (1,),
    ]


@pytest.mark.parametrize(
    "actual, expected, line",
    [
        ([(1,)], [(1,), (2,)], "only in the store (1): (2,)"),
        ([(1,), (3,), (3,)], [(1,)], "only in the rule (2): (3,) x2"),
        ([(1,), (1,), (1,)], [(1,)], "repeats 2 solutions"),
        ([(1,), (1,)], [(1,), (1,), (1,)], "only in the store (1): (1,)"),
        (
            [(BLANK,), (ABSENT,), (UNBOUND,)],
            [(1,), (2,), (3,)],
            "unbound in 3 solutions",
        ),
    ],
)
def test_each_difference_has_its_own_line(actual, expected, line):
    with pytest.raises(AssertionError) as caught:
        assert_rows(lambda: actual, expected)
    assert line in str(caught.value).splitlines()


def test_a_store_with_the_repeats_is_not_a_repeat():
    """Two copies on each side: equal, no ``repeats`` line"""
    assert assert_rows(lambda: [(1,), (1,)], [(1,), (1,)]) == [(1,), (1,)]


def test_a_crash_is_a_difference():
    with pytest.raises(AssertionError, match="^raises KeyError: '_'$"):
        assert_rows(lambda: {}["_"], [(1,)])


def test_a_defect_with_the_signature_lets_the_assertion_through():
    """The AssertionError is what the xfail mark absorbs"""
    with pytest.raises(AssertionError, match="only in the store"):
        assert_rows(lambda: [(1,)], [(1,), (2,)], defects=[MATCHES])


def test_a_defect_without_the_signature_fails_outright():
    with pytest.raises(pytest.fail.Exception, match="a second defect"):
        assert_rows(lambda: [(1,)], [(1,), (2,)], defects=[OTHER])


def test_normalize_prolog_maps_access_ids_and_nil():
    """``f<id>`` is an access id, ``nil`` is None, at any depth"""
    row = ("f12", "nil", "file.txt", 3, ("f1", "f2"), Compound("-", ("f3", "nil")))
    assert normalize_prolog(row) == (
        12,
        None,
        "file.txt",
        3,
        (1, 2),
        Compound("-", (3, None)),
    )
