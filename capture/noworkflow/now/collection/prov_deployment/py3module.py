# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Python 3 Import Hook"""

from importlib.machinery import PathFinder, SourceFileLoader
from importlib.abc import Loader
from ...persistence import content


class GenericLoader(Loader):

    def __init__(self, metascript, loader):
        self.metascript = metascript
        self.loader = loader

    def __getattr__(self, attr):
        return getattr(self.loader, attr)
    
    def create_module(self, spec):
        return self.loader.create_module(spec)
    
    def load_module(self, fullname):
        return self.loader.load_module(fullname)
    
    def module_repr(self, module):
        return self.loader.module_repr(module)

    def exec_module(self, module):
        with content.use_safe_open():
            create_module = not self.metascript.bypass_modules
            if create_module:
                source_path = module.__file__
                id_ = self.metascript.definition.create_code_block(
                    None, source_path, "module", True, True
                )[1]
                self.loader.exec_module(module)

                # To get version, the module must execute first
                self.metascript.deployment.add_module(
                    module.__name__,
                    self.metascript.deployment.get_version(module),
                    source_path,
                    id_,
                    False
                )
            else:
                self.loader.exec_module(module)


class SourceLoader(SourceFileLoader):

    def __init__(self, metascript, loader):
        self.metascript = metascript
        self.loader = loader

    def __getattr__(self, attr):
        return getattr(self.loader, attr)
    
    def create_module(self, spec):
        return self.loader.create_module(spec)
    
    def load_module(self, fullname):
        return self.loader.load_module(fullname)
    
    def module_repr(self, module):
        return self.loader.module_repr(module)

    def exec_module(self, module):
        with content.use_safe_open():
            source_path = self.get_filename(module.__name__)
            required = 2
            required -= int(source_path.startswith(self.metascript.dir))
            create_module = not self.metascript.bypass_modules

            if self.metascript.context >= required:
                code, id_, transformed = self.metascript.definition.collect(
                    None, source_path, "exec"
                )
                exec(code, module.__dict__)
                create_module = True # Override bypass_modules
            else:
                if create_module:
                    transformed = False
                    id_ = self.metascript.definition.create_code_block(
                        None, source_path, "module", False, True
                    )[1]
                self.loader.exec_module(module)

            if create_module:
                # To get version, the module must execute first
                self.metascript.deployment.add_module(
                    module.__name__,
                    self.metascript.deployment.get_version(module),
                    source_path,
                    id_,
                    transformed
                )


def finder(metascript):
    loaders = {}

    class Finder(PathFinder):
        @classmethod
        def find_spec(cls, fullname, path=None, target=None):
            with content.use_safe_open():
                spec = super(Finder, cls).find_spec(fullname, path, target)
                if spec is None:
                    return None
                loader = spec.loader
                if id(loader) not in loaders:
                    if type(loader) == SourceFileLoader: 
                        # Playing safe here: instead of using isinstance, I'm checking the actual type
                        # I don't know if the noworkflow loader supports any subtype of SourceFileLoader
                        loaders[id(loader)] = SourceLoader(metascript, loader)
                    else:
                        loaders[id(loader)] = GenericLoader(metascript, loader)
                spec.loader = loaders[id(loader)]

                return spec
            
    return Finder
