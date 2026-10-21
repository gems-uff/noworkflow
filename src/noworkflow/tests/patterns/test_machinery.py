# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``patterns/machinery.py``: variables, queries, rule options, model rules

A pattern query binds ``Variable`` objects while it runs: each result binds
the query's variables, and the query unbinds them when it ends. A function
rule (``create_rule``) explores the values of an option
(``restrict_rule``, ``set_options_in_rule``) when its argument is unbound,
and a restricted option refuses any other value. A model rule
(``ModelRule``) turns a call into a SQLAlchemy query over one table of the
connected store.

The tests without a store use the helper rule ``member``, which answers
from a Python list, and two small rules defined here. The tests of model
rules run on ``connected_two_trials`` and compare with SQL on the same
store's ``db.sqlite``, for each of its two trials.

Three defects of the machinery show here, each with a characterization and
a ``_desired`` twin: a query left before its last result keeps its
variables bound (abandoned-query-keeps-bindings), an option that a rule
explores is bound only on the first result of each of its values
(rule-option-binding-lost), and ``hasattr`` on a model rule raises
KeyError (model-rule-getattr-keyerror). The last one is why no model rule
is bound to a global name of this module: ``--doctest-modules`` asks every
global for ``__wrapped__`` and would fail to collect it. A model rule
called with a keyword that is not one of its attributes fails on its first
row; the timestamp rules reach that through stale attribute names
(``test_timestamp_rules.py``).
"""

import collections
import doctest

import pytest

from noworkflow import patterns
from noworkflow.now.persistence.models import CodeComponent
from noworkflow.patterns import (
    BLANK,
    create_rule,
    restrict_rule,
    rules,
    set_options_in_rule,
    var,
)
from noworkflow.patterns import models as pattern_models
from noworkflow.patterns.machinery import NullQuery, Variable, VariableFactory
from noworkflow.tests.patterns.support import (
    Defect,
    assert_rows,
    bindings,
    known_defects,
)

ABANDONED = Defect(
    "#353: BoundQuery.__iter__ and "
    "RuleQuery.apply_function unbind the variables after the last result, "
    "not in a finally, so a query left by break, next() or an exception "
    "keeps them bound and filters the next query that uses them",
    "stays bound",
)
OPTION_BINDING = Defect(
    "#344: RuleQuery.apply_function resets to "
    "BLANK, after each result, every variable in self.binds, including the "
    "option that prepare_values bound, so only the first result of each "
    "value of the option binds it",
    "results bind no K",
)
GETATTR = Defect(
    "#343: ModelRule.__getattr__ indexes "
    "self._names and raises KeyError instead of AttributeError for an "
    "unknown name, which hasattr, getattr with a default and doctest's "
    "finder (inspect.unwrap) expect",
    "KeyError: 'nope'",
)

TRIALS = pytest.mark.parametrize("number", [1, 2], ids=["trial1", "trial2"])


@restrict_rule(kind=["a", "b"])
@create_rule
def pairs(kind, value):
    """``kind`` restricted to a and b, ``value`` in 1 and 2"""
    return rules.member(value, [1, 2])


@set_options_in_rule(kind=["a", "b"])
@create_rule
def explored(kind, value):
    """``kind`` explored over a and b when unbound, any value otherwise"""
    return rules.member(value, [1, 2])


OPTION_RULES = pytest.mark.parametrize(
    "rule", [pairs, explored], ids=["restricted", "explored"]
)


def trial_id(project, number):
    return project.trials()[number - 1]["id"]


def sql_rows(project, sql, *params):
    return [tuple(row.values()) for row in project.query(sql, *params)]


def abandon(how, variable):
    """Leave ``member(variable, [1, 2, 3])`` at its first result"""
    if how == "break":
        for _ in rules.member(variable, [1, 2, 3]):
            break
    elif how == "next":
        next(iter(rules.member(variable, [1, 2, 3])))
    else:
        try:
            for _ in rules.member(variable, [1, 2, 3]):
                raise ValueError("stop")
        except ValueError:
            pass


# --- variables and queries ---------------------------------------------------


def test_calling_a_variable_binds_it():
    """``x(5)`` binds x and returns it; ``reset`` unbinds it again"""
    x = Variable("x")
    assert x.bound is BLANK
    assert x(5) is x
    assert (x.bound, x.key(), repr(x)) == (5, 5, "x")
    x.reset()
    assert x.bound is BLANK
    assert x.name == "x"


def test_the_variable_factory_returns_one_variable_per_name():
    """An attribute or an item names one shared variable; a call creates
    new ones

    The factory is one of its own: the global ``var`` would keep ``x`` for
    the rest of the process.
    """
    factory = VariableFactory()
    assert factory.x is factory.x
    assert factory["x"] is factory.x
    assert factory("x") is not factory.x
    assert dir(factory) == ["x"]
    factory.x(1)
    factory.reset()
    assert factory.x.bound is BLANK
    created = factory(3)
    assert len({id(variable) for variable in created}) == 3
    assert [repr(variable) for variable in factory("a b")] == ["a", "b"]
    assert [repr(variable) for variable in factory(("z", "w"))] == ["z", "w"]
    assert isinstance(factory(), Variable)


def test_a_completed_query_unbinds_its_variables():
    """Control: iterated to the end, a query leaves its variable unbound"""
    w = var("W")
    assert [binds[w] for _, binds in rules.member(w, [1, 2])] == [1, 2]
    assert w.bound is BLANK


@pytest.mark.parametrize("how", ["break", "next", "exception"])
def test_an_abandoned_query_leaves_its_variables_bound(how):
    """Left at its first result by ``break``, ``next()`` or an exception, a
    query keeps its variable bound to that result, and the next query that
    uses the variable answers only that value
    """
    x = var("X")
    abandon(how, x)
    assert x.bound == 1
    assert len(list(rules.member(x, [1, 2, 3]))) == 1


@pytest.mark.parametrize("how", ["break", "next", "exception"])
@known_defects(ABANDONED)
def test_an_abandoned_query_unbinds_its_variables_desired(how):
    """However it is left, a query unbinds its variables, so the next query
    answers every value
    """
    x = var("X")
    abandon(how, x)
    assert x.bound is BLANK, "X stays bound to {!r}".format(x.bound)
    assert len(list(rules.member(x, [1, 2, 3]))) == 3


def test_a_null_query_joined_with_anything_has_no_results():
    """A NullQuery on either side of ``&`` makes the join a NullQuery"""
    x = var("X")
    assert list(NullQuery()) == []
    for query in (
        NullQuery() & rules.member(x, [1]),
        rules.member(x, [1]) & NullQuery(),
    ):
        assert isinstance(query, NullQuery)
        assert list(query) == []


# --- rule options ------------------------------------------------------------


def test_a_restricted_option_rejects_a_value_outside_it():
    """``pairs("c", V)`` is a NullQuery; ``pairs("a", V)`` answers 1 and 2"""
    v = var("V")
    assert isinstance(pairs("c", v), NullQuery)
    assert bindings(pairs("c", v), v) == []
    assert bindings(pairs("a", v), v) == [(1,), (2,)]


def test_a_set_option_accepts_a_value_outside_it():
    """``set_options_in_rule`` only lists the values explored when the
    argument is unbound; a bound value outside them still runs the rule
    """
    v = var("V")
    assert bindings(explored("z", v), v) == [(1,), (2,)]


def test_a_join_narrows_an_explored_option():
    """K bound by the left side of ``&`` selects one option, or none"""
    k, v = var("K V")
    assert bindings(rules.member(k, ["b"]) & pairs(k, v), k, v) == [("b", 1), ("b", 2)]
    assert bindings(rules.member(k, ["c"]) & pairs(k, v), k, v) == []


@OPTION_RULES
def test_an_unbound_option_is_bound_only_on_the_first_result_of_each_value(rule):
    """With K unbound the rule explores a and b, but from the second result
    of each value on, K is BLANK in the binds
    """
    k, v = var("K V")
    assert bindings(rule(k, v), k, v) == [("a", 1), (BLANK, 2), ("b", 1), (BLANK, 2)]


@OPTION_RULES
@known_defects(OPTION_BINDING)
def test_an_unbound_option_is_bound_on_every_result_desired(rule):
    """Every result binds K to the value of the option that produced it:
    the product of the options a and b with member's 1 and 2
    """
    k, v = var("K V")
    rows = bindings(rule(k, v), k, v)
    unbound = sum(1 for row in rows if row[0] is BLANK)
    assert not unbound, "{} results bind no K".format(unbound)
    assert rows == [("a", 1), ("a", 2), ("b", 1), ("b", 2)]


# --- model rules -------------------------------------------------------------


def test_hasattr_on_a_model_rule_raises_key_error():
    """``hasattr``, ``getattr`` with a default and doctest's finder expect
    AttributeError for a missing attribute; a model rule raises KeyError

    Its own attributes still work: ``dir`` lists them, and each one is the
    column of the model.
    """
    rule = patterns.code_component
    with pytest.raises(KeyError, match="nope"):
        hasattr(rule, "nope")
    with pytest.raises(KeyError, match="nope"):
        getattr(rule, "nope", None)
    with pytest.raises(KeyError, match="__wrapped__"):
        doctest.DocTestFinder().find(pattern_models)
    assert "first_char_line" in dir(rule)
    assert rule.first_char_line is CodeComponent.m.first_char_line


@known_defects(GETATTR)
def test_a_model_rule_answers_hasattr_and_doctest_desired():
    """A missing attribute of a model rule is an AttributeError, so
    ``hasattr`` answers False and doctest can search ``patterns.models``
    """
    rule = patterns.code_component
    assert hasattr(rule, "nope") is False
    assert getattr(rule, "nope", None) is None
    assert isinstance(doctest.DocTestFinder().find(pattern_models), list)


def test_a_model_rule_documents_its_prolog_attributes(two_trial_project):
    """The docstring of ``code_component`` is its Prolog head, whose
    attributes are the columns of the table, in the table's order
    """
    columns = [
        row["name"]
        for row in two_trial_project.query("PRAGMA table_info(code_component)")
    ]
    rule = patterns.code_component
    assert rule.__doc__ == "code_component({})".format(", ".join(columns))
    assert dir(rule) == sorted(columns)


@TRIALS
def test_a_model_rule_matches_the_rows_of_its_table(connected_two_trials, number):
    """``activation(T, Id, Name)`` answers the activations of trial T, and
    only them: both trials ran the same script, so a rule that ignored T
    would answer every row twice
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    expected = sql_rows(
        project, "SELECT id, name FROM activation WHERE trial_id = ?", trial
    )
    identifier, name = var("Id Name")
    assert_rows(
        lambda: bindings(
            patterns.activation(trial, identifier, name), identifier, name
        ),
        expected,
    )


