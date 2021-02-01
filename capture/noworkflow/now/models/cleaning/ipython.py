# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""""This file has functions for generating a history notebook from a living IPython Kernel (without noWorkflow)"""

def getname():
    """Get name from Jupyter Notebook - Does not work on Jupyter Lab"""
    # ToDo: use the following code? https://github.com/jupyter/notebook/issues/1000
    ip = get_ipython()
    display(Javascript('IPython.notebook.kernel.execute("__notebook_name__ = " + "\'"+IPython.notebook.notebook_name+"\'");'))
    for i in range(50):
        name = ip.user_global_ns.get("__notebook_name__", ip.user_ns.get("__notebook_name__"))
        if name is not None:
            return name
        time.sleep(.1)


def create_history(filename=None, name=None, create_header=True, write=True):
    """Create history notebook from history_manager"""
    filename = filename or 'History-{}'.format(getname())

    nb = nbf.v4.new_notebook()
 
    header = filename
    if name is not None:
        header = "History of {}".format(name)

    if create_header:
        cells = [nbf.v4.new_markdown_cell((
            '# {}\n'
            'Created at {}'
        ).format(header, datetime.now()))]
    else:
        cells = []
    
    ip = get_ipython()
    for session, lineno, inline in ip.history_manager.get_range(raw=True, output=True):
        if '<IGNORE CELL>' in inline[0].upper():
            continue
        outputs = []
        if inline[1] is not None:
            outputs = [nbf.v4.new_output(
                output_type=u'execute_result',
                data={'text/plain': inline[1],},
                execution_count=lineno
            )]
        cells.append(nbf.v4.new_code_cell(
            inline[0],
            execution_count=lineno,
            outputs=outputs
        ))
    nb['cells'] = cells
    if write:
        with open(filename, 'w') as f:
            nbf.write(nb, f)
            print('Created history notebook: {}'.format(filename))
    return nb