# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``content/safeopen.py``: the original ``open``s and the safe-open flag

``restore_open`` puts Python's four ``open`` functions back for the length
of a block (the dulwich engine writes its trees in one) and then reinstalls
whatever was there, the collector's wrappers during a trial. It does so for
``io.open``, ``codecs.open`` and ``os.open``; ``builtins.open`` stays
Python's after the block, because the value it saves for
``__builtins__["open"]`` is read after it replaced ``builtins.open``, and
``__builtins__`` is the builtins module or its dict, the same object. That
defect has a characterization and a ``_desired`` twin, for both shapes of
``__builtins__``.

The tests install stand-ins for the four functions (each one forwards to
the original, so a stray call still works) and always put the originals
back before they end. ``use_safe_open`` sets a per-thread flag that the
collector reads to leave noWorkflow's own reads unrecorded.
"""

import builtins
import codecs
import contextlib
import io
import os
import threading

import pytest

from ...now.persistence.config import PersistenceConfig
from ...now.persistence.content import safeopen
from ...now.persistence.content.plain_engine import PlainEngine
from ..helpers.defects import Defect, known_defects

# Python's own functions, captured when this module is imported (the leak
# detector checks that safeopen captured the same ones).
PYTHON_OPENS = {
    "builtins.open": builtins.open,
    "io.open": io.open,
    "codecs.open": codecs.open,
    "os.open": os.open,
}
MODULES = {
    "builtins.open": builtins,
    "io.open": io,
    "codecs.open": codecs,
    "os.open": os,
}
SAFEOPEN_COPIES = {
    "builtins.open": safeopen.std_open,
    "io.open": safeopen.io_open,
    "codecs.open": safeopen.codecs_open,
    "os.open": safeopen.os_open,
}
BUILTINS_SHAPES = pytest.mark.parametrize(
    "shape", ["dict", "module"], ids=["builtins-is-a-dict", "builtins-is-a-module"]
)

BUILTINS_OPEN_KEPT = Defect(
    "#353: safeopen.restore_open saves "
    "__builtins__['open'] after it set builtins.open to the original, and "
    "__builtins__ is the builtins module (or its dict), so the finally "
    "block writes the original back over the restored wrapper",
    signature="'builtins.open': 'original'",
)


def stand_in(original):
    """A distinct function that forwards to ``original``"""

    def open_stand_in(*args, **kwargs):
        return original(*args, **kwargs)

    return open_stand_in


def state(stand_ins):
    """``{name: "original" | "stand-in" | "other"}`` of the four opens"""
    result = {}
    for name, module in MODULES.items():
        current = module.open
        if current is PYTHON_OPENS[name]:
            result[name] = "original"
        elif current is stand_ins[name]:
            result[name] = "stand-in"
        else:
            result[name] = "other"
    return result


@contextlib.contextmanager
def stand_ins_installed(monkeypatch, shape="dict"):
    """Install stand-ins for the four opens; ``shape`` "module" makes
    safeopen see ``__builtins__`` as the builtins module. Everything is
    undone on exit, also after a failure."""
    stand_ins = {name: stand_in(original) for name, original in PYTHON_OPENS.items()}
    with monkeypatch.context() as patch:
        if shape == "module":
            patch.setattr(safeopen, "__builtins__", builtins)
        for name, module in MODULES.items():
            patch.setattr(module, "open", stand_ins[name])
        yield stand_ins


def restore_open_states(monkeypatch, shape="dict", restore=None):
    """The state of the opens inside ``restore_open`` and after it"""
    restore = restore or safeopen.restore_open
    with stand_ins_installed(monkeypatch, shape) as stand_ins:
        with restore():
            inside = state(stand_ins)
        after = state(stand_ins)
    return inside, after


def test_safeopen_keeps_pythons_opens():
    """Premise: safeopen's copies are Python's own functions"""
    assert SAFEOPEN_COPIES == PYTHON_OPENS


@BUILTINS_SHAPES
def test_restore_open_brings_back_the_originals_inside_the_block(monkeypatch, shape):
    """Inside the block the four opens are Python's; after it the stand-ins
    of io, codecs and os are back, but builtins.open stays Python's"""
    inside, after = restore_open_states(monkeypatch, shape)

    assert inside == dict.fromkeys(MODULES, "original")
    assert after == {
        "builtins.open": "original",
        "io.open": "stand-in",
        "codecs.open": "stand-in",
        "os.open": "stand-in",
    }


@BUILTINS_SHAPES
@known_defects(BUILTINS_OPEN_KEPT)
def test_restore_open_brings_back_the_originals_inside_the_block_desired(
    monkeypatch, shape
):
    """Desired: after the block every open is what it was before it"""
    _, after = restore_open_states(monkeypatch, shape)

    assert after == dict.fromkeys(MODULES, "stand-in"), "after the block: {}".format(
        after
    )


def test_restore_open_puts_the_stand_ins_back_after_an_exception(monkeypatch):
    """An exception inside the block propagates, and the opens come back
    as after a normal exit"""
    with stand_ins_installed(monkeypatch) as stand_ins:
        with pytest.raises(ValueError):
            with safeopen.restore_open():
                raise ValueError("inside")
        after = state(stand_ins)

    assert after == {
        "builtins.open": "original",
        "io.open": "stand-in",
        "codecs.open": "stand-in",
        "os.open": "stand-in",
    }


def test_engine_restore_open_is_safeopen_restore_open(monkeypatch, tmp_path):
    """A content engine's ``restore_open`` swaps the opens the same way"""
    config = PersistenceConfig()
    config.path = str(tmp_path)
    engine = PlainEngine(config)

    assert restore_open_states(monkeypatch, restore=engine.restore_open) == (
        restore_open_states(monkeypatch)
    )


def test_use_safe_open_is_per_thread_and_nests(tmp_path):
    """The flag is set inside ``use_safe_open``, in this thread only;
    nested blocks restore the outer value; the engine's methods are the
    same flag"""
    config = PersistenceConfig()
    config.path = str(tmp_path)
    engine = PlainEngine(config)
    other_thread = []

    def read_flag():
        other_thread.append(safeopen.should_use_safe_open())

    assert safeopen.should_use_safe_open() is False
    with engine.use_safe_open():
        assert engine.should_use_safe_open() is True
        worker = threading.Thread(target=read_flag)
        worker.start()
        worker.join()
        with safeopen.use_safe_open():
            assert safeopen.should_use_safe_open() is True
        assert safeopen.should_use_safe_open() is True
    assert safeopen.should_use_safe_open() is False
    assert other_thread == [False]


def test_print_open_prints_the_four_originals(capsys):
    """``print_open`` prints Python's open (which is io.open), io.open, the
    file of codecs.open and os.open"""
    safeopen.print_open()

    assert capsys.readouterr().out.splitlines() == [
        str(io.open),
        str(io.open),
        codecs.open.__code__.co_filename,
        str(os.open),
    ]
