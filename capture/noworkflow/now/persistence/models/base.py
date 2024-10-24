# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Model base"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from collections import OrderedDict, namedtuple
from functools import wraps

from future.utils import with_metaclass, viewitems, viewvalues, viewkeys
from sqlalchemy import Column
from sqlalchemy.orm import relationship

from .. import relational


class MetaModel(type):
    """Model metaclass

    Keep track of all model classes and instances
    Classes must have __modelname__ defined to be tracked
    """
    __classes__ = {}

    def __new__(mcs, name, bases, attrs):
        attrs["__refs__"] = []
        attrs["REPLACE"] = attrs.get("REPLACE", {})
        attrs["DEFAULT"] = attrs.get("DEFAULT", {})
        if "__modelname__" not in attrs:
            attrs["__modelname__"] = name

        cls = super(MetaModel, mcs).__new__(mcs, name, bases, attrs)
        mcs.__classes__[attrs["__modelname__"]] = cls
        return cls

    def __call__(cls, *args, **kwargs):
        instance = super(MetaModel, cls).__call__(*args, **kwargs)
        instance.__class__.__refs__.append(weakref.ref(instance))
        return instance

    def get_instances(cls):
        """Return all instances from Model class"""
        for inst_ref in cls.__refs__:
            inst = inst_ref()
            if inst is not None:
                yield inst

    def set_instances_default(cls, attr, value):
        """Set DEFAULT attribute for instances of classes created
        by this metaclass


        Arguments:
        attr -- attribute name
        value -- new attribute value
        """
        for instance in cls.get_instances():
            instance.set_instance_attr(attr, value)

    @classmethod
    def all_models(mcs):
        """Return all instances from all models"""
        for cls in viewvalues(mcs.__classes__):
            for instance in cls.get_instances():
                yield instance

    @classmethod
    def set_class_default(mcs, model, attr, value, instances=False):
        """Set DEFAULT attribute for Model class

        Arguments:
        model -- name of model class
        attr -- attribute name
        value -- new attribute value


        Keyword arguments:
        instances -- update instances too (default=False)
        """
        cls = mcs.__classes__[model]
        if attr in cls.REPLACE:
            attr = cls.REPLACE[attr]
        if attr in cls.DEFAULT:
            cls.DEFAULT[attr] = value
        if instances:
            cls.set_instances_default(attr, value)

    @classmethod
    def set_classes_default(mcs, attr, value, instances=False, model="*"):
        """Set DEFAULT attribute for Model classes that match model filter

        Arguments:
        model -- name of model class
        attr -- attribute name
        value -- new attribute value


        Keyword arguments:
        instances -- update instances too (default=False)
        model -- filter model (default="*")
        """
        if model == "*":
            for name in viewkeys(mcs.__classes__):
                mcs.set_class_default(name, attr, value, instances=instances)
        else:
            mcs.set_class_default(model, attr, value, instances=instances)


class Model(with_metaclass(MetaModel)):
    """Model base"""

    REPLACE = {}
    DEFAULT = {}

    def __init__(self, *args, **kwargs):
        pass

    def set_instance_attr(self, attr, value, check=True):
        """Initialize attr to instance

        If attr exists in REPLACE, use its variant
        If attr has ".", use getattr until the actual item
        """
        if attr in self.REPLACE:
            attr = self.REPLACE[attr]
        obj = self
        while "." in attr:
            attr0, attr = attr.split(".", 1)
            obj = getattr(self, attr0)
        if not check or hasattr(obj, attr):
            setattr(obj, attr, value)

    def initialize_default(self, kwargs):
        """Initialize DEFAULT and kwargs parameters to instance"""
        for key, value in viewitems(self.DEFAULT):
            self.set_instance_attr(key, value, check=False)
        for key, value in viewitems(kwargs):
            self.set_instance_attr(key, value)


def proxy(element):
    """Return proxy instance from SQLALchemy object"""
    cls = element.__class__
    if cls in AlchemyProxy.__alchemy_refs__:
        return AlchemyProxy.__alchemy_refs__[cls](element)
    else:
        return element


def proxy_gen(query):
    """Return proxy generator from iterable

    Iterable can be a SQLALchemy query"""
    for element in query:
        yield proxy(element)


def proxy_gen_first(query):
    """Return proxy instance from SQLALchemy object when uselist=True"""
    for element in query:
        return proxy(element)


def proxy_property(func, proxy_func=proxy, doc=None):
    """Return a proxy property to a __model__ function"""
    @wraps(func)
    def prop(self, *args, **kwargs):
        """Proxy property"""
        obj = self._get_instance()                                               # pylint: disable=protected-access
        result = func(obj, *args, **kwargs)
        return proxy_func(result)
    return property(prop, doc=doc)


