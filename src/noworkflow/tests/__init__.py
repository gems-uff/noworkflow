# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""noWorkflow's test suite, run by pytest from the repository root

pytest finds every test by its file name (``python_files`` and
``testpaths`` in ``pyproject.toml``); nothing here lists them. Importing
the package connects the persistence layer to in-memory stores, before any
test module is imported.
"""
from .helpers.persistence import connect_in_memory

connect_in_memory()
