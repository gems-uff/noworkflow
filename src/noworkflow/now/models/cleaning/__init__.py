# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

"""Notebooks without the cells that did not contribute to a result"""

# The names of history are loaded on first use (PEP 562): history imports
# nbformat, and importing merge, which `now diff` does for lcs, runs this
# file first; every `now` imports every command (#426).
_HISTORY = ("get_cells", "create_clean", "create_merged_from_cells")


def __getattr__(name):
    if name in _HISTORY:
        from . import history

        return getattr(history, name)
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
