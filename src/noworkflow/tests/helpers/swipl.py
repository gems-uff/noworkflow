# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Run SWI-Prolog on a file of facts and read back what it answers

The Prolog side of the tests needs an engine that noWorkflow does not
control: ``swipl`` runs a goal over the facts of ``now export prolog`` (and
the rules that ``-r`` appends), reads a file term by term, or reads back an
atom that a test quoted. Every call starts its own ``swipl`` process with a
time limit inside Prolog and a timeout outside it, so a goal that never ends
fails the test instead of hanging the suite.

``solutions`` loads the facts, runs one goal and returns every solution as a
tuple of Python values, one per variable asked for, in that order::

    Prolog                         Python
    integer                        int
    float                          float (1.0Inf, -1.0Inf, 1.5NaN included)
    rational (2r3)                 fractions.Fraction
    atom, string                   str ('' for the empty atom)
    proper list ([] included)      tuple, items mapped the same way
    compound (partial lists too)   Compound(name, args), args a tuple
    unbound variable               UNBOUND
    anything else (blobs, dicts)   Other(text), the term written by ~q

The atom ``[]`` written with quotes is a str (``'[]'``), the empty list a
tuple (``()``). When the goal raises, ``error`` holds the exception term
(variables written as ``_``) and the message SWI-Prolog prints for it, for
example ``time_limit_exceeded: Time limit exceeded`` or
``error(existence_error(procedure,trial/9),...): ... Unknown procedure:
trial/9``; the solutions found before it stay in ``rows``. A signature should
use the stable part: the term, or the message after its context.

The solutions travel through a file as JSON, with every atom and string as
its list of character codes, so no quoting convention of ``writeq`` (``':'``
unquoted, escapes that change between versions) reaches the parser, and
nothing the goal prints on stdout mixes with them. The ``swipl`` process
runs with ``-f none`` (no user init file) and the files are read as UTF-8.

