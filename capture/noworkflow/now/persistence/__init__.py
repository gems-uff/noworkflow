# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Persistence Module. Perform database connection, and queries"""
from __future__ import (absolute_import, print_function,
                        division)

from .config import PersistenceConfig
from .content_database import ContentDatabase
from .relational_database import RelationalDatabase

persistence_config = PersistenceConfig()                                         # pylint: disable=invalid-name
content = ContentDatabase(persistence_config)                                    # pylint: disable=invalid-name
relational = RelationalDatabase(persistence_config)                              # pylint: disable=invalid-name


def get_serializer(arg):                                                         # pylint: disable=unused-argument
    """Select serializer according to argument"""
    # ToDo #54: use arg to select serialize
    # from .serializers import jsonpickle_serializer, jsonpickle_content
    # from .serializers import SimpleSerializer
    # return SimpleSerializer().serialize
    # return jsonpickle_serializer
    # return jsonpickle_content
    return repr


__all__ = [
    "persistence_config",
    "content",
    "relational",
    "get_serializer",
]
