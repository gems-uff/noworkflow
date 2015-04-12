# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

class Mock(object):

    def __getattr__(self, name):
        print(name)
        return lambda *args, **kwargs: None
