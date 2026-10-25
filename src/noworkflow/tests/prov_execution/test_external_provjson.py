# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The pure functions that find and read the PROV-JSON of an R provenance
tool (#207)

No R runs here, so these tests run on every system. ``DOCUMENT`` keeps
the structure of a ``prov.json`` that rdtLite 1.4 wrote under R 4.6 for
the ``model.R`` of the paper's case study (``prov.run("model.R",
prov.dir = ".")``), cut to the entities and relations the reader looks
at, with the paths of the machine replaced by ``/p``. The tracer that
uses these functions is tested in ``test_external_process_execution.py``
(``TestRProvenanceDocuments``) and, under rdtLite itself,
``e2e/test_beyond_python.py``.
"""

import json
import os

import pytest

from ...now.collection.prov_execution.external_provjson import (
    changed_documents,
    documents_in,
    is_prov_json,
    read_prov_json,
)

POSIX = pytest.mark.skipif(os.name == "nt", reason="the documents hold POSIX paths")

DOCUMENT = {
    "prefix": {
        "prov": "http://www.w3.org/ns/prov#",
        "rdt": "https://github.com/End-to-end-provenance/ExtendedProvJson/blob/master/JSON-format.md",
    },
    "agent": {"rdt:a1": {"rdt:tool.name": "rdtLite", "rdt:tool.version": "1.4"}},
    "activity": {
        "rdt:p5": {"rdt:name": "data <- read.csv(input)", "rdt:type": "Operation"},
        "rdt:p11": {"rdt:name": "write.csv(data.frame(", "rdt:type": "Operation"},
    },
    "entity": {
        "rdt:environment": {
            "rdt:name": "environment",
            "rdt:language": "R",
            "rdt:script": "/p/model.R",
            "rdt:scriptHash": "a2a4ac4d7f8f8d1c5ff52b2a1d1b0a0b",
            "rdt:sourcedScripts": "",
            "rdt:sourcedScriptHashes": "",
            "rdt:hashAlgorithm": "md5",
            "rdt:workingDirectory": "/p",
            "rdt:provDirectory": "/p/prov_model",
        },
        "rdt:d1": {"rdt:name": "args", "rdt:value": "...", "rdt:type": "Data"},
        "rdt:d4": {
            "rdt:name": "prepared.csv",
            "rdt:value": "data/4-prepared.csv",
            "rdt:type": "File",
            "rdt:hash": "14e246ff8f578453051634d48881c42d",
            "rdt:location": "/p/prepared.csv",
        },
        "rdt:d10": {
            "rdt:name": "pred.csv",
            "rdt:value": "data/10-pred.csv",
            "rdt:type": "File",
            "rdt:hash": "7c4186ce40730ef03a55bbed823c8b9f",
            "rdt:location": "/p/pred.csv",
        },
        "rdt:l1": {"name": "base", "prov:type": {"$": "prov:Collection"}},
    },
    "wasInformedBy": {
        "rdt:pp1": {"prov:informant": "rdt:p5", "prov:informed": "rdt:p11"}
    },
    "wasGeneratedBy": {
        "rdt:pd1": {"prov:activity": "rdt:p5", "prov:entity": "rdt:d1"},
        "rdt:pd9": {"prov:activity": "rdt:p11", "prov:entity": "rdt:d10"},
    },
    "used": {
        "rdt:dp1": {"prov:entity": "rdt:d1", "prov:activity": "rdt:p5"},
        "rdt:dp4": {"prov:entity": "rdt:d4", "prov:activity": "rdt:p5"},
    },
}


def document(**changes):
    """``DOCUMENT`` as text, with entities of the environment changed"""
    data = json.loads(json.dumps(DOCUMENT))
    data["entity"]["rdt:environment"].update(changes)
    return json.dumps(data)


@POSIX
def test_a_document_of_rdtlite():
    """The file the script used is a read, the file it generated a write,
    the script a read; a data entity, a library and the environment are
    no files"""
    assert read_prov_json(document(), "/elsewhere") == {
        "/p/model.R": False,
        "/p/prepared.csv": False,
        "/p/pred.csv": True,
    }


@POSIX
def test_the_sourced_scripts_are_reads():
    """``rdt:sourcedScripts`` is a path when one script was sourced and a
    list when several were"""
    one = read_prov_json(document(**{"rdt:sourcedScripts": "/p/utils.R"}), "/p")
    assert one["/p/utils.R"] is False
    two = read_prov_json(document(**{"rdt:sourcedScripts": ["/p/a.R", "/p/b.R"]}), "/p")
    assert (two["/p/a.R"], two["/p/b.R"]) == (False, False)


@POSIX
def test_a_file_read_and_written_is_a_write():
    """A file entity both relations name may have changed"""
    data = json.loads(document())
    data["used"]["rdt:dp9"] = {"prov:entity": "rdt:d10", "prov:activity": "rdt:p5"}
    data["wasGeneratedBy"]["rdt:pd4"] = {
        "prov:activity": "rdt:p11",
        "prov:entity": "rdt:d4",
    }
    files = read_prov_json(json.dumps(data), "/p")
    assert (files["/p/prepared.csv"], files["/p/pred.csv"]) == (True, True)


@POSIX
def test_a_relative_location_resolves_against_the_working_directory():
    """A relative ``rdt:location`` resolves against the document's working
    directory, or against the launch's directory without one"""
    data = json.loads(document())
    data["entity"]["rdt:d4"]["rdt:location"] = "data/../prepared.csv"
    assert "/p/prepared.csv" in read_prov_json(json.dumps(data), "/elsewhere")
    del data["entity"]["rdt:environment"]
    files = read_prov_json(json.dumps(data), "/launch")
    assert files == {"/launch/prepared.csv": False, "/p/pred.csv": True}


