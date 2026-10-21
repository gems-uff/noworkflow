# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``helpers/swipl.py``: the SWI-Prolog driver the Prolog comparisons use

The patterns, the Prolog facts and the serializers compare what noWorkflow
exports with what SWI-Prolog makes of it, so the driver must neither lose a
solution, nor turn an error into "no solution", nor hang. Each test writes a
small file of facts whose answers follow from Prolog's semantics, and checks
what the driver reports: the solutions mapped to Python, an existence
error, the time and inference limits, syntax errors when reading a file, and
quoted atoms that read back as the text they quote.

``quoted_atom`` and the skip run everywhere; the rest skips where ``swipl``
is not on the PATH (CI installs it only where the paper example runs).
"""

import fractions
import math
import subprocess
import sys
import time

import pytest

from noworkflow.tests.helpers import swipl
from noworkflow.tests.helpers.swipl import (
    UNBOUND,
    Compound,
    PrologError,
    quoted_atom,
    read_terms,
    solutions,
    swipl_or_skip,
)

FACTS = """\
edge(a, b).
edge(b, c).
spin :- repeat, fail.
loop :- loop.
"""
# Writes the driver's last line to the file it is given, then never exits.
HANGS_AFTER_DONE = (
    "import sys, time\n"
    "with open(sys.argv[1], 'w', encoding='utf-8') as handle:\n"
    "    handle.write('{\"done\":true}\\n')\n"
    "time.sleep(600)\n"
)


@pytest.fixture
def facts(tmp_path):
    swipl_or_skip()
    path = tmp_path / "facts.pl"
    path.write_text(FACTS, encoding="utf-8")
    return path


def test_without_swipl_on_the_path_the_test_skips(monkeypatch):
    """The text of the skip is the one the paper example uses"""
    monkeypatch.setattr(swipl, "SWIPL", None)
    with pytest.raises(
        pytest.skip.Exception, match=r"^SWI-Prolog \(swipl\) is not on the PATH$"
    ):
        swipl_or_skip()


@pytest.mark.parametrize(
    "text, expected",
    [
        ("plain", "'plain'"),
        ("it's", "'it''s'"),
        ("back\\slash", "'back\\\\slash'"),
        ("a\nb\tc", "'a\\nb\\tc'"),
        ("nul\x00bel\x07", "'nul\\x0\\bel\\a'"),
        ("", "''"),
    ],
)
def test_quoted_atom_writes_the_iso_escapes(text, expected):
    """ISO 13211-1: a quote doubles, a backslash and control characters
    escape (a raw newline is not allowed inside quotes)"""
    assert quoted_atom(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "it's",
        "''",
        "back\\slash",
        "end\\",
        "a\nb",
        "tab\there\r",
        "nul\x00here",
        "é→\U0001f600",
        "%c ~w '\\'",
    ],
)
def test_quoted_atom_reads_back_as_the_same_text_in_swipl(tmp_path, text):
    """The atom ``swipl`` reads from the quoted form has the original name"""
    swipl_or_skip()
    path = tmp_path / "atoms.pl"
    path.write_text("atom_fact({}).\n".format(quoted_atom(text)), encoding="utf-8")
    result = solutions(path, "atom_fact(A), atom(A)", ["A"])
    assert (result.rows, result.error, result.stderr) == ([(text,)], None, "")


def test_every_solution_is_a_tuple_in_the_order_of_the_variables(facts):
    """Clauses answer in file order; variables in the order asked for"""
    result = solutions(facts, "edge(X, Y)", "Y X")
    assert result.rows == [("b", "a"), ("c", "b")]
    assert (result.error, result.stderr) == (None, "")


def test_a_goal_without_solutions_answers_no_rows_and_no_error(facts):
    result = solutions(facts, "edge(c, Y)", ["Y"])
    assert (result.rows, result.error) == ([], None)


def test_a_goal_without_variables_answers_one_empty_tuple_per_solution(facts):
    assert solutions(facts, "edge(_, _)", []).rows == [(), ()]


def test_terms_map_to_python_values(facts):
    """Numbers, text, lists, compounds and unbound variables"""
    goal = (
        "I = -42, F is 0.1 + 0.2, A = 'it''s', S = \"caf\u00e9\", "
        "E = '', L = [1, [x]], N = [], Q = '[]', C = f(x, _), "
        "P = [a|_]"
    )
    rows = solutions(facts, goal, "I F A S E L N Q C P").rows
    assert rows == [
        (
            -42,
            0.1 + 0.2,
            "it's",
            "caf\u00e9",
            "",
            (1, ("x",)),
            (),
            "[]",
            Compound("f", ("x", UNBOUND)),
            Compound("[|]", ("a", UNBOUND)),
        )
    ]


def test_unbounded_numbers_map_to_int_and_fraction(facts):
    """Where SWI-Prolog was built with unbounded integers (GMP)"""
    [(bounded,)] = solutions(facts, "current_prolog_flag(bounded, B)", ["B"]).rows
    if bounded != "false":
        pytest.skip("this swipl has bounded integers and no rationals")
    rows = solutions(facts, "I is 2 ** 70, R is 2 rdiv 3", "I R").rows
    assert rows == [(2**70, fractions.Fraction(2, 3))]


def test_special_floats_map_to_python_floats(facts):
    rows = solutions(facts, "P is inf, M is -inf, N is nan, Z is -0.0", "P M N Z").rows
    [(positive, negative, nan, zero)] = rows
    assert (positive, negative) == (math.inf, -math.inf)
    assert math.isnan(nan)
    assert (zero, math.copysign(1, zero)) == (0.0, -1.0)


def test_a_variable_the_goal_leaves_unbound_is_unbound(facts):
    assert solutions(facts, "edge(a, _), X = X", ["X"]).rows == [(UNBOUND,)]


def test_an_unknown_procedure_is_reported_with_the_rows_before_it(facts):
    """The solutions found before the error stay; the error names the
    procedure, as the term and as SWI-Prolog's message"""
    result = solutions(facts, "between(1, 3, X), (X < 3 -> true ; missing(X))", ["X"])
    assert result.rows == [(1,), (2,)]
    assert "existence_error(procedure,missing/1)" in result.error
    assert "Unknown procedure: missing/1" in result.error
    with pytest.raises(PrologError, match="Unknown procedure: missing/1"):
        result.rows_or_raise()


