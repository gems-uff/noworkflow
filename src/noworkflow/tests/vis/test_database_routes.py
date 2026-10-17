# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The database routes of ``now vis``: ``/db/tables``, ``/db/table`` and
``/db/query``

The database widget of the frontend draws the tables and their foreign
keys from ``/db/tables``, opens a table with ``/db/table/<name>`` and runs
the SQL typed in the query widget through ``POST /db/query``. Expected
values come from the same SQL on the store (``project.query`` or a
connection of the test's own), never from literals.

The read-only routes run on the shared two-trial store, whose fingerprint
check also proves that a SELECT through ``/db/query`` writes nothing; so do
the transaction statements the route refuses before they reach SQLite.
Every test that sends ``/db/query`` a statement that writes, or ``END``
(which reaches SQLite), runs on ``vis_own``, the store meant for the routes
that write, and checks its fingerprint before and after.

``/db/query`` running arbitrary SQL, and the f-string ``PRAGMA`` of
``/db/table`` that a quote in the name reaches, are #224's; they are
characterized here without a twin. Known defects with a ``_desired`` twin:

- ``QUERY_KEYWORD_SUBSTRING``: the transaction keywords are matched as
  substrings, so a harmless SELECT is refused;
- ``QUERY_END``: ``END``, SQLite's synonym of ``COMMIT``, is not refused
  and the route crashes;
- ``QUERY_DUPLICATE_COLUMNS``: rows are dicts keyed by column name, so a
  column that repeats a name (``SELECT *`` over a join) loses its values.

Their mechanisms are plain Python and SQLite, the same on every version
(measured on macOS with Python 3.11 to 3.15).
"""
import json
import sqlite3

import pytest

from .support import Defect, known_defects

QUERY_KEYWORD_SUBSTRING = Defect(
    reason="#366: db_query refuses a query "
           "whenever its upper-cased text contains BEGIN, COMMIT, ROLLBACK, "
           "SAVEPOINT, RELEASE or TRANSACTION anywhere, so a read-only "
           "SELECT that names the OS_RELEASE environment attribute or has "
           "one of those words in a string literal answers 400",
    signature="which is not allowed",
)
QUERY_END = Defect(
    reason="#366: db_query does not refuse END, SQLite's "
           "synonym of COMMIT, so it commits the route's own BEGIN and the "
           "ROLLBACK in the route's finally raises OperationalError: the "
           "route answers 500 (and skips closing its connection)",
    signature="cannot rollback - no transaction is active",
)
QUERY_DUPLICATE_COLUMNS = Defect(
    reason="#362: db_query builds each row as "
           "dict(zip(columns, row)), so when two columns share a name "
           "(SELECT * over a join, as the database widget builds) only the "
           "last one's value reaches the response, under both columns",
    signature="lose the values of a duplicated column name",
)

# A join whose two tables share the names id, trial_id and name: what
# ``SELECT *`` gives when the database widget joins two selected tables.
JOIN_QUERY = (
    'SELECT * FROM "file_access" JOIN "activation" '
    'ON "activation".trial_id = "file_access".trial_id '
    'AND "activation".id = "file_access".activation_id '
    'ORDER BY "file_access".trial_id, "file_access".id'
)


def post_query(vis, body):
    """POST ``body`` (a dict) to ``/db/query``: the response, already read"""
    return vis.post("/db/query", json=body)


def query_json(vis, sql, status=200):
    """POST ``sql`` to ``/db/query`` and return its JSON

    The message names the status and the route's ``error``, which only
    holds SQLite's or the route's text, never a value of the store.
    """
    response = post_query(vis, {"query": sql})
    assert response.mimetype == "application/json", (
        "POST /db/query: status {}, {}, expected JSON".format(
            response.status_code, response.mimetype))
    body = json.loads(response.get_data(as_text=True))
    assert response.status_code == status, (
        "POST /db/query: status {}, expected {}; error: {}".format(
            response.status_code, status,
            body.get("error") if isinstance(body, dict) else None))
    return body


def table_names(project, order=" ORDER BY name"):
    """The tables of the store, by the SQL the routes use"""
    return [row["name"] for row in project.query(
        "SELECT name FROM sqlite_master WHERE type='table'" + order)]


def foreign_keys(project, table):
    """``PRAGMA foreign_key_list`` of a table, as dicts"""
    return project.query('PRAGMA foreign_key_list("{}")'.format(table))


def sql_result(project, sql):
    """``(columns, rows as tuples)`` of ``sql`` on the store

    Tuples keep every column, also when two share a name.
    """
    with project.db() as connection:
        cursor = connection.execute(sql)
        columns = [description[0] for description in cursor.description]
        rows = [tuple(row) for row in cursor.fetchall()]
    return columns, rows


def answer_values(answer):
    """The rows of a ``/db/query`` answer as tuples in column order

    Today a row is a dict keyed by column name; a fix may send lists or
    rename repeated names, and the desired twins accept either.
    """
    def values(row):
        if isinstance(row, dict):
            return tuple(row.get(column) for column in answer["columns"])
        return tuple(row)
    return [values(row) for row in answer["rows"]]


# --- /db/tables -------------------------------------------------------------


def test_tables_lists_every_table_of_the_store_by_name(vis):
    """``/db/tables`` lists the tables of ``sqlite_master``, sorted"""
    tables = vis.json("/db/tables")["tables"]
    assert tables == table_names(vis.project)
    assert "trial" in tables, "the store has no trial table"


def test_tables_gives_the_foreign_keys_of_each_table_that_has_any(vis):
    """``foreign_keys`` maps each table with a foreign key to its
    ``PRAGMA foreign_key_list``, and leaves out the tables without one
    """
    answer = vis.json("/db/tables")["foreign_keys"]
    expected = {}
    for table in table_names(vis.project):
        keys = foreign_keys(vis.project, table)
        if keys:
            expected[table] = keys
    assert answer == expected
    assert "trial" in answer, "no foreign key in the store"


# --- /db/table/<table_name> -------------------------------------------------


def test_table_info_matches_pragma_for_every_table(vis):
    """For every table, ``/db/table/<name>`` gives its columns (from
    ``PRAGMA table_info``), its foreign keys, and the foreign keys of the
    other tables that reference it
    """
    project = vis.project
    # The route walks sqlite_master in its own order for referenced_by.
    every_table = table_names(project, order="")
    for table in every_table:
        info = vis.json("/db/table/" + table)
        columns = [{
            "name": column["name"],
            "type": column["type"],
            "notnull": bool(column["notnull"]),
            "default": column["dflt_value"],
            "pk": bool(column["pk"]),
        } for column in project.query(
            'PRAGMA table_info("{}")'.format(table))]
        referenced_by = [{
            "referencing_table": other,
            "referencing_column": key["from"],
            "referenced_column": key["to"],
            "on_update": key["on_update"],
            "on_delete": key["on_delete"],
        } for other in every_table if other != table
            for key in foreign_keys(project, other) if key["table"] == table]
        assert set(info) == {"columns", "foreign_keys", "referenced_by"}, (
            "/db/table/{}: keys {}".format(table, sorted(info)))
        assert info["columns"] == columns, "/db/table/{}: columns".format(
            table)
        assert info["foreign_keys"] == foreign_keys(project, table), (
            "/db/table/{}: foreign keys".format(table))
        assert info["referenced_by"] == referenced_by, (
            "/db/table/{}: referenced_by".format(table))


def test_table_info_of_the_trial_table_names_its_referencing_tables(vis):
    """The trial table is referenced by the tables of a trial's
    provenance, and ``referenced_by`` names them
    """
    info = vis.json("/db/table/trial")
    referencing = {key["referencing_table"] for key in info["referenced_by"]}
    assert {"activation", "tag", "file_access"} <= referencing
    assert "trial" not in referencing, "a table is not its own referrer"


def test_table_info_of_an_unknown_table_is_empty(vis):
    """A name that is no table gives three empty lists"""
    assert "no_such_table" not in table_names(vis.project)
    info = vis.json("/db/table/no_such_table")
    assert info == {"columns": [], "foreign_keys": [], "referenced_by": []}


@pytest.mark.parametrize("name", ["a'b", "trial'"])
def test_table_info_with_a_quote_answers_the_sql_error_with_200(vis, name):
    """A quote in the name reaches the f-string ``PRAGMA`` (#224) and
    breaks its syntax: the route answers 200 with only SQLite's error

    The frontend only builds this URL from the names ``/db/tables`` gives,
    which have no quote.
    """
    info = vis.json("/db/table/" + name)
    assert set(info) == {"error"}, "keys {}".format(sorted(info))
    assert "syntax error" in info["error"] or "unrecognized token" in (
        info["error"]), "not a syntax error: {}".format(info["error"])


# --- /db/query: what it answers ---------------------------------------------


def test_query_select_returns_the_columns_and_rows_of_the_same_sql(vis):
    """A SELECT answers its columns, and one dict per row equal to the same
    SQL on the store (the shared store's check proves it wrote nothing)
    """
    sql = ("SELECT id, sequence_key, script, status FROM trial "
           "ORDER BY sequence_key")
    answer = query_json(vis, sql)
    expected = vis.project.query(sql)
    assert answer["columns"] == ["id", "sequence_key", "script", "status"]
    assert answer["rows"] == expected
    assert [row["id"] for row in answer["rows"]] == vis.trial_ids


def test_query_select_star_of_one_table_gives_every_column_in_order(vis):
    """``SELECT *`` of one table gives every column, in table order (the
    tag table, which holds nothing of the environment)
    """
    sql = 'SELECT * FROM "tag" ORDER BY id'
    columns, rows = sql_result(vis.project, sql)
    answer = query_json(vis, sql)
    assert answer["columns"] == columns
    assert [tuple(row[column] for column in columns)
            for row in answer["rows"]] == rows
    assert len(rows) == len(vis.trial_ids), "one automatic tag per trial"


@pytest.mark.parametrize("body", [
    {"query": ""}, {"query": "  \n\t"}, {},
], ids=["empty", "blank", "missing"])
def test_query_without_text_answers_400(vis, body):
    """An empty, blank or missing query answers 400 with an error"""
    response = post_query(vis, body)
    assert response.status_code == 400
    answer = json.loads(response.get_data(as_text=True))
    assert answer == {"error": "No query provided"}


@pytest.mark.parametrize("sql, keyword", [
    ("BEGIN", "BEGIN"),
    ("BEGIN TRANSACTION", "BEGIN"),
    ("COMMIT", "COMMIT"),
    ("commit", "COMMIT"),
    ("ROLLBACK", "ROLLBACK"),
    ("SAVEPOINT s", "SAVEPOINT"),
    ("RELEASE s", "RELEASE"),
    ("COMMIT TRANSACTION", "COMMIT"),
])
def test_query_with_a_transaction_statement_answers_400(vis, sql, keyword):
    """A statement that controls the transaction is refused before it
    reaches SQLite, in any case, with an error naming the keyword
    """
    answer = query_json(vis, sql, status=400)
    assert set(answer) == {"error"}
    assert "keyword '{}'".format(keyword) in answer["error"]
    assert "not allowed" in answer["error"]


@pytest.mark.parametrize("sql, fragment", [
    ("SELECT * FROM no_such_table", "no such table"),
    ("SELECT 1; SELECT 2", "one statement at a time"),
    ("SELEKT 1", "syntax error"),
], ids=["unknown-table", "two-statements", "syntax"])
def test_query_error_answers_200_with_sqlites_error(vis, sql, fragment):
    """SQL that SQLite rejects answers 200 with only its error, which the
    query widget shows; a second statement is never run
    """
    answer = query_json(vis, sql)
    assert set(answer) == {"error"}, "keys {}".format(sorted(answer))
    assert fragment in answer["error"]


# --- /db/query: writes and transactions -------------------------------------


@pytest.mark.parametrize("sql", [
    "DELETE FROM trial",
    "UPDATE trial SET script = 'other.py'",
    "INSERT INTO remote (server_url, name, used, hide) "
    "VALUES ('http://remote.invalid/experiments/x', 'x', 0, 0)",
    "DROP TABLE tag",
], ids=["delete", "update", "insert", "drop"])
def test_query_write_is_rolled_back_and_leaves_the_store_unchanged(
        vis_own, sql):
    """A statement that writes runs inside the route's transaction, which
    is rolled back: it answers no rows and the store stays as it was
    """
    before = vis_own.project.fingerprint()
    trial_ids = vis_own.trial_ids
    answer = query_json(vis_own, sql)
    assert answer == {"columns": [], "rows": []}
    same = vis_own.project.fingerprint() == before
    assert same, "{} changed the store".format(sql.split()[0])
    assert vis_own.trial_ids == trial_ids
    assert table_names(vis_own.project) == vis_own.json(
        "/db/tables")["tables"]


def test_query_write_followed_by_end_is_not_committed(vis_own):
    """``END`` after a write in the same query never runs: SQLite takes
    one statement at a time, so the write is rolled back with the error
    """
    before = vis_own.project.fingerprint()
    answer = query_json(vis_own, "DELETE FROM tag; END")
    assert set(answer) == {"error"}
    assert "one statement at a time" in answer["error"]
    same = vis_own.project.fingerprint() == before
    assert same, "DELETE ...; END changed the store"


def test_query_end_crashes_after_committing_only_the_routes_begin(vis_own):
    """``END`` is not in the refused keywords: it commits the route's own
    empty transaction, and the route's final ROLLBACK raises (#366);
    nothing was written
    """
    before = vis_own.project.fingerprint()
    with pytest.raises(sqlite3.OperationalError,
                       match="cannot rollback - no transaction is active"):
        post_query(vis_own, {"query": "END"})
    same = vis_own.project.fingerprint() == before
    assert same, "END changed the store"


@known_defects(QUERY_END)
def test_query_end_desired(vis_own):
    """``END`` is refused like ``COMMIT``: a JSON error, no crash, and the
    store unchanged
    """
    before = vis_own.project.fingerprint()
    response = post_query(vis_own, {"query": "END"})
    assert response.status_code < 500, "POST /db/query: status {}".format(
        response.status_code)
    answer = json.loads(response.get_data(as_text=True))
    assert "error" in answer, "END was not refused"
    same = vis_own.project.fingerprint() == before
    assert same, "END changed the store"


# --- /db/query: known defects -----------------------------------------------

KEYWORD_AS_TEXT = [
    ("SELECT COUNT(*) AS n FROM environment_attr WHERE name = 'OS_RELEASE'",
     "RELEASE"),
    ("SELECT 'commit' AS word", "COMMIT"),
]


@pytest.mark.parametrize("sql, keyword", KEYWORD_AS_TEXT,
                         ids=["attribute-name", "string-literal"])
def test_query_refuses_a_select_with_a_keyword_inside_its_text(
        vis, sql, keyword):
    """A SELECT whose text merely contains a transaction keyword (an
    attribute name, a string literal) is refused with 400
    """
    answer = query_json(vis, sql, status=400)
    assert "keyword '{}'".format(keyword) in answer["error"]


@pytest.mark.parametrize("sql, keyword", KEYWORD_AS_TEXT,
                         ids=["attribute-name", "string-literal"])
@known_defects(QUERY_KEYWORD_SUBSTRING)
def test_query_select_with_a_keyword_inside_its_text_desired(
        vis, sql, keyword):
    """A SELECT that only mentions a transaction keyword as text answers
    the rows of the same SQL on the store
    """
    response = post_query(vis, {"query": sql})
    answer = json.loads(response.get_data(as_text=True))
    assert response.status_code == 200, (
        "POST /db/query: status {}, refused: {}".format(
            response.status_code, answer.get("error")))
    columns, rows = sql_result(vis.project, sql)
    assert answer["columns"] == columns, keyword
    assert answer_values(answer) == rows, keyword


def test_query_keeps_one_value_per_column_name(vis):
    """When two columns share a name, ``columns`` lists both but each row
    holds the name once, with the value of the last such column
    """
    columns, rows = sql_result(vis.project, JOIN_QUERY)
    duplicated = sorted({name for name in columns if columns.count(name) > 1})
    assert {"id", "name", "trial_id"} <= set(duplicated)
    assert rows, "the store has no file access"
    answer = query_json(vis, JOIN_QUERY)
    assert answer["columns"] == columns
    assert len(answer["rows"]) == len(rows)
    last = {name: len(columns) - 1 - columns[::-1].index(name)
            for name in duplicated}
    for row, expected in zip(answer["rows"], rows):
        assert len(row) == len(set(columns)) < len(columns)
        same = all(row[name] == expected[index]
                   for name, index in last.items())
        assert same, "a duplicated name does not hold its last column"


@known_defects(QUERY_DUPLICATE_COLUMNS)
def test_query_keeps_every_column_desired(vis):
    """Each row of the answer gives, in column order, the values of the
    same SQL on the store, also when two columns share a name

    Only a difference confined to the columns whose name repeats carries
    the defect's signature; any other difference fails outright.
    """
    columns, rows = sql_result(vis.project, JOIN_QUERY)
    answer = query_json(vis, JOIN_QUERY)
    assert rows, "the store has no file access"
    assert len(answer["columns"]) == len(columns), "a column is missing"
    values = answer_values(answer)
    assert len(values) == len(rows), "a row is missing"
    repeated = [index for index, name in enumerate(columns)
                if columns.count(name) > 1]
    unique = [index for index in range(len(columns))
              if index not in repeated]
    same_unique = all(got[index] == expected[index]
                      for got, expected in zip(values, rows)
                      for index in unique)
    assert same_unique, "a column whose name is unique differs from the SQL"
    same = values == rows
    assert same, "the rows {} ({})".format(
        QUERY_DUPLICATE_COLUMNS.signature,
        sorted({columns[index] for index in repeated}))


# --- /db/query: request bodies the widget never sends -----------------------


@pytest.mark.parametrize("body, error", [
    ("null", "'NoneType' object has no attribute 'get'"),
    ('["SELECT 1"]', "'list' object has no attribute 'get'"),
    ('{"query": 1}', "'int' object has no attribute 'strip'"),
], ids=["null", "list", "number"])
def test_query_with_a_body_that_is_not_an_object_with_text_crashes(
        vis, body, error):
    """JSON that is not an object with a string ``query`` crashes the
    route (robustness: the query widget always sends one)
    """
    with pytest.raises(AttributeError, match=error):
        vis.post("/db/query", data=body, content_type="application/json")


def test_query_with_a_body_that_is_not_json_answers_415(vis):
    """A body without the JSON media type is refused by Flask with 415"""
    response = vis.post("/db/query", data="SELECT 1",
                        content_type="text/plain")
    assert response.status_code == 415