@TRIALS
def test_a_model_rule_with_a_repeated_variable_matches_equal_columns(
    connected_two_trials, number
):
    """``code_component(T, Z, first_char_line=Z)`` answers the components
    whose id equals their first line
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    expected = sql_rows(
        project,
        "SELECT id FROM code_component WHERE trial_id = ? AND id = first_char_line",
        trial,
    )
    total = sql_rows(project, "SELECT id FROM code_component WHERE trial_id = ?", trial)
    assert 0 < len(expected) < len(total), "the case does not filter"
    z = var("Z")
    assert_rows(
        lambda: bindings(patterns.code_component(trial, z, first_char_line=z), z),
        expected,
    )


@TRIALS
def test_a_model_rule_accepts_a_sqlalchemy_condition(connected_two_trials, number):
    """A SQLAlchemy expression in place of an argument filters the rows"""
    project = connected_two_trials
    trial = trial_id(project, number)
    expected = sql_rows(
        project,
        "SELECT id FROM code_component WHERE trial_id = ? AND first_char_line > 40",
        trial,
    )
    assert expected, "no component after line 40"
    rule = patterns.code_component
    q = var("Q")
    assert_rows(
        lambda: bindings(rule(trial, q, rule.first_char_line > 40), q), expected
    )


@TRIALS
def test_a_join_binds_the_shared_variable(connected_two_trials, number):
    """``evaluation(...) & code_component(...)`` joins on the shared
    variable, and a variable whose name starts with ``_`` stays out of the
    binds
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    expected = sql_rows(
        project,
        "SELECT evaluation.id FROM evaluation "
        "JOIN code_component ON code_component.trial_id = evaluation.trial_id"
        " AND code_component.id = evaluation.code_component_id "
        "WHERE evaluation.trial_id = ? AND code_component.name = 'csv_read'",
        trial,
    )
    assert expected, "no evaluation of csv_read"
    code, evaluation = var("_code E")
    query = patterns.evaluation(
        trial, evaluation, code_component_id=code
    ) & patterns.code_component(trial, code, "csv_read")
    results = [dict(binds) for _, binds in query]
    assert all(set(binds) == {evaluation} for binds in results), (
        "binds other than E: {}".format(results)
    )
    assert collections.Counter(
        (binds[evaluation],) for binds in results
    ) == collections.Counter(expected)