def proxy_attr(name, proxy_func=proxy, doc=None):
    """Return a proxy property to a __model__ attribute"""
    def func(self):
        """Return {}""".format(name)
        return getattr(self, name)
    return proxy_property(func, proxy_func=proxy_func, doc=doc)


class AlchemyProxy(Model):
    """Alchemy Proxy super class.

    Store _alchemy_pk primary key and other columns from table
    """

    __alchemy_refs__ = {}

    m = __model__ = None                                                         # pylint: disable=invalid-name
    t = __table__ = None                                                         # pylint: disable=invalid-name
    __modelname__, __columns__ = None, []

    def __init__(self, obj):
        super(AlchemyProxy, self).__init__(obj)
        if isinstance(obj, relational.base):
            self._store_pk(obj)
        else:
            self._alchemy_pk = obj
        self._restore_instance()

    def __hash__(self):
        return hash((type(self), tuple(self._alchemy_pk)))

    def __eq__(self, other):
        # pylint: disable=protected-access
        if not isinstance(other, type(self)):
            return False
        return self._alchemy_pk == other._alchemy_pk

    def __repr__(self):
        if hasattr(self, 'prolog_description'):
            return self.prolog_description.fact(self)                            # pylint: disable=no-member
        return super(AlchemyProxy, self).__repr__()                              # pylint: disable=no-member

    def _store_pk(self, obj):
        self._alchemy_pk = obj.__mapper__.primary_key_from_instance(obj)

    def _restore_instance(self):
        """Restore instance with new session"""
        obj = self._get_instance()
        for column in self.__columns__:
            setattr(self, column, getattr(obj, column))

    def _get_instance(self):
        return relational.session.query(self.__model__).get(self._alchemy_pk)

    def __getstate__(self):
        return (self._alchemy_pk,)

    def __setstate__(self, state):
        (self._alchemy_pk,) = state
        self._restore_instance()

    def to_dict(self, ignore=tuple(), extra=tuple()):
        """Return object as dict"""
        result = OrderedDict(
            (attr, getattr(self, attr)) for attr in extra
        )
        for key in self.__columns__:
            if key not in ignore and key not in extra:
                result[key] = getattr(self, key)

        return result

    @classmethod
    def store(cls, object_store, partial, conn=None):
        """Bulk insert lightweight objects from ObjectStore"""
        if object_store.has_items():
            _conn = conn if conn else relational.engine.connect()
            _conn.execute(
                cls.__model__.__table__.insert().prefix_with("OR REPLACE"),
                *object_store.generator(partial)
            )
            if conn is None:
                _conn.close()
    @classmethod
    def load_by_trials(cls, trial_ids_list, session=None):
        session = session or relational.session
        return (
            session.query(cls.m)
            .filter((cls.m.trial_id.in_(trial_ids_list))).all()
        )
    @classmethod  # query
    def all(cls, session=None):
        """Return all tuples


        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        return proxy_gen(session.query(cls.m))


ModelMethod = namedtuple("ModelMethod", "func proxy")


def query_many_property(func):
    """Property is part of the Model class. It should return a generator"""
    return ModelMethod(func, proxy_gen)


def query_one_property(func):
    """Property is part of the Model class. It should return a single instance"""
    return ModelMethod(func, proxy)


def proxy_class(cls):
    """Proxy decorator


    Use it for classes that define SQLAlchemy attributes
    This decorator creates __model__, __table__, __columns__ attributes
    It will also register the class in the proxy list
    """
    description = cls.__dict__
    attributes = {}
    to_remove = set()
    for name, var in viewitems(description):
        if isinstance(var, Column):
            to_remove.add(name)
            attributes[name] = var
        elif isinstance(var, ModelMethod):
            new_name = name
            setattr(cls, name, proxy_attr(
                new_name, proxy_func=var.proxy, doc=var.func.__doc__
            ))
            attributes[new_name] = property(var.func, doc=var.func.__doc__)
        elif name in ('__tablename__', '__table_args__'):
            attributes[name] = var

    for name in to_remove:
        delattr(cls, name)

    cls.__modelname__ = cls.__name__
    cls.m = cls.__model__ = type(cls.__name__, (relational.base,), attributes)
    cls.t = cls.__table__ = cls.__model__.__table__
    cls.__columns__ = cls.__table__.columns.keys()

    AlchemyProxy.__alchemy_refs__[cls.__model__] = cls

    return cls


def is_none(attribute):
    """Filter SQLAlchemy attribute is None"""
    return attribute == None                                                     # pylint: disable=singleton-comparison
