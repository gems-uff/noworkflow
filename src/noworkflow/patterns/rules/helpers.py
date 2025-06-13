# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Helpers for rule implementation"""

from copy import copy
from itertools import product

from ..machinery import Variable, BLANK, var, create_rule


@create_rule
def between(low, high, value, _binds):
    """Check if value is between low and high"""
    if isinstance(low, Variable) or isinstance(high, Variable):
        raise TypeError("Low and High should be values")
    if isinstance(value, Variable):
        for individual in range(low, high + 1):
            _match(value, individual, _binds)
            yield individual, _binds
            value.reset()
            del _binds[value]
    elif low <= value <= high:
        yield value, _binds


@create_rule
def once(query, _binds):
    """Yields a single result from query"""
    for result, binds in _apply(_binds, query):
        yield result, binds
        return


@create_rule
def member(value, values, _binds):
    """Check if value is member of values"""
    for value_item in _get_value(values):
        bound = isinstance(value, Variable) and value.bound is not BLANK
        if _match(value, value_item, _binds):
            yield _get_value(value), _binds
        if isinstance(value, Variable) and not bound:
            value.reset()
            del _binds[value]

def _get_value(value):
    """Get value from variable"""
    if isinstance(value, Variable) and value.bound is not BLANK:
        return value.bound
    return value


def _match(value1, value2, _binds):
    """Match values"""
    if value1 is BLANK or value2 is BLANK:
        return True
    if isinstance(value1, Variable):
        if value1.bound is BLANK:
            temp = _get_value(value2)
            _binds[value1] = temp
            value1.bound = temp
            return True
        else:
            value1 = value1.bound
    if isinstance(value2, Variable):
        if value2.bound is BLANK:
            temp = _get_value(value1)
            _binds[value2] = temp
            value2.bound = temp
            return True
        else:
            value2 = value2.bound
    return value1 == value2


def _create_list(element, size):
    """Create list for element of specific size"""
    if isinstance(element, list):
        if len(element) != size:
            return None
        return element
    elif isinstance(element, Variable):
        return var(size)
    elif element is BLANK:
        return [BLANK] * size
    return None


def _list_to_variable(element, elist, _binds):
    """Convert list to a single bound element"""
    if not isinstance(element, Variable):
        return
    values = []
    for variable in elist:
        values.append(_binds[variable])
        del _binds[variable]
    _match(element, values, _binds)


def _list_matcher(single_func, _binds, *params):
    """Match list or single param for function"""
    # pylint: disable=too-many-locals
    if all(not isinstance(par, list) for par in params):
        for result in single_func(*params):
            yield result
        return
    # There is at least one list. Let's find it
    the_list = None
    for par in params:
        if isinstance(par, list):
            the_list = par
            break
    # Transform params to list to match cardinality
    lists = []
    for par in params:
        par_to_list = _create_list(par, len(the_list))
        if par_to_list is None:
            return
        lists.append(par_to_list)

    # Match individual parts
    answers = [[] for _ in range(len(the_list))]
    for i, new_params in enumerate(zip(*lists)):
        failed = True
        for component, binds in single_func(*new_params):
            failed = False
            answers[i].append((component, copy(binds)))
        if failed:
            return

    # Create results
    for answer in product(*answers):
        result = []
        result_binds = copy(_binds)
        for res, binds in answer:
            result.append(res)
            result_binds.update(binds)
        for param, param_list in zip(params, lists):
            _list_to_variable(param, param_list, result_binds)
        yield result, result_binds

def _apply(_binds, query):
    """Apply query and update original binds"""
    for result, binds, in query:
        new_binds = copy(_binds)
        new_binds.update(binds)
        yield result, new_binds


class UniversalSet(set):
    """Intersect with this set should return the other set"""
    def __and__(self, other):
        return other


def _bagof_append_sort(metaquery, ids, lines, _binds):
    """Get all sorted lines that matches the ids"""
    match_any = (Variable, type(BLANK))
    ids_result = set()
    lines_result = set()
    ids_list = ids
    lines_set = UniversalSet()
    if isinstance(ids, match_any):
        ids_list = [var("_id")]
    if not isinstance(lines, match_any):
        lines_set = set(lines)
    if not isinstance(ids_list, list):
        return

    for the_id in ids_list:
        first, last = var("_first _last")
        query = metaquery(the_id, first, last)
        for _, _ in _apply(_binds, query):
            for line in lines_set & set(range(first.bound, last.bound + 1)):
                ids_result.add(_get_value(the_id))
                lines_result.add(line)

    ids_result = sorted(ids_result)
    lines_result = sorted(lines_result)
    if not _match(ids, ids_result, _binds):
        return
    if not _match(lines, lines_result, _binds):
        return
    yield lines_result, _binds
