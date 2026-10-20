# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now schema prolog`` and the Prolog terms of ``now export prolog``

``test_export.py`` checks that every fact of the export has its declared
number of arguments, counted with commas. Here each argument must also be a
Prolog term that SWI-Prolog reads as atomic (``models/model_rows.ATOMIC``),
and, where ``swipl`` is installed, SWI-Prolog itself reads the export with
the declared arities: an unquoted ``None`` (a variable) or an unquoted UUID
(not a term) passes a comma count. A NULL column must be ``nil``; the
fullpath of a module is the exception today (#353).

``now schema prolog`` prints the descriptions of the exported facts and the
rules, ``-d`` draws the facts; neither depends on a trial, and both are
compared with what ``export prolog`` declares. Without a trial the text form
prints only an error (#253).

The exports hold the environment of the machine and the trial's user id
holds the hostname: the messages report predicates, argument positions and
counts, or text passed through ``project.normalize``. Known defects have a
characterization and a ``_desired`` twin marked through ``known_defects``;
their mechanisms are in Python string formatting and the command's control
flow, the same on every system and Python version (measured on macOS with
3.11 to 3.15).
"""
import collections
import re
from pathlib import Path

import pytest

import noworkflow
from noworkflow.tests.e2e.normalize import (
    prolog_facts,
    prolog_statements,
    strip_prolog_predicate,
)
from noworkflow.tests.e2e.oracle import Defect, known_defects
from noworkflow.tests.helpers import swipl
from noworkflow.tests.models.model_rows import fact_arguments, non_atomic

RULES = Path(noworkflow.__file__).resolve().parent / "resources" / "rules.pl"

# What `now export prolog` writes, in its order (trial_prolog.py).
EXPORTED = ["trial", "tag", "argument", "module", "environment",
            "code_component", "code_block", "activation", "evaluation",
            "dependency", "access", "member"]
DEFINITION = re.compile(r"^% FACT DEFINITION: (\w+)\((.*)\)\.$", re.MULTILINE)
DECLARATION = re.compile(r":- dynamic\((\w+)/(\d+)\)\.")
# A node of the diagram: `name [shape=none label=<...>];`, one port per
# argument.
NODE = re.compile(r"^\s*(\w+) \[shape=none label=<(.*)>\];$", re.MULTILINE)
PORT = re.compile(r'\bPORT="(\w+)"')
NO_TRIAL = "[now] Trial None not found\n"

SCHEMA_WITHOUT_TRIAL = Defect(
    reason="#253: cmd_schema.prolog_text builds TrialProlog(Trial()), and "
           "Trial() raises RuntimeError('Trial None not found') in a "
           "project without trials, which main prints with return code 0; "
           "the descriptions and rules.pl depend on no trial",
    signature="[now] Trial None not found",
)
FULLPATH_NONE = Defect(
    reason="#353: module.py describes fullpath with "
           "PrologRepr, which writes a NULL column as the atom 'None', while "
           "the NULL version of the same fact (PrologNullableRepr) is nil",
    signature="fullpath is 'None', not nil",
)


def rule_lines():
    """The clauses of ``rules.pl``, one per line (a premise pinned in
    ``models/test_prolog_facts.py``)"""
    return [line.strip()
            for line in RULES.read_text(encoding="utf-8").split("\n")
            if line.strip() and not line.strip().startswith("%")]


def declared_arities(text):
    """``{name: N}`` of the ``:- dynamic(name/N).`` of an export, in order"""
    return {name: declared for name, (declared, _)
            in prolog_facts(text).items() if declared is not None}


def facts_of(text):
    """``[(name, body)]`` of the facts of an export"""
    facts = []
    for kind, body in prolog_statements(text):
        match = re.match(r"(\w+)\(", body)
        if kind == "clause" and match:
            facts.append((match.group(1), body.strip()))
    return facts


def last_trial_modules(project):
    """``{id: row}`` of the modules of the last trial, from SQL"""
    trial_id = project.trials()[-1]["id"]
    rows = project.query(
        "SELECT id, version, fullpath FROM module WHERE trial_id = ?",
        trial_id)
    return {row["id"]: row for row in rows}


def module_facts_without_fullpath(project):
    """``[(fact arguments, normalized fact)]`` of the module facts of
    ``export prolog -t`` whose row has a NULL fullpath, which SQL shows"""
    rows = last_trial_modules(project)
    missing = {module_id for module_id, row in rows.items()
               if row["fullpath"] is None}
    # Not vacuous: the weather corpus imports a local module, whose
    # fullpath noWorkflow leaves NULL.
    assert missing, "no module of the last trial has a NULL fullpath"
    found = []
    text = project.run("export", "prolog", "-t").stdout
    for name, body in facts_of(text):
        if name != "module":
            continue
        arguments = [part.strip() for part in fact_arguments(body, name)]
        assert len(arguments) == 8, project.normalize(body)
        if int(arguments[1]) in missing:
            found.append((arguments, project.normalize(body).strip()))
    assert len(found) == len(missing)
    return found


# --- now schema prolog --------------------------------------------------------


def test_schema_prolog_in_a_project_without_trials(project):
    """In a project without trials, ``now schema prolog`` prints only
    ``Trial None not found`` and exits 0, while ``-d`` draws the diagram

    Characterization of #253.
    """
    result = project.run("schema", "prolog")
    assert result.stdout == NO_TRIAL, str(result)
    diagram = project.run("schema", "prolog", "-d")
    assert diagram.stdout.startswith("digraph G{"), str(diagram)
    assert diagram.stdout.rstrip().endswith("}"), str(diagram)


@known_defects(SCHEMA_WITHOUT_TRIAL)
def test_schema_prolog_in_a_project_without_trials_desired(project):
    """In a project without trials, ``now schema prolog`` prints the
    descriptions of the exported facts and the rules
    """
    result = project.run("schema", "prolog")
    names = [name for name, _ in DEFINITION.findall(result.stdout)]
    assert names == EXPORTED, str(result)
    # rules.pl indents its rules; rule_lines() strips them.
    lines = {line.strip() for line in result.stdout.splitlines()}
    missing = [rule for rule in rule_lines() if rule not in lines]
    assert missing == [], str(result)


def test_schema_prolog_describes_the_exported_facts(two_trial_project):
    """``now schema prolog`` describes each fact that ``export prolog``
    declares, with one variable per argument, and prints every rule of
    ``rules.pl`` after the descriptions
    """
    result = two_trial_project.run("schema", "prolog")
    definitions = [(name, len(arguments.split(", ")))
                   for name, arguments in DEFINITION.findall(result.stdout)]
    export = two_trial_project.run("export", "prolog", "-t").stdout
    assert definitions == list(declared_arities(export).items())
    assert [name for name, _ in definitions] == EXPORTED
    lines = [line.strip() for line in result.stdout.splitlines()]
    last_definition = max(index for index, line in enumerate(lines)
                          if line.startswith("% FACT DEFINITION: "))
    assert [line for line in lines[last_definition + 1:]
            if line and not line.startswith("%")] == rule_lines()


def test_schema_prolog_diagram_draws_the_exported_facts(two_trial_project):
    """``now schema prolog -d`` draws one node per fact that ``export
    prolog`` declares, in its order, with one port per argument
    """
    result = two_trial_project.run("schema", "prolog", "-d")
    assert result.stdout.startswith("digraph G{"), str(result)
    nodes = [(name, len(PORT.findall(label)))
             for name, label in NODE.findall(result.stdout)]
    export = two_trial_project.run("export", "prolog", "-t").stdout
    assert nodes == list(declared_arities(export).items())


# --- the terms of export prolog ---------------------------------------------


def test_export_prolog_facts_are_atomic_prolog_terms(two_trial_project):
    """Every argument of every fact of ``export prolog -t`` is a Prolog
    term that SWI-Prolog reads as atomic: a quoted atom, a number, ``nil``
    or a lowercase atom such as ``f1``

    The message lists predicates and argument positions only.
    """
    text = two_trial_project.run("export", "prolog", "-t").stdout
    facts = facts_of(text)
    # Not vacuous: every exported predicate has facts in the weather store.
    assert {name for name, _ in facts} == set(EXPORTED)
    rejected = collections.Counter()
    for name, body in facts:
        arguments = fact_arguments(body, name)
        assert arguments is not None, "a {} fact does not close".format(name)
        for index, _ in non_atomic(arguments):
            rejected[(name, index)] += 1
    assert rejected == collections.Counter()


@pytest.mark.skipif(swipl.SWIPL is None, reason=swipl.SKIP_REASON)
def test_export_prolog_reads_in_swi_prolog_with_the_declared_arities(
        two_trial_project, tmp_path):
    """SWI-Prolog reads ``export prolog -t`` (without the environment)
    term by term with no syntax error: each declaration, and each fact with
    the arity its predicate declares

    SWI-Prolog's reader is the instrument that the Python counting in
    ``test_export.py`` and the grammar above stand for.
    """
    text = strip_prolog_predicate(
        two_trial_project.run("export", "prolog", "-t").stdout,
        "environment")
    path = tmp_path / "facts.pl"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    read = swipl.read_terms(path)
    assert read.errors == []
    declared = declared_arities(text)
    expected = collections.Counter(
        (name, declared[name]) for name, _ in facts_of(text))
    expected[(":-", 1)] = len(declared)
    assert read.clauses == expected


def test_export_prolog_of_a_module_without_fullpath(two_trial_project):
    """A module whose fullpath is NULL is exported with the atom
    ``'None'`` as its fullpath, while its NULL version is ``nil``

    Characterization of #353.
    """
    rows = last_trial_modules(two_trial_project)
    for arguments, fact in module_facts_without_fullpath(two_trial_project):
        assert arguments[7] == "'None'", fact
        # The contrast: the version of the same module is NULL too.
        assert rows[int(arguments[1])]["version"] is None, fact
        assert arguments[3] == "nil", fact


@known_defects(FULLPATH_NONE)
def test_export_prolog_of_a_module_without_fullpath_desired(
        two_trial_project):
    """A module whose fullpath is NULL is exported with ``nil`` as its
    fullpath
    """
    for arguments, fact in module_facts_without_fullpath(two_trial_project):
        assert arguments[7] == "nil", "fullpath is {}, not nil, in {}".format(
            arguments[7], fact)
