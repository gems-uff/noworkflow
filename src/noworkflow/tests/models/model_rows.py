# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""One row of each model, and the Prolog term syntax its fact must follow

``insert_model_row`` builds a row of any model from its table alone: every
text column holds ``PROBE``, a value with the characters that a Prolog
writer must escape (a quote, a comma, a backslash, a newline and a closing
parenthesis), and every other column a value of its SQL type. The row goes
in through ``Model.t.insert()``, so nothing of the model's own code decides
what is stored, and the proxy that comes back reads it like any query of
noWorkflow does.

``ATOMIC`` is the grammar of one argument of a fact, the terms that
SWI-Prolog reads as atomic: a quoted atom (a quote doubled, a backslash
starting a valid escape, raw newlines allowed as SWI allows them), a number
(an exponent without a fraction too, as Python's ``repr`` writes ``5e-06``
and SWI reads it), or an unquoted atom that starts with a lowercase letter
(``nil``, ``f7``). An unquoted ``None`` is a variable and an unquoted UUID
is not a term: counting commas misses both. ``test_prolog_facts.py`` checks
the grammar against SWI-Prolog's own reader.
"""

import datetime
import re

import sqlalchemy as sa

from ...now.persistence import relational
from ...now.persistence.models import Trial
from ..e2e.normalize import argument_spans

# Text that a Prolog writer must escape, in every text column.
PROBE = "a, b'c\\d\ne)"
# Trial ids are UUIDs; a column that holds one gets this (or OTHER_TRIAL).
TRIAL_ID = "0e4f1c2a-1b2c-4d5e-8f90-1234567890ab"
OTHER_TRIAL = "1f4f1c2a-1b2c-4d5e-8f90-1234567890ab"
# Integer columns that hold the UUID of another trial.
TRIAL_REFERENCES = ("parent_id", "modules_inherited_from_trial_id")
STAMP = datetime.datetime(2016, 4, 8, 1, 18)
# The value of every integer primary key, and the first of the other
# integer columns (each gets its own).
KEY = 7

QUOTED_ATOM = (
    r"'(?:[^'\\]|''"
    r"|\\[\\'\"`abfnrtv\n]"
    r"|\\x[0-9a-fA-F]+\\"
    r"|\\[0-7]+\\)*'"
)
NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
UNQUOTED_ATOM = r"[a-z][A-Za-z0-9_]*"
ATOMIC = re.compile(
    r"\s*(?:{}|{}|{})\s*".format(QUOTED_ATOM, NUMBER, UNQUOTED_ATOM), re.DOTALL
)


def check_values(table):
    """``{column: value}``: the first value each ``IN (...)`` CHECK allows

    CHECK constraints are declared on the table or on the column itself
    (``code_component.mode``).
    """
    constraints = list(table.constraints)
    for column in table.columns:
        constraints.extend(column.constraints)
    values = {}
    for constraint in constraints:
        if isinstance(constraint, sa.CheckConstraint):
            match = re.match(r"\s*(\w+) IN \('([^']*)'", str(constraint.sqltext))
            if match:
                values[match.group(1)] = match.group(2)
    return values


def column_value(column, position, text, checks):
    """The value of one column in the row of ``insert_model_row``"""
    kind = column.type
    if column.name in checks:
        return checks[column.name]
    if column.name in TRIAL_REFERENCES:
        return OTHER_TRIAL
    if column.primary_key and isinstance(kind, sa.Integer):
        return KEY
    if isinstance(kind, sa.Boolean):
        return True
    if isinstance(kind, sa.Integer):
        return KEY + position
    if isinstance(kind, sa.Float):
        return 1.5
    if isinstance(kind, sa.DateTime):
        return STAMP
    if (
        column.name == "trial_id"
        or column.name == "id"
        and (column.table.name == "trial")
    ):
        return TRIAL_ID
    if column.name == "id" or column.name.endswith("_id"):
        # The ids of the collaboration models and the references to
        # them are UUIDs too (``uuid_gen``).
        return OTHER_TRIAL
    return text


def model_row(model, text=PROBE, nulls=()):
    """``{column: value}`` of the row that ``insert_model_row`` inserts"""
    table = model.t
    checks = check_values(table)
    row = {
        column.name: column_value(column, position, text, checks)
        for position, column in enumerate(table.columns)
    }
    for name in nulls:
        assert name in row, "{} has no column {}".format(table.name, name)
        row[name] = None
    return row


def insert_model_row(model, text=PROBE, nulls=()):
    """Insert one row of ``model`` and return its proxy

    ``nulls`` names the columns left NULL. The row is committed to the
    store the persistence layer is connected to (the in-memory one, in the
    in-process suite); the caller erases it.
    """
    row = model_row(model, text, nulls)
    relational.session.execute(model.t.insert(), row)
    relational.session.commit()
    if model is Trial:
        return Trial(trial_ref=row["id"])
    key = tuple(row[column.name] for column in model.t.primary_key.columns)
    return model(key if len(key) > 1 else key[0])


def fact_arguments(fact, name):
    """The texts of the top-level arguments of ``name(...)``, or None

    >>> fact_arguments("f('a, b', nil, g(1, 2)).", "f")
    ["'a, b'", ' nil', ' g(1, 2)']
    >>> fact_arguments("g(1).", "f") is None
    True
    """
    prefix = name + "("
    if not fact.startswith(prefix):
        return None
    spans = argument_spans(fact, len(prefix))
    if spans is None:
        return None
    return [fact[start:end] for start, end in spans]


def non_atomic(arguments):
    """``[(index, text)]`` of the arguments that ``ATOMIC`` rejects

    >>> non_atomic(["'a''b'", " 5e-06", " None", " f7", " 1b2c-3d"])
    [(2, ' None'), (4, ' 1b2c-3d')]
    """
    return [
        (index, text)
        for index, text in enumerate(arguments)
        if not ATOMIC.fullmatch(text)
    ]
