# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``known_defects``: what a ``_desired`` twin does with today's failure

The decorated function is called directly, so each outcome is observed
without the xfail mark absorbing it: the mark itself is read from the
function.
"""
import sys

import pytest

from noworkflow.tests.helpers.defects import Defect, known_defects

HERE = Defect("#NNN: an example mechanism", "KeyError: 'spam'")
ELSEWHERE = Defect("#NNN: an example mechanism", "KeyError: 'spam'",
                   before=(3, 0))


def raises(error):
    def test():
        raise error
    return test


def marks(test):
    return [(mark.name, mark.kwargs) for mark in test.pytestmark]


def test_a_defect_that_applies_marks_the_test_strict_xfail():
    decorated = known_defects(HERE)(raises(AssertionError("x")))
    assert marks(decorated) == [("xfail", {
        "strict": True, "raises": AssertionError,
        "reason": "#NNN: an example mechanism"})]


def test_an_assertion_with_the_signature_stays_an_assertion():
    error = AssertionError("got KeyError: 'spam' in the store")
    with pytest.raises(AssertionError) as caught:
        known_defects(HERE)(raises(error))()
    assert caught.value is error


def test_a_crash_with_the_signature_becomes_an_assertion():
    with pytest.raises(AssertionError, match="^KeyError: 'spam'$"):
        known_defects(HERE)(raises(KeyError("spam")))()


def test_a_failure_without_the_signature_fails_outright():
    """``pytest.fail`` is not an AssertionError: the mark cannot absorb it"""
    for error in (AssertionError("another message"), KeyError("eggs")):
        with pytest.raises(pytest.fail.Exception, match="a second defect"):
            known_defects(HERE)(raises(error))()


def test_where_no_defect_applies_the_test_runs_untouched():
    """No mark, and the original exception, whatever its text"""
    assert sys.version_info >= (3, 0)
    decorated = known_defects(ELSEWHERE)(raises(KeyError("eggs")))
    assert not hasattr(decorated, "pytestmark")
    with pytest.raises(KeyError):
        decorated()
