# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""A stand-in for jsonpickle, in the test process and in a project

``now run -r jsonpickle`` and ``-r jsonpickle_content`` import jsonpickle
when they serialize the first value, and jsonpickle comes only with the
``all`` extra, which no CI leg syncs. The stub keeps the one property of
the real ``jsonpickle.encode`` that the serializers rely on, that it
returns a ``str`` (measured with jsonpickle 4.1), and writes a JSON text that says what it was given: the ``repr`` of
the value and the ``keys`` flag.

``SOURCE`` is the module's text. ``write_into(project)`` writes it as
``jsonpickle.py`` next to the script, where the script's directory, first
on ``sys.path``, shadows an installed jsonpickle (measured). ``install``
puts a module built from the same text into ``sys.modules`` of the test
process and records each call, and ``encode`` is that same function, for
computing what the stub returned to the code under test.
"""
import sys
import types

SOURCE = '''\
"""Stand-in for jsonpickle: encode returns a str, as jsonpickle.encode does"""
import json


def encode(value, keys=False):
    return json.dumps({"value": repr(value), "keys": keys})
'''


def _module():
    module = types.ModuleType("jsonpickle")
    exec(compile(SOURCE, "<jsonpickle stub>", "exec"), vars(module))  # pylint: disable=exec-used
    return module


encode = _module().encode


def install(monkeypatch):
    """Put the stub in ``sys.modules`` for one test; returns its calls

    Each call to ``encode`` appends ``(value, keys)`` to the list returned.
    ``monkeypatch`` removes the stub when the test ends.
    """
    calls = []
    module = _module()
    stub_encode = module.encode

    def recording_encode(value, keys=False):
        calls.append((value, keys))
        return stub_encode(value, keys=keys)

    module.encode = recording_encode
    monkeypatch.setitem(sys.modules, "jsonpickle", module)
    return calls


def write_into(project):
    """Write the stub as ``jsonpickle.py`` into a ``NowProject``"""
    project.write("jsonpickle.py", SOURCE)
