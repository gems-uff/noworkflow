# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``persistence/serializers.py``: the text recorded for each value

``now run -r`` chooses how the collector turns every value it records
into the text of ``evaluation.repr``: ``repr`` (the default,
``repr_serializer``), ``jsonpickle``, ``jsonpickle_content`` (the encoding
goes to the content store and the text points to it) and ``simple``
(``SimpleSerializer``, which never calls the script's ``__repr__``).
``get_serializer`` maps the choice to the function.

Expected values come from Python itself (``repr``, ``id``, attribute
lookup), from the jsonpickle stub of ``helpers/jsonpickle_stub.py``
(jsonpickle is not a dependency), and, for ``jsonpickle_content``, from a
round trip through the content store. The store is the in-memory one the
suite connects on import; a test that writes to it uses an empty content
dictionary of its own.

Three defects get a characterization and a ``_desired`` twin:
``repr_serializer`` formats a class whose metaclass is not ``type`` (any
ABC) with the ``__repr__`` it defines for its instances
(repr-serializer-class-repr; the run that crashes is the oracle case
``abc_class_repr``), ``jsonpickle_content`` hands a ``str`` to the
content store, which hashes bytes only (jsonpickle-content-puts-str), and
``SimpleSerializer`` leaves its object texts without the closing ``>``
(simple-serializer-unclosed-angle-bracket). The ``now run`` side of the
serializers is in ``e2e/test_serializers_cli.py``.

``SimpleSerializer``'s fallbacks for an object without a visible
``__class__`` depend on the Python version: before 3.13 such an object
makes ``isinstance`` against ``numbers.Number`` raise, so the serializer
raises before reaching them. Each version gets the test of what it does.
"""

import re
import sys
from argparse import Namespace
from array import array
from collections import OrderedDict, deque, namedtuple

import pytest

from noworkflow.now.persistence import content, get_serializer
from noworkflow.now.persistence.serializers import (
    SimpleSerializer,
    jsonpickle_content,
    jsonpickle_serializer,
    repr_serializer,
)
from noworkflow.tests.helpers import jsonpickle_stub
from noworkflow.tests.helpers.defects import Defect, known_defects

CLASS_REPR = Defect(
    "#340: repr_serializer "
    "(persistence/serializers.py) skips the lookup of the traced __repr__ "
    "only when type(value) is type; for a class with another metaclass "
    "(ABCMeta, any custom one) object.__getattribute__ returns the "
    "__repr__ in the class's own namespace, written for its instances, and "
    "repr_serializer calls its original_def with the class as self, while "
    "Python formats a class with its metaclass's __repr__",
    signature="Shape(0)",
)
CONTENT_PUTS_STR = Defect(
    "#339: jsonpickle_content "
    "(persistence/serializers.py) passes the str that jsonpickle.encode "
    "returns to content.put, and both the plain engine and the in-memory "
    "mock (persistence/content/plain_engine.py, content/base.py) hash it "
    "with hashlib.sha1, which takes bytes only",
    signature="Strings must be encoded before hashing",
)
UNCLOSED_ANGLE_BRACKET = Defect(
    "#353: "
    "SimpleSerializer._default (persistence/serializers.py) formats an "
    "object as '<{} instance at 0x{:x}' and a named one as "
    "'<{} at 0x{:x}', without the closing '>' that its third format, "
    "'<callable at 0x{:x}>', has",
    signature="'<C instance at 0x<id>'",
)

# A hexadecimal address, as SimpleSerializer writes id().
ADDRESS = re.compile(r"0x[0-9a-f]+")
# What the content store's put returns is appended to this prefix.
CONTENT_PREFIX = "now-content:"


def masked(text):
    """``text`` with every address written ``0x<id>``"""
    return ADDRESS.sub("0x<id>", text)


@pytest.fixture
def stub_jsonpickle(monkeypatch):
    """The jsonpickle stub in ``sys.modules``; its calls, ``(value, keys)``"""
    return jsonpickle_stub.install(monkeypatch)


@pytest.fixture
def empty_content(monkeypatch):
    """An empty dictionary behind the in-memory content store's put and get

    The mock engine keeps what ``put`` receives in ``temp``; the original
    dictionary comes back when the test ends, so nothing it stores reaches
    another test.
    """
    monkeypatch.setattr(content.content_database_engine, "temp", {})


# --- get_serializer ---------------------------------------------------------


def test_get_serializer_returns_the_function_of_each_run_r_choice():
    """Each choice of ``now run -r`` selects its serializer; ``simple``
    gets the method of a new ``SimpleSerializer`` each time"""

    def chosen(name):
        return get_serializer(Namespace(serializer=name))

    assert chosen("repr") is repr_serializer
    assert chosen("jsonpickle") is jsonpickle_serializer
    assert chosen("jsonpickle_content") is jsonpickle_content
    simple = chosen("simple")
    assert simple.__func__ is SimpleSerializer.serialize
    assert isinstance(simple.__self__, SimpleSerializer)
    assert chosen("simple").__self__ is not simple.__self__


def test_get_serializer_falls_back_to_repr_for_an_unknown_name():
    """Characterization: a name that is not a choice gets the default
    (argparse's choices stop it before it reaches here)"""
    assert get_serializer(Namespace(serializer="bogus")) is repr_serializer


# --- repr_serializer --------------------------------------------------------


@pytest.mark.parametrize(
    "value", [1, "a", [1], int, None], ids=["int", "str", "list", "class", "None"]
)
def test_repr_serializer_formats_values_with_repr(value):
    """Values whose ``__repr__`` the script did not write get ``repr()``"""
    assert repr_serializer(value) == repr(value)


def traced_repr(original):
    """A stand-in for a ``__repr__`` that ``now run`` traced

    ``Collector.collect_function_def`` sets ``original_def`` on the traced
    function to the untransformed copy, and ``repr_serializer`` calls that
    copy, so that recording a value does not record the call.
    """

    def __repr__(self):
        return "TRACED"

    __repr__.original_def = original
    return __repr__


def original_repr(self):
    return "Shape({})".format(self.side)


def test_repr_serializer_calls_the_original_definition_of_a_traced_repr():
    """An instance whose ``__repr__`` was traced is formatted by the
    original definition (a bound method forwards ``original_def`` from its
    function)"""

    class Shape:
        __repr__ = traced_repr(original_repr)

        def __init__(self):
            self.side = 3

    assert repr(Shape()) == "TRACED"
    assert repr_serializer(Shape()) == "Shape(3)"


def test_repr_serializer_formats_a_plain_class_with_python_repr():
    """Control: a class whose metaclass is ``type`` is formatted by
    ``repr()``, although it defines a traced ``__repr__`` for its
    instances"""

    class Shape:
        __repr__ = traced_repr(original_repr)

    assert repr_serializer(Shape) == repr(Shape)


class Meta(type):
    """A metaclass that adds nothing: only ``type(cls) is not type``"""


def test_repr_serializer_class_with_another_metaclass_and_an_instance_repr():
    """Characterization: a class with another metaclass is formatted by
    the ``__repr__`` it defines for its instances, called with the class as
    ``self``, which raises when it reads an instance attribute"""

    class Shape(metaclass=Meta):
        __repr__ = traced_repr(original_repr)

    with pytest.raises(
        AttributeError, match="type object 'Shape' has no attribute 'side'"
    ):
        repr_serializer(Shape)


@known_defects(CLASS_REPR)
def test_repr_serializer_class_with_another_metaclass_and_an_instance_repr_desired():
    """A class with another metaclass is formatted by ``repr()``, as any
    class is (a class attribute keeps the instance ``__repr__`` from
    raising, so that today's wrong text shows)"""

    class Shape(metaclass=Meta):
        side = 0
        __repr__ = traced_repr(original_repr)

    text = repr_serializer(Shape)
    assert text == repr(Shape), "recorded as {!r}".format(text)


# --- jsonpickle -------------------------------------------------------------


def test_jsonpickle_serializer_encodes_with_keys(stub_jsonpickle):
    """``-r jsonpickle`` records what ``jsonpickle.encode`` returns, called
    with ``keys=True`` (dictionary keys encoded as objects too)"""
    assert jsonpickle_serializer([1]) == jsonpickle_stub.encode([1], keys=True)
    assert stub_jsonpickle == [([1], True)]


def test_jsonpickle_content_of_a_list(stub_jsonpickle, empty_content):
    """Characterization: ``-r jsonpickle_content`` passes the text that
    ``jsonpickle.encode`` returns to the content store, which raises because
    it hashes bytes only"""
    with pytest.raises(TypeError, match="Strings must be encoded before hashing"):
        jsonpickle_content([1])
    assert stub_jsonpickle == [([1], True)]


@known_defects(CONTENT_PUTS_STR)
def test_jsonpickle_content_of_a_list_desired(stub_jsonpickle, empty_content):
    """``-r jsonpickle_content`` records a reference to the content store,
    where the encoding of the value is kept"""
    text = jsonpickle_content([1])
    assert text.startswith(CONTENT_PREFIX), text
    stored = content.get(text[len(CONTENT_PREFIX) :])
    assert stored.decode("utf-8") == jsonpickle_stub.encode([1], keys=True)


# --- SimpleSerializer -------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        1,
        1.5,
        True,
        None,
        "a'b",
        b"x",
        Ellipsis,
        3 + 4j,
    ],
    ids=["int", "float", "bool", "None", "str", "bytes", "Ellipsis", "complex"],
)
def test_simple_serializer_formats_immutables_with_repr(value):
    """Numbers, text, bytes, None and Ellipsis get ``repr()``"""
    assert SimpleSerializer().serialize(value) == repr(value)