The facts of an export include the environment of the machine that ran the
script (the hostname inside ``trial``'s user id among them): never put a
whole facts file, or the solutions of a goal that binds those values, into
an assertion message.
"""

import collections
import fractions
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import typing
import warnings

import pytest

SWIPL = shutil.which("swipl")
SKIP_REASON = "SWI-Prolog (swipl) is not on the PATH"
# The process timeout is the time limit inside Prolog plus this margin, for
# loading the facts and starting the process.
PROCESS_MARGIN = 30
# Seconds a process that wrote its last line gets to exit before it is
# killed, and how often the wait looks at the output in the meantime.
EXIT_GRACE = 2
WAIT_SLICE = 0.2
VARIABLE_NAME = re.compile(r"[A-Z_][A-Za-z0-9_]*\Z")

Compound = collections.namedtuple("Compound", "name args")
Other = collections.namedtuple("Other", "text")


class _Unbound:
    """The value of a variable that a solution leaves unbound"""

    def __repr__(self):
        return "<unbound>"


UNBOUND = _Unbound()


class PrologError(Exception):
    """A goal raised in Prolog: the term and its message, as ``error``"""


class Solutions(typing.NamedTuple):
    """What a goal answered

    ``rows`` is the list of solutions, each a tuple with one value per
    variable asked for; ``error`` is None, or the text of what the goal
    raised (``"<term>: <message>"``); ``stderr`` is what ``swipl`` printed
    there (loading a clean export prints nothing).
    """

    rows: list
    error: str
    stderr: str

    def rows_or_raise(self):
        """The rows, or ``PrologError(error)`` when the goal raised"""
        if self.error is not None:
            raise PrologError(self.error)
        return self.rows


class ReadTerms(typing.NamedTuple):
    """What ``read_terms`` found in a file

    ``clauses`` is a Counter of ``(name, arity)``: the head of each ``Head
    :- Body``, the term itself for a fact, ``(":-", 1)`` for a directive.
    ``errors`` lists the syntax errors in file order, each as
    ``"<line>:<column>: <message>"`` with SWI-Prolog's line and column
    (``"2:4: Syntax error: Operator expected"``).
    """

    clauses: collections.Counter
    errors: list


def swipl_or_skip():
    """The path of ``swipl``, or skip the test when it is not on the PATH"""
    if SWIPL is None:
        pytest.skip(SKIP_REASON)
    return SWIPL


_QUOTED = {
    "\\": "\\\\",
    "'": "''",
    "\n": "\\n",
    "\t": "\\t",
    "\r": "\\r",
    "\a": "\\a",
    "\b": "\\b",
    "\f": "\\f",
    "\v": "\\v",
}


def quoted_atom(text):
    """The ISO Prolog quoted atom whose name is ``text``

    A quote is doubled and a backslash escaped; the other control
    characters, which ISO does not allow raw inside quotes, become escape
    sequences (``\\n``, ``\\t``, ``\\x0\\`` for NUL). Everything else stays as
    it is, so a file that holds the result is written in UTF-8. This is one
    spelling among the ones ISO allows: a raw newline that SWI-Prolog
    accepts, or ``\\'`` for a quote, reads back as the same atom, so compare
    atoms through ``swipl`` when the spelling is not the point.
    """
    parts = []
    for char in text:
        if char in _QUOTED:
            parts.append(_QUOTED[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            parts.append("\\x{:x}\\".format(ord(char)))
        else:
            parts.append(char)
    return "'{}'".format("".join(parts))


# The driver: a module, the body of ``solutions`` or ``read_terms``, and the
# job(Output, Job) fact that the Python side appends. It writes one JSON
# object per line to Output: {"q":0,"row":[...]} per solution,
# {"q":0,"error":Codes,"message":Codes} (q is -1 when loading or reading
# failed), {"q":0,"missing":Codes} for variables absent from the goal,
# {"q":0,"end":true} when the goal is over; {"clause":Codes,"arity":N} and
# {"line":L,"column":C,"message":Codes} for read_terms; {"done":true} last.
_PRELUDE = r"""
:- module(nowtest_swipl, [main/0]).
:- encoding(utf8).
:- use_module(library(time)).

:- multifile prolog:message//1.
prolog:message(inference_limit_exceeded) --> ['Inference limit exceeded'].

main :-
    job(Output, Job),
    setup_call_cleanup(
        open(Output, write, Out, [encoding(utf8)]),
        ( run(Out, Job), emit(Out, '{"done":true}', []) ),
        close(Out)).

emit(Out, Format, Arguments) :-
    format(Out, Format, Arguments), nl(Out), flush_output(Out).

% An error is reported; unwinding (halt/0 in SWI-Prolog 10, abort) goes on.
report(_, _, Error) :-
    ( Error = unwind(_) ; Error == '$aborted' ), !,
    throw(Error).
report(Out, Index, Error) :- emit_error(Out, Index, Error).

emit_error(Out, Index, Error) :-
    copy_term(Error, Copy),
    numbervars(Copy, 0, _, [singletons(true)]),
    format(codes(Term), '~W', [Copy, [quoted(true), numbervars(true)]]),
    message(Error, Message),
    emit(Out, '{"q":~d,"error":~w,"message":~w}', [Index, Term, Message]).

message(Error, Codes) :-
    catch(( '$messages':translate_message(Error, Lines, []),
            with_output_to(codes(Codes),
                           print_message_lines(current_output, '', Lines))
          ), _, fail),
    !.
message(_, []).
"""

_SOLUTIONS = r"""
run(Out, query(Files, Text, Names, TimeLimit, InferenceLimit)) :-
    catch(( load_files(user:Files, [encoding(utf8)]), Loaded = true ),
          LoadError, Loaded = error(LoadError)),
    (   Loaded = error(Error)
    ->  report(Out, -1, Error)
    ;   run_query(Out, 0, Text, Names, TimeLimit, InferenceLimit)
    ).

run_query(Out, Index, Text, Names, TimeLimit, InferenceLimit) :-
    catch(( term_string(Goal, Text, [variable_names(Bindings), module(user)]),
            Parsed = true ),
          ParseError, Parsed = error(ParseError)),
    (   Parsed = error(Error)
    ->  emit_error(Out, Index, Error)
    ;   findall(Name, ( member(Name, Names),
                        \+ memberchk(Name=_, Bindings) ), Missing),
        Missing \== []
    ->  atomic_list_concat(Missing, ' ', Atom), atom_codes(Atom, Codes),
        emit(Out, '{"q":~d,"missing":~w}', [Index, Codes])
    ;   maplist(binding(Bindings), Names, Values),
        catch(call_with_time_limit(TimeLimit,
                  forall(limited(Goal, InferenceLimit),
                         emit_row(Out, Index, Values))),
              Error, report(Out, Index, Error))
    ),
    emit(Out, '{"q":~d,"end":true}', [Index]).

binding(Bindings, Name, Value) :- memberchk(Name=Value, Bindings).

limited(Goal, none) :- !, call(user:Goal).
limited(Goal, Limit) :-
    call_with_inference_limit(user:Goal, Limit, Result),
    (   Result == inference_limit_exceeded
    ->  throw(inference_limit_exceeded)
    ;   true
    ).

emit_row(Out, Index, Values) :-
    with_output_to(string(Json), json(Values)),
    emit(Out, '{"q":~d,"row":~s}', [Index, Json]).

json(X) :- var(X), !, write(null).
json(X) :- integer(X), !, write(X).
json(X) :- float(X), !, format(codes(C), '~w', [X]), format('{"float":~w}', [C]).
json(X) :- rational(X, N, D), !, format('{"rational":[~w,~w]}', [N, D]).
json(X) :- string(X), !, string_codes(X, C), format('{"string":~w}', [C]).
json(X) :- is_list(X), !, write('['), json_items(X), write(']').
json(X) :- atom(X), !, atom_codes(X, C), format('{"atom":~w}', [C]).
json(X) :- compound(X), !,
    compound_name_arguments(X, Name, Arguments), atom_codes(Name, C),
    format('{"compound":~w,"args":[', [C]), json_items(Arguments), write(']}').
json(X) :- format(codes(C), '~q', [X]), format('{"other":~w}', [C]).

json_items([]).
json_items([X]) :- !, json(X).
json_items([X|Xs]) :- json(X), write(','), json_items(Xs).
"""

_READ_TERMS = r"""
run(Out, read(Path, TimeLimit)) :-
    catch(call_with_time_limit(TimeLimit,
              setup_call_cleanup(open(Path, read, In, [encoding(utf8)]),
                                 read_loop(In, Out),
                                 close(In))),
          Error, report(Out, -1, Error)).

read_loop(In, Out) :-
    character_count(In, Before),
    catch(read_term(In, Term, []), Error, true),
    character_count(In, After),
    (   nonvar(Error)
    ->  syntax_error_line(Out, In, Error),
        (   Error = error(syntax_error(_), _), After > Before
        ->  read_loop(In, Out)
        ;   true
        )
    ;   Term == end_of_file
    ->  true
    ;   clause_key(Term, Name, Arity),
        atom_codes(Name, Codes),
        emit(Out, '{"clause":~w,"arity":~d}', [Codes, Arity]),
        read_loop(In, Out)
    ).

syntax_error_line(Out, In, Error) :-
    (   Error = error(_, Context), nonvar(Context),
        ( Context = file(_, Line, Column, _)
        ; Context = stream(_, Line, Column, _)
        )
    ->  true
    ;   line_count(In, Line), line_position(In, Column)
    ),
    (   Error = error(syntax_error(What), _)
    ->  message(error(syntax_error(What), _), Message)
    ;   message(Error, Message)
    ),
    emit(Out, '{"line":~d,"column":~d,"message":~w}', [Line, Column, Message]).

clause_key((Head :- _), Name, Arity) :- callable(Head), !,
    functor(Head, Name, Arity).
clause_key(Term, Name, Arity) :- callable(Term), !, functor(Term, Name, Arity).
clause_key(Term, Name, 0) :- format(atom(Name), '~q', [Term]).
"""


def _codes(codes):
    return "".join(map(chr, codes))


def _float(text):
    lowered = text.lower()
    if "nan" in lowered:
        return float("nan")
    if "inf" in lowered:
        return float("-inf") if text.startswith("-") else float("inf")
    return float(text)


def _value(item):
    """A Python value for one JSON-encoded Prolog term (see the table)"""
    if item is None:
        return UNBOUND
    if isinstance(item, int):
        return item
    if isinstance(item, list):
        return tuple(_value(element) for element in item)
    if "atom" in item:
        return _codes(item["atom"])
    if "string" in item:
        return _codes(item["string"])
    if "float" in item:
        return _float(_codes(item["float"]))
    if "rational" in item:
        return fractions.Fraction(*item["rational"])
    if "compound" in item:
        return Compound(
            _codes(item["compound"]), tuple(_value(arg) for arg in item["args"])
        )
    return Other(_codes(item["other"]))


def _error_text(line):
    term = _codes(line["error"])
    message = _codes(line["message"]).strip()
    return "{}: {}".format(term, message) if message else term


def _run(job, body, timeout):
    """Run the driver with ``job``; return (output lines, stderr, status)

    ``status`` is the exit status, or None when the process timed out.
    """
    swipl = swipl_or_skip()
    with tempfile.TemporaryDirectory(prefix="nowtest-swipl-") as directory:
        driver = os.path.join(directory, "driver.pl")
        output = os.path.join(directory, "output.jsonl")
        with open(driver, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_PRELUDE)
            handle.write(body)
            handle.write("\njob({}, {}).\n".format(quoted_atom(_posix(output)), job))
        process = subprocess.Popen(
            [
                swipl,
                "-f",
                "none",
                "-q",
                "-g",
                "nowtest_swipl:main",
                "-t",
                "halt",
                driver,
            ],
            cwd=directory,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        stderr, status = _wait(process, output, timeout)
        lines = []
        if os.path.exists(output):
            with open(output, encoding="utf-8") as handle:
                for line in handle:
                    try:
                        lines.append(json.loads(line))
                    except ValueError:
                        break  # cut short by the timeout
    return lines, stderr, status


def _wait(process, output, timeout):
    """Wait for ``swipl``; return (stderr, exit status or None)

    None when the process was killed: at ``timeout``, or ``EXIT_GRACE``
    seconds after it wrote ``{"done":true}`` without exiting. Ubuntu's
    SWI-Prolog 9 sometimes blocks in the ``halt`` that follows a goal run
    under ``call_with_time_limit``; its output is complete then, so the
    callers take it, and a warning says that the process had to be killed.
    """
    deadline = time.monotonic() + timeout
    done_at = None
    while True:
        try:
            _, stderr = process.communicate(timeout=WAIT_SLICE)
            return stderr, process.returncode
        except subprocess.TimeoutExpired:
            pass
        now = time.monotonic()
        if done_at is None and _finished(output):
            done_at = now
        late = done_at is not None and now - done_at > EXIT_GRACE
        if late or now > deadline:
            process.kill()
            _, stderr = process.communicate()
            if late:
                warnings.warn(
                    "swipl wrote its whole output and did not exit within "
                    "{} s; killed".format(EXIT_GRACE),
                    RuntimeWarning,
                )
            return stderr, None


def _finished(output):
    """Whether the driver wrote its last line, ``{"done":true}``"""
    try:
        with open(output, encoding="utf-8") as handle:
            return any(
                json.loads(line).get("done") for line in handle if line.endswith("\n")
            )
    except (OSError, ValueError):
        return False


def _text(data):
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return data or ""


def _posix(path):
    """A path as SWI-Prolog reads it on every system: absolute, with /"""
    return os.path.abspath(os.fspath(path)).replace(os.sep, "/")


def _stopped(status, timeout):
    if status is None:
        return "swipl did not finish within {} s".format(timeout)
    return "swipl stopped before the goal finished (exit status {})".format(status)


def solutions(facts_path, goal, variables, time_limit=10, inference_limit=5_000_000):
    """Load ``facts_path`` into ``swipl`` and collect the solutions of ``goal``

    ``facts_path`` is a file (or a list of files, loaded in order) in UTF-8,
    such as the stdout of ``now export prolog -r``; ``goal`` is the text of
    a goal; ``variables`` names the variables of the goal whose values make
    up each solution, as a list or a space-separated string (``"A B"``; a
    name that the goal does not use raises ValueError). Returns
    ``Solutions(rows, error, stderr)``; the mapping of terms to Python is in
    the module docstring.

    ``time_limit`` (seconds) bounds the whole enumeration, through
    ``call_with_time_limit``; ``inference_limit`` bounds the inferences of
    each solution, through ``call_with_inference_limit`` (None lifts it).
    Each limit ends the goal with an error (``time_limit_exceeded``,
    ``inference_limit_exceeded``) and keeps the rows found before it. A goal
    that loops without inferences (a hang in a builtin) is stopped by the
    time limit; one that keeps the process from reaching it, by a timeout of
    the process ``PROCESS_MARGIN`` seconds later, which also covers loading
    the facts (SWI-Prolog does not deliver the time limit while a directive
    runs). Keep ``time_limit`` small for a goal that is known to hang, so
    that its test stays fast. Never call ``halt`` in the goal: SWI-Prolog 10
    turns it into an error that ends the process, while 9 (Ubuntu's
    ``swi-prolog-nox``) blocks under ``call_with_time_limit`` until the
    process timeout.

    Skips the test when ``swipl`` is not on the PATH.
    """
    if isinstance(variables, str):
        variables = variables.split()
    variables = list(variables)
    for name in variables:
        if not VARIABLE_NAME.match(name):
            raise ValueError("{!r} is not a Prolog variable name".format(name))
    if isinstance(facts_path, (str, os.PathLike)):
        facts_path = [facts_path]
    facts_path = list(facts_path)
    files = []
    for path in facts_path:
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        files.append(quoted_atom(_posix(path)))
    if not time_limit > 0:
        raise ValueError("time_limit must be positive")
    limit = "none" if inference_limit is None else str(int(inference_limit))
    job = "query([{}], {}, [{}], {:.3f}, {})".format(
        ", ".join(files),
        quoted_atom(goal),
        ", ".join(quoted_atom(name) for name in variables),
        time_limit,
        limit,
    )
    timeout = time_limit + PROCESS_MARGIN
    lines, stderr, status = _run(job, _SOLUTIONS, timeout)
    rows, error, ended, done = [], None, False, False
    for line in lines:
        if line.get("q") == -1:
            raise RuntimeError(
                "swipl could not load {}: {}".format(
                    ", ".join(map(os.fspath, facts_path)), _error_text(line)
                )
            )
        if "missing" in line:
            raise ValueError(
                "the goal {!r} does not use the variables {}".format(
                    goal, _codes(line["missing"])
                )
            )
        if "row" in line:
            rows.append(tuple(_value(item) for item in line["row"]))
        elif "error" in line:
            error = _error_text(line)
        elif "end" in line:
            ended = True
        elif line.get("done"):
            done = True
    # Killed between the end of the goal and the last line, the process may
    # have lost rows it had not flushed: only "done" proves the output whole.
    if not (ended and done) and error is None:
        error = _stopped(status, timeout)
    return Solutions(rows, error, stderr)


def read_terms(path, time_limit=10):
    """Read ``path`` term by term with ``read_term`` and count the clauses

    Nothing is consulted: no directive runs, no clause is added, so a file
    that would print warnings or fail to load is still read whole (an
    ``op/3`` directive is not applied either). After a syntax error the
    reader resumes at the next clause, as ``consult`` does; an error inside
    an unterminated quoted atom swallows the rest of the file, and any other
    error of ``read_term`` (an I/O error) is listed too and ends the reading.
    Returns
    ``ReadTerms(clauses, errors)``. Skips the test when ``swipl`` is not on
    the PATH.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    job = "read({}, {:.3f})".format(quoted_atom(_posix(path)), time_limit)
    timeout = time_limit + PROCESS_MARGIN
    lines, stderr, status = _run(job, _READ_TERMS, timeout)
    clauses, errors, done = collections.Counter(), [], False
    for line in lines:
        if "clause" in line:
            clauses[(_codes(line["clause"]), line["arity"])] += 1
        elif "line" in line:
            errors.append(
                "{}:{}: {}".format(
                    line["line"], line["column"], _codes(line["message"]).strip()
                )
            )
        elif "error" in line:
            raise RuntimeError(
                "swipl could not read {}: {}".format(os.fspath(path), _error_text(line))
            )
        elif line.get("done"):
            done = True
    if not done:
        raise RuntimeError(
            "{} reading {}\n{}".format(
                _stopped(status, timeout), os.fspath(path), stderr
            )
        )
    return ReadTerms(clauses, errors)
