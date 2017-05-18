
import os
import sys

from ..now.collection.metadata import Metascript
from ..now.persistence.models import Tag, Trial, Argument


class OverrideShell(object):
    """Override IPython Shell to use noWorkflow"""

    def __init__(self, shell, collect_environment=True):
        self.shell = shell
        
        self.metascript = metascript = Metascript().read_jupyter_args()
        self.metascript.namespace = self.shell.user_global_ns
        self.collect_environment = collect_environment
        self.old_run_cell = self.shell.run_cell

        self.shell.run_cell = self.run_cell
        metascript.trial_id = Trial.create(*metascript.create_trial_args())

        metascript.deployment.collect_provenance()
        self.metascript.execution.configure()


    def run_cell(self, raw_cell, store_history=False, silent=False,
                 shell_futures=True):
        """Run a complete IPython cell.
        https://github.com/ipython/ipython/blob/master/
            IPython/core/interactiveshell.py#L2561
        """
        # ToDo: collect code_block
        #   We probably want to use self.shell.input_transformer_manager.transform_cell(raw_cell)
        # ToDo: override IPython.core.compilerop.CachingCompiler.parse_ast to use pyposast
        #   We can use the parameter "filename" to collect the code block name
        #   and the parameter code as the source code
        # ToDo: add RewriteAST to shell.ast_transformers

        #sys.meta_path.insert(0, metascript.definition.finder)
        result = self.old_run_cell(
            raw_cell, store_history=store_history, silent=silent,
            shell_futures=shell_futures
        )
        #sys.meta_path.remove(metascript.definition.finder)
        # ToDo: capture exception: result.error_in_exec
        self.metascript.execution.collector.store(partial=True, status="cell")
        return result

    # Interesting functions:
    # run_ast_nodes
    # https://github.com/ipython/ipython/blob/master/
    #   IPython/core/interactiveshell.py#L2740
    
    # run_code
    # https://github.com/ipython/ipython/blob/master/
    #   IPython/core/interactiveshell.py#L2821
    