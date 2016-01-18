# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Model base"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from collections import defaultdict

from future.utils import with_metaclass, iteritems
from sqlalchemy import inspect
from sqlalchemy.orm.attributes import InstrumentedAttribute

from ..persistence import persistence


class MetaModel(type):
    """Model metaclass

    Keep track of all model classes and instances
    Classes must have __modelname__ defined to be tracked
    """
    __classes__ = {}

    def __new__(meta, name, bases, attrs):
        attrs["__refs__"] = []
        attrs["REPLACE"] = attrs.get("REPLACE", {})
        attrs["DEFAULT"] = attrs.get("DEFAULT", {})

        cls = super(MetaModel, meta).__new__(meta, name, bases, attrs)
        if "__modelname__" in attrs:
            meta.__classes__[attrs["__modelname__"]] = cls
        return cls

    def __call__(meta, *args, **kwargs):
        instance = super(MetaModel, meta).__call__(*args, **kwargs)
        instance.__class__.__refs__.append(weakref.ref(instance))
        return instance


    def get_instances(cls):
        """Return all instances from Model class"""
        for inst_ref in cls.__refs__:
            inst = inst_ref()
            if inst is not None:
                yield inst

    def set_instances_default(cls, model, attr, value):
        """Set DEFAULT attribute for instances of classes created
        by this metaclass


        Arguments:
        model -- name of model class
        attr -- attribute name
        value -- new attribute value
        """
        for instance in cls.get_instances():
            instance.set_instance_attr(attr, value)

    @classmethod
    def all_models(meta):
        """Return all instances from all models"""
        for name, cls in iteritems(meta.__classes__):
            for instance in cls.get_instances():
                yield instance

    @classmethod
    def set_class_default(meta, model, attr, value, instances=False):
        """Set DEFAULT attribute for Model class

        Arguments:
        model -- name of model class
        attr -- attribute name
        value -- new attribute value


        Keyword arguments:
        instances -- update instances too (default=False)
        """
        cls = meta.__classes__[model]
        if attr in cls.DEFAULT:
            cls.DEFAULT[attr] = value
        if instances:
            cls.set_instances_default(model, attr, value)

    @classmethod
    def set_classes_default(meta, attr, value, instances=False, model="*"):
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
            for name, cls in iteritems(meta.__classes__):
                meta.set_class_default(name, attr, value, instances=instances)
        else:
            meta.set_class_default(model, attr, value, instances=instances)




class Model(with_metaclass(MetaModel)):
    """Model base"""

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
        for key, value in iteritems(self.DEFAULT):
            self.set_instance_attr(key, value, check=False)
        for key, value in iteritems(kwargs):
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


class AlchemyProxy(Model):
    """Alchemy Proxy super class.

    Store _alchemy instance and _alchemy_pk primary key
    Reset _alchemy if it is detached

    Define proxy for instance attributes
    """

    __alchemy_refs__ = {}

    def __init__(self, obj):
        #self.__alchemy_refs__[self.__model__] = self.__class__
        if isinstance(obj, persistence.base):
            self._alchemy = obj
            self._store_pk()
        else:
            self._alchemy_pk = obj
            self._restore_instance(do_inspection=False)

    def _store_pk(self):
        obj = self._alchemy
        self._alchemy_pk = obj.__mapper__.primary_key_from_instance(obj)

    def _restore_instance(self, do_inspection=True):
        """Restore instance with new session"""
        if do_inspection:
            insp = inspect(self._alchemy)
            if not insp.detached:
                return
        if self._alchemy_pk:
            self._alchemy = (
                persistence.session.query(type(self._alchemy))
                .get(self._alchemy_pk)
            )

    def __getattr__(self, attr):
        if attr == '_alchemy' or attr in self.__dict__:
            super(AlchemyProxy, self).__getattr__(self, attr)
        self._restore_instance()
        return getattr(self._alchemy, attr)


class RedirectProxy(object):
    """Proxy for class attributes"""
    def __init__(self, model, name):
        self.model = model
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return getattr(self.model, self.name)
        self._restore_instance()
        return getattr(obj._alchemy, self.name)

    def __set__(self, obj, value):
        if obj is None:
            setattr(self.model, self.name, value)
        setattr(obj._alchemy, self.name, value)

    def __delete__(self, obj):
        if obj is None:
            delattr(self.model, self.name)
        delattr(obj._alchemy, self.name)


def set_proxy(model):
    """Create proxy metaclass for specific SQLAlchemy Model"""

    class MetaProxy(MetaModel):
        """Proxy Metaclass

        Store __model__ class attribute
        Map SQLAlchemy Model to Proxy

        Define proxy for class attributes
        It will ignore attributes starting with '_'
        """

        def __new__(meta, name, bases, attrs):
            bases = (AlchemyProxy,)
            if not "__modelname__" in attrs:
                attrs["__modelname__"] = model.__name__
            for attr in model.__dict__:
                if not attr.startswith("_") or attr == "__repr__":
                    attrs[attr] = RedirectProxy(model, attr)
            cls = super(MetaProxy, meta).__new__(meta, name, bases, attrs)
            cls.__model__ = model
            AlchemyProxy.__alchemy_refs__[model] = cls
            return cls

        def __getattr__(cls, attr):
            if attr in cls.__model__.__dict__:
                return getattr(cls.__model__, attr)
            return super(MetaProxy, cls).__getattr__(cls, attr)

        @property
        def query(cls):
            return persistence.session.query(cls.__model__)

    return MetaProxy