Point = namedtuple("Point", "x y")


class Items(list):
    """A list subclass"""


def test_simple_serializer_formats_containers_with_their_class_name():
    """A container is written as its class name around the list of its
    items, each serialized in turn; a dictionary's items are pairs, and an
    array starts with its type code"""
    serialize = SimpleSerializer().serialize
    assert serialize((1, "a")) == "tuple([{}, {}])".format(repr(1), repr("a"))
    assert serialize([1, [2]]) == "list([1, list([2])])"
    assert serialize({3}) == "set([3])"
    assert serialize(frozenset([3])) == "frozenset([3])"
    assert serialize(deque([1])) == "deque([1])"
    assert serialize({"k": [1]}) == "dict([({}, list([1]))])".format(repr("k"))
    assert serialize(array("i", [1, 2])) == "array(i, [1, 2])"


def test_simple_serializer_names_a_subclass_by_its_own_class():
    """A subclass of a container is named after its own class, with the
    blanks of the name turned into underscores"""
    serialize = SimpleSerializer().serialize
    assert serialize(OrderedDict(a=1)) == "OrderedDict([({}, 1)])".format(repr("a"))
    assert serialize(Point(1, 2)) == "Point([1, 2])"
    assert serialize(Items([1])) == "Items([1])"
    assert serialize(type("my list", (list,), {})([1])) == "my_list([1])"


