
class OverrideShell(object):
    """Override IPython Shell to use noWorkflow"""

    def __init__(self, shell, collect_environment=True):
        self.shell = shell
        self.collect_environment = collect_environment
        self.old_run_cell = self.shell.run_cell
        self.old_run_ast_nodes = self.shell.run_ast_nodes

        self.shell.run_cell = self.run_cell
        self.shell.run_ast_nodes = self.run_ast_nodes


    def run_cell(self, raw_cell, store_history=False, silent=False,
                 shell_futures=True):
        """Run a complete IPython cell."""
        print(raw_cell)
        result = self.old_run_cell(
            raw_cell, store_history=store_history, silent=silent,
            shell_futures=shell_futures
        )

        return result

    def run_ast_nodes(self, nodelist, cell_name, interactivity='last_expr',
                      compiler=compile, result=None):
        """Run a sequence of AST nodes. The execution mode depends on the
        interactivity parameter."""
        print(nodelist, cell_name)
        return self.old_run_ast_nodes(
            nodelist, cell_name, interactivity=interactivity,
            compiler=compiler, result=result
        )