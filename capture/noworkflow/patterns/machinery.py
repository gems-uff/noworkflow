# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Pattern Matching Machinery"""
# pylint: disable=invalid-name

import inspect
from collections import OrderedDict, defaultdict
from copy import copy
from itertools import chain, product

from future.utils import viewitems, viewvalues
from sqlalchemy.sql.expression import and_, ColumnElement

from ..now.persistence import relational
from ..now.utils.cross_version import zip_longest
from ..now.persistence.models.base import proxy


class Blank(object):
    """Singleton object to represent _"""
    # pylint: disable=too-few-public-methods
    def __repr__(self):
        return "_"


class Variable(object):
    """Variable for joining matches"""
    # pylint: disable=too-few-public-methods
    def __init__(self, name=None):
        self.results = set()
        self.bound = BLANK
        self.name = str(id(self) if name is None else name)
        self.temp = self.name.startswith("_")

    def reset(self):
        """Reset variable"""
        self.__init__(self.name)

    def __call__(self, val):
        """Binds variable to value"""
        self.bound = val
        return self

    def __repr__(self):
        return self.name


class VariableFactory(object):
    """Create variables"""
    # pylint: disable=too-few-public-methods

    def __init__(self):
        self.known = {}

    def __getitem__(self, item):
        if item not in self.known:
            self.known[item] = Variable(item)
        return self.known[item]

    def __getattr__(self, attr):
        return self[attr]

    def __dir__(self):
        return list(self.known)

    def reset(self):
        """Reset all variables"""
        for _, value in viewitems(self.known):
            value.reset()

    def __call__(self, names_or_count=None):
        """Create variables

        Usage:
        >>> var = VariableFactory()
        >>> a, b, c = var(3)
        >>> isinstance(a, Variable)
        True
        >>> d = var("d")
        >>> isinstance(d, Variable)
        True
        >>> e = var()
        >>> isinstance(e, Variable)
        True
        >>> x, y = var("x y")
        >>> isinstance(x, Variable)
        True
        >>> z, w = var(("z", "w"))
        >>> isinstance(w, Variable)
        True
        """
        if names_or_count is None:
            return Variable()
        if isinstance(names_or_count, int):
            return [Variable() for _ in range(names_or_count)]
        if isinstance(names_or_count, str):
            names = names_or_count.split(" ")
            if len(names) == 1:
                return Variable(names[0])
        else:
            # Iterable
            names = names_or_count

        return [Variable(name) for name in names]


class BoundQuery(object):
    """Generic pattern matching query"""

    def __init__(self):
        self.patterns = {}
        self.binds = {}
        self.reverse_patterns = defaultdict(list)

    def __and__(self, other):
        if isinstance(self, NullQuery) or isinstance(other, NullQuery):
            return NullQuery()
        return GenericJoinedQuery(self, other)

    def reset_patterns(self):
        """Reset pattern mappings"""
        self.patterns = {}
        self.reverse_patterns = defaultdict(list)

    def process_value(self, attr, val):
        """Process variable pattern or value"""
        if isinstance(val, Variable):
            if val.bound is BLANK:
                self.patterns[attr] = val
                self.reverse_patterns[val].append(attr)
            return val.bound
        return val

    def get_bound(self, result, attr):
        """Get bound value in result"""
        # pylint: disable=no-self-use, unused-argument
        return BLANK

    def iterate(self):
        """Abstract generator"""
        # pylint: disable=no-self-use
        yield

    def __iter__(self):
        self.binds.clear()
        for result in self.iterate():
            for attr, pattern in viewitems(self.patterns):
                temp = self.get_bound(result, attr)
                pattern.results.add(temp)
                pattern.bound = temp
                self.binds[pattern] = temp
            yield result, {k: v for k, v in viewitems(self.binds) if not k.temp}

        for pattern in self.binds:
            pattern.bound = BLANK


