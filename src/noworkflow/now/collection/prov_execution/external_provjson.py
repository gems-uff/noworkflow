# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The PROV-JSON that an R provenance tool writes, read as the files of a
launch (#207)

An R script run under rdtLite (or RDataTracker, its predecessor), as in
``Rscript -e 'rdtLite::prov.run("model.R", prov.dir = ".")'``, leaves its
provenance in ``prov_model/prov.json``: an Extended PROV-JSON document
(https://github.com/End-to-end-provenance/ExtendedProvJson) whose
entities of ``rdt:type`` ``File`` are the files the script read and
wrote, by their absolute path (``rdt:location``), and whose ``used`` and
``wasGeneratedBy`` relations tie each one to the operation that read or
wrote it. The script itself, and every script it ran through
``source()``, are in the ``rdt:environment`` entity (``rdt:script``,
``rdt:sourcedScripts``). The command line names none of them, so the
``argv`` backend sees none; once the launch ends,
``ExternalProcessTracer.link_prov_json`` reads the document and makes
each file an access of the launch, as the strace backend does with the
files of its log.

This module only finds and reads the document, with no collector, so that
both are tested with fixture documents on any system. What becomes of
the files is the tracer's business.

**Which documents.** A file named ``prov.json`` in a directory whose name
starts with ``prov`` (``prov_<script>``, the directory both tools create)
that the launch wrote: a new file the snapshot or the strace log found,
or one that was already there and changed (``changed_documents``: rdtLite
deletes and recreates its directory on each run, which the snapshot of
paths alone does not see).

**What a document gives** (``read_prov_json``): ``{path: written}``,
the absolute path of each file and whether the script may have changed
it. A ``File`` entity that a ``wasGeneratedBy`` names was written, one
that only ``used`` names was read, one that neither names is skipped;
the scripts are read. A relative location is resolved against the
document's ``rdt:workingDirectory``, or the launch's directory. Any other
entity (``URL``, ``Data``, ``Snapshot``...) is no file of the launch. The
hashes the tools record (``rdt:hash``, MD5 by default) are not the
store's: the tracer hashes the files itself.
"""

import json
import os

# The name of the document, and the prefix of the directory it lives in.
DOCUMENT_NAME = "prov.json"
DIRECTORY_PREFIX = "prov"
# The entity that holds the scripts and the working directory.
ENVIRONMENT_ENTITY = "rdt:environment"
FILE_TYPE = "File"


def is_prov_json(path):
    """Whether a path names a document of an R provenance tool:
    ``prov.json`` in a directory whose name starts with ``prov``"""
    directory, name = os.path.split(path)
    return name == DOCUMENT_NAME and os.path.basename(directory).startswith(
        DIRECTORY_PREFIX
    )


def stat_signature(path):
    """What tells that a file was rewritten: inode, size and mtime, or
    None when there is no such file"""
    try:
        info = os.stat(path)
    except (OSError, ValueError):
        return None
    return (info.st_ino, info.st_size, info.st_mtime_ns)


def documents_in(paths):
    """The documents among the paths of a snapshot, with their signature,
    as ``{path: signature}``"""
    found = {}
    for path in paths:
        if is_prov_json(path):
            signature = stat_signature(path)
            if signature is not None:
                found[path] = signature
    return found


def changed_documents(before):
    """The documents of ``before`` (``documents_in`` at the launch) that a
    process rewrote: their signature changed and they are still there"""
    changed = []
    for path, signature in sorted(before.items()):
        now = stat_signature(path)
        if now is not None and now != signature:
            changed.append(path)
    return changed


def read_prov_json(text, base):
    """``{absolute path: written}`` of the files a PROV-JSON document of
    rdtLite names, resolving a relative location against its working
    directory or ``base``; raises ``ValueError`` when ``text`` is no such
    document"""
    try:
        document = json.loads(text)
    except ValueError as error:
        raise ValueError("not JSON: {}".format(error)) from None
    entities = document.get("entity") if isinstance(document, dict) else None
    if not isinstance(entities, dict):
        raise ValueError("no entity object")
    environment = entities.get(ENVIRONMENT_ENTITY)
    if not isinstance(environment, dict):
        environment = {}
    directory = environment.get("rdt:workingDirectory")
    if not isinstance(directory, str) or not os.path.isabs(directory):
        directory = base
    files = {}
    for identifier, entity in entities.items():
        if not isinstance(entity, dict) or entity.get("rdt:type") != FILE_TYPE:
            continue
        location = entity.get("rdt:location")
        if not isinstance(location, str) or not location:
            continue
        files[identifier] = os.path.normpath(os.path.join(directory, location))
    used = related(document.get("used"), files)
    generated = related(document.get("wasGeneratedBy"), files)
    found = {}
    for script in scripts(environment):
        found[os.path.normpath(os.path.join(directory, script))] = False
    for identifier, path in files.items():
        if identifier in generated:
            found[path] = True
        elif identifier in used:
            found.setdefault(path, False)
    return found


def related(relations, files):
    """The identifiers of ``files`` that the ``prov:entity`` of a
    relation object names"""
    found = set()
    if not isinstance(relations, dict):
        return found
    for relation in relations.values():
        if isinstance(relation, dict):
            entity = relation.get("prov:entity")
            if entity in files:
                found.add(entity)
    return found


def scripts(environment):
    """The script the tool ran and the scripts it sourced: one path, or a
    list of them, in ``rdt:script`` and ``rdt:sourcedScripts``"""
    found = []
    for key in ("rdt:script", "rdt:sourcedScripts"):
        value = environment.get(key)
        values = value if isinstance(value, list) else [value]
        found.extend(item for item in values if isinstance(item, str) and item)
    return found
