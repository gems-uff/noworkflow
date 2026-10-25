# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Whether the strace backend of the external process tracer (#206) can
trace here, for the tests that need it

The backend runs only on Linux, with ``strace`` on the PATH, where strace
can trace a process (a container without ptrace cannot): the same
conditions under which ``now run --external-tracer strace`` does not fall
back to ``argv``, measured by the tracer's own probe
(``external.strace_support``). A test that needs it calls
``require_strace()``, which skips elsewhere; on the legs that install
strace, ``NOW_STRACE=require`` turns the skip into a failure, so that a
leg that lost strace does not pass by skipping.
"""

import os
import shutil
import sys

import pytest

from ...now.collection.prov_execution import external

REQUIRE_STRACE = os.environ.get("NOW_STRACE") == "require"


def strace_reason():
    """Why the strace backend cannot trace here, or None when it can"""
    if not sys.platform.startswith("linux"):
        return "strace exists on Linux only"
    strace = shutil.which(external.STRACE_PROGRAM)
    if strace is None:
        return "strace is not on the PATH"
    detail = external.strace_support(os.path.abspath(strace))
    if detail is not None:
        return "strace cannot trace here ({})".format(detail)
    return None


def require_strace():
    """Skip the test where the strace backend cannot trace, or fail it
    under ``NOW_STRACE=require``"""
    reason = strace_reason()
    if reason is None:
        return
    if REQUIRE_STRACE:
        pytest.fail("{} (NOW_STRACE=require)".format(reason), pytrace=False)
    pytest.skip(reason)
