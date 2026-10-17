# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now export prov``: subscripts, augmented assignments and PROV-N strings

The golden of ``test_export.py`` holds the export of the weather script,
which never reads an item of a list by subscript and has no augmented
assignment. ``subscripts.py`` has both: it runs once per module into a store
of its own, and the expected collection of each subscript comes from that
store's SQL (``dependency.collection_id``), not from the export's order.
Entities are named by the export's own convention, ``<line>_<name>`` for a
name and ``<line>_<name>@<key>`` for a subscript; each name the tests expect
is checked to be declared by an ``entity(`` line of the same export.

The PROV-N strings are checked on the shared two-trial weather store
against the grammar of the W3C PROV-N recommendation, only inside the
attribute lists: the identifiers follow noWorkflow's own naming. The
user entity holds the hostname, so it is left out and every line a message
shows is normalized.

Known defects have a characterization of today's behavior and a
``_desired`` twin marked through ``known_defects``. Their mechanisms are
plain Python string formatting in ``models/prov/export.py``, the same on
every system (measured on macOS with Python 3.11 to 3.15).
"""
import re

import pytest

from noworkflow.tests.e2e.harness import NowProject
from noworkflow.tests.helpers.defects import Defect, known_defects

SUBSCRIPTS = (
    "a = [1, 2]\n"
    "z = [7, 8]\n"
    "b = a[0]\n"
    "y = z[1]\n"
    "a[1] = b + y\n"
    "x = 1\n"
    "x += a[1]\n"
    "print(b, y, x, a)\n"
)

# Each subscript read of SUBSCRIPTS, by the script's meaning: the entity of
# the item it reads and its key.
READ_ITEMS = {
    "3_a@0": ("1_1", "0"),  # the 1 of line 1
    "4_z@1": ("2_8", "1"),  # the 8 of line 2
    "7_a@1": ("5_a@1", "1"),  # the value written on line 5
}

# PROV-N: STRING_LITERAL ::= '"' ([^#x22#x5C#xA#xD] | ECHAR)* '"' and
# ECHAR ::= '\' [tbnrf\"'], in an attribute list ``[name="...", ...]``
# that closes the statement.
STRING_LITERAL = r'"(?:[^"\\\n\r]|\\[tbnrf\\"\'])*"'
ATTRIBUTES = re.compile(
    r"\[\s*(?:[\w:]+=" + STRING_LITERAL + r"\s*,?\s*)*\]\)$")
# ``used(access<N>, <collection>, -, [version:checkpoint=...])``: the use of
# a collection by an access activity (the use of the key has no checkpoint).
USED_COLLECTION = re.compile(
    r"^used\((access\d+), (\w+), -, \[version:checkpoint=", re.MULTILINE)

COLLECTION_SHIFT = Defect(
    reason="#335: export_prov walks the "
           "dependencies of a subscript read in (dependent, type) order, so "
           "the access group writes version:collection before the value "
           "group sets it: each read names the collection of the subscript "
           "before it, and its collection is used by the next access "
           "activity",
    signature='version:collection=""',
)
UNESCAPED_QUOTES = Defect(
    reason="#336: export_prov writes values and labels "
           "as \"{}\" without escaping a double quote or a backslash, so a "
           "string literal of the script ends the PROV-N string early",
    signature='newline="")"',
)


@pytest.fixture(scope="module")
def subscripts_prov(tmp_path_factory):
    """``(project, normalized export prov)`` of ``subscripts.py``"""
    project = NowProject(tmp_path_factory.mktemp("subscripts"))
    project.write("subscripts.py", SUBSCRIPTS)
    result = project.run("run", "subscripts.py")
    assert result.stdout.strip().endswith("1 8 10 [1, 9]"), str(result)
    text = project.normalize(project.run("export", "prov").stdout)
    return project, text


def line_starting(text, prefix):
    """The only line of ``text`` that starts with ``prefix``"""
    lines = [line for line in text.splitlines() if line.startswith(prefix)]
    assert len(lines) == 1, "{} lines start with {}".format(
        len(lines), prefix)
    return lines[0]


def declared(text, entity):
    return any(line.startswith("entity({}, ".format(entity))
               for line in text.splitlines())


def subscript_reads(project):
    """``[(read, collection)]`` of each subscript read, by SQL

    ``read`` is the entity of the read (``3_a@0``); ``collection`` the
    entity of the collection read, after its ``assignment`` dependency
    when it is a name read (the export names a name read after the name's
    definition: the read of ``a`` on line 3 is ``1_a``).
    """
    rows = project.query(
        "SELECT read.first_char_line AS line, read.name AS name, "
        "coll_ev.id AS collection_eval, coll.first_char_line AS coll_line, "
        "coll.name AS coll_name "
        "FROM dependency AS dep "
        "JOIN evaluation AS ev ON ev.trial_id = dep.trial_id "
        "AND ev.id = dep.dependent_id "
        "JOIN code_component AS read ON read.trial_id = ev.trial_id "
        "AND read.id = ev.code_component_id "
        "JOIN evaluation AS coll_ev ON coll_ev.trial_id = dep.trial_id "
        "AND coll_ev.id = dep.collection_id "
        "JOIN code_component AS coll ON coll.trial_id = coll_ev.trial_id "
        "AND coll.id = coll_ev.code_component_id "
        "WHERE dep.type = 'access' AND read.mode = 'r' ORDER BY dep.id")
    reads = []
    for row in rows:
        defined = project.query(
            "SELECT cc.first_char_line AS line, cc.name AS name "
            "FROM dependency AS dep "
            "JOIN evaluation AS ev ON ev.trial_id = dep.trial_id "
            "AND ev.id = dep.dependency_id "
            "JOIN code_component AS cc ON cc.trial_id = ev.trial_id "
            "AND cc.id = ev.code_component_id "
            "WHERE dep.type = 'assignment' AND dep.dependent_id = ?",
            row["collection_eval"])
        source = defined[0] if defined else {
            "line": row["coll_line"], "name": row["coll_name"]}
        name, key = re.fullmatch(r"(\w+)\[(.*)\]", row["name"]).groups()
        reads.append(("{}_{}@{}".format(row["line"], name, key),
                      "{}_{}".format(source["line"], source["name"])))
    return reads


def test_export_prov_derives_a_subscript_write_and_an_augmented_assignment(
        subscripts_prov):
    """``x += a[1]`` is an ``add_assign`` operation that derives the new
    ``x`` from the old one and from ``a[1]``; ``a[1] = ...`` writes key 1
    of the list defined on line 1
    """
    _, text = subscripts_prov
    for entity in ("1_a", "5_a@1", "6_x", "7_a@1", "7_x"):
        assert declared(text, entity), entity
    assert 'activity(add_assign1, [type="script:operation"])' in (
        text.splitlines())
    line_starting(text, "wasDerivedFrom(7_x, 6_x, add_assign1, ")
    line_starting(text, "wasDerivedFrom(7_x, 7_a@1, add_assign1, ")
    write = line_starting(text, "wasDerivedFrom(5_a@1, ")
    assert ('version:collection="1_a", version:key="1", '
            'version:access="w"') in write, write


def test_export_prov_derives_each_subscript_read_from_the_item_it_read(
        subscripts_prov):
    """A subscript read derives from the item it read, through an access
    activity, with the key of its subscript and the mode ``r``
    """
    project, text = subscripts_prov
    assert [read for read, _ in subscript_reads(project)] == list(READ_ITEMS)
    for read, (item, key) in READ_ITEMS.items():
        assert declared(text, read) and declared(text, item), (read, item)
        line = line_starting(
            text, "wasDerivedFrom({}, {}, access".format(read, item))
        assert 'version:key="{}", version:access="r"'.format(key) in line, (
            line)


def test_export_prov_of_subscript_reads(subscripts_prov):
    """Today the first read, ``a[0]``, names no collection, ``z[1]`` names
    ``a``, and the use of each collection goes to the next access activity

    Characterization of a defect.
    """
    _, text = subscripts_prov
    first = line_starting(text, "wasDerivedFrom(3_a@0, ")
    assert ", access1, " in first and 'version:collection=""' in first
    second = line_starting(text, "wasDerivedFrom(4_z@1, ")
    assert ", access2, " in second and 'version:collection="1_a"' in second
    # The collections used by an access activity, in the order of the
    # export: the last one comes from the write of a[1] on line 5.
    assert USED_COLLECTION.findall(text) == [
        ("access2", "1_a"), ("access3", "2_z"), ("access3", "1_a"),
        ("access4", "1_a")]


@known_defects(COLLECTION_SHIFT)
def test_export_prov_of_subscript_reads_desired(subscripts_prov):
    """Each subscript read names the collection it read, which its access
    activity uses"""
    project, text = subscripts_prov
    reads = subscript_reads(project)
    assert [read for read, _ in reads] == list(READ_ITEMS)
    wrong = []
    for read, collection in reads:
        assert declared(text, collection), collection
        line = line_starting(text, "wasDerivedFrom({}, ".format(read))
        activity = line.split(", ")[2]
        if 'version:collection="{}"'.format(collection) not in line:
            wrong.append(line)
        used = "used({}, {}, ".format(activity, collection)
        if not any(each.startswith(used) for each in text.splitlines()):
            wrong.append("no {}...".format(used))
    assert not wrong, "\n".join(wrong)


def test_export_prov_of_a_double_quoted_string(two_trial_project):
    """Today the label of ``open(path, newline="")`` keeps its double
    quotes raw inside the PROV-N string

    Characterization of a defect (``simulation.py`` line 14).
    """
    text = two_trial_project.normalize(
        two_trial_project.run("export", "prov").stdout)
    assert 'label="open(path, newline="")"' in text


@known_defects(UNESCAPED_QUOTES)
def test_export_prov_of_a_double_quoted_string_desired(two_trial_project):
    """Every attribute value is a PROV-N string literal: a double quote or
    a backslash inside it is escaped"""
    text = two_trial_project.normalize(
        two_trial_project.run("export", "prov").stdout)
    lines = [line for line in text.splitlines()
             if line.endswith("])") and not line.startswith("entity(user_")]
    # Not vacuous: entities, derivations and members have attributes.
    assert len(lines) > 100
    bad = [line for line in lines if not ATTRIBUTES.search(line)]
    # Every line, so the signature cannot fall outside a window when
    # another system adds invalid lines before it.
    assert not bad, "{} lines with an invalid string:\n{}".format(
        len(bad), "\n".join(bad))
