# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Diagrams module. Define both Schema and Prolog Diagram"""


def viz_table(body, border=0, cellborder=1, cellpadding=2, cellspacing=0,        # pylint: disable=too-many-arguments, unused-argument
              bgcolor="white", color="dodgerblue3"):                             # pylint: disable=unused-argument
    """Create HTML table for graphviz"""
    return (
        '<TABLE BORDER="{border}" CELLBORDER="{cellborder}"'
        ' CELLSPACING="{cellspacing}" CELLPADDING="{cellpadding}"'
        ' BGCOLOR="{bgcolor}" COLOR="{color}">'
        '{body}'
        '</TABLE>'
    ).format(**locals())


def viz_tr(body, port=None):
    """Create HTML tr for graphviz"""
    if port:
        return '<TR PORT="{}">{}</TR>'.format(port, body)
    return '<TR>{}</TR>'.format(body)


def viz_td(body, port=None, align="CENTER"):                                     # pylint: disable=unused-argument
    """Create HTML td for graphviz"""
    port_text = "" if port is None else 'PORT="{}"'.format(port)
    return '<TD {port_text} ALIGN="{align}">{body}</TD>'.format(**locals())


def viz_b(body):
    """Create HTML b for graphviz"""
    return '<B>{}</B>'.format(body)


def viz_white(body, bgcolor="white"):                                            # pylint: disable=unused-argument
    """Create hidden text for graphviz"""
    return '<FONT COLOR="{bgcolor}">{body}</FONT>'.format(**locals())


def viz_white_wrap(body, char, bgcolor="white"):                                 # pylint: disable=unused-argument
    """Wrap body with hidden text for graphviz"""
    return (
        '<FONT COLOR="{bgcolor}">'
        ' <FONT COLOR="black">{body}</FONT>'
        '{char}</FONT>'
    ).format(**locals())


def viz_property(statement, properties):
    """Create properties for graphviz element"""
    if not properties:
        return statement + ";";
    return statement + "[{}];".format(" ".join(properties))


class ViewDiagram(object):
    """ViewDiagram Base Class"""

    def __init__(self, _format="svg"):
        self.points = 0
        self.format = _format
        self.output = ""
        self.links = []
        self.result = []

    def _repr_svg_(self):
        if self.format == "svg":
            ipython = get_ipython()
            return ipython.run_cell_magic(
                "dot", "--format {}".format(self.format), self.as_dot()
            )

    def _repr_png_(self):
        if self.format == "png":
            ipython = get_ipython()
            return ipython.run_cell_magic(
                "dot", "--format {}".format(self.format), self.as_dot()
            )

    def as_dot(self):                                                            # pylint: disable=no-self-use
        """Export diagram to dot"""
        pass

    def __enter__(self):
        self.links = []
        self.points = 0
        self.result = ["digraph G{"]
        self.result.append("    rankdir=LR;")
        self.result.append("    overlap=false;")
        self.result.append("    splines=polyline;")
        return self.result

    def __exit__(self, *args):
        self.result += self.links
        self.result.append("}")
        self.output = "\n".join(self.result)


class ViewPrologDiagram(ViewDiagram):
    """View Prolog Diagram"""

    def __init__(self, descriptions, _format="svg"):
        super(ViewPrologDiagram, self).__init__(_format=_format)
        self.description = descriptions

    def add_link(self, model, link, attr_name):
        """Create edge"""
        if link:
            splitted = link.split('.')
            source = "{}:{}".format(model, attr_name)
            target = "{}:{}".format(*splitted)

            if splitted[0] == model:
                link_format = "    {0}:e -> p_{1} -> {2}:e".format(
                    source, self.points, target
                )
                point = viz_property(
                    "    p_{}".format(self.points),
                    ["shape=point", "color=dodgerblue3"]
                )
                self.links.append(point)
                self.points += 1
            else:
                link_format = "    {}:_ -> {}:_".format(source, target)

            self.links.append(viz_property(
                link_format,
                ["dir=none", "color=dodgerblue3"]
            ))

    def as_dot(self):
        with self as result:
            for model in self.description:
                content = [
                    viz_tr(viz_td(viz_white_wrap(viz_b(model.name), "(")))
                ]
                for attr in model.attributes[:-1]:
                    content.append(viz_tr(
                        viz_td(viz_white_wrap(attr.variable(), ","),
                               port=attr.name)
                    ))
                    self.add_link(model.name, attr.link, attr.name)
                attr = model.attributes[-1]
                content.append(viz_tr(
                    viz_td(viz_white_wrap(attr.variable(), ")"),
                           port=attr.name)
                ))
                self.add_link(model.name, attr.link, attr.name)
                result.append('    {0} [shape=none label=<{1}>];'.format(
                    model.name, viz_table("".join(content))
                ))
        return self.output


class ViewRelationalDiagram(ViewDiagram):
    """View SQL Diagram"""

    def __init__(self, order, _format="svg"):
        super(ViewRelationalDiagram, self).__init__(_format=_format)
        self.order = order

    def add_link(self, model, link, attr_name):
        """Create arrow"""
        link_properties = ['label="{}"'.format(attr_name), "color=dodgerblue3"]
        splitted = link.split('.')
        source = model
        target = "{}:{}".format(*splitted)

        if splitted[0] == model:
            link_format = "    {0}:n -> {1}:e".format(source, target)
        else:
            link_format = "    {0}:_ -> {1}:_".format(source, target)

        self.links.append(viz_property(link_format, link_properties))

    def as_dot(self):
        with self as result:
            for model in self.order:
                name = model.__tablename__
                table = model.t
                content = [viz_tr(viz_td(viz_b(name)))]
                attributes = []
                for column in table.columns:
                    if not column.foreign_keys:
                        attributes.append(viz_tr(viz_td(
                            "{}: {!s}".format(column.name, column.type),
                            align="LEFT", port=column.name
                        )))
                    else:
                        for fkey in column.foreign_keys:
                            if not fkey.column.foreign_keys:
                                link = fkey.target_fullname
                                self.add_link(name, link, column.name)
                if attributes:
                    content.append(viz_tr(viz_td(viz_table(
                        "".join(attributes), border=0, cellborder=0
                    ))))
                else:
                    content.append(viz_tr(viz_td("")))
                result.append('    {0} [shape=none label=<{1}>];'.format(
                    name,
                    viz_table("".join(content), cellspacing=0)
                ))
        return self.output
