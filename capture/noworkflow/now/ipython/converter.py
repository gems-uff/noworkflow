# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Convert code the Jupyter Notebook files"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import json

def nbconvert(code):
    """Create Jupyter Notebook code


    Return dict in ipynb format
    Arguments:
    code -- code string separated by \\n
    """
    cells = []
    for cell in code.split("\n# <codecell>\n"):
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {
                "collapsed": True,
            },
            "outputs": [],
            "source": [cell]
        })
    result = {
        "cells": cells,
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 2",
                "language": "python",
                "name": "python2"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 2
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython2",
                "version": "2.7.6"
            }
        }
    }
    return result


def create_ipynb(name, code):
    """Create ipynb file
    Store file with ipynb format


    Arguments:
    name -- filename
    code -- code string separated by \\n
    """
    inb = nbconvert(code)
    with open(name, "w") as ipynb:
        json.dump(inb, ipynb)
