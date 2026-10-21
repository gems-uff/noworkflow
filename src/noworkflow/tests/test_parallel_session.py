# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The root conftest.py under pytest-xdist

The Linux legs of ci.yml run the suite with ``-n 4`` (#426). The root
conftest.py runs every session from a scratch directory and checks every
test for leaks; each test here runs a child pytest with two workers and
checks that the workers still collect, that coverage still reports, and
that a leak in a worker still reaches the LEAKS section the controller
prints.
"""

import pytest

from .e2e.harness import last_line
from .helpers.child_pytest import child_report, run_child_pytest
from .test_leak_detector import LEAK_LINE, LEAKING_TEST, leaks_section

pytest.importorskip("xdist")

WORKERS = ("-n", "2")
TWO_TESTS = "def test_one():\n    pass\n\n\ndef test_two():\n    pass\n"


def test_the_workers_collect_a_relative_test_path(request, tmp_path):
    """The child gets ``suite``, relative to where it starts, as the
    ``testpaths`` of the root pyproject.toml are; the workers must not
    resolve it against the scratch directory"""
    result = run_child_pytest(request, tmp_path, TWO_TESTS, args=WORKERS)
    report = child_report(result)
    assert result.returncode == 0, report
    assert "2 passed" in last_line(result.stdout), report


def test_coverage_under_the_workers_reports_without_an_internal_error(
    request, tmp_path
):
    """pytest-cov returns to the directory it recorded at session start
    once the tests end; that directory must not be the scratch directory,
    which is gone by then"""
    result = run_child_pytest(
        request, tmp_path, TWO_TESTS, args=WORKERS + ("--cov", "--cov-report=term")
    )
    report = child_report(result)
    assert result.returncode == 0, report
    assert "INTERNALERROR" not in result.stdout + result.stderr, report
    assert "2 passed" in last_line(result.stdout), report


@pytest.mark.parametrize("mode", ["fail", "warn"])
def test_a_leak_in_a_worker_reaches_the_leaks_section(request, tmp_path, mode):
    """The worker checks the leak; the controller prints the summary, so
    the leak travels in the test's report"""
    result = run_child_pytest(request, tmp_path, LEAKING_TEST, mode, args=WORKERS)
    report = child_report(result)
    summary = last_line(result.stdout)
    if mode == "fail":
        assert result.returncode != 0, report
        assert "1 passed" in summary and "1 error" in summary, report
    else:
        assert result.returncode == 0, report
        assert "1 passed" in summary and "error" not in summary, report
    assert LEAK_LINE in (leaks_section(result.stdout) or []), report
