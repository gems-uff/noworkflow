# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Python 3 Import Hook"""

import inspect
from functools import wraps
from importlib.machinery import PathFinder, SourceFileLoader
from importlib.abc import Loader
from ...persistence import content


def proxy(loader, name):
    attr = getattr(loader, name)
    if callable(attr):
        @wraps(attr)
        def wrapper(self, *args, **kwargs):
            return getattr(loader, name)(*args, **kwargs)
        return wrapper
    
    @property
    def attribute(self):
        return getattr(loader, name)
    
    @attribute.setter
    def attribute(self, new_value):
        setattr(loader, name, new_value)

    @attribute.deleter
    def attribute(self):
        delattr(loader, name)
    return attribute
    

def create_generic_loader(metascript, loader):

    if hasattr(loader, 'exec_module'):  # new module format
        class GenericLoader(type(loader)):

            def __init__(self):
                pass

            def __getattr__(self, attr):
                return getattr(loader, attr)
            
            def create_module(self, spec):
                return loader.create_module(spec)

            def exec_module(self, module):
                with content.use_safe_open():
                    create_module = not metascript.bypass_modules
                    if create_module:
                        source_path = module.__file__
                        id_ = metascript.definition.create_code_block(
                            None, source_path, "module", True, True
                        )[1]
                        loader.exec_module(module)

                        # To get version, the module must execute first
                        metascript.deployment.add_module(
                            module.__name__,
                            metascript.deployment.get_version(module),
                            source_path,
                            id_,
                            False
                        )
                    else:
                        loader.exec_module(module)
    else:
        class GenericLoader(type(loader)):

            def __init__(self):
                pass

            def __getattr__(self, attr):
                return getattr(loader, attr)
            
            def load_module(self, fullname):
                with content.use_safe_open():
                    module = loader.load_module(fullname)
                    create_module = not metascript.bypass_modules
                    if create_module:
                        source_path = module.__file__
                        id_ = metascript.definition.create_code_block(
                            inspect.getsource(module), source_path, "module", False, False
                        )[1]
                        metascript.deployment.add_module(
                            module.__name__,
                            metascript.deployment.get_version(module),
                            source_path,
                            id_,
                            False
                        )
                    return module

    instance = GenericLoader()
    return instance


def create_source_loader(metascript, loader):

    class SourceLoader(type(loader)):

        def __init__(self):
            pass

        def __getattr__(self, attr):
            return getattr(loader, attr)

        def create_module(self, spec):
            return loader.create_module(spec)

        def exec_module(self, module):
            with content.use_safe_open():
                source_path = loader.get_filename(module.__name__)
                required = 2
                required -= int(source_path.startswith(metascript.dir))
                create_module = not metascript.bypass_modules

                if metascript.context >= required:
                    code, id_, transformed = metascript.definition.collect(
                        None, source_path, "exec"
                    )
                    exec(code, module.__dict__)
                    create_module = True # Override bypass_modules
                else:
                    if create_module:
                        transformed = False
                        id_ = metascript.definition.create_code_block(
                            None, source_path, "module", False, True
                        )[1]
                    loader.exec_module(module)

                if create_module:
                    # To get version, the module must execute first
                    metascript.deployment.add_module(
                        module.__name__,
                        metascript.deployment.get_version(module),
                        source_path,
                        id_,
                        transformed
                    )

    instance = SourceLoader()
    return instance

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
                        loaders[id(loader)] = create_source_loader(metascript, loader)
                    else:
                        loaders[id(loader)] = create_generic_loader(metascript, loader)
                spec.loader = loaders[id(loader)]

                return spec
            
    return Finder
