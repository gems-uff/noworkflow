# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Premises: the facts that a workaround, a pin or an exclusion depends on

Each test pins one fact that some line of the repository relies on (a
version pin, an ignored advisory, a lint exclusion, a test that
characterizes a defect). When one fails, the reason for that line changed:
the assert message names what to edit and the issue that tracks it.
``corpus_spy`` is a pytest plugin that ``test_premises`` loads in a child
pytest; it is not a test module.
"""
