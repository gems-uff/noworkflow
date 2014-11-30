# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .provider import Provider, row_to_dict
from .database import DatabaseProvider
from .storage import StorageProvider
from .trial import TrialProvider
from .run import RunProvider
from .checkout import CheckoutProvider

class Persistence(CheckoutProvider, DatabaseProvider, TrialProvider,
				  RunProvider, StorageProvider):
	pass

persistence = Persistence()

__all__ = [
    b'persistence',
    b'row_to_dict',
]