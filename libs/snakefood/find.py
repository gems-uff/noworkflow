"""
Parsing and finding routines.
This could be considered the core of snakefood, and where all the complexity lives.
"""
# This file is part of the Snakefood open source package.
# See http://furius.ca/snakefood/ for licensing details.

import sys, os, logging
import compiler
from compiler.visitor import ASTVisitor
from compiler.ast import Discard, Const, AssName, List, Tuple
from compiler.consts import OP_ASSIGN
from os.path import *

from snakefood.roots import find_package_root
from snakefood.local import filter_unused_imports

__all__ = ('find_dependencies', 'find_imports',
           'parse_python_source',
           'ImportVisitor', 'get_local_names', 'check_duplicate_imports',
           'ERROR_IMPORT', 'ERROR_SYMBOL', 'ERROR_UNUSED')


ERROR_IMPORT = "    Line %d: Could not import module '%s'"
ERROR_SYMBOL = "    Line %d: Symbol is not a module: '%s'"
ERROR_UNUSED = "    Line %d: Ignored unused import: '%s'"
ERROR_SOURCE = "       %s"
WARNING_OPTIONAL = "    Line %d: Pragma suppressing import '%s'"

def find_dependencies(fn, verbose, process_pragmas, ignore_unused=False):
    "Returns a list of the files 'fn' depends on."
    file_errors = []

    ast, _ = parse_python_source(fn)
    if ast is None:
        return [], file_errors
    found_imports = get_ast_imports(ast)
    if found_imports is None:
        return [], file_errors

    # Filter out the unused imports if requested.
    if ignore_unused:
        found_imports, unused_imports = filter_unused_imports(ast, found_imports)
        for modname, rname, lname, lineno, level, pragma in unused_imports:
            file_errors.append((ERROR_UNUSED, lname))

    output_code = (verbose >= 2)
    source_lines = None
    if output_code:
        source_lines = open(fn, 'rU').read().splitlines()

    files = []
    assert not isdir(fn)
    dn = dirname(fn)
    seenset = set()
    for x in found_imports:
        mod, rname, lname, lineno, level, pragma = x
        if process_pragmas and pragma == 'OPTIONAL':
            if rname is None:
                msg = WARNING_OPTIONAL % (lineno, mod)
            else:
                msg = '%s.%s' % (mod, rname)
            logging.warning(msg)
            continue

        sig = (mod, rname)
        if sig in seenset:
            continue
        seenset.add(sig)

        modfile, errors = find_dotted_module(mod, rname, dn, level)
        if errors:
            file_errors.extend(errors)
            for err, name in errors:
                if err is ERROR_IMPORT:
                    efun = logging.warning
                else:
                    efun = logging.debug
                efun(err % (lineno, name))
                if output_code:
                    efun(ERROR_SOURCE % source_lines[lineno-1].rstrip())

        if modfile is None:
            continue
        files.append(realpath(modfile))

    return files, file_errors

def find_imports(fn, verbose, ignores):
    "Yields a list of the module names the file 'fn' depends on."

    ast, _ = parse_python_source(fn)
    if ast is None:
        raise StopIteration

    found_imports = get_ast_imports(ast)
    if found_imports is None:
        raise StopIteration

    dn = dirname(fn)

    packroot = None
    for modname, rname, lname, lineno, _, _ in found_imports:
        islocal = False
        names = modname.split('.')
        if find_dotted(names, dn):
            # This is a local import, we need to find the root in order to
            # compute the absolute module name.
            if packroot is None:
                packroot = find_package_root(fn, ignores)
                if not packroot:
                    logging.warning(
                        "%d: Could not find package root for local import '%s' from '%s'." %
                        (lineno, modname, fn))
                    continue

            reldir = dirname(fn)[len(packroot)+1:]

            modname = '%s.%s' % (reldir.replace(os.sep, '.'), modname)
            islocal = True

        if rname is not None:
            modname = '%s.%s' % (modname, rname)
        yield (modname, lineno, islocal)


class ImportVisitor(object):
    """AST visitor for grabbing the import statements.

    This visitor produces a list of

       (module-name, remote-name, local-name, line-no, pragma)

    * remote-name is the name off the symbol in the imported module.
    * local-name is the name of the object given in the importing module.
    """
    def __init__(self):
        self.modules = []
        self.recent = []

    def visitImport(self, node):
        self.accept_imports()
        self.recent.extend((x[0], None, x[1] or x[0], node.lineno, 0)
                           for x in node.names)

    def visitFrom(self, node):
        self.accept_imports()
        modname = node.modname
        if modname == '__future__':
            return # Ignore these.
        for name, as_ in node.names:
            if name == '*':
                # We really don't know...
                mod = (modname, None, None, node.lineno, node.level)
            else:
                mod = (modname, name, as_ or name, node.lineno, node.level)
            self.recent.append(mod)

    # For package initialization files, try to fetch the __all__ list, which
    # implies an implicit import if the package is being imported via
    # from-import; from the documentation:
    #
    #  The import statement uses the following convention: if a package's
    #  __init__.py code defines a list named __all__, it is taken to be the list
    #  of module names that should be imported when from package import * is
    #  encountered. It is up to the package author to keep this list up-to-date
    #  when a new version of the package is released. Package authors may also
    #  decide not to support it, if they don't see a use for importing * from
    #  their package.
    def visitAssign(self, node):
        lhs = node.nodes
        if (len(lhs) == 1 and
            isinstance(lhs[0], AssName) and
            lhs[0].name == '__all__' and
            lhs[0].flags == OP_ASSIGN):

            rhs = node.expr
            if isinstance(rhs, (List, Tuple)):
                for namenode in rhs:
                    # Note: maybe we should handle the case of non-consts.
                    if isinstance(namenode, Const):
                        modname = namenode.value
                        mod = (modname, None, modname, node.lineno, 0)#node.level
                        self.recent.append(mod)

    def default(self, node):
        pragma = None
        if self.recent:
            if isinstance(node, Discard):
                children = node.getChildren()
                if len(children) == 1 and isinstance(children[0], Const):
                    const_node = children[0]
                    pragma = const_node.value

        self.accept_imports(pragma)

    def accept_imports(self, pragma=None):
        self.modules.extend((m, r, l, n, lvl, pragma)
                            for (m, r, l, n, lvl) in self.recent)
        self.recent = []

    def finalize(self):
        self.accept_imports()
        return self.modules


