# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``utils/io.py``: the ``[now]`` messages and the swap of the streams

``print_msg`` writes every message noWorkflow prints, and
``redirect_output`` silences the standard streams while the debugging
builtins that ``now run`` gives the script import IPython, start a debugger
or start the vis (``prov_execution/debugger.py``). Both run in every ``now
run``. These tests pin what each one does with the arguments it receives.

``print_msg``'s default stream is bound when ``utils/io.py`` is imported
(the premise ``test_print_msg_does_not_follow_a_swapped_sys_stdout`` pins
it), so under pytest it is pytest's own capture object, which neither
``capsys`` nor ``capfd`` reads. Every test here passes ``file=``
explicitly; the default stream is covered by the premise and by the e2e
tests.
"""

import io
import sys

import pytest

from noworkflow.now.utils import io as now_io
from noworkflow.now.utils.io import print_error, print_msg, redirect_output


@pytest.fixture
def quiet(monkeypatch):
    """``now`` without ``-v``: ``print_msg`` prints only when forced"""
    monkeypatch.setattr(now_io, "verbose", False)


@pytest.fixture
def verbose(monkeypatch):
    """``now run -v``: ``cmd_run.py`` sets ``io.verbose`` from the flag"""
    monkeypatch.setattr(now_io, "verbose", True)


def test_print_msg_prefixes_the_now_label_when_forced(quiet):
    """A forced message is printed with the ``[now] `` prefix that every
    line of noWorkflow's own output carries, and a newline"""
    buffer = io.StringIO()
    print_msg("hello", force=True, file=buffer)
    assert buffer.getvalue() == "[now] hello\n"


def test_print_msg_prints_nothing_unless_verbose_or_forced(quiet):
    """Without ``-v`` and without ``force``, a message is dropped"""
    buffer = io.StringIO()
    print_msg("hello", file=buffer)
    assert buffer.getvalue() == ""


def test_print_msg_prints_without_force_in_verbose_mode(verbose):
    """Under ``-v`` every message is printed, forced or not"""
    buffer = io.StringIO()
    print_msg("hello", file=buffer)
    assert buffer.getvalue() == "[now] hello\n"


def test_print_msg_formats_a_non_string_message_with_str(quiet):
    """A message that is not a string, such as an exception, is printed as
    ``str()`` gives it, which is how ``now`` reports a ``RuntimeError`` that
    a command raises (``noworkflow.now.cmd.main``)"""
    buffer = io.StringIO()
    print_msg(ValueError("bad"), True, file=buffer)
    assert buffer.getvalue() == "[now] bad\n"


def test_print_msg_writes_to_the_stream_given_at_call_time(quiet, capfd):
    """A stream given in the call is the one written to: ``sys.stderr``,
    looked up at the call, reaches the process's stderr and nothing goes to
    stdout"""
    print_msg("e", True, file=sys.stderr)
    captured = capfd.readouterr()
    assert (captured.out, captured.err) == ("", "[now] e\n")


def test_print_error_is_a_forced_message_with_the_now_label(quiet):
    """``print_error`` prints without ``-v``, with the ``[now] `` prefix and
    ``str()`` of its message, as ``main`` reports a ``RuntimeError``"""
    buffer = io.StringIO()
    print_error(RuntimeError("Trial 99 not found"), file=buffer)
    assert buffer.getvalue() == "[now] Trial 99 not found\n"


def test_print_error_defaults_to_the_stderr_bound_at_import():
    """Without ``file=``, ``print_error`` writes to ``io.STDERR``, the
    stderr bound when the module was imported, and never to the stdout
    bound there: an error of ``now`` goes to the process's stderr even when
    the traced script replaced ``sys.stderr``"""
    buffer = io.StringIO()
    old = now_io.STDERR
    now_io.print_error.__defaults__ = (buffer,)
    try:
        print_error("e")
    finally:
        now_io.print_error.__defaults__ = (old,)
    assert buffer.getvalue() == "[now] e\n"
    assert print_error.__defaults__ == (now_io.STDERR,)
    assert now_io.STDERR is not now_io.STDOUT


def test_redirect_output_swaps_stdout_and_stderr_and_restores_them():
    """By default both streams are replaced by buffers inside the block,
    the old streams are what the block receives, and they are back after
    it"""
    old_stdout, old_stderr = sys.stdout, sys.stderr
    with redirect_output() as olds:
        assert olds == [old_stdout, old_stderr]
        assert sys.stdout is not old_stdout
        assert sys.stderr is not old_stderr
        print("inside")
        print("error", file=sys.stderr)
        inside = (sys.stdout.getvalue(), sys.stderr.getvalue())
    assert sys.stdout is old_stdout
    assert sys.stderr is old_stderr
    assert inside == ("inside\n", "error\n")


def test_redirect_output_restores_the_streams_when_the_body_raises():
    """An exception in the block propagates, and the streams are restored
    all the same"""
    old_stdout = sys.stdout
    with pytest.raises(ValueError, match="in the block"):
        with redirect_output(["stdout"]) as olds:
            assert olds == [old_stdout]
            raise ValueError("in the block")
    assert sys.stdout is old_stdout


def test_redirect_output_swaps_only_the_named_streams():
    """Naming ``stderr`` alone leaves ``sys.stdout`` untouched"""
    old_stdout, old_stderr = sys.stdout, sys.stderr
    with redirect_output(["stderr"]) as olds:
        assert olds == [old_stderr]
        assert sys.stdout is old_stdout
        assert isinstance(sys.stderr, io.StringIO)
    assert sys.stderr is old_stderr
