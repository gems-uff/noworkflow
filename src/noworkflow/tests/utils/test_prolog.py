# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``utils/prolog.py``: how each attribute of a fact is written as Prolog

``now export prolog`` writes every model through a ``PrologDescription``
whose attributes say how a column becomes Prolog text: a number as it is
(``PrologAttribute``), a trial id or a text as a quoted atom
(``PrologTrial``, ``PrologRepr``), a time as seconds since the epoch or
``nil`` (``PrologTimestamp``), a missing value as ``nil`` (the
``Nullable`` attributes), a flag as ``1`` or ``0`` (``PrologBoolean``).
The export goldens cover the descriptions of the real models; these tests
pin each attribute on values chosen for the case, with ``SimpleNamespace``
stand-ins for the model objects.

The expected atoms come from ``helpers.swipl.quoted_atom``, ISO Prolog's
quoting written independently of ``PrologRepr`` (a quote doubled, a
backslash escaped), and the round trip through ``swipl`` checks that
SWI-Prolog reads each fact back as the value it was given.
``PrologRepr`` also strips what a ``repr()`` adds (the quotes of a string,
#103, and the letter before them, as in ``b'...'``); since #111 it no
longer calls ``repr()`` on text but applies the same heuristics to it, so
a file name such as ``l'Avenue.txt``, whose second character is a quote,
loses its first letter (prolog-repr-strips-letter-before-quote, with a
characterization and a ``_desired`` twin; the e2e side is in
``e2e/test_serializers_cli.py``).

``PrologTimestamp.use_nil`` is a class attribute that ``now export prolog
-t`` sets and nothing resets, so every test that reads a timestamp sets it
first.
"""

import calendar
from datetime import datetime
from types import SimpleNamespace as NS

import pytest

from noworkflow.now.utils.prolog import (
    PrologAttribute,
    PrologBoolean,
    PrologDescription,
    PrologNullable,
    PrologNullableRepr,
    PrologRepr,
    PrologTimestamp,
    PrologTrial,
)
from noworkflow.tests.helpers import swipl
from noworkflow.tests.helpers.defects import Defect, known_defects

LETTER_BEFORE_QUOTE = Defect(
    "#338: PrologRepr.fact "
    "(utils/prolog.py) applies the heuristics meant for a stored repr() to "
    "plain text: when the second character is a quote it drops the first "
    "(meant for the b of b'...'), and then drops a leading quote that "
    "matches the last character, so `now export prolog` writes the file "
    "name l'Avenue.txt as '''Avenue.txt', which Prolog reads as "
    "'Avenue.txt",
    signature="'''Avenue.txt'",
)


def description():
    """A fact with a trial id, a number and a text, like ``access/8``"""
    return PrologDescription(
        "access",
        (PrologTrial("trial_id"), PrologAttribute("id"), PrologRepr("name")),
        description="first line\nsecond line",
    )


def repr_fact(value):
    """The text ``PrologRepr`` writes for ``value``"""
    return PrologRepr("v").fact(NS(v=value))


# --- PrologDescription ------------------------------------------------------


def test_description_repr_names_each_attribute_as_a_camel_case_variable():
    """The fact definition names each attribute as a Prolog variable: an
    upper-case CamelCase word (#103)"""
    assert repr(description()) == "access(TrialId, Id, Name)."


def test_description_comment_is_made_of_prolog_comment_lines():
    """The comment holds only blank lines and ``%`` lines, shows the fact
    definition and the description's lines in order; an empty description
    has no DESCRIPTION line"""
    desc = description()
    comment = desc.comment()
    lines = comment.split("\n")
    assert all(line == "" or line.startswith("%") for line in lines), lines
    assert "% FACT DEFINITION: access(TrialId, Id, Name)." in lines
    described = [line for line in lines if "line" in line]
    assert len(described) == 2, lines
    assert described[0].startswith("% DESCRIPTION: ")
    assert described[0].endswith("first line")
    assert described[1].startswith("% ")
    assert described[1].endswith("second line")
    bare = PrologDescription("bare", (PrologAttribute("id"),)).comment()
    assert "DESCRIPTION" not in bare
    assert "% FACT DEFINITION: bare(Id)." in bare.split("\n")


def test_description_dynamic_declares_the_name_and_the_arity():
    """``dynamic/1`` gets ``Name/Arity``, the arity being the number of
    attributes"""
    assert description().dynamic() == ":- dynamic(access/3)."


def test_description_fact_joins_the_fact_of_each_attribute(monkeypatch):
    """A fact is the name and each attribute's text, comma separated, with
    a period; a missing time is the integer -1, joined as text"""
    monkeypatch.setattr(PrologTimestamp, "use_nil", False)
    desc = PrologDescription(
        "access",
        (
            PrologTrial("trial_id"),
            PrologAttribute("id"),
            PrologRepr("name"),
            PrologTimestamp("start"),
        ),
    )
    obj = NS(trial_id="t1", id=7, name="'n'", start=None)
    assert desc.fact(obj) == "access({}, 7, {}, -1).".format(
        swipl.quoted_atom("t1"), swipl.quoted_atom("n")
    )


def test_description_empty_fact_has_a_zero_per_attribute():
    """The placeholder fact has one ``0`` per attribute"""
    assert description().empty() == "access(0, 0, 0)."


def test_description_retract_binds_only_the_trial_id():
    """``retract`` matches the facts of one trial: its id as a quoted atom,
    the anonymous variable for every other attribute"""
    assert description().retract("t'1") == "retract(access({}, _, _))".format(
        swipl.quoted_atom("t'1")
    )


# --- PrologAttribute and PrologTrial ----------------------------------------


def test_attribute_reads_a_dotted_attr_name_and_prefers_fn():
    """A dotted ``attr_name`` follows the attributes in turn, ``fn`` is
    applied to the object instead, and ``link`` is kept"""
    dotted = PrologAttribute("x", attr_name="a.b.c")
    assert dotted.fact(NS(a=NS(b=NS(c=42)))) == "42"
    computed = PrologAttribute(
        "id", fn=lambda obj: "f{}".format(obj.id), link="evaluation.id"
    )
    assert computed.fact(NS(id=3)) == "f3"
    assert computed.link == "evaluation.id"


def test_trial_attribute_quotes_the_id_and_doubles_its_quotes():
    """A trial id is written as a quoted atom"""
    assert PrologTrial("id").fact(NS(id="ab'c")) == swipl.quoted_atom("ab'c")


# --- PrologRepr -------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "it's",
        "back\\slash",
        "end\\",
    ],
    ids=["plain", "quote", "backslash", "trailing-backslash"],
)
def test_repr_quotes_a_string_doubling_quotes_and_backslashes(value):
    """A text is written as the quoted atom of the same name"""
    assert repr_fact(value) == swipl.quoted_atom(value)