def test_simple_serializer_stops_at_maxlevel():
    """Nesting deeper than ``maxlevel`` (5 by default) is cut: the
    container there is written as an object, by class and address, so a
    list that contains itself ends too"""
    serialize = SimpleSerializer().serialize
    nested = [[[[[[1]]]]]]
    cut = nested[0][0][0][0][0]
    head = "list([" * 5 + "<list instance at 0x{:x}".format(id(cut))
    text = serialize(nested)
    assert text.startswith(head), text
    # Then the cut object's closing bracket, when it has one
    # (simple-serializer-unclosed-angle-bracket), and five closings.
    assert text[len(head) :] in ("])" * 5, ">" + "])" * 5), text
    alone = [1]
    assert serialize(alone, maxlevel=0).startswith(
        "<list instance at 0x{:x}".format(id(alone))
    )
    looped = []
    looped.append(looped)
    assert serialize(looped).startswith(
        "list([" * 5 + "<list instance at 0x{:x}".format(id(looped))
    )


# Before Python 3.13, isinstance against an ABC (numbers.Number, one of
# IMMUTABLE) reads the object's __class__ and lets its AttributeError
# through; from 3.13 a missing __class__ is no match (measured on 3.11 to
# 3.15), so only then does SimpleSerializer reach its fallbacks.
HIDDEN_CLASS_RAISES = sys.version_info < (3, 13)
HIDDEN_CLASS_REASON = (
    "before Python 3.13 isinstance against numbers.Number raises the "
    "AttributeError of a hidden __class__"
)


