# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .provider import Provider, row_to_dict
from .database import DatabaseProvider
from .storage import StorageProvider
from .trial import TrialProvider
from .run import RunProvider
from .restore import RestoreProvider


class Persistence(RestoreProvider, DatabaseProvider, TrialProvider,
				  RunProvider, StorageProvider):
	pass

persistence = Persistence()


def get_serialize(arg):
    # ToDo: use arg to select serialize
    #from .serializers import jsonpickle_serializer, jsonpickle_content
    #from .serializers import SimpleSerializer
    # return SimpleSerializer().serialize
    # return jsonpickle_serializer
    # return jsonpickle_content
    return repr


__all__ = [
    b'persistence',
    b'row_to_dict',
    b'get_serializer',
]