def test_repr_strips_the_quotes_of_a_string_repr():
    """A stored ``repr()`` of a string loses the quotes it added, single or
    double: the atom's quotes take their place (#103)"""
    assert repr_fact("'abc'") == swipl.quoted_atom("abc")
    assert repr_fact('"abc"') == swipl.quoted_atom("abc")


@pytest.mark.parametrize(
    "value",
    [1, 1.5, None, True, (1, "a")],
    ids=["int", "float", "None", "bool", "tuple"],
)
def test_repr_formats_a_value_that_is_not_a_string_with_repr(value):
    """A value that is not a string is written as the quoted atom of its
    ``repr()``"""
    assert repr_fact(value) == swipl.quoted_atom(repr(value))


def test_repr_strips_the_prefix_letter_of_a_bytes_repr():
    """Bytes lose the ``b`` and the quotes of their ``repr()``:
    ``repr(b"a'b")`` is ``b"a'b"``"""
    assert repr_fact(b"a'b") == swipl.quoted_atom("a'b")


def test_repr_of_a_string_with_an_apostrophe_after_its_first_letter():
    """Characterization: a text whose second character is a quote loses
    its first letter, and then the quote, if the text ends with one"""
    assert repr_fact("l'Avenue.txt") == "'''Avenue.txt'"
    assert repr_fact("O'Brien.csv") == "'''Brien.csv'"
    assert repr_fact("a'") == "''"


@known_defects(LETTER_BEFORE_QUOTE)
def test_repr_of_a_string_with_an_apostrophe_after_its_first_letter_desired():
    """A file name such as ``l'Avenue.txt`` is written as the quoted atom
    of the same name"""
    names = ["l'Avenue.txt", "O'Brien.csv"]
    written = [repr_fact(name) for name in names]
    assert written == [swipl.quoted_atom(name) for name in names], (
        "written as {}".format(written)
    )


