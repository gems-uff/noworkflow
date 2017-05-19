# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Python 3 Import Hook"""

from importlib.machinery import PathFinder, SourceFileLoader

def finder(metascript):

    class SourceLoader(SourceFileLoader):

        def exec_module(self, module):
            source_path = self.get_filename(module.__name__)
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
                super(SourceLoader, self).exec_module(module)

            if create_module:
                # To get version, the module must execute first
                metascript.deployment.add_module(
                    module.__name__,
                    metascript.deployment.get_version(module),
                    source_path,
                    id_,
                    transformed
                )

    def create_generic_loader(superclass):
        class GenericLoader(superclass):
            def exec_module(self, module):
                create_module = not metascript.bypass_modules
                if create_module:
                    source_path = module.__file__
                    id_ = metascript.definition.create_code_block(
                        None, source_path, "module", True, True
                    )[1]
                    super(GenericLoader, self).exec_module(module)
                    # To get version, the module must execute first
                    metascript.deployment.add_module(
                        module.__name__,
                        metascript.deployment.get_version(module),
                        source_path,
                        id_,
                        False
                    )
                else:
                    super(GenericLoader, self).exec_module(module)
                    
        return GenericLoader

    generic_loaders = {
        SourceFileLoader: SourceLoader,
    }


    class Finder(PathFinder):
        @classmethod
        def find_spec(cls, fullname, path=None, target=None):
            spec = super(Finder, cls).find_spec(fullname, path, target)
            if spec is None:
                return None
            loader = spec.loader
            lcls = type(loader)
            if lcls not in generic_loaders:
                generic_loaders[lcls] = create_generic_loader(lcls)
            loader.__class__ = generic_loaders[lcls]

            return spec
            
    return Finder
