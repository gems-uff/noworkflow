# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``patterns/rules/helpers.py`` and what every rule shares with rules.pl

``between``, ``member`` and ``once`` mirror the Prolog built-ins of the same
names and answer from Python values, so their expected answers are those of
``between/3``, ``member/2`` and ``once/1``, and they need no store.
``_match`` (unification of one value) and ``_create_list`` (a list of the
size of another) are what the rules that accept lists build on.

The last test holds every rule of ``noworkflow.patterns.rules`` to its
counterpart in ``resources/rules.pl``, which ``now export prolog -r``
appends to the facts: a predicate of the same name and arity. The clause
heads are read from the text of rules.pl, independently of the Python
rules; an argument whose name starts with ``_`` is the rule's own (an
option it explores), not one of the predicate's.
"""
import collections
import pathlib
import re

import pytest

import noworkflow
from noworkflow.patterns import BLANK, rules, var
from noworkflow.patterns.machinery import FunctionRule, Variable
from noworkflow.patterns.rules.helpers import _create_list, _match
from noworkflow.tests.e2e.normalize import clause_arity, prolog_statements
from noworkflow.tests.patterns.support import bindings

RULES_PL = pathlib.Path(noworkflow.__file__).parent / "resources" / "rules.pl"
# The helpers that mirror Prolog built-ins, which rules.pl does not define.
BUILTINS = {"between", "member", "once"}


def test_between_enumerates_the_closed_interval():
    """``between(1, 3, X)`` answers 1, 2 and 3; an empty interval nothing"""
    x = var("X")
    assert bindings(rules.between(1, 3, x), x) == [(1,), (2,), (3,)]
    assert bindings(rules.between(1, 0, x), x) == []
    assert x.bound is BLANK


def test_between_checks_a_bound_value():
    """A bound value inside the interval succeeds once, outside it fails"""
    assert len(list(rules.between(1, 3, 2))) == 1
    assert list(rules.between(1, 3, 5)) == []


def test_between_rejects_unbound_bounds():
    """Unlike Prolog, which raises an instantiation error, a variable bound
    raises TypeError
    """
    with pytest.raises(TypeError, match="Low and High should be values"):
        list(rules.between(var("Low"), 3, var("X")))


def test_member_enumerates_and_checks():
    """``member(X, L)`` answers each item in order; with a value it checks
    membership; an empty list has no members
    """
    x = var("X")
    assert bindings(rules.member(x, [1, 2, 3]), x) == [(1,), (2,), (3,)]
    assert len(list(rules.member(2, [1, 2]))) == 1
    assert list(rules.member(5, [1, 2])) == []
    assert list(rules.member(x, [])) == []
    assert x.bound is BLANK


def test_once_yields_only_the_first_result():
    """``once`` answers the first solution of its query and unbinds it"""
    x, y = var("X Y")
    assert bindings(rules.once(rules.member(x, [7, 8])), x) == [(7,)]
    assert bindings(rules.once(rules.between(1, 3, y)), y) == [(1,)]
    assert (x.bound, y.bound) == (BLANK, BLANK)


def test_helpers_join_on_a_shared_variable():
    """``&`` keeps the values both sides answer"""
    x, y = var("X Y")
    assert bindings(
        rules.member(x, [1, 2]) & rules.member(x, [2, 3]), x) == [(2,)]
    assert bindings(
        rules.between(1, 4, y) & rules.member(y, [2, 4, 6]), y) == [
            (2,), (4,)]


def test_match_binds_an_unbound_variable_and_compares_bound_ones():
    """BLANK matches anything; an unbound variable is bound and recorded
    in the binds; a bound one is compared by its value, on either side
    """
    assert _match(BLANK, 1, {}) is True
    unbound, binds = var("V"), {}
    assert _match(unbound, 3, binds) is True
    assert (unbound.bound, binds) == (3, {unbound: 3})
    bound = var("B")(2)
    assert _match(bound, 2, {}) is True
    assert _match(1, bound, {}) is False
    other, binds = var("W"), {}
    assert _match(4, other, binds) is True
    assert (other.bound, binds) == (4, {other: 4})


def test_create_list_matches_the_cardinality():
    """A list of the size passes, another size does not; BLANK and a
    variable become that many blanks or fresh variables; a scalar does not
    fit
    """
    assert _create_list([1, 2], 2) == [1, 2]
    assert _create_list([1], 2) is None
    assert _create_list(BLANK, 2) == [BLANK, BLANK]
    created = _create_list(var("V"), 2)
    assert len(created) == 2 and len({id(item) for item in created}) == 2
    assert all(isinstance(item, Variable) and item.bound is BLANK
               for item in created)
    assert _create_list(5, 2) is None


def rules_pl_heads():
    """``{name: {arities}}`` of the clause heads of rules.pl"""
    lines = [line.strip() for line in
             RULES_PL.read_text(encoding="utf-8").splitlines()
             if not line.lstrip().startswith("%")]
    heads = collections.defaultdict(set)
    for kind, text in prolog_statements("\n".join(lines)):
        match = re.match(r"([a-z]\w*)\(", text.strip())
        if kind == "clause" and match:
            heads[match.group(1)].add(
                clause_arity(text.strip()[match.end():]))
    return heads


def test_every_rule_has_a_rules_pl_predicate_of_the_same_arity():
    """Each FunctionRule of ``noworkflow.patterns.rules`` but the built-in
    mirrors names a predicate of rules.pl with as many arguments as the
    rule's own arguments (the ones without a leading ``_``)
    """
    heads = rules_pl_heads()
    assert len(heads) > 50, "rules.pl was not parsed: {}".format(len(heads))
    found = {name: rule for name, rule in vars(rules).items()
             if isinstance(rule, FunctionRule) and name not in BUILTINS}
    assert len(found) > 50, "the rules package lists {}".format(len(found))
    mismatches = {}
    for name, rule in sorted(found.items()):
        arity = len([arg for arg in rule.args if not arg.startswith("_")])
        if arity not in heads.get(name, ()):
            mismatches[name] = (arity, sorted(heads.get(name, ())))
    assert mismatches == {}, (
        "rule: (Python arity, rules.pl arities): {}".format(mismatches))
