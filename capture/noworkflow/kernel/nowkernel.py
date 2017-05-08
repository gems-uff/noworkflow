import re
from ipykernel.ipkernel import IPythonKernel
from .shell import OverrideShell


class NowKernel(IPythonKernel):

    def __init__(self, **kwargs):
        super(NowKernel, self).__init__(**kwargs)
        OverrideShell(self.shell)

    def do_execute(self, code, silent, store_history=True,
                   user_expressions=None, allow_stdin=False):
        reply_content = super(NowKernel, self).do_execute(
            code, silent, store_history=store_history,
            user_expressions=user_expressions, allow_stdin=allow_stdin)
        return reply_content