class NullQuery(BoundQuery):
    """Null query that has no results"""
    def iterate(self):
        """Null query"""
        #pylint: disable=unreachable
        return
        yield


class RuleQuery(BoundQuery):
    """Call rules function for all possibilities of unbound_options"""

    def __init__(self, func, args, values, has_binds, unbound_options):
        # pylint: disable=too-many-arguments
        super(RuleQuery, self).__init__()
        self.func = func
        self.args = args
        self.values = values
        self.has_binds = has_binds
        self.unbound_options = unbound_options

    def apply_function(self, values):
        """Apply function to values"""
        kwargs = {}
        if self.has_binds:
            kwargs["_binds"] = self.binds
        func_result = self.func(*values, **kwargs)
        if func_result is not None:
            for result, binds in func_result:
                if binds is not self.binds:
                    self.binds.update(binds)
                yield result

                for pattern in self.binds:
                    pattern.bound = BLANK
        for pattern in self.binds:
            pattern.bound = BLANK


    def get_bound(self, result, attr):
        """Get bound value in result"""
        if attr in self.patterns:
            return self.patterns[attr].bound
        return BLANK


    def final_value(self, current):
        """Transform value"""
        # pylint: disable=no-self-use
        if current is BLANK:
            return var("_")
        if isinstance(current, Variable) and current.bound is not BLANK:
            return current.bound
        return current

    def prepare_values(self, order, bind):
        """Prepare values for exploration"""
        self.reset_patterns()
        new_values = copy(self.values)
        for i, arg in enumerate(order):
            prevalue = new_values[self.args[arg]]
            val = self.process_value(arg, prevalue)
            if val is not BLANK and val != bind[i]:
                # Variable bound to a different value
                return None
            elif val != bind[i] and isinstance(prevalue, Variable):
                prevalue.bound = bind[i]
                self.binds[prevalue] = bind[i]
            if bind[i] is not BLANK:
                new_values[self.args[arg]] = bind[i]
        return map(self.final_value, new_values)

    def iterate(self):
        """generator"""
        order = list(self.unbound_options)
        explored = False
        exploration = product(*(self.unbound_options[x] for x in order))
        for bind in exploration:
            explored = True
            new_values = self.prepare_values(order, bind)
            if new_values is not None:
                for result in self.apply_function(new_values):
                    yield result
        if not explored:
            for result in self.apply_function(self.values):
                yield result


class ModelQuery(BoundQuery):
    """Use SQLAlchemy to run query"""

    def __init__(self, model_rule, conditions):
        super(ModelQuery, self).__init__()
        self.conditions = conditions
        self.model_rule = model_rule

    def _get(self, attr):
        """Get attribute from model"""
        return getattr(self.model_rule, attr)

    def _eq(self, attr, val):
        """Get equal condition or custom ColumnElement"""
        if isinstance(val, ColumnElement):
            return val
        return self._get(attr) == val

    def get_bound(self, result, attr):
        """Get result attribute"""
        return self.model_rule.get_proxy_attr(result, attr)

    def iterate(self):
        """Iterate on query generation"""
        session = relational.session
        conditions = []
        for attr, val in self.conditions:
            val = self.process_value(attr, val)
            if val is not BLANK:
                conditions.append(self._eq(attr, val))
        for attrs in viewvalues(self.reverse_patterns):
            attr0 = attrs[0]
            for attr in attrs:
                if attr != attr0:
                    conditions.append(self._eq(attr0, self._get(attr)))

        sql_result = session.query(self.model_rule.get_model()).filter(
            and_(*conditions)
        )
        for sql_model in sql_result:
            yield proxy(sql_model)


class GenericJoinedQuery(BoundQuery):
    """Joined BoundQuery"""

    def __init__(self, bound_a, bound_b):
        super(GenericJoinedQuery, self).__init__()
        self.bound_a = bound_a
        self.bound_b = bound_b

    def iterate(self):
        """Iterate on query generation"""
        for result_a, binds_a in self.bound_a:
            for result_b, self.binds in self.bound_b:
                if not isinstance(result_a, tuple):
                    result_a = (result_a,)
                if not isinstance(result_b, tuple):
                    result_b = (result_b,)
                self.binds.update(binds_a)
                yield tuple(chain(result_a, result_b))