VALUES_READ_BY_SWIPL = [
    pytest.param("a\nb", id="newline"),
    pytest.param("tab\there", id="tab"),
    pytest.param("a\rb", id="carriage-return"),
    pytest.param("back\\slash", id="backslash"),
    pytest.param("end\\", id="trailing-backslash"),
    pytest.param("it's", id="quote"),
    pytest.param("é", id="non-ascii"),
    pytest.param("%c", id="percent"),
    pytest.param("a\x00b", id="nul"),
]


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
@pytest.mark.parametrize("value", VALUES_READ_BY_SWIPL)
def test_repr_fact_reads_back_unchanged_in_swipl(tmp_path, value):
    """SWI-Prolog loads the declaration and the fact without a warning, and
    reads the atom back as the value written"""
    desc = PrologDescription("v", (PrologRepr("value"),))
    path = tmp_path / "facts.pl"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("{}\n{}\n".format(desc.dynamic(), desc.fact(NS(value=value))))
    answer = swipl.solutions(path, "v(A)", "A")
    assert answer.stderr == ""
    assert answer.rows_or_raise() == [(value,)]


# --- PrologTimestamp --------------------------------------------------------


def test_timestamp_counts_seconds_since_the_naive_epoch(monkeypatch):
    """A time is written as the seconds since 1970-01-01, fraction
    included"""
    monkeypatch.setattr(PrologTimestamp, "use_nil", False)
    time = datetime(1970, 1, 2, 0, 0, 1, 500000)
    expected = calendar.timegm(time.timetuple()) + time.microsecond / 1e6
    assert expected == 86401.5
    assert float(PrologTimestamp("t").fact(NS(t=time))) == expected


def test_timestamp_of_a_missing_time_is_minus_one(monkeypatch):
    """A missing time (an unfinished trial's finish) is the integer -1"""
    monkeypatch.setattr(PrologTimestamp, "use_nil", False)
    fact = PrologTimestamp("t").fact(NS(t=None))
    assert fact == -1
    assert type(fact) is int


def test_timestamp_prints_nil_when_timestamps_are_hidden(monkeypatch):
    """With ``use_nil`` (``now export prolog -t``) every time is ``nil``"""
    monkeypatch.setattr(PrologTimestamp, "use_nil", True)
    assert PrologTimestamp("t").fact(NS(t=datetime(2020, 1, 1))) == "nil"
    assert PrologTimestamp("t").fact(NS(t=None)) == "nil"


# --- nullable and boolean attributes ----------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "parent_id",
        "modules_inherited_from_trial_id",
        "experiment_id",
        "user_id",
    ],
)
def test_nullable_prints_nil_for_none_and_quotes_trial_references(name):
    """A reference to a trial, an experiment or a user is a quoted atom,
    and ``nil`` when missing"""
    attribute = PrologNullable(name)
    assert attribute.fact(NS(**{name: None})) == "nil"
    assert attribute.fact(NS(**{name: "o'k"})) == swipl.quoted_atom("o'k")


def test_nullable_writes_any_other_value_as_it_is():
    """Under any other name, a value is written with ``str`` and a missing
    one as ``nil``"""
    attribute = PrologNullable("line")
    assert attribute.fact(NS(line=3)) == "3"
    assert attribute.fact(NS(line=None)) == "nil"


def test_nullable_repr_prints_nil_for_none_and_quotes_otherwise():
    """``PrologNullableRepr`` writes ``nil`` for a missing value and a
    quoted atom, as ``PrologRepr`` does, for any other"""
    attribute = PrologNullableRepr("v")
    assert attribute.fact(NS(v=None)) == "nil"
    assert attribute.fact(NS(v="'v'")) == swipl.quoted_atom("v")
    assert attribute.fact(NS(v="w")) == swipl.quoted_atom("w")


@pytest.mark.parametrize(
    "value, expected",
    [
        (1, "1"),
        ([1], "1"),
        (True, "1"),
        (0, "0"),
        (None, "0"),
        ([], "0"),
    ],
    ids=["one", "list", "true", "zero", "none", "empty-list"],
)
def test_boolean_prints_one_or_zero(value, expected):
    """A flag is ``1`` when the value is true in Python, ``0`` otherwise"""
    assert PrologBoolean("v").fact(NS(v=value)) == expected
