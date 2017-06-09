# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Pattern Matching Queries"""
# pylint: disable=invalid-name

from collections import OrderedDict, defaultdict
from itertools import zip_longest, chain
from sqlalchemy.sql.expression import and_, BinaryExpression
from future.utils import viewitems, viewvalues
from ..persistence import relational
from ..persistence.models.base import proxy
from ..persistence.models import Activation
from ..persistence.models import Argument
from ..persistence.models import CodeBlock
from ..persistence.models import CodeComponent
from ..persistence.models import Compartment
from ..persistence.models import Dependency
from ..persistence.models import EnvironmentAttr
from ..persistence.models import Evaluation
from ..persistence.models import FileAccess
from ..persistence.models import Module
from ..persistence.models import Tag
from ..persistence.models import Trial
from ..persistence.models import Value


BLANK = object()


class Variable(object):
    """Variable for joining matches"""
    # pylint: disable=too-few-public-methods
    def __init__(self):
        self.results = set()
        self.bound = BLANK

    def reset(self):
        """Reset variable"""
        self.__init__()

    def __call__(self, val):
        """Binds p to value"""
        self.bound = val
        return self


class Query(object):
    """Pattern matching query"""
    # pylint: disable=too-few-public-methods

    def __and__(self, other):
        return GenericJoinedQuery(self, other)


class BoundQuery(Query):
    """BoundQuery that supports joins"""
    # pylint: disable=too-few-public-methods

    def __init__(self, model_rule, conditions):
        self.conditions = conditions
        self.model_rule = model_rule

    def _get(self, attr):
        """Get attribute from model"""
        return getattr(self.model_rule, attr)

    def _eq(self, attr, val):
        """Get equal condition or custom BinaryExpression"""
        if isinstance(value, BinaryExpression):
            return val
        return self._get(attr) == val

    def _result_attr(self, result, attr):
        """Get result attribute"""
        return self.model_rule.get_proxy_attr(result, attr)

    def __iter__(self):
        """Iterate on results. Support Variables"""
        patterns = {}
        reverse_patterns = defaultdict(list)
        session = relational.session
        conditions = []
        for attr, val in self.conditions:
            if isinstance(val, Variable):
                if val.bound is BLANK:
                    patterns[attr] = val
                    reverse_patterns[val].append(attr)
                    continue
                else:
                    val = val.bound
            if val is BLANK:
                continue
            conditions.append(self._eq(attr, val))
        for attrs in viewvalues(reverse_patterns):
            attr0 = attrs[0]
            for attr in attrs:
                if attr != attr0:
                    conditions.append(self._eq(attr0, self._get(attr)))

        sql_result = session.query(self.model_rule.get_model()).filter(
            and_(*conditions)
        )

        binds = set()
        for sql_model in sql_result:
            result = proxy(sql_model)
            for attr, pattern in viewitems(patterns):
                temp = self._result_attr(result, attr)
                pattern.results.add(temp)
                pattern.bound = temp
                binds.add(pattern)
            yield result

        for pattern in binds:
            pattern.bound = BLANK


class GenericJoinedQuery(Query):
    """Joined BoundQuery"""

    def __init__(self, bound_a, bound_b):
        self.bound_a = bound_a
        self.bound_b = bound_b

    def __iter__(self):
        """Iterate on results. Support Variables"""
        for result_a in self.bound_a:
            for result_b in self.bound_b:
                if not isinstance(result_a, tuple):
                    result_a = (result_a,)
                if not isinstance(result_b, tuple):
                    result_b = (result_b,)
                yield tuple(chain(result_a, result_b))


class ModelRule(object):
    """Pattern matching rule for model"""
    # pylint: disable=too-few-public-methods

    def __init__(self, model):
        self._model = model
        self._prolog = model.prolog_description
        self.__doc__ = "{}({})".format(
            self._prolog.name,
            ', '.join(
                attr.name
                for attr in self._prolog.attributes
            )
        )
        self._names = OrderedDict(
            (attr.name, attr.attr_name)
            for attr in self._prolog.attributes
        )

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
        return BoundQuery(self, conditions)

    def __getattr__(self, attr):
        return getattr(self._model.m, self._names[attr])

    def __dir__(self):
        return list(self._names)


activation = ModelRule(Activation)
argument = ModelRule(Argument)
code_block = ModelRule(CodeBlock)
code_component = ModelRule(CodeComponent)
compartment = ModelRule(Compartment)
dependency = ModelRule(Dependency)
environment = ModelRule(EnvironmentAttr)
evaluation = ModelRule(Evaluation)
access = ModelRule(FileAccess)
module = ModelRule(Module)
tag = ModelRule(Tag)
trial = ModelRule(Trial)
value = ModelRule(Value)
