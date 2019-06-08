# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Bundle"""


from ..models import CodeBlock
from .. import content

from .base import BaseLW, define_attrs


class BundleLW(BaseLW):
    """Bundle lightweight object"""
    def __init__(self):
        self.trials=[]
        self.activations=[]
        self.arguments=[]
        self.codeBlocks=[]
        self.codeComponents=[]
        self.compositions=[]
        self.dependencies=[]
        self.environmentAttrs=[]
        self.evaluations=[]
        self.fileAccesses=[]
        self.members=[]
        self.modules=[]
        
    def __json__(self):
        return {
            'trials':   [x.__json__() for x in self.trials],
            'activations': [x.__json__() for x in self.activations],
            'arguments': [x.__json__() for x in self.arguments],
            'codeBlocks': [x.__json__() for x in self.codeBlocks],
            'codeComponents': [x.__json__() for x in self.codeComponents],
            'compositions': [x.__json__() for x in self.compositions],
            'dependencies': [x.__json__() for x in self.dependencies],
            'environmentAttrs': [x.__json__() for x in self.environmentAttrs],
            'evaluations': [x.__json__() for x in self.evaluations],
            'fileAccesses': [x.__json__() for x in self.fileAccesses],
            'members': [x.__json__() for x in self.members],
            'modules': [x.__json__() for x in self.modules]
        }
  
