"""
`%hierarchy` and `%%dot` magics for IPython
===========================================

This extension provides two magics.

First magic is ``%hierarchy``.  This magic command draws hierarchy of
given class or the class of given instance.  For example, the
following shows class hierarchy of currently running IPython shell.::

    %hierarchy get_ipython()


Second magic is ``%%dot``.  You can write graphiz dot language in a
cell using this magic.  Example::

    %%dot -- -Kfdp
    digraph G {
        a->b; b->c; c->d; d->b; d->a;
    }


License for ipython-hierarchymagic
----------------------------------

ipython-hierarchymagic is licensed under the term of the Simplified
BSD License (BSD 2-clause license), as follows:

Copyright (c) 2012 Takafumi Arakaki
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


License for Sphinx
------------------

`run_dot` function and `HierarchyMagic._class_name` method in this
extension heavily based on Sphinx code `sphinx.ext.graphviz.render_dot`
and `InheritanceGraph.class_name`.

Copyright notice for Sphinx can be found below.

Copyright (c) 2007-2011 by the Sphinx team (see AUTHORS file).
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

* Redistributions of source code must retain the above copyright
  notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright
  notice, this list of conditions and the following disclaimer in the
  documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""

from IPython.core.magic import Magics, magics_class, line_magic, cell_magic
from IPython.core.magic_arguments import (argument, magic_arguments,
                                          parse_argstring)
from IPython.core.display import display_png, display_svg

from sphinx.ext.inheritance_diagram import InheritanceGraph

from future.utils import lmap


def run_dot(code, options=[], format='png'):                                     # pylint: disable=redefined-builtin, dangerous-default-value
    """run_dot"""
    # mostly copied from sphinx.ext.graphviz.render_dot
    import os
    from subprocess import Popen, PIPE
    from sphinx.util.osutil import EPIPE, EINVAL

    dot_args = ['dot'] + options + ['-T', format]
    if os.name == 'nt':
        # Avoid opening shell window.
        # * https://github.com/tkf/ipython-hierarchymagic/issues/1
        # * http://stackoverflow.com/a/2935727/727827
        process = Popen(dot_args, stdout=PIPE, stdin=PIPE, stderr=PIPE,
                        creationflags=0x08000000)
    else:
        process = Popen(dot_args, stdout=PIPE, stdin=PIPE, stderr=PIPE)
    wentwrong = False
    try:
        # Graphviz may close standard input when an error occurs,
        # resulting in a broken pipe on communicate()
        stdout, stderr = process.communicate(code.encode('utf-8'))
    except (OSError, IOError) as err:
        if err.errno != EPIPE:
            raise
        wentwrong = True
    if wentwrong:
        # in this case, read the standard output and standard error streams
        # directly, to get the error message(s)
        stdout, stderr = process.stdout.read(), process.stderr.read()
        process.wait()
    if process.returncode != 0:
        raise RuntimeError('dot exited with error:\n[stderr]\n{0}'
                           .format(stderr.decode('utf-8')))
    return stdout


@magics_class
class GraphvizMagic(Magics):
    """GraphvizMagic"""

    @magic_arguments()
    @argument(
        '-f', '--format', default='png', choices=('png', 'svg'),
        help='output format (png/svg)'
    )
    @argument(
        'options', default=[], nargs='*',
        help='options passed to the `dot` command'
    )
    @cell_magic
    def dot(self, line, cell):
        """Draw a figure using Graphviz dot command."""
        args = parse_argstring(self.dot, line)

        image = run_dot(cell, args.options, format=args.format)

        if args.format == 'png':
            display_png(image, raw=True)
        elif args.format == 'svg':
            display_svg(image, raw=True)


class FoldedInheritanceGraph(InheritanceGraph):
    """InheritanceGraph"""

    def __init__(self, *args, **kwds):
        self._width = kwds.pop('width', 40)
        super(FoldedInheritanceGraph, self).__init__(*args, **kwds)

    @staticmethod
    def _foldclassname(classname, width):
        """Split `classname` in newlines if the width is wider than `width`.

        >>> fold = FoldedInheritanceGraph._foldclassname
        >>> fold('aaa.bbb.ccc', 7)
        'aaa.bbb\\n.ccc'
        >>> fold('aaa.bbb.ccc', 3)
        'aaa\\n.bbb\\n.ccc'
        >>> identity = lambda x, y: ''.join(fold(x, y).split('\\n'))
        >>> identity('aaa.bbb.ccc', 7)
        'aaa.bbb.ccc'
        >>> identity('aaa.bbb.ccc', 3)
        'aaa.bbb.ccc'
        """
        parts = classname.split('.')
        lines = []
        chunk = [parts.pop(0)]
        for part in parts:
            if len('.'.join(chunk + [part])) > width:
                lines.append('.'.join(chunk))
                chunk = [part]
            else:
                chunk.append(part)
        lines.append('.'.join(chunk))
        return '\\n.'.join(lines)

    def _class_info(self, *args, **kwds):
        class_info = super(FoldedInheritanceGraph, self) \
            ._class_info(*args, **kwds)
        width = self._width

        def fold(elem):
            """fold"""
            (nodename, fullname, baselist) = elem
            nodename = self._foldclassname(nodename, width)
            baselist = [self._foldclassname(b, width) for b in baselist]
            return (nodename, fullname, baselist)

        return lmap(fold, class_info)


@magics_class
class HierarchyMagic(Magics):
    """HierarchyMagic"""

    @magic_arguments()
    @argument(
        '-r', '--rankdir', default='TB',
        help='direction of the hierarchy graph (default: %(default)s)'
    )
    @argument(
        '-s', '--size', default='5.0, 12.0',
        help='size of the generated figure (default: %(default)s)',
    )
    @argument(
        '-w', '--name-width', default=40, type=int,
        help='width of each nodes in character length (default: %(default)s)',
    )
    @argument(
        'object', nargs='+',
        help='Class hierarchy of these classes or objects will be drawn',
    )
    @line_magic
    def hierarchy(self, parameter_s=''):
        """Draw hierarchy of a given class."""
        args = parse_argstring(self.hierarchy, parameter_s)
        objects = lmap(self.shell.ev, args.object)
        clslist = lmap(self._object_to_class, objects)
        namelist = lmap(self._class_name, clslist)
        igraph = FoldedInheritanceGraph(
            namelist, '',
            width=args.name_width)
        code = igraph.generate_dot(
            'inheritance_graph',
            graph_attrs={'rankdir': args.rankdir,
                         'size': '"{0}"'.format(args.size)})
        stdout = run_dot(code, format='png')
        display_png(stdout, raw=True)

    @staticmethod
    def _object_to_class(obj):
        if isinstance(obj, type):
            return obj
        elif hasattr(obj, "__class__"):
            return obj.__class__
        else:
            raise ValueError(
                "Given object {0} is not a class or an instance".format(obj))

    @staticmethod
    def _class_name(clas, parts=0):
        """Given a class object, return a fully-qualified name.

        This works for things I've tested in matplotlib so far, but may not be
        completely general.
        """
        module = clas.__module__
        if module == '__builtin__':
            fullname = clas.__name__
        else:
            fullname = '%s.%s' % (module, clas.__name__)
        if parts == 0:
            return fullname
        name_parts = fullname.split('.')
        return '.'.join(name_parts[-parts:])


def load_ipython_extension(ipython):
    """Load the extension in IPython."""
    global _loaded                                                               # pylint: disable=global-statement, invalid-name
    if not _loaded:
        ipython.register_magics(HierarchyMagic)
        ipython.register_magics(GraphvizMagic)
        _loaded = True

_loaded = False                                                                  # pylint: disable=invalid-name
