# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Persistence Module. Perform database connection, and queries"""

from __future__ import absolute_import, division, print_function

from .config import PersistenceConfig
from .content_database import ContentDatabase
from .relational_database import RelationalDatabase

persistence_config = PersistenceConfig()  # pylint: disable=invalid-name
content = ContentDatabase(persistence_config)  # pylint: disable=invalid-name
relational = RelationalDatabase(persistence_config)  # pylint: disable=invalid-name


def get_serializer(arg):  # pylint: disable=unused-argument
    """Select serializer according to argument"""
    from .serializers import (
        SimpleSerializer,
        jsonpickle_content,
        jsonpickle_serializer,
        repr_serializer,
    )

    if arg.serializer == "jsonpickle_content":
        return jsonpickle_content
    elif arg.serializer == "jsonpickle":
        return jsonpickle_serializer
    elif arg.serializer == "simple":
        return SimpleSerializer().serialize

    # else: # arg.serializer == "repr":
    return repr_serializer


__all__ = ["persistence_config", "content", "relational", "get_serializer"]