@TRIALS
def test_a_function_rule_accepts_a_model_rule_and_keywords(
    connected_two_trials, number
):
    """``name`` takes the model as its name, as the model rule itself or
    as a keyword, and its other arguments as keywords too
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    expected = sql_rows(
        project, "SELECT id, name FROM file_access WHERE trial_id = ?", trial
    )
    assert expected, "no file access"
    calls = {
        "model rule": lambda i, n: rules.name(trial, patterns.access, i, n),
        "keywords": lambda i, n: rules.name(trial, model="access", id=i, name=n),
        "name": lambda i, n: rules.name(trial, "access", i, n),
    }
    for label, call in calls.items():
        identifier, name = var("Id Name")
        rows = bindings(call(identifier, name), identifier, name)
        assert collections.Counter(rows) == collections.Counter(expected), label


@TRIALS
def test_a_model_rule_with_an_unknown_keyword_fails_on_its_first_row(
    connected_two_trials, number
):
    """A keyword that is not an attribute of the rule (``start`` for
    ``activation``, whose attribute is ``start_checkpoint``) becomes the
    attribute BLANK: a variable raises KeyError(BLANK) when the first row
    binds it, and a value raises TypeError when the SQL query is built,
    before any row
    """
    trial = trial_id(connected_two_trials, number)
    with pytest.raises(KeyError) as caught:
        list(patterns.activation(trial, var("I"), start=var("S")))
    assert caught.value.args == (BLANK,)
    with pytest.raises(TypeError, match="not 'Blank'"):
        list(patterns.activation(trial, var("I"), start=0.1))
