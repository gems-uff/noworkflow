# Copyright (c) 2018 Universidade Federal Fluminense (UFF)
# Copyright (c) 2018 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""IPython extensions to display dot files"""

import subprocess
import platform
import errno
import sys
import os
import tempfile
from collections import OrderedDict

LOADED = False

MIME_MAP = {
    # png
    "png": "image/png",
    "image/png": "image/png",
    # svg
    "svg": "image/svg+xml",
    "image/svg+xml": "image/svg+xml",
    # pdf
    "dot.pdf": "application/pdf",
    "ink.pdf": "application/pdf",
    "pdf": "application/pdf",
    "application/pdf": "application/pdf",
    # txt
    "txt": "text/plain",
    "text/plain": "text/plain",
    # dot
    "dot": "text/vnd.graphviz",
    "text/vnd.graphviz": "text/vnd.graphviz",
}

STARTUPINFO = None

if platform.system().lower() == 'windows':
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    STARTUPINFO.wShowWindow = subprocess.SW_HIDE


def run_dot(dot, ext="svg", prog="dot", extra=None):
    """Run graphviz for `dot` text and returns its output"""
    extra = extra or []
    args = [prog] + extra + ['-T', ext]
    process = subprocess.Popen(
        args, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
        startupinfo=STARTUPINFO
    )
    try:
        tout, terr = process.communicate(dot.encode('utf-8'))
    except (OSError, IOError) as err:
        if err.errno != errno.ENOENT:
            raise
        # Get error message
        tout, terr = process.stdout.read(), process.stderr.read()
        process.wait()
    process.terminate()
    if process.returncode != 0:
        if terr is None:
            terr = b"Incomplete input"
        raise RuntimeError(
            'dot exited with error code {0}\n{1}'
            .format(process.returncode, terr.decode('utf-8'))
        )
    return tout


def dot_to_pdf(dot, prog, extra, force_ink=False):
    """Convert dot to pdf.
    First try to use graphviz (dot -> svg) and inkscape (svg -> pdf).
    If it fails, use graphviz (dot -> pdf)"""

    try:
        svg_text = run_dot(dot, "svg", prog, extra)
        if svg_text is None:
            raise RuntimeError("Invalid svg")
    except (OSError, IOError, RuntimeError):
        if force_ink:
            raise
        return run_dot(dot, "pdf", prog, extra)

    fd1, filename1 = tempfile.mkstemp()
    fd2, filename2 = tempfile.mkstemp()
    try:
        os.write(fd1, svg_text)
        os.close(fd1)
        os.close(fd2)
        try:
            # Assumes that graphviz already generated the svg
            ink_args = ["inkscape", "-D", "-z", "--file={}".format(filename1),
                        "--export-pdf={}".format(filename2)]
            subprocess.check_call(ink_args, startupinfo=STARTUPINFO)
        except OSError as e:
            if e.errno == errno.ENOENT:
                if force_ink:
                    raise
                return run_dot(dot, "pdf", prog, extra)
        with open(filename2, "rb") as file:
            return file.read()
    finally:
        os.remove(filename1)
        os.remove(filename2)


class DotDisplay(object):
    """Display class for Dot text"""

    def __init__(self, dot, format="png", prog="dot", extra=None):
        self.extensions = format
        if isinstance(format, str):
            self.extensions = [format]
        self.dot = dot
        self.prog = prog
        self.extra = extra

    def save(self, *files, formats=None):
        """Save dot file into specific format"""
        extensions = self.extensions
        formats = formats or [x.split('.')[-1] for x in files]
        self.extensions = set(formats)
        result = self.display_result()
        self.extensions = extensions
        for filename, format in zip(files, formats):
            mime = MIME_MAP.get(format.lower())
            if not mime:
                print("Invalid format {} for {}".format(format, filename))
                continue
            mode = "w"
            if mime in {"image/png", "application/pdf"}:
                mode = "wb"
            with open(filename, mode) as file:
                file.write(result[mime])

    def display_result(self):
        """Create display dictionary"""
        dot, prog, extra = self.dot, self.prog, self.extra
        result = OrderedDict()
        try:
            for ext in self.extensions:
                ext = ext.lower()
                mime = MIME_MAP.get(ext)
                if mime == "image/png":
                    result[mime] = run_dot(dot, "png", prog, extra)
                if mime == "image/svg+xml":
                    svg_text = run_dot(dot, "svg", prog, extra)
                    if svg_text is not None:
                        result[mime] = svg_text.decode("utf-8")
                if mime == "application/pdf":
                    if ext != "dot.pdf":
                        force_ink = ext == "ink.pdf"
                        result[mime] = dot_to_pdf(dot, prog, extra, force_ink)
                    else:
                        result[mime] = run_dot(dot, "pdf", prog, extra)
                if mime == "text/plain":
                    result[mime] = dot
                if mime == "text/vnd.graphviz":
                    result[mime] = dot

        except (OSError, IOError, RuntimeError) as err:
            sys.stderr.write("{}\n".format(err))
        if not result:
            sys.stderr.write("Fallback to dot text\n")
            result["text/plain"] = dot
        return result

    def _ipython_display_(self):
        from IPython.display import display
        result = self.display_result()
        display(result, raw=True)


def load_ipython_extension(ipython):
    """Load the extension in IPython."""
    from IPython import get_ipython
    from IPython.core.magic import Magics, magics_class, cell_magic
    from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring
    from IPython.utils.text import DollarFormatter

    @magics_class
    class DotMagic(Magics):
        """Dot Magic.
        Add cell magic %%dot to display dot graph in Jupyter"""

        @magic_arguments()
        @argument('-p', '--prog', default="dot", type=str, help="Command for rendering (dot, neato, ...)")
        @argument('-f', '--format', default="png", help="Output format")
        @argument('-s', '--save', default=[], nargs="+", help="Save files")
        @argument('extra', default=[], nargs='*', help="Extra options for graphviz")
        @cell_magic
        def dot(self, line, cell):
            """%%dot magic"""
            # Remove comment on %%provn line
            pos = line.find("#")
            line = line[:pos if pos != -1 else None]

            formatter = DollarFormatter()
            line = formatter.vformat(
                line, args=[], kwargs=self.shell.user_ns.copy()
            )
            args = parse_argstring(self.dot, line)
            dot_display = DotDisplay(cell, args.format, args.prog, args.extra)

            if args.save:
                dot_display.save(*args.save)
            return dot_display
        
    global LOADED                                                               # pylint: disable=global-statement, invalid-name
    ipython = get_ipython()
    if not LOADED and ipython:
        ipython.register_magics(DotMagic)
        LOADED = True
