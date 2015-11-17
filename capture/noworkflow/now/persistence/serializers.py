# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Object serializers """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import jsonpickle
from . import persistence


class Serializer(object):

    def serialize(self, obj):
        pass


class ReprSerializer(Serializer):
    
    def serialize(self, obj):
        return repr(obj)


class JsonPickleSerializer(Serializer):

    def serialize(self, obj):
        return jsonpickle.encode(obj)


class JsonPickleContentSerializer(Serializer):
   
    def serializer(self, obj):
        return "now-content:" + persistence.put(jsonpickle.encode(obj))