def check_duplicate_imports(found_imports):
    """
    Heuristically check for duplicate imports, and return two lists:
    a list of the unique imports and a list of the duplicates.
    """
    uniq, dups = [], []
    simp = set()
    for x in found_imports:
        modname, rname, lname, lineno, _, pragma = x
        if rname is not None:
            key = modname + '.' + rname
        else:
            key = modname
        if key in simp:
            dups.append(x)
        else:
            uniq.append(x)
            simp.add(key)
    return uniq, dups


def get_local_names(found_imports):
    """
    Convert the results of running the ImportVisitor into a simple list of local
    names.
    """
    return [(lname, no)
            for modname, rname, lname, no, _, pragma in found_imports
            if lname is not None]


class ImportWalker(ASTVisitor):
    "AST walker that we use to dispatch to a default method on the visitor."

    def __init__(self, visitor):
        ASTVisitor.__init__(self)
        self._visitor = visitor

    def default(self, node, *args):
        self._visitor.default(node)
        ASTVisitor.default(self, node, *args)


def parse_python_source(fn):
    """Parse the file 'fn' and return two things:

    1. The AST tree.
    2. A list of lines of the source line (typically used for verbose error
       messages).

    If the file has a syntax error in it, the first argument will be None.
    """
    # Read the file's contents to return it.
    # Note: we make sure to use universal newlines.
    try:
        contents = open(fn, 'rU').read()
        lines = contents.splitlines()
    except (IOError, OSError), e:
        logging.error("Could not read file '%s'." % fn)
        return None, None

    # Convert the file to an AST.
    try:
        ast = compiler.parse(contents)
    except SyntaxError, e:
        err = '%s:%s: %s' % (fn, e.lineno or '--', e.msg)
        logging.error("Error processing file '%s':\n%s" %
                      (fn, err))
        return None, lines

    return ast, lines

def get_ast_imports(ast):
    """
    Given an AST, return a list of module tuples for the imports found, in the
    form:
        (modname, remote-name, local-name, lineno, pragma)
    """
    assert ast is not None
    vis = ImportVisitor()
    compiler.walk(ast, vis, ImportWalker(vis))
    found_imports = vis.finalize()
    return found_imports


# **WARNING** This is where all the evil lies.  Risk and peril.  Watch out.

if sys.platform == "win32":
    #  Location of  python lib on win32
    libpath = join(sys.prefix, 'lib')
else:
    libpath = join(sys.prefix, 'lib', 'python%d.%d' % sys.version_info[:2])


exceptions = ('os.path',)
builtin_module_names = sys.builtin_module_names + exceptions

module_cache = {}

def find_dotted_module(modname, rname, parentdir, level):
    """
    A version of find_module that supports dotted module names (packages).  This
    function returns the filename of the module if found, otherwise returns
    None.

    If 'rname' is not None, it first attempts to import 'modname.rname', and if it
    fails, it must therefore not be a module, so we look up 'modname' and return
    that instead.

    'parentdir' is the directory of the file that attempts to do the import.  We
    attempt to do a local import there first.

    'level' is the level of a relative import (i.e. the number of leading dots).
    If 0, the import is absolute.
    """
    # Check for builtins.
    if modname in builtin_module_names:
        return join(libpath, modname), None

    errors = []
    names = modname.split('.')
    for i in range(level - 1):
        parentdir = dirname(parentdir)
    # Try relative import, then global imports.
    fn = find_dotted(names, parentdir)
    if not fn:
        try:
            fn = module_cache[modname]
        except KeyError:
            fn = find_dotted(names)
            module_cache[modname] = fn

        if not fn:
            errors.append((ERROR_IMPORT, modname))
            return None, errors

    # If this is a from-form, try the target symbol as a module.
    if rname:
        fn2 = find_dotted([rname], dirname(fn))
        if fn2:
            fn = fn2
        else:
            errors.append((ERROR_SYMBOL, '.'.join((modname, rname))))
            # Pass-thru and return the filename of the parent, which was found.

    return fn, errors

try:
    from imp import ImpImporter
except ImportError:
    try:
        from pkgutil import ImpImporter
    except ImportError:
        from snakefood.fallback.pkgutil import ImpImporter

def find_dotted(names, parentdir=None):
    """
    Dotted import.  'names' is a list of path components, 'parentdir' is the
    parent directory.
    """
    filename = None
    for name in names:
        mod = ImpImporter(parentdir).find_module(name)
        if not mod:
            break
        filename = mod.get_filename()
        if not filename:
            break
        parentdir = dirname(filename)
    else:
        return filename