class C:
    """An object of the script's own class"""


class Opaque:
    """An object that hides every attribute, ``__class__`` included"""

    def __getattribute__(self, name):
        raise AttributeError(name)


class Named:
    """An object that shows only a ``__name__``"""

    def __getattribute__(self, name):
        if name == "__name__":
            return "the_name"
        raise AttributeError(name)


class CallableOnly:
    """An object that shows only a ``__call__``"""

    def __getattribute__(self, name):
        if name == "__call__":
            return lambda: None
        raise AttributeError(name)


class HiddenList(list):
    """A list that hides its ``__class__``"""

    def __getattribute__(self, name):
        if name == "__class__":
            raise AttributeError(name)
        return list.__getattribute__(self, name)


def test_simple_serializer_formats_other_objects_by_class_and_address():
    """Characterization: an object is written as its class name and its
    address, without a closing ``>``"""
    obj = C()
    assert SimpleSerializer().serialize(obj) == (
        "<C instance at 0x{:x}".format(id(obj))
    )


@known_defects(UNCLOSED_ANGLE_BRACKET)
def test_simple_serializer_formats_other_objects_by_class_and_address_desired():
    """An object is written between ``<`` and ``>``, as Python's default
    ``repr`` and the serializer's own callable format are"""
    obj = C()
    text = SimpleSerializer().serialize(obj)
    assert masked(text) == "<C instance at 0x<id>>", "written as {!r}".format(
        masked(text)
    )
    assert text == "<C instance at 0x{:x}>".format(id(obj))


@pytest.mark.skipif(HIDDEN_CLASS_RAISES, reason=HIDDEN_CLASS_REASON)
def test_simple_serializer_falls_back_when_an_object_hides_its_class():
    """An object without a visible ``__class__`` is written by its name, as
    callable or as unsupported, with its address; a container without one
    is named after its type"""
    serialize = SimpleSerializer().serialize
    named, opaque, callable_only = Named(), Opaque(), CallableOnly()
    # The named format lacks its closing ">" like the instance format
    # (simple-serializer-unclosed-angle-bracket): accepted either way here.
    assert serialize(named).rstrip(">") == "<the_name at 0x{:x}".format(id(named))
    assert serialize(callable_only) == "<callable at 0x{:x}>".format(id(callable_only))
    assert serialize(opaque) == "<unsupported type at 0x{:x}>".format(id(opaque))
    assert serialize(HiddenList([1, 2])) == "HiddenList([1, 2])"


@pytest.mark.skipif(
    not HIDDEN_CLASS_RAISES, reason="from Python 3.13 the fallbacks are reached"
)
@pytest.mark.parametrize(
    "make",
    [
        Named,
        Opaque,
        CallableOnly,
        lambda: HiddenList([1, 2]),
    ],
    ids=["named", "opaque", "callable", "container"],
)
def test_simple_serializer_object_that_hides_its_class_before_python_3_13(make):
    """Characterization: before Python 3.13 an object that hides its
    ``__class__`` makes the serializer raise that ``AttributeError`` at its
    first check, ``isinstance(obj, IMMUTABLE)``, before any fallback"""
    with pytest.raises(AttributeError, match="__class__"):
        SimpleSerializer().serialize(make())
