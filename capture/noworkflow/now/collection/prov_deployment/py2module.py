# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Python 2 ModuleFinder"""

import imp
import sys
import pkgutil



def finder(metascript):
    from imp import PY_SOURCE, PY_COMPILED

    class Finder(object):
        @classmethod
        def find_module(cls, fullname, path=None):
            index = sys.meta_path.index(cls)
            sys.meta_path.pop(index)
            loader = pkgutil.find_loader(fullname)
            sys.meta_path.insert(index, cls)

            if isinstance(loader, pkgutil.ImpLoader):
                loader.__class__ = Loader
                return loader
            return None

    class Loader(pkgutil.ImpLoader):

        def add_module(self, name):
            """PyImport_AddModule and _PyImport_AddModuleObject
            https://github.com/python/cpython/blob/2.7/Python/import.c#L663
            https://github.com/python/cpython/blob/2.7/Python/import.c#L636

            I removed many error handling
            """
            if name in sys.modules:
                return sys.modules[name]

            mod = imp.new_module(name)
            if mod is not None:
                sys.modules[name] = mod
            return mod

        def load_module(self, fullname):
            """Mimics Python's load_module"""
            self._reopen()
            create_module = not metascript.bypass_modules
            required = 2
            required -= int(self.filename.startswith(metascript.dir))
            try:
                module = None
                suffix, mode, type_ = self.etc
                if mode and (not mode.startswith(('r', 'U')) or '+' in mode):
                    raise ValueError('invalid file open mode {!r}'.format(mode))
                elif file is None and type_ in {PY_SOURCE, PY_COMPILED}:
                    raise ValueError(
                        'file object required for import (type code {})'
                        .format(type_)
                    )
                elif type_ == PY_SOURCE and metascript.context >= required:
                    # load_source_module
                    # https://github.com/python/cpython/blob/2.7/Python/import.c#L1054
                    code, id_, transformed = metascript.definition.collect(
                        None, self.filename, "exec"
                    )
                    # PyImport_ExecCodeModuleEx
                    # https://github.com/python/cpython/blob/2.7/Python/import.c#L700
                    module = self.add_module(fullname)
                    if module is not None:
                        if not hasattr(module, "__builtins__"):
                            module.__builtins__ = __builtins__
                        pathname = self.filename
                        if pathname is None:
                            pathname = code.co_filename
                        module.__file__ = pathname
                        try:
                            exec(code, module.__dict__)
                        except:
                            del sys.modules[fullname]
                            raise
                    create_module = True # Override bypass_modules

                if module is None:
                    if create_module:
                        transformed = False
                        id_ = metascript.definition.create_code_block(
                            None, self.filename, "module", False, True
                        )[1]
                    module = imp.load_module(
                        fullname, self.file, self.filename, self.etc
                    )
            finally:
                if self.file:
                    self.file.close()
            if create_module:
                # To get version, the module must execute first
                metascript.deployment.add_module(
                    module.__name__,
                    metascript.deployment.get_version(module),
                    self.filename,
                    id_,
                    transformed
                )
            return module

    return Finder
