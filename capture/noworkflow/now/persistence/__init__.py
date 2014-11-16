from __future__ import absolute_import

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