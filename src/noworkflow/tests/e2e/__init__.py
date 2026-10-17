# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""End-to-end tests: the `now` command run as a process on a real store

``harness`` runs the command and reads the store, ``normalize`` masks what
changes between two identical runs, and ``golden`` compares the result with
the files under ``goldens/``. The scripts under ``corpus/`` are what the
tests trace; pytest never collects them (see the root ``conftest.py``).
"""
