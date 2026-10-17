# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Python version gates for the test suite"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import unittest


def only(*versions):
    """Run the test only when at least one of the version flags holds

    ``cross_version.only`` returns ``None`` otherwise, which makes both
    unittest and pytest drop the test silently. This one skips it instead,
    so the test stays visible in the count.
    """
    return unittest.skipUnless(
        any(versions), "not supported by this Python version")
