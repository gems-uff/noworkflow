# Copyright (c) Universidade Federal Fluminense (UFF)
# Copyright (c) NYU Tandon School of Engineering
# This file uses part of noWorkflow 1 and 2. Please, check the LICENSE file the repository:
#   https://github.com/gems-uff/noworkflow
"""Definition provenance collector

Uses noWorkflow to collect definition provenance
"""
import sys
import argparse
import modulefinder
import inspect
from pathlib import Path
from noworkflow.now.cmd.cmd_run import ScriptArgs
from noworkflow.now.collection.metadata import Metascript, MAIN, PACKAGE, ALL
from noworkflow.now.persistence.models.trial import Trial
from noworkflow.now.persistence import content

from noworkflow.now.utils import io


def collect(metascript):
    """Collect only definition provenance"""
    try:
        # noworkflow2.now.cmd.cmd_run:run
        metascript.trial_id = Trial.create(*metascript.create_trial_args())

        io.print_msg("collection definition provenance")

        # Custom
        scripts = []
        if metascript.context == MAIN:
            scripts.append((metascript.code, metascript.path))
        elif metascript.context == PACKAGE:
            parentpath = Path(metascript.path).parent 
            for code, path in modules_with_source(metascript):
                try:
                    Path(path).relative_to(parentpath)
                    scripts.append((code, path))          
                except ValueError: # expected for modules that do not belong to the same package
                    pass
        elif metascript.context == ALL:
            for code, path in modules_with_source(metascript):
                scripts.append((code, path))                

        for code, path in scripts:
            # noworkflow2.now.collection.prov_execution.execution:Execution.collect_provenance
            try:
                metascript.definition.compile(
                    code, path, "exec"
                )
            except:
                # Bug in noWorkflow/pyposast collection
                print(path)
    finally:
        io.print_msg("storing provenance")
        # noworkflow2.now.cmd.cmd_run:run
        for key, value in metascript.code_components_store.store.items():
            print(key, value)
        #metascript.definition.store_provenance()
        message = metascript.message or "Trial {}".format(metascript.trial_id)
        content.commit_content(message)
        io.print_msg(message)

def find_modules(metascript):
    """Use modulefinder to find modules"""
    # noworkflow1.now.collection.prov_deployment.deployment:Deployment._find_modules
    excludes = set()
    last_name = "A" * 255  # invalid name
    max_atemps = 1000
    for i in range(max_atemps):
        try:
            finder = modulefinder.ModuleFinder(excludes=excludes)
            finder.run_script(metascript.path)
            return finder.modules
        except SyntaxError as exc:
            name = exc.filename.split("site-packages/")[-1]
            name = name.replace(os.sep, ".")
            name = name[:name.rfind(".")]
            if last_name in name:
                last_name = last_name[last_name.find(".") + 1:]
            else:
                last_name = name
            excludes.add(last_name)
            io.print_msg("   skip module due syntax error: {} ({}/{})"
                         .format(last_name, i + 1, max_atemps))
    return {}

def get_version(module_name):                                         # pylint: disable=no-self-use
    """Get module version"""
    import platform
    import pkg_resources
    import importlib
    # Check built-in module
    if module_name in sys.builtin_module_names:
        return platform.python_version()

    # Check package declared module version
    try:
        # ToDo: This is slow! Is there any alternative?
        return pkg_resources.get_distribution(module_name).version
    except Exception:                                                        # pylint: disable=broad-except
        pass

    # Check explicitly declared module version
    try:
        module = importlib.import_module(module_name)
        for attr in ["__version__", "version", "__VERSION__", "VERSION"]:
            try:
                module_version = getattr(module, attr)
                if isinstance(module_version, str):
                    return str(module_version)
                if isinstance(module_version, tuple):
                    return ".".join(map(str, module_version))

            except AttributeError:
                pass
    except Exception:                                                        # pylint: disable=broad-except
        pass

    # If no other option work, return None
    return None

def modules_with_source(metascript):
    """Collect source code from imported modules recursively"""
    for name, module in find_modules(metascript).items():
        #print(module.__file__, get_version(name))
        if module.__file__ and module.__code__:
            try:
                code = inspect.getsource(module.__code__)
                yield (code, module.__file__)
            except OSError:  # expected when the code does not exists (.pyc, .so, ...)
                pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create trial with definition provenance')
    parser.add_argument("script", nargs="*", action=ScriptArgs,
                        help="Python script to be executed")
    parser.add_argument("-c", "--context", choices=["main", "package", "all"],
                        default="main",
                        help="functions subject to depth computation when capturing "
                             "activations (default: main)")
    parser.add_argument("--name", type=str, help="R|set script name.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="increase output verbosity")
    parser.add_argument("--content-engine", type=str,
                        help="set the content database engine")
    parser.add_argument("--dir", type=str,
                        help="set project path. The noworkflow database folder will "
                             "be created in this path. Default to script directory")

    # Internal
    parser.add_argument("--create_last", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--meta", action="store_true", help=argparse.SUPPRESS)
    # Ignored
    parser.add_argument("-b", "--bypass-modules", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("-d", "--depth", type=int, default=sys.getrecursionlimit(), help=argparse.SUPPRESS)
    parser.add_argument("-s", "--save-frequency", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("-S", "--call-storage-frequency", type=int, default=10000, help=argparse.SUPPRESS)
    parser.add_argument("--message", type=str, default=None, help=argparse.SUPPRESS)

    args, _ = parser.parse_known_args()
    io.verbose = args.verbose
    io.print_msg("creating metascript")

    # noworkflow2.now.cmd.cmd_run:Run.execute
    metascript = Metascript().read_cmd_args(args)
    import __main__
    metascript.namespace = __main__.__dict__
    metascript.clear_sys()
    #metascript.clear_namespace()

    collect(metascript)
    
    