# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Helpers for Prolog Extraction"""


from datetime import datetime
from string import ascii_letters


class PrologDescription(object):
    """Prolog Description. Generate comments, facts, dynamic, and retract"""

    def __init__(self, name, attributes, description=""):
        self.name = name
        self.attributes = attributes
        self.description = description.split("\n")

    def comment(self):
        """Return prolog comment"""
        result = []
        result.append("")
        result.append("%")
        result.append("% FACT DEFINITION: {}".format(repr(self)))
        if len(self.description) > 1 or self.description[0]:
            result.append("% DESCRIPTION: {}".format(self.description[0]))
            for desc in self.description[1:]:
                result.append("%              {}".format(desc))
        result.append("%")
        result.append("")
        return "\n".join(result)

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
            self, ', '.join(x.variable() for x in self.attributes)
        )


class PrologAttribute(object):
    """Represent a single attribute"""

    def __init__(self, name, fn=None, attr_name=None, link=None):
        self.name = name
        self.attr_name = self.name if attr_name is None else attr_name
        self.func = fn
        self.link = link

    def variable(self):
        return "".join(x.title() for x in self.name.split("_"))

    def value(self, obj):
        """Return attribute self.attr_name of obj"""
        if self.func:
            return self.func(obj)
        attr = self.attr_name
        while "." in attr:
            attr0, attr = attr.split(".", 1)
            obj = getattr(obj, attr0)
        return getattr(obj, attr)

    def retract(self, trial_id):                                                 # pylint: disable=unused-argument, no-self-use
        """Attribute does not identify fact. Retrun _"""
        return "_"

    def fact(self, obj):
        """Return attribute self.attr_name of obj as str"""
        return str(self.value(obj))

    def empty(self):                                                             # pylint: disable=no-self-use
        """Represent empty attribute"""
        return "0"


class PrologTrial(PrologAttribute):
    """Represent Trial id attribute, used for retract"""

    def retract(self, trial_id):
        """Trial Attribute identifies fact. Retrun trial_id"""
        return str(trial_id)


class PrologRepr(PrologAttribute):
    """Represent an attribute that should be written with quotes"""

    def fact(self, obj):
        """Return attribute self.attr_name of obj as escaped repr"""
        value = self.value(obj)
        if not isinstance(value, str):
            value = repr(value)

        if len(value) > 1:
            if value[0] in ascii_letters and value[1] in ('"', "'"):
                value = value[1:]
            if value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]

        return "'{}'".format(value.replace("'", "''"))


class PrologTimestamp(PrologAttribute):
    """Represent a timestamp"""

    use_nil = False

    def fact(self, obj):
        """Return attribute self.attr_name of obj as formatted timestamp"""
        if PrologTimestamp.use_nil:
            return "nil"
        time = self.value(obj)
        if not time:
            return -1
        epoch = datetime(1970, 1, 1)
        return str((time - epoch).total_seconds())


class PrologNullable(PrologAttribute):
    """Represent an attribute that accepts nil as value"""

    def fact(self, obj):
        """Replace None by nil if attribute self.attr_name of obj"""
        value = self.value(obj)
        return str(value) if value else "nil"


class PrologNullableRepr(PrologRepr):
    """Represent an attribute that accepts nil as value and requires quotes"""

    def fact(self, obj):
        """Return attribute self.attr_name of obj as escaped repr"""
        if not self.value(obj):
            return "nil"
        return super(PrologNullableRepr, self).fact(obj)
