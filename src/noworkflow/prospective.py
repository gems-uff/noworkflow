# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import persistence
import sys
import os.path
import pkg_resources
import modulefinder
from utils import write
import utils
import platform
import importlib

def clean(path):
    'Use package name instead of __init__.py'
    if os.path.basename(path) == '__init__.py':
        return os.path.dirname(path)
    else:
        return path
    
def get_module_dependencies(path):
    'returns a set of module dependencies in the form: (name, version, path, code hash)'
    write('finding module dependencies')
    finder = modulefinder.ModuleFinder()
    finder.run_script(path)
    
    write('collecting provenance from {} dependencies'.format(len(finder.modules)))
    dependencies = []
    for name, module in finder.modules.iteritems():
        if name != '__main__':
            version = get_version(name)
            path = module.__file__
            if path == None:
                code_hash = None
            else:
                with open(path, 'rb') as f:
                    code_hash = persistence.put(f.read())
            dependencies.append((name, version, path, code_hash))
    return sorted(dependencies)
                 
def get_version(module_name):       
    # Check built-in module
    if module_name in sys.builtin_module_names:
        return platform.python_version()
     
    # Check package declared module version
    try:
        return pkg_resources.get_distribution(module_name).version 
    except: 
        pass
    
    # Check explicitly declared module version
    try:    
        module = importlib.import_module(module_name)
        for attr in ['__version__', 'version', '__VERSION__', 'VERSION']:
            try:
                version = getattr(module, attr)
                if isinstance(version, basestring):
                    return version
            except:
                pass
    except:
        pass
         
    # If no other option work, return None    
    return None

def collect_provenance(script_path, list_modules):

    modules_dep = get_module_dependencies(script_path)    
    if (list_modules):
        utils.list_dependencies(modules_dep)
    
    

    