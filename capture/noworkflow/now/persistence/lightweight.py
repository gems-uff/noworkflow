# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight objects for storage during collection"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime

from future.utils import viewitems, viewvalues

from . import content


class ObjectStore(object):
    """Temporary storage for LW objects"""

    def __init__(self, cls):
        """Initialize Object Store


        Arguments:
        cls -- LW object class
        """
        self.cls = cls
        self.store = {}
        self.id = 0                                                              # pylint: disable=invalid-name
        self.count = 0

    def __getitem__(self, index):
        return self.store[index]

    def __delitem__(self, index):
        self.store[index] = None
        self.count -= 1

    def add(self, *args):
        """Add object using its __init__ arguments and return id"""
        self.id += 1
        self.count += 1
        self.store[self.id] = self.cls(self.id, *args)
        return self.id

    def add_object(self, *args):
        """Add object using its __init__ arguments and return object"""
        self.id += 1
        self.count += 1
        self.store[self.id] = self.cls(self.id, *args)
        return self.store[self.id]

    def dry_add(self, *args):
        """Return object that would be added by add_object
        Do not add it to storage
        """
        return self.cls(-1, *args)

    def remove(self, value):
        """Remove object from storage"""
        for key, val in viewitems(self.store):
            if val == value:
                del self.store[key]
                self.count -= 1

    def __iter__(self):
        """Iterate on objects, and not ids"""
        return viewvalues(self.store)

    def items(self):
        """Iterate on both ids and objects"""
        for key, value in viewitems(self.store):
            yield key, value

    def iteritems(self):
        """Iterate on both ids and objects"""
        for key, value in viewitems(self.store):
            yield key, value

    def values(self):
        """Iterate on objects if they exist"""
        for value in viewvalues(self.store):
            if value is not None:
                yield value

    def clear(self):
        """Remove deleted objects from storage"""
        self.store = {key: val for key, val in viewitems(self.store) if val}
        self.count = len(self.store)

    def generator(self, trial_id, partial=False):
        """Generator used for storing objects in database"""
        for obj in self.values():
            if partial and obj.is_complete():
                del self[obj.id]
            obj.trial_id = trial_id
            yield obj
        if partial:
            self.clear()

    def has_items(self):
        """Return true if it has items"""
        return bool(self.count)


def define_attrs(required, extra=[]):                                            # pylint: disable=dangerous-default-value
    """Create __slots__ by adding extra attributes to required ones"""
    slots = tuple(required + extra)
    attributes = tuple(required)

    return slots, attributes


class BaseLW:                                                                    # pylint: disable=too-few-public-methods
    """Lightweight modules base class"""

    def keys(self):
        """Return attributes that should be saved"""
        return self.attributes                                                   # pylint: disable=no-member

    def __iter__(self):
        return iter(self.attributes)                                             # pylint: disable=no-member

    def __getitem__(self, key):
        if key in self.special and getattr(self, key) == -1:                     # pylint: disable=no-member
            return None
        return getattr(self, key)


# Deployment

class ModuleLW(BaseLW):
    """Module lightweight object
    There are type definitions on lightweight.pxd
    """

    __slots__, attributes = define_attrs(
        ["id", "name", "path", "version", "code_hash"],
        ["trial_id"]
    )
    special = set()

    def __init__(self, oid, name, version, path, code_hash):                     # pylint: disable=too-many-arguments
        self.trial_id = -1
        self.id = oid                                                            # pylint: disable=invalid-name
        self.name = name
        self.version = version
        self.path = path
        self.code_hash = code_hash

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Module can always be removed from object store"""
        return True

    def __repr__(self):
        return ("Module(id={}, name={}, version={})").format(
            self.id, self.name, self.version)


class DependencyLW(BaseLW):
    """Dependency lightweight object
    There are type definitions on lightweight.pxd
    """

    __slots__, attributes = define_attrs(
        ["trial_id", "module_id"], ["id"]
    )
    special = set()

    def __init__(self, oid, module_id):
        self.trial_id = -1
        self.id = oid                                                            # pylint: disable=invalid-name
        self.module_id = module_id

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Dependency can always be removed from object store"""
        return True

    def __repr__(self):
        return ("Dependency(module_id={})").format(self.module_id)