def test_the_time_limit_ends_a_goal_that_never_answers(facts):
    """Without an inference limit, only the time limit stops ``spin``"""
    started = time.monotonic()
    result = solutions(facts, "spin", [], time_limit=0.3, inference_limit=None)
    assert time.monotonic() - started < 5
    assert (result.rows, result.error) == (
        [],
        "time_limit_exceeded: Time limit exceeded",
    )


def test_a_process_that_wrote_its_last_line_and_hangs_is_killed_soon(tmp_path):
    """Ubuntu's SWI-Prolog 9 sometimes blocks in ``halt`` after the goal;
    its output is complete, so the wait kills it ``EXIT_GRACE`` seconds
    after ``{"done":true}`` instead of at the process timeout, and warns.
    A Python child stands in for that swipl."""
    output = tmp_path / "output.jsonl"
    process = subprocess.Popen(
        [sys.executable, "-c", HANGS_AFTER_DONE, str(output)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
    )
    started = time.monotonic()
    with pytest.warns(RuntimeWarning, match="did not exit"):
        _, status = swipl._wait(process, str(output), timeout=60)
    assert time.monotonic() - started < swipl.EXIT_GRACE + 10
    assert status is None
    assert process.poll() is not None


def test_a_process_killed_before_its_last_line_is_an_error(tmp_path, monkeypatch):
    """The goal ended (``end``), but the process was killed before
    ``{"done":true}``: rows it had not flushed may be lost, so the result
    is an error, with the rows that arrived"""
    path = tmp_path / "facts.pl"
    path.write_text(FACTS, encoding="utf-8")
    lines = [{"q": 0, "row": [7]}, {"q": 0, "end": True}]
    monkeypatch.setattr(swipl, "_run", lambda job, body, timeout: (lines, "", None))
    result = solutions(path, "X = 7", ["X"])
    assert result.rows == [(7,)]
    assert result.error == "swipl did not finish within {} s".format(
        10 + swipl.PROCESS_MARGIN
    )


def test_the_inference_limit_ends_an_endless_recursion(facts):
    result = solutions(facts, "loop", [], inference_limit=10_000)
    assert (result.rows, result.error) == (
        [],
        "inference_limit_exceeded: Inference limit exceeded",
    )


def test_facts_that_are_missing_are_a_usage_error(tmp_path):
    swipl_or_skip()
    with pytest.raises(FileNotFoundError):
        solutions(tmp_path / "missing.pl", "true", [])


def test_a_syntax_error_in_the_goal_is_reported_as_the_error(facts):
    result = solutions(facts, "edge(X, Y", ["X"])
    assert result.rows == []
    assert result.error.startswith("error(syntax_error(")
    assert "Syntax error" in result.error


def test_a_variable_the_goal_does_not_use_is_a_usage_error(facts):
    with pytest.raises(ValueError, match="does not use the variables Z"):
        solutions(facts, "edge(X, _)", "X Z")
    with pytest.raises(ValueError, match="not a Prolog variable name"):
        solutions(facts, "edge(X, _)", ["x"])


def test_read_terms_counts_clauses_and_lists_syntax_errors(tmp_path):
    """Heads of rules, facts and directives are counted by name/arity;
    a syntax error is listed with its line and reading goes on after it"""
    swipl_or_skip()
    path = tmp_path / "clauses.pl"
    path.write_text(
        "a(1).\nb(x y).\nc :- a(_).\n:- dynamic(d/1).\na(2).\n", encoding="utf-8"
    )
    clauses, errors = read_terms(path)
    assert clauses == {("a", 1): 2, ("c", 0): 1, (":-", 1): 1}
    assert len(errors) == 1, errors
    assert errors[0].startswith("2:")
    assert "Operator expected" in errors[0]


def test_read_terms_runs_no_directive(tmp_path):
    """``:- halt.`` would end a consult before the clause after it"""
    swipl_or_skip()
    path = tmp_path / "halts.pl"
    path.write_text(":- halt.\nafter(1).\n", encoding="utf-8")
    assert read_terms(path) == ({(":-", 1): 1, ("after", 1): 1}, [])


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
def test_two_trial_prolog_exports_the_rows_of_each_trial(
    two_trial_prolog, two_trial_project
):
    """One export per trial, in trial order; ``swipl`` loads each one
    without a message, and its ``trial`` and ``evaluation`` facts are the
    rows SQL finds for that trial (whatever the arity of the facts)"""
    trials = [row["id"] for row in two_trial_project.trials()]
    assert list(two_trial_prolog) == trials
    template = "current_predicate({0}/N), functor(F, {0}, N), call(F), arg(1, F, T)"
    for trial_id, path in two_trial_prolog.items():
        result = solutions(path, template.format("trial"), ["T"])
        assert (result.rows, result.error, result.stderr) == ([(trial_id,)], None, "")
        result = solutions(path, template.format("evaluation"), ["T"])
        assert result.error is None
        assert result.rows == [(trial_id,)] * two_trial_project.count(
            "evaluation", trial_id
        )
