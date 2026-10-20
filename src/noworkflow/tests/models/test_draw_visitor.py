# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``DrawVisitor``: the DOT text of a reconstructed AST

``DrawVisitor`` (Python API only, ``noworkflow.now.models.ast``) draws a
tree that ``create_trees`` rebuilt from the code components and the
compositions of a trial: one node per tree node and per attribute value,
labelled with its ``repr``, and one edge per attribute, labelled with the
attribute's name; ``_repr_svg_`` pipes ``dot_text`` through Graphviz. The
tree here is rebuilt from plain rows, with no store: one ``name`` node
whose ``value`` attribute comes from a composition's ``extra``, which
``add_attr`` evaluates. The collector writes only numbers, booleans and
identifiers there; a store received from someone else can hold any value.

``dot_text`` is read with ``DotGraph`` and ``rendered`` of
``e2e/test_export.py``, which follow Graphviz's lexer and grammar, so no
test needs Graphviz (#393). Known defects get a characterization of what
``DrawVisitor`` does today and a ``_desired`` twin decorated with
``known_defects``, which cites the issue (``#NNN``) and the signature of
today's failure.
"""

from types import SimpleNamespace

import pytest

from noworkflow.now.models.ast import DrawVisitor, create_trees
from noworkflow.tests.e2e.test_export import DotGraph, rendered
from noworkflow.tests.helpers.defects import Defect, known_defects

# Both quote characters: its repr is written between single quotes, with
# the double quotes as they are.
BOTH_QUOTES = 'say "it\'s"'
BOTH_QUOTES_LABEL = Defect(
    reason='#401: DrawVisitor.dot_text writes each label as "{!r}" with no '
    "escaping: the repr of a str that holds a quote character holds "
    "a raw double quote (one of the str's own, or the delimiters of "
    "the repr), and the first one closes the label",
    signature='[label="\'say "it\\\'s"\'"]',
)


def draw(value):
    """``(node, dot_text)``: ``DrawVisitor`` over a ``name`` node whose
    ``value`` attribute is ``value``
    """
    component = SimpleNamespace(id=1, trial_id="t", type="name", name="target")
    composition = SimpleNamespace(
        whole_id=1,
        part_id=None,
        type="value",
        position=None,
        extra="str({!r})".format(value),
    )
    node = create_trees([component], {}, [composition])[1]
    visitor = DrawVisitor()
    visitor.visit(node)
    return node, visitor.dot_text


def assert_draws(node, value, text):
    """``text`` is a DOT graph of two nodes and one edge ``value`` between
    them: the origin draws the repr of ``node``, the target the repr of
    ``value`` or ``value`` itself
    """
    graph = DotGraph(text)
    assert (len(graph.nodes), len(graph.edges)) == (2, 1), text
    origin, target, attributes = graph.edges[0]
    assert rendered(attributes["label"]) == "value", text
    assert rendered(graph.nodes[origin]["label"]) == repr(node), text
    assert rendered(graph.nodes[target]["label"]) in (repr(value), value), text


def test_draw_visitor_label_of_a_plain_value():
    """A value without quote characters draws a well-formed graph: the
    node's repr, the value's repr, and the edge ``value`` between them

    Control of the #401 twin below: the same checks pass today, and keep
    passing under a fix that draws the value itself instead of its repr.
    """
    node, text = draw("plain")

    assert_draws(node, "plain", text)


def test_draw_visitor_label_of_a_value_with_both_quotes():
    """A value that holds both quote characters is written as its repr
    between double quotes, its own double quotes raw: the first one
    closes the label, and Graphviz and ``DotGraph`` reject the graph (#401
    changes it)
    """
    _, text = draw(BOTH_QUOTES)

    assert text.splitlines() == [
        "digraph G {",
        "  n0 [label=\"AST(name, t, 1, 'target')\"];",
        "  n1 " + BOTH_QUOTES_LABEL.signature + ";",
        '  n0 -> n1 [label="value"]',
        "}",
    ]
    with pytest.raises(AssertionError, match=r"^not a DOT graph: unexpected '\\\\'"):
        DotGraph(text)


@known_defects(BOTH_QUOTES_LABEL)
def test_draw_visitor_label_of_a_value_with_both_quotes_desired():
    """A value that holds both quote characters draws a well-formed graph,
    whose target draws the value's repr or the value itself: a fix may
    escape either, in any spelling Graphviz reads back as that text
    """
    node, text = draw(BOTH_QUOTES)

    assert_draws(node, BOTH_QUOTES, text)