class EnvironmentAttrLW(BaseLW):
    """EnvironmentAttr lightweight object
    There are type definitions on lightweight.pxd
    """

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "name", "value"]
    )
    special = set()

    def __init__(self, oid, name, value):
        self.trial_id = -1
        self.id = oid                                                            # pylint: disable=invalid-name
        self.name = name
        self.value = value

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """EnvironmentAttr can always be removed from object store"""
        return True

    def __repr__(self):
        return ("EnvironmentAttr(id={}, name={}, value={})").format(
            self.id, self.name, self.value)


# Definition

class DefinitionLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """Definition lightweight object
    May represent files, classes and function definitions
    There are type definitions on lightweight.pxd
    """

    __slots__, attributes = define_attrs(
        ["id", "name", "code_hash", "trial_id", "first_line", "last_line",
         "docstring"],
        ["type", "code", "parent", "namespace"],
    )
    special = set()

    def __init__(self, aid, previous_namespace, name, code, dtype, parent,       # pylint: disable=too-many-arguments
                 first_line, last_line, docstring):
        self.trial_id = -1
        self.id = aid                                                            # pylint: disable=invalid-name
        self.namespace = (
            previous_namespace +
            ("." if previous_namespace else "") +
            name
        )
        self.name = self.namespace
        self.parent = (parent if parent is not None else -1)
        self.type = dtype
        self.code = code
        self.code_hash = content.put(code.encode("utf-8"))
        self.first_line = first_line
        self.last_line = last_line
        self.docstring = docstring or ""

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """DefinitionLW can always be removed from object store"""
        return True

    def __repr__(self):
        return ("DefinitionLW(id={}, name={}, type={})").format(
            self.id, self.name, self.type)


class ObjectLW(BaseLW):
    """Object lightweight object
    There are type definitions on lightweight.pxd
    """

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "name", "type", "function_def_id"]
    )
    special = set()

    def __init__(self, oid, name, otype, function_def_id):
        self.trial_id = -1
        self.id = oid                                                            # pylint: disable=invalid-name
        self.name = name
        self.type = otype
        self.function_def_id = function_def_id

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Object can always be removed from object store"""
        return True

    def __repr__(self):
        return (
            "Object(id={}, name={}, type={}, "
            "function_def={})"
        ).format(self.id, self.name, self.type, self.function_def_id)


# Profiler

class ActivationLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """Activation lightweight object
    There are type definitions on lightweight.pxd
    """

    __slots__, attributes = define_attrs(
        ["id", "name", "line", "return_value", "start", "finish", "caller_id",
         "trial_id"],
        ["file_accesses", "context", "slice_stack", "lasti", "definition_file",
         "args", "kwargs", "starargs", "with_definition", "filename",
         "is_main", "has_parameters",
         "loops", "conditions", "permanent_conditions",
         "temp_context", "temp_line"]
    )
    special = {"caller_id"}

    def __init__(self, aid, definition_file, filename, name, line, lasti,        # pylint: disable=too-many-arguments
                 caller_id, with_definition):
        self.trial_id = aid
        self.id = aid                                                            # pylint: disable=invalid-name
        self.name = name
        self.line = line
        self.start = datetime.now()
        self.finish = None
        self.caller_id = (caller_id if caller_id else -1)
        self.return_value = None

        # Name of the script with the call
        self.filename = filename
        # Name of the script with the function definition
        self.definition_file = definition_file
        # Activation has definition or not
        self.with_definition = with_definition
        # Activation is __main__
        self.is_main = aid == 1
        # Activation has parameters. Use only for slicing!
        self.has_parameters = True

        # File accesses. Used to get the content after the activation
        self.file_accesses = []
        # Variable context. Used in the slicing lookup
        self.context = {}

        # Temporary variables
        self.temp_context = set()
        self.temp_line = None

        # Line execution stack.
        # Used to evaluate function calls before execution line
        self.slice_stack = []
        self.lasti = lasti

        self.args = []
        self.kwargs = []
        self.starargs = []

        self.loops = []
        self.conditions = []
        self.permanent_conditions = []

    def is_complete(self):
        """Activation can be removed from object store after setting finish"""
        return self.finish is not None

    def is_comprehension(self):
        """Check if activation is comprehension"""
        return self.name in [
            "<setcomp>", "<dictcomp>", "<genexpr>", "<listcomp>"
        ]

    def __repr__(self):
        return (
            "Activation(id={}, line={}, lasti={}, filename={}, "
            " name={}, start={}, finish={}, return={}, caller_id={})"
        ).format(
            self.id, self.line, self.lasti, self.filename, self.name,
            self.start, self.finish, self.return_value, self.caller_id
        )


class ObjectValueLW(BaseLW):
    """ObjectValue lightweight object
    There are type definitions on lightweight.pxd
    """

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "name", "value", "type", "function_activation_id"]
    )
    special = set()

    def __init__(self, oid, name, value, otype, function_activation_id):         # pylint: disable=too-many-arguments
        self.trial_id = -1
        self.id = oid                                                            # pylint: disable=invalid-name
        self.name = name
        self.value = value
        self.type = otype
        self.function_activation_id = function_activation_id

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """ObjectValue can always be removed"""
        return True

    def __repr__(self):
        return (
            "ObjectValue(id={}, name={}, value={}, type={}, "
            "activation={})"
        ).format(
            self.id, self.name,
            self.value, self.type, self.function_activation_id
        )


class FileAccessLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """FileAccess lightweight object
    There are type definitions on lightweight.pxd
    """

    __slots__, attributes = define_attrs(
        ["id", "name", "mode", "buffering", "timestamp", "trial_id",
         "content_hash_before", "content_hash_after",
         "function_activation_id"],
        ["done"]
    )
    special = {"function_activation_id"}

    def __init__(self, fid, name):
        self.trial_id = -1
        self.id = fid                                                            # pylint: disable=invalid-name
        self.name = name
        self.mode = "r"
        self.buffering = "default"
        self.content_hash_before = None
        self.content_hash_after = None
        self.timestamp = datetime.now()
        self.function_activation_id = -1
        self.done = False

    def update(self, variables):
        """Update file access with dict"""
        for key, value in viewitems(variables):
            setattr(self, key, value)

    def is_complete(self):
        """FileAccess can be removed once it is tagged as done"""
        return self.done

    def __repr__(self):
        return ("FileAccess(id={}, name={}").format(self.id, self.name)


# Slicing

class VariableLW(BaseLW):
    """Variable lightweight object
    There are type definitions on lightweight.pxd
    """
    __slots__, attributes = define_attrs(
        ["id", "activation_id", "name", "line", "value", "time", "trial_id",
         "type"]
    )
    special = set()

    def __init__(self, vid, activation_id, name, line, value, time, _type):             # pylint: disable=too-many-arguments
        self.id = vid                                                            # pylint: disable=invalid-name
        self.activation_id = activation_id
        self.name = name
        self.line = line
        self.value = value
        self.time = time
        self.type = _type

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Variable can never be removed"""
        return False

    def __repr__(self):
        return ("Variable(id={}, activation_id={}, name={}, line={}, type={},"
                "value={})").format(self.id, self.activation_id, self.name,
                                    self.line, self.type, self.value)


