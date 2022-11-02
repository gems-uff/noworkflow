
import os
import sys
import datetime

from ast import PyCF_ONLY_AST
from datetime import datetime
from functools import partial

from IPython.core import compilerop
from IPython.core import interactiveshell

from ..now.collection.metadata import Metascript
from ..now.persistence.models import Tag, Trial, Argument
from ..now.utils.cross_version import cross_compile


class CachingCompilerOverride(compilerop.CachingCompiler):
    """A compiler that caches code compiled from interactive statements."""

    def __init__(self, metascript, *args, **kwargs):
        self.metascript = metascript
        super(CachingCompilerOverride, self).__init__(*args, **kwargs)

    def ast_parse(self, source, filename='<unknown>', symbol='exec'):
        """Parse code to an AST with the current compiler flags active."""
        if self.metascript.jupyter_original:
            return super(CachingCompilerOverride, self).ast_parse(
                source, filename, symbol
            )

        tree = self.metascript.definition.parse(
            "cell", source, filename, symbol
        )[0]
        return cross_compile(
            tree, filename, symbol,
            self.flags | PyCF_ONLY_AST, 1
        )

class OverrideShell(object):
    """Override IPython Shell to use noWorkflow"""

    def __init__(self, shell):
        self.shell = shell

        self.metascript = Metascript().read_jupyter_args()
        self.metascript.namespace = self.shell.user_global_ns
        self.metascript.definition.first = False
        self.override_ipython()
        self.start_noworkflow()

    def override_ipython(self):
        """Override IPython Core to use noWorkflow"""
        self.old_run_cell = self.shell.run_cell

        self.shell.run_cell = self.run_cell
        compilerop.CachingCompiler = partial(
            CachingCompilerOverride, self.metascript
        )
        interactiveshell.CachingCompiler = compilerop.CachingCompiler
        self.shell.compile.__class__ = CachingCompilerOverride
        self.shell.compile.metascript = self.metascript

    def start_noworkflow(self):
        """Start noWorkflow for Jupyter"""
        metascript = self.metascript
        metascript.trial_id = Trial.create(*metascript.create_trial_args())

        metascript.deployment.collect_provenance()
        metascript.execution.configure()

        _, id_ = self.metascript.definition.create_code_block(
            "", os.getcwd(), "notebook", False, False,
        )
        self.activation = metascript.execution.collector.start_script(
            "__main__", id_, None
        )
        evaluation = self.activation.evaluation
        # Never remove main evaluation from store
        evaluation.is_complete = lambda: False
        self.now_save()

    def now_save(self):
        """Save noWorkflow provenance"""
        metascript = self.metascript
        tnow, now = datetime.now(), metascript.execution.collector.get_time()
        self.activation.evaluation.checkpoint = now
        metascript.deployment.store_provenance()
        metascript.definition.store_provenance()
        metascript.execution.collector.store(partial=True, status="cell")

        Trial.fast_update(
            metascript.trial_id,
            metascript.main_id, tnow, "finished")

    def run_cell(self, raw_cell, store_history=False, silent=False,
                 shell_futures=True, cell_id=None):
        """Run a complete IPython cell.
        https://github.com/ipython/ipython/blob/master/
            IPython/core/interactiveshell.py#L2561
        """
        if store_history and not self.metascript.jupyter_original:
            # ToDo: variable dependency
            sys.meta_path.insert(0, self.metascript.definition.finder)
            result = self.old_run_cell(
                raw_cell, store_history=store_history, silent=silent,
                shell_futures=shell_futures, cell_id=cell_id
            )
            sys.meta_path.remove(self.metascript.definition.finder)
            # ToDo: capture exception: result.error_in_exec
            self.now_save()
        else:
            old_original = self.metascript.jupyter_original
            self.metascript.jupyter_original = True
            result = self.old_run_cell(
                raw_cell, store_history=store_history, silent=silent,
                shell_futures=shell_futures, cell_id=cell_id
            )
            self.metascript.jupyter_original = old_original
        return result

    # Interesting functions:
    # run_ast_nodes
    # https://github.com/ipython/ipython/blob/master/
    #   IPython/core/interactiveshell.py#L2740
    
    # run_code
    # https://github.com/ipython/ipython/blob/master/
    #   IPython/core/interactiveshell.py#L2821
    