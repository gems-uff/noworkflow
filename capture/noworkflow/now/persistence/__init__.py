# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .config import PersistenceConfig
from .content_database import ContentDatabase
from .relational_database import RelationalDatabase

persistence_config = PersistenceConfig()
content = ContentDatabase(persistence_config)
relational = RelationalDatabase(persistence_config)


def get_serializer(arg):
    # ToDo: use arg to select serialize
    # from .serializers import jsonpickle_serializer, jsonpickle_content
    # from .serializers import SimpleSerializer
    # return SimpleSerializer().serialize
    # return jsonpickle_serializer
    # return jsonpickle_content
    return repr


__all__ = [
    b"persistence_config",
    b"content",
    b"relational",
    b"get_serializer",
]