class ModelRule(object):
    """Pattern matching rule for model"""
    # pylint: disable=too-few-public-methods

    def __init__(self, model):
        self._model = model
        self._prolog = model.prolog_description
        self.__doc__ = "{}({})".format(
            self.get_name(),
            ', '.join(
                attr.name
                for attr in self._prolog.attributes
            )
        )
        self._names = OrderedDict(
            (attr.name, attr.attr_name)
            for attr in self._prolog.attributes
        )

    def get_name(self):
        """Return Model name"""
        return self._prolog.name

    def get_model(self):
        """Return SQLAlchemy model for this rule"""
        return self._model.m

    def get_proxy_attr(self, model, attr):
        """Get attribute value of proxy model"""
        return getattr(model, self._names[attr])

    def __call__(self, *args, **kwargs):
        arg_iter = zip_longest(viewvalues(self._names), args, fillvalue=BLANK)
        conditions = [
            (attr_name, value)
            for attr_name, value in arg_iter
            if value is not BLANK
        ] + [
            (self._names.get(name, BLANK), value)
            for name, value in viewitems(kwargs)
        ]
        return ModelQuery(self, conditions)

    def __getattr__(self, attr):
        return getattr(self._model.m, self._names[attr])

    def __dir__(self):
        return list(self._names)


class FunctionRule(object):
    """Rule function"""
    # pylint: disable=too-few-public-methods

    def __init__(self, func):
        self.func = func
        all_args = inspect.getargs(func.__code__).args
        self.args = OrderedDict(
            (arg, i)
            for i, arg in enumerate(all_args)
        )
        self.has_binds = False
        if "_binds" in self.args:
            self.has_binds = True
            del self.args["_binds"]
        self.options = {}
        self.restrictions = {}
        self.__doc__ = "{}({})".format(func.__name__, ", ".join(self.args))
        self.prolog = []

    def _process_val(self, val):
        """If bound value is ModelRule, returns its name"""
        # pylint: disable=no-self-use
        if isinstance(val, ModelRule):
            return val.get_name()
        return val

    def __call__(self, *args, **kwargs):
        values = [BLANK] * len(self.args)
        for i, val in enumerate(args):
            values[i] = self._process_val(val)
        for arg, val in viewitems(kwargs):
            values[self.args[arg]] = self._process_val(val)
        unbound_options = {}
        for arg, options in viewitems(self.options):
            bound_value = values[self.args[arg]]
            restrictions = self.restrictions.get(arg)
            if bound_value is BLANK or isinstance(bound_value, Variable):
                unbound_options[arg] = options
            elif restrictions and bound_value not in restrictions:
                return NullQuery()
        return RuleQuery(self.func, self.args, values, self.has_binds, unbound_options)


def create_rule(func):
    """Create rule object"""
    return FunctionRule(func)


def restrict_rule(**options):
    """Restrict domain of rule"""
    def apply_restrictions(rule):
        """Apply restrictions to rule"""
        for key, values in viewitems(options):
            rule.options[key] = values
            rule.restrictions[key] = values
        return rule
    return apply_restrictions


def set_options_in_rule(**options):
    """Add pattern to domain of rule"""
    def apply_options(rule):
        """Apply pattern options to rule"""
        for key, values in viewitems(options):
            rule.options[key] = values
        return rule
    return apply_options


def prolog_rule(line):
    """Specify prolog equivalent"""
    def specify(rule):
        """Apply restrictions to rule"""
        rule.prolog.insert(0, line)
        return rule
    return specify


BLANK = Blank()
var = VariableFactory()  # pylint: disable=invalid-name
