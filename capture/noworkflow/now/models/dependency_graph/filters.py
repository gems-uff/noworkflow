# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Filters for dependency graph"""

from .node_types import AccessNode, ValueNode, ClusterNode
from .node_types import EvaluationNode


class Filter(object):
    """Filter that accepts all nodes"""
    # pylint: disable=too-few-public-methods
    def __contains__(self, item):
        if isinstance(item, tuple):
            (source, target), attrs = item
            same_id = source.node_id == target.node_id
            if same_id and not isinstance(source, ValueNode):
                return False
            isargument = attrs.get("_type").startswith("argument")
            if isinstance(source, ClusterNode) and isargument:
                return False
        return True

    def __getattr__(self, attr):
        """By default, all attrs return true.
        Use this information to flag what the filter hides"""
        return True

    @property
    def before_synonym(self):
        """Apply filter before synonymer"""
        return self

    @property
    def after_synonym(self):
        """Apply filter after synonymer"""
        return self

    @property
    def dependencies(self):
        """Apply filter for dependencies pairs"""
        return self


AcceptAllNodesFilter = Filter


class FilterValuesOut(AcceptAllNodesFilter):
    """Filter that ignores values"""
    # pylint: disable=too-few-public-methods
    def __contains__(self, node):
        if isinstance(node, ValueNode):
            return False
        return super(FilterValuesOut, self).__contains__(node)

    show_values = False


class FilterAccessesOut(AcceptAllNodesFilter):
    """Filter that ignores accesses"""
    # pylint: disable=too-few-public-methods
    def __contains__(self, node):
        if isinstance(node, AccessNode):
            return False
        return super(FilterAccessesOut, self).__contains__(node)

    show_accesses = False


class FilterExternalAccessesOut(AcceptAllNodesFilter):
    """Filter that ignores external accesses"""
    # pylint: disable=too-few-public-methods
    def __contains__(self, node):
        if isinstance(node, AccessNode):
            return node.access.is_internal
        return super(FilterExternalAccessesOut, self).__contains__(node)

    show_external_accesses = False


class FilterInternalsOut(AcceptAllNodesFilter):
    """Filter that ignores evaluations that start with _"""
    # pylint: disable=too-few-public-methods
    def __contains__(self, node):
        if isinstance(node, EvaluationNode):
            return not node.name.startswith("_")
        return super(FilterInternalsOut, self).__contains__(node)


class _JoinedFilterAttribute(object):
    """Joined attribute"""
    # pylint: disable=too-few-public-methods
    def __init__(self, all_filters, attr):
        self.all_filters = all_filters
        self.attr = attr

    def __contains__(self, node):
        """Check if any subfilter does not contain node"""
        for filter_ in self.all_filters:
            if node not in getattr(filter_, self.attr):
                return False
        return True


class JoinedFilter(Filter):
    """Filter that joins other filters"""

    @classmethod
    def create(cls, *args):
        """Named constructor. Might return a joined synonymer or not"""
        if not args:
            return FilterValuesOut()
        elif len(args) == 1:
            return args[0]

        return cls(*args)

    def __init__(self, *args):
        self._filters = args
        super(JoinedFilter, self).__init__()
        self._before_synonym = _JoinedFilterAttribute(args, "before_synonym")
        self._after_synonym = _JoinedFilterAttribute(args, "after_synonym")
        self._dependencies = _JoinedFilterAttribute(args, "dependencies")

    def __getattr__(self, attr):
        """By default, all attrs return true.
        Use this information to flag what the filter hides"""
        for filter_ in self._filters:
            if not getattr(filter_, attr):
                return False
        return True

    def __contains__(self, node):
        """Check if any subfilter does not contain node"""
        for filter_ in self._filters:
            if node not in filter_:
                return False
        return True

    @property
    def before_synonym(self):
        """Apply filter before synonymer"""
        return self._before_synonym

    @property
    def after_synonym(self):
        """Apply filter after synonymer"""
        return self._after_synonym

    @property
    def dependencies(self):
        """Apply filter for dependencies pairs"""
        return self._dependencies