@POSIX
def test_an_entity_no_relation_names_and_other_types_are_skipped():
    """A file entity that no relation names, and a URL, are no files the
    script exchanged"""
    data = json.loads(document())
    data["entity"]["rdt:d20"] = {"rdt:type": "File", "rdt:location": "/p/idle.csv"}
    data["entity"]["rdt:d21"] = {"rdt:type": "URL", "rdt:location": "https://x/y.csv"}
    data["used"]["rdt:dp21"] = {"prov:entity": "rdt:d21", "prov:activity": "rdt:p5"}
    files = read_prov_json(json.dumps(data), "/p")
    assert "/p/idle.csv" not in files
    assert not any("y.csv" in path for path in files)


@pytest.mark.parametrize(
    "text",
    ["not json", "[]", '{"entity": []}', '{"agent": {}}'],
    ids=["not-json", "a-list", "entities-not-an-object", "no-entities"],
)
def test_what_is_no_prov_json_raises_value_error(text):
    with pytest.raises(ValueError):
        read_prov_json(text, "/p")


def test_malformed_entities_and_relations_are_skipped():
    """Entities and relations of the wrong type are skipped, not raised"""
    text = json.dumps(
        {
            "entity": {
                "rdt:environment": "?",
                "rdt:d1": "?",
                "rdt:d2": {"rdt:type": "File", "rdt:location": 3},
                "rdt:d3": {"rdt:type": "File", "rdt:location": os.path.abspath("f")},
            },
            "used": {"rdt:dp1": "?", "rdt:dp2": {"prov:entity": "rdt:d3"}},
            "wasGeneratedBy": [],
        }
    )
    assert read_prov_json(text, os.getcwd()) == {os.path.abspath("f"): False}


@pytest.mark.parametrize(
    "path, expected",
    [
        (os.path.join("p", "prov_model", "prov.json"), True),
        (os.path.join("p", "prov_model_2026-10-25T18.00.00", "prov.json"), True),
        (os.path.join("p", "prov", "prov.json"), True),
        (os.path.join("p", "results", "prov.json"), False),
        (os.path.join("p", "prov_model", "data.json"), False),
        ("prov.json", False),
    ],
)
def test_is_prov_json(path, expected):
    """A document is ``prov.json`` in a directory named ``prov...``, as
    rdtLite and RDataTracker name it (``overwrite = FALSE`` adds a time
    stamp)"""
    assert is_prov_json(path) is expected


def test_a_rewritten_document_is_a_changed_document(tmp_path):
    """The signature of a document tells a rewrite (rdtLite deletes and
    recreates its directory) from a document left alone; a document that
    is gone, and a file that is not a document, are not reported"""
    kept = tmp_path / "prov_a" / "prov.json"
    rewritten = tmp_path / "prov_b" / "prov.json"
    gone = tmp_path / "prov_c" / "prov.json"
    other = tmp_path / "prov_d" / "other.json"
    for path in (kept, rewritten, gone, other):
        path.parent.mkdir()
        path.write_text("{}", encoding="utf-8")
    before = documents_in(str(path) for path in (kept, rewritten, gone, other))
    assert sorted(before) == sorted(str(path) for path in (kept, rewritten, gone))
    rewritten.unlink()
    rewritten.write_text('{"entity": {}}', encoding="utf-8")
    gone.unlink()
    assert changed_documents(before) == [str(rewritten)]
