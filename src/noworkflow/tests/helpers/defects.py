# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Known defects: the xfail mark where they show, and today's signature

A test that states the behavior an issue asks for (a ``_desired`` twin)
fails today. ``Defect`` describes why: the issue and the mechanism, the
versions and systems where it was measured, and the signature of today's
failure. ``known_defects`` marks the test ``xfail(strict=True)`` where a
defect applies and checks that the failure carries its signature, so that a
second defect, or a new regression, cannot hide behind the mark; where no
defect applies, the test must pass.

The e2e oracle (``e2e/oracle.py``) re-exports these names.
"""
import dataclasses
import functools
import sys

import pytest


@dataclasses.dataclass(frozen=True)
class Defect:
    """A known defect of one test, on the versions and systems it shows

    ``reason`` starts with the issue that will fix it (``#NNN: ``) and says
    the mechanism; ``signature`` is a piece of text that the failing run
    prints today (an exception and its message, a line of the script's
    output), checked by ``expect_known_failure``. The mark applies on the
    Python versions ``since <= (major, minor) < before`` (each bound
    optional), when ``systems`` is given only on the ``sys.platform``
    values it lists, and only where ``condition`` holds (a fact of the
    machine that the version and the system do not capture, computed once
    when the test module is imported); elsewhere the test must pass. The range is the one
    measured on the matrix, never a guess: ``strict`` turns an unexpected
    pass into a failure.
    """

    reason: str
    signature: str
    since: tuple = None
    before: tuple = None
    systems: tuple = None
    condition: bool = True

    def applies(self):
        if not self.condition:
            return False
        version = sys.version_info[:2]
        if self.since is not None and version < tuple(self.since):
            return False
        if self.before is not None and version >= tuple(self.before):
            return False
        return self.systems is None or sys.platform in self.systems


def defect_marks(defects):
    """The ``xfail(strict=True)`` mark of the defects that apply here"""
    current = [defect for defect in defects if defect.applies()]
    if not current:
        return []
    return [pytest.mark.xfail(
        strict=True, raises=AssertionError,
        reason="; ".join(defect.reason for defect in current))]


def expect_known_failure(defects, text):
    """Fail outright unless ``text`` shows a known defect that applies

    Call it once the test knows that it fails, with everything the failing
    run printed. Without a defect that applies, it does nothing and the
    assertion that follows fails as usual. ``pytest.fail`` is not an
    ``AssertionError``, so the xfail mark cannot absorb it.
    """
    current = [defect for defect in defects if defect.applies()]
    if current and not any(defect.signature in text for defect in current):
        pytest.fail(
            "fails, but not with the signature of its known defect ({}); "
            "a second defect or a new regression:\n{}".format(
                " | ".join(repr(defect.signature) for defect in current),
                text),
            pytrace=False)


def known_defects(*defects):
    """Decorate a test that fails today because of ``defects``

    Applies ``defect_marks`` and checks the signature of the failure: an
    ``AssertionError`` must carry the signature of a defect that applies,
    and any other exception is held to the same rule and then turned into
    an ``AssertionError`` (``"<Type>: <message>"``), so that a twin whose
    defect is a crash needs no ``try``. Where no defect applies, the test
    runs untouched and must pass. Works on plain functions and on
    ``unittest`` methods.
    """
    def decorate(test):
        @functools.wraps(test)
        def wrapper(*args, **kwargs):
            if not any(defect.applies() for defect in defects):
                return test(*args, **kwargs)
            try:
                return test(*args, **kwargs)
            except AssertionError as error:
                expect_known_failure(defects, str(error))
                raise
            except Exception as error:  # pylint: disable=broad-except
                text = "{}: {}".format(type(error).__name__, error)
                expect_known_failure(defects, text)
                raise AssertionError(text) from error
        for mark in defect_marks(defects):
            wrapper = mark(wrapper)
        return wrapper
    return decorate
