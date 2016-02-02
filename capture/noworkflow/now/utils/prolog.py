# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Helpers for Prolog Extraction"""

import textwrap

from datetime import datetime


class PrologDescription(object):

    def __init__(self, name, attributes):
        self.name = name
        self.attributes = attributes

    def comment(self):
        """Return prolog comment"""
        return textwrap.dedent(
            """
            %
            % FACT: {}
            %
            """
        ).format(repr(self))

    def dynamic(self):
        """Return prolog dynamic clause"""
        return ":- dynamic({0.name}/{1}).".format(self, len(self.attributes))

    def retract(self, trial_id):
        """Return prolog retract for trial"""
        return "retract({0.name}({1}))".format(
            self, ', '.join(x.retract(trial_id) for x in self.attributes)
        )

    def fact(self, obj):
        """Convert obj to prolog fact"""
        return "{0.name}({1}).".format(
            self, ', '.join(x.fact(obj) for x in self.attributes)
        )

    def empty(self):
        """Return empty fact"""
        return "{0.name}({1}).".format(
            self, ', '.join(x.empty() for x in self.attributes)
        )

    def __repr__(self):
        return "{0.name}({1}).".format(
            self, ', '.join(x.name for x in self.attributes)
        )


class PrologAttribute(object):

    def __init__(self, name, fn=None, attr_name=None):
        self.name = name
        self.attr_name = self.name if attr_name is None else attr_name
        self.fn = fn

    def value(self, obj):
        """Return attribute self.attr_name of obj"""
        if self.fn:
            return self.fn(obj)
        attr = self.attr_name
        while "." in attr:
            attr0, attr = attr.split(".", 1)
            obj = getattr(self, attr0)
        return getattr(obj, attr)

    def retract(self, trial_id):
        """Attribute does not identify fact. Retrun _"""
        return "_"

    def fact(self, obj):
        """Return attribute self.attr_name of obj as str"""
        return str(self.value(obj))

    def empty(self):
        """Represent empty attribute"""
        return "0"


class PrologTrial(PrologAttribute):

    def retract(self, trial_id):
        """Trial Attribute identifies fact. Retrun trial_id"""
        return str(trial_id)


class PrologRepr(PrologAttribute):

    def fact(self, obj):
        """Return attribute self.attr_name of obj as escaped repr"""
        result = repr(self.value(obj))
        if result[1] in ('"', "'"):
            result = result[1:]
        return result


class PrologTimestamp(PrologAttribute):

    def fact(self, obj):
        """Return attribute self.attr_name of obj as formatted timestamp"""
        time = self.value(obj)
        if not time:
            return -1
        epoch = datetime(1970, 1, 1)
        return str((time - epoch).total_seconds())


class PrologNullable(PrologAttribute):

    def fact(self, obj):
        """Replace None by nil if attribute self.attr_name of obj"""
        value = self.value(obj)
        return str(value) if value else "nil"


class PrologNullableRepr(PrologRepr):

    def fact(self, obj):
        """Return attribute self.attr_name of obj as escaped repr"""
        if not self.value(obj):
            return "nil"
        return super(PrologNullableRepr, self).fact(obj)