class VariableDependencyLW(BaseLW):
    """Variable Dependency lightweight object
    There are type definitions on lightweight.pxd
    """
    __slots__, attributes = define_attrs(
        ["id", "source_activation_id", "source_id",
         "target_activation_id", "target_id", "trial_id", "type"]
    )
    special = set()

    def __init__(self, vid, source_activation_id, source_id,                     # pylint: disable=too-many-arguments
                 target_activation_id, target_id, _type):
        self.id = vid                                                            # pylint: disable=invalid-name
        self.source_activation_id = source_activation_id
        self.source_id = source_id
        self.target_activation_id = target_activation_id
        self.target_id = target_id
        self.trial_id = -1
        self.type = _type

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Variable Dependency can always be removed"""
        return True

    def __repr__(self):
        return (
            "Dependent(id={}, "
            "sact_id={}, source_id={}, "
            "tact_id={}, target_id={}, type={})"
        ).format(
            self.id,
            self.source_activation_id, self.source_id,
            self.target_activation_id, self.target_id, self.type
        )


class VariableUsageLW(BaseLW):
    """Variable Usage lightweight object
    There are type definitions on lightweight.pxd
    """
    __slots__, attributes = define_attrs(
        ["id", "activation_id", "variable_id",
         "line", "ctx", "trial_id"]
    )
    special = set()

    def __init__(self, vid, activation_id, variable_id, line, ctx):              # pylint: disable=too-many-arguments
        self.id = vid                                                            # pylint: disable=invalid-name
        self.activation_id = activation_id
        self.variable_id = variable_id
        self.line = line
        self.ctx = ctx
        self.trial_id = -1

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Variable Usage can always be removed"""
        return True

    def __repr__(self):
        return (
            "Usage(id={}, variable_id={}, line={}, ctx={})"
        ).format(self.id, self.variable_id, self.line, self.ctx)
