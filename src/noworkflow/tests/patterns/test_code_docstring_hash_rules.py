# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The code, docstring and hash rules, in Python and in rules.pl

``code_line_id`` and ``map_code_lines_id`` (``patterns/rules/
code_rules.py``), ``code_docstring_id``, ``activation_docstring_id``,
``docstring_id`` and ``docstring`` (``docstring_rules.py``), and
``hash_id``, ``changed_id``, ``hash`` and ``changed`` (``hash_rules.py``)
exist as Python rules, run here in-process on ``connected_two_trials``,
and as predicates of ``resources/rules.pl``, run by ``swipl`` over the
facts of ``now export prolog -r`` for the same trial
(``two_trial_prolog``). Both are compared, for each of the two trials,
with what SQL finds in the store's ``db.sqlite``, as multisets. On the
rules.pl side, code component names are spelled as the export's own facts
spell them (#103; ``test_id_name_rules.py`` checks that they differ from
the store's only for string literals), and access ids (``f<id>``, #57) and
``nil`` are mapped back.

``map_code_lines_id(T, Ids, Lines)`` is rules.pl's ``bagof`` of each id's
lines, appended and sorted: Lines is the sorted union of the lines of the
ids, in any order. The Python rule (``helpers._bagof_append_sort``) differs
in two ways, both bagof-append-sort-compare: it intersects the lines it
finds with a bound Lines before comparing, so it accepts any subset of
them, and it compares the ids it found, as a sorted set, with Ids as
given, so ids out of order or repeated find nothing. ``hash_id`` with an
unbound moment binds it only on the first result of each moment
(rule-option-binding-lost). ``docstring`` with an unbound name never
answers in rules.pl, because ``name`` enumerates lists for an unbound id
(rules-pl-name-enumerates-lists); the rules.pl cases bind the name through
``setof`` over the facts instead.
"""
import collections

import pytest

from noworkflow.patterns import BLANK, var
from noworkflow.patterns import rules
from noworkflow.tests.helpers import swipl
from noworkflow.tests.patterns.support import (
    Defect, assert_rows, bindings, defect_marks, known_defects,
    normalize_prolog,
)

TRIALS = pytest.mark.parametrize("number", [1, 2], ids=["trial1", "trial2"])
NEEDS_SWIPL = pytest.mark.skipif(swipl.SWIPL is None,
                                 reason=swipl.SKIP_REASON)
# Two code components that span the first lines of the script, and the one
# whose lines they are compared with (the module docstring and its
# expression).
SPANNING = [2, 3]

BAGOF_REASON = (
    "#347: helpers._bagof_append_sort intersects "
    "the lines it finds with a bound Lines and compares the sorted set of "
    "the ids it found with Ids as given, where rules.pl appends each id's "
    "bagof of lines and sorts the result")
BAGOF_SUBSET = Defect(BAGOF_REASON, "accepts a proper subset")
BAGOF_ORDER = Defect(BAGOF_REASON, "map_code_lines_id([3, 2]) -> []")
# The signature is the end of a row whose last value, Moment, is BLANK
# (printed _), not any unbound value.
OPTION_BINDING = Defect(
    "#344: hash_id explores its restricted option "
    "model_moment when it is unbound, and RuleQuery.apply_function resets "
    "the variable that prepare_values bound after the first result of each "
    "moment",
    ", _)")
NAME_LISTS = Defect(
    "#350: docstring/4 calls name/4 with Id "
    "unbound, and the name rules of rules.pl enumerate [], [[]]... before "
    "their scalar clause, so docstring with an unbound name never answers",
    "Time limit exceeded")


class PythonSide:
    """The store's names as the Python rules answer them: unchanged"""

    @staticmethod
    def name(code_id, name):
        return name


class PrologSide:
    """The store's code component names as the export spells them"""

    def __init__(self, spellings):
        self.spellings = spellings

    def name(self, code_id, name):
        return self.spellings[code_id]


PYTHON = PythonSide()


def trial_id(project, number):
    return project.trials()[number - 1]["id"]


def sql_rows(project, sql, *params):
    """The rows of a query as tuples (give columns distinct names)"""
    return [tuple(row.values()) for row in project.query(sql, *params)]


# --- what the store holds ----------------------------------------------------


def code_lines(project, trial, side):
    """(Id, Line) for every line from first_char_line to last_char_line"""
    return [(code, line) for code, first, last in sql_rows(
        project, "SELECT id, first_char_line, last_char_line "
        "FROM code_component WHERE trial_id = ?", trial)
        for line in range(first, last + 1)]


def lines_of(identifier):
    def expected(project, trial, side):
        return [(line,) for code, line in code_lines(project, trial, side)
                if code == identifier]
    return expected


def ids_on(line):
    def expected(project, trial, side):
        return [(code,) for code, found in code_lines(project, trial, side)
                if found == line]
    return expected


def union_of_lines(identifiers):
    """One row: the sorted union of the lines of ``identifiers``"""
    def expected(project, trial, side):
        return [(tuple(sorted({
            line for code, line in code_lines(project, trial, side)
            if code in identifiers})),)]
    return expected


def nothing(project, trial, side):
    return []


def block_docstrings(project, trial, side):
    return sql_rows(project, "SELECT id, docstring FROM code_block "
                    "WHERE trial_id = ?", trial)


ACTIVATION_BLOCKS = (
    "FROM activation JOIN code_block "
    "ON code_block.trial_id = activation.trial_id "
    "AND code_block.id = activation.code_block_id ")


def activation_docstrings(project, trial, side):
    return sql_rows(
        project, "SELECT activation.id, code_block.docstring "
        + ACTIVATION_BLOCKS + "WHERE activation.trial_id = ?", trial)


def block_names_and_docstrings(project, trial, side):
    """(Name, Docstring) of each code block, named by its code component"""
    return [(side.name(code, name), docstring)
            for code, name, docstring in sql_rows(
                project, "SELECT code_component.id AS code_id, "
                "code_component.name, code_block.docstring "
                "FROM code_block JOIN code_component "
                "ON code_component.trial_id = code_block.trial_id "
                "AND code_component.id = code_block.id "
                "WHERE code_block.trial_id = ?", trial)]


def evaluation_names_and_docstrings(project, trial, side):
    """(Name, Docstring) of each activation with a code block, named by
    the code component of its evaluation
    """
    return [(side.name(code, name), docstring)
            for code, name, docstring in sql_rows(
                project, "SELECT code_component.id AS code_id, "
                "code_component.name, code_block.docstring "
                + ACTIVATION_BLOCKS + "JOIN evaluation "
                "ON evaluation.trial_id = activation.trial_id "
                "AND evaluation.id = activation.id "
                "JOIN code_component "
                "ON code_component.trial_id = evaluation.trial_id "
                "AND code_component.id = evaluation.code_component_id "
                "WHERE activation.trial_id = ?", trial)]


def activation_names_and_docstrings(project, trial, side):
    return sql_rows(
        project, "SELECT activation.name, code_block.docstring "
        + ACTIVATION_BLOCKS + "WHERE activation.trial_id = ?", trial)


DOCSTRING_IDS = {
    "code_component": block_docstrings,
    "code_block": block_docstrings,
    "evaluation": activation_docstrings,
    "activation": activation_docstrings,
}
DOCSTRINGS = {
    "code_component": block_names_and_docstrings,
    "code_block": block_names_and_docstrings,
    "evaluation": evaluation_names_and_docstrings,
    "activation": activation_names_and_docstrings,
}

HASH_COLUMNS = {
    "before": "content_hash_before",
    "after": "content_hash_after",
}


def hash_ids(moment):
    """(Id, Hash) of the accesses before or after, or of the code blocks"""
    def expected(project, trial, side):
        if moment == "code_block":
            return sql_rows(project, "SELECT id, code_hash FROM code_block "
                            "WHERE trial_id = ?", trial)
        return sql_rows(project, "SELECT id, {} FROM file_access "
                        "WHERE trial_id = ?".format(HASH_COLUMNS[moment]),
                        trial)
    return expected


def hash_ids_of_every_moment(project, trial, side):
    return [row + (moment,)
            for moment in ("before", "after", "code_block")
            for row in hash_ids(moment)(project, trial, side)]


def hashes_by_name(moment):
    """(Name, Hash) of the accesses by file name, or of the code blocks by
    the name of their code component
    """
    def expected(project, trial, side):
        if moment == "code_block":
            return [(side.name(code, name), code_hash)
                    for code, name, code_hash in sql_rows(
                        project, "SELECT code_component.id AS code_id, "
                        "code_component.name, code_block.code_hash "
                        "FROM code_block JOIN code_component "
                        "ON code_component.trial_id = code_block.trial_id "
                        "AND code_component.id = code_block.id "
                        "WHERE code_block.trial_id = ?", trial)]
        return sql_rows(project, "SELECT name, {} FROM file_access "
                        "WHERE trial_id = ?".format(HASH_COLUMNS[moment]),
                        trial)
    return expected


CHANGED = ("FROM file_access WHERE trial_id = ? "
           "AND content_hash_before IS NOT content_hash_after")


def changed_ids(project, trial, side):
    return sql_rows(project, "SELECT id " + CHANGED, trial)


def changed_names(project, trial, side):
    return sql_rows(project, "SELECT name " + CHANGED, trial)


# --- the Python rules --------------------------------------------------------


def rule_case(case_id, rule, names, expected, *defects):
    """``rule(trial, *variables)``, the variables named by ``names``"""
    return pytest.param(rule, names, expected, defects, id=case_id,
                        marks=defect_marks(defects))


RULE_CASES = [
    rule_case("code_line_id", rules.code_line_id, "Id Line", code_lines),
    rule_case("code_line_id-of-1",
              lambda t, line: rules.code_line_id(t, 1, line), "Line",
              lines_of(1)),
    rule_case("code_line_id-on-line-3",
              lambda t, i: rules.code_line_id(t, i, 3), "Id", ids_on(3)),
    rule_case("map_code_lines_id", lambda t, lines: rules.map_code_lines_id(
        t, SPANNING, lines), "Lines", union_of_lines(SPANNING)),
    rule_case("map_code_lines_id-unknown-id",
              lambda t, lines: rules.map_code_lines_id(t, [2, 999999], lines),
              "Lines", nothing),
    rule_case("map_code_lines_id-scalar-id",
              lambda t, lines: rules.map_code_lines_id(t, 2, lines), "Lines",
              nothing),
    rule_case("code_docstring_id", rules.code_docstring_id, "Id Docstring",
              block_docstrings),
    rule_case("activation_docstring_id", rules.activation_docstring_id,
              "Id Docstring", activation_docstrings),
] + [
    rule_case("docstring_id-" + model,
              lambda t, i, d, model=model: rules.docstring_id(t, model, i, d),
              "Id Docstring", DOCSTRING_IDS[model])
    for model in DOCSTRING_IDS
] + [
    rule_case("docstring-" + model,
              lambda t, n, d, model=model: rules.docstring(t, model, n, d),
              "Name Docstring", DOCSTRINGS[model])
    for model in DOCSTRINGS
] + [
    rule_case("hash_id-" + moment,
              lambda t, i, h, moment=moment: rules.hash_id(t, i, h, moment),
              "Id Hash", hash_ids(moment))
    for moment in ("before", "after", "code_block")
] + [
    rule_case("hash_id-unbound-moment", rules.hash_id, "Id Hash Moment",
              hash_ids_of_every_moment, OPTION_BINDING),
] + [
    rule_case("hash-" + moment,
              lambda t, n, h, moment=moment: rules.hash(t, n, h, moment),
              "Name Hash", hashes_by_name(moment))
    for moment in ("before", "after", "code_block")
] + [
    rule_case("changed_id", rules.changed_id, "Id", changed_ids),
    rule_case("changed", rules.changed, "Name", changed_names),
]


@TRIALS
@pytest.mark.parametrize("rule, names, expected, defects", RULE_CASES)
def test_rule_matches_the_store(connected_two_trials, number, rule, names,
                                expected, defects):
    """The Python rule answers the rows SQL finds for the trial"""
    project = connected_two_trials
    trial = trial_id(project, number)
    variables = [var(name) for name in names.split()]
    assert_rows(lambda: bindings(rule(trial, *variables), *variables),
                expected(project, trial, PYTHON), defects)


@TRIALS
def test_hash_id_with_an_unbound_moment_binds_it_once_per_moment(
        connected_two_trials, number):
    """``hash_id(T, Id, Hash, Moment)`` binds Moment on the first result of
    before, after and code_block, and leaves it BLANK on every other result
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    store = collections.Counter(row[2] for row in hash_ids_of_every_moment(
        project, trial, PYTHON))
    identifier, code_hash, moment = var("Id Hash Moment")
    found = collections.Counter(row[0] for row in bindings(
        rules.hash_id(trial, identifier, code_hash, moment), moment))
    expected = {value: 1 for value in store}
    expected[BLANK] = sum(store.values()) - len(store)
    assert found == expected


def spanned_lines(project, trial):
    """The sorted union of the lines of the SPANNING components"""
    (lines,), = union_of_lines(SPANNING)(project, trial, PYTHON)
    assert len(lines) > 2, "the components span {}".format(lines)
    return list(lines)


def solutions(query):
    return len(list(query))


@TRIALS
def test_map_code_lines_id_checks_a_bound_list_of_lines(
        connected_two_trials, number):
    """Control: the exact sorted union of the lines is one solution; a list
    with a line outside them, or a missing id, is none
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    lines = spanned_lines(project, trial)
    assert solutions(rules.map_code_lines_id(trial, SPANNING, lines)) == 1
    assert solutions(rules.map_code_lines_id(
        trial, SPANNING, lines + [lines[-1] + 1000])) == 0
    assert solutions(rules.map_code_lines_id(
        trial, SPANNING, lines[:1] + [lines[-1] + 1000])) == 0
    assert solutions(rules.map_code_lines_id(
        trial, SPANNING + [999999], lines)) == 0


@TRIALS
def test_map_code_lines_id_accepts_a_subset_of_the_lines(
        connected_two_trials, number):
    """A bound list with only some of the lines is one solution too"""
    project = connected_two_trials
    trial = trial_id(project, number)
    lines = spanned_lines(project, trial)
    for subset in (lines[:2], lines[:1], lines[1:]):
        assert solutions(rules.map_code_lines_id(
            trial, SPANNING, subset)) == 1, subset


@TRIALS
@known_defects(BAGOF_SUBSET)
def test_map_code_lines_id_rejects_a_subset_of_the_lines_desired(
        connected_two_trials, number):
    """Lines must be the whole sorted union, as rules.pl's bagof, append
    and sort make it: a proper subset is no solution
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    lines = spanned_lines(project, trial)
    accepted = [subset for subset in (lines[:2], lines[:1], lines[1:])
                if solutions(rules.map_code_lines_id(
                    trial, SPANNING, subset))]
    assert not accepted, (
        "map_code_lines_id({}) accepts a proper subset of the lines {}: {}"
        .format(SPANNING, lines, accepted))


def lines_of_ids(trial, identifiers):
    """The Lines that map_code_lines_id binds for ``identifiers``"""
    found = var("Lines")
    return bindings(rules.map_code_lines_id(trial, identifiers, found),
                    found)


@TRIALS
def test_map_code_lines_id_of_unsorted_or_repeated_ids_finds_nothing(
        connected_two_trials, number):
    """The ids must come sorted and without repeats: [3, 2] and [2, 2]
    answer nothing, while [2, 3] answers the union of their lines
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    assert lines_of_ids(trial, [2, 3]) == [(tuple(spanned_lines(
        project, trial)),)]
    assert lines_of_ids(trial, [3, 2]) == []
    assert lines_of_ids(trial, [2, 2]) == []


@TRIALS
@known_defects(BAGOF_ORDER)
def test_map_code_lines_id_ignores_the_order_and_repeats_of_the_ids_desired(
        connected_two_trials, number):
    """Lines is the sorted union of the lines of the ids, whatever their
    order and repeats, as rules.pl's bagof, append and sort make it
    """
    project = connected_two_trials
    trial = trial_id(project, number)
    failures = []
    for identifiers in ([3, 2], [2, 2]):
        expected = union_of_lines(identifiers)(project, trial, PYTHON)
        found = lines_of_ids(trial, identifiers)
        if found != expected:
            failures.append("map_code_lines_id({}) -> {}".format(
                identifiers, [list(lines) for lines, in found]))
    assert not failures, "; ".join(failures)


# --- rules.pl ----------------------------------------------------------------


@pytest.fixture(scope="module")
def spellings(two_trial_prolog):
    """``{trial id: {code component id: its name in the export}}``"""
    result = {}
    for trial, path in two_trial_prolog.items():
        rows = swipl.solutions(
            path, "code_component({}, Id, Name, _, _, _, _, _, _, _)".format(
                swipl.quoted_atom(trial)), "Id Name").rows_or_raise()
        result[trial] = dict(rows)
    return result


def prolog_case(case_id, goal, names, expected, *defects, ids=()):
    """``goal`` over the trial's facts, T bound to the trial id

    ``ids`` lists the columns that hold access ids or nullable hashes,
    which ``normalize_prolog`` maps back to the store's.
    """
    return pytest.param(goal, names, ids, expected, defects, id=case_id,
                        marks=defect_marks(defects))


# Every name of a code component, each once: docstring/4 cannot enumerate
# them (rules-pl-name-enumerates-lists).
CODE_NAMES = ("setof(N, I^A^B^C^D^E^F^G^code_component("
              "T, I, N, A, B, C, D, E, F, G), Names), member(Name, Names)")
ACTIVATION_NAMES = ("setof(N, I^A^B^activation(T, I, N, A, B), Names), "
                    "member(Name, Names)")
NAMES_OF_MODEL = {
    "code_component": CODE_NAMES,
    "code_block": CODE_NAMES,
    "evaluation": CODE_NAMES,
    "activation": ACTIVATION_NAMES,
}

PROLOG_CASES = [
    prolog_case("code_line_id", "code_line_id(T, Id, Line)", "Id Line",
                code_lines),
    prolog_case("code_line_id-of-1", "code_line_id(T, 1, Line)", "Line",
                lines_of(1)),
    prolog_case("code_line_id-on-line-3", "code_line_id(T, Id, 3)", "Id",
                ids_on(3)),
    prolog_case("map_code_lines_id", "map_code_lines_id(T, {}, Lines)".format(
        SPANNING), "Lines", union_of_lines(SPANNING)),
    prolog_case("map_code_lines_id-unsorted",
                "map_code_lines_id(T, [3, 2], Lines)", "Lines",
                union_of_lines([2, 3])),
    prolog_case("map_code_lines_id-repeated",
                "map_code_lines_id(T, [2, 2], Lines)", "Lines",
                union_of_lines([2])),
    prolog_case("map_code_lines_id-unknown-id",
                "map_code_lines_id(T, [2, 999999], Lines)", "Lines", nothing),
    prolog_case("map_code_lines_id-scalar-id",
                "map_code_lines_id(T, 2, Lines)", "Lines", nothing),
    prolog_case("code_docstring_id", "code_docstring_id(T, Id, Docstring)",
                "Id Docstring", block_docstrings),
    prolog_case("activation_docstring_id",
                "activation_docstring_id(T, Id, Docstring)", "Id Docstring",
                activation_docstrings),
] + [
    prolog_case("docstring_id-" + model,
                "docstring_id(T, {}, Id, Docstring)".format(model),
                "Id Docstring", DOCSTRING_IDS[model])
    for model in DOCSTRING_IDS
] + [
    prolog_case("docstring-" + model,
                "{}, docstring(T, {}, Name, Docstring)".format(
                    NAMES_OF_MODEL[model], model),
                "Name Docstring", DOCSTRINGS[model])
    for model in DOCSTRINGS
] + [
    prolog_case("hash_id-" + moment,
                "hash_id(T, Id, Hash, {})".format(moment), "Id Hash",
                hash_ids(moment), ids=(0, 1))
    for moment in ("before", "after", "code_block")
] + [
    prolog_case("hash_id-unbound-moment", "hash_id(T, Id, Hash, Moment)",
                "Id Hash Moment", hash_ids_of_every_moment, ids=(0, 1)),
] + [
    prolog_case("hash-" + moment, "hash(T, Name, Hash, {})".format(moment),
                "Name Hash", hashes_by_name(moment), ids=(1,))
    for moment in ("before", "after", "code_block")
] + [
    prolog_case("changed_id", "changed_id(T, Id)", "Id", changed_ids,
                ids=(0,)),
    prolog_case("changed", "changed(T, Name)", "Name", changed_names),
]


@NEEDS_SWIPL
@TRIALS
@pytest.mark.parametrize("goal, names, ids, expected, defects", PROLOG_CASES)
def test_rules_pl_matches_the_store(two_trial_project, two_trial_prolog,
                                    spellings, number, goal, names, ids,
                                    expected, defects):
    """The predicate of rules.pl answers the rows SQL finds for the trial"""
    project = two_trial_project
    trial = trial_id(project, number)

    def answer():
        rows = swipl.solutions(
            two_trial_prolog[trial],
            "T = {}, {}".format(swipl.quoted_atom(trial), goal),
            names).rows_or_raise()
        return [tuple(normalize_prolog(value) if index in ids else value
                      for index, value in enumerate(row)) for row in rows]

    assert_rows(answer, expected(project, trial, PrologSide(
        spellings[trial])), defects)


@NEEDS_SWIPL
@TRIALS
def test_rules_pl_map_code_lines_id_rejects_a_subset_of_the_lines(
        two_trial_project, two_trial_prolog, number):
    """Control for bagof-append-sort-compare: rules.pl answers the exact
    union of the lines once, and a proper subset of it never
    """
    project = two_trial_project
    trial = trial_id(project, number)
    lines = spanned_lines(project, trial)
    for given, count in ((lines, 1), (lines[:2], 0), (lines[:1], 0),
                         (lines[1:], 0)):
        found = swipl.solutions(
            two_trial_prolog[trial], "T = {}, map_code_lines_id(T, {}, {})"
            .format(swipl.quoted_atom(trial), SPANNING, given), [])
        assert found.rows_or_raise() == [()] * count, given


@NEEDS_SWIPL
@known_defects(NAME_LISTS)
def test_rules_pl_docstring_by_an_unbound_name_desired(
        two_trial_project, two_trial_prolog, spellings):
    """``docstring(T, code_block, Name, Docstring)`` with Name unbound
    answers each code block's name and docstring (trial 1; one second is
    hundreds of times what the answer takes)
    """
    project = two_trial_project
    trial = trial_id(project, 1)
    rows = swipl.solutions(
        two_trial_prolog[trial], "T = {}, docstring(T, code_block, Name, "
        "Docstring)".format(swipl.quoted_atom(trial)), "Name Docstring",
        time_limit=1).rows_or_raise()
    assert_rows(lambda: rows, block_names_and_docstrings(
        project, trial, PrologSide(spellings[trial])))
