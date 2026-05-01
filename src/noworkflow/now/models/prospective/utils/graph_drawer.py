# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Graph Drawer"""

class GraphDrawer:
    def __init__(self, provenance_graph):
        self.graphProv = provenance_graph
        self.color = dict(nodes='#85CBC0',
                          assign='#976BAA',
                          notes='#808080',
                          times='#FFDE6A')
        self.shape = dict(loops='ellipse',
                          note='note',
                          condition='diamond',
                          times='cds')
        self.edges = dict(back='dashed',
                          none='none')

    def calls(self, hashing, text):
        try:
            self.graphProv.node(hashing, label=text)
            return [True, self.graphProv]
        except SystemError:
            return [False, None]

    def loops(self, hashing, text, condition):
        try:
            self.graphProv.node(hashing + 'c',
                                label=condition,
                                shape=self.shape['note'],
                                fillcolor="white",
                                color=self.color['notes']
                                )
            self.graphProv.node(hashing,
                                label=text,
                                shape=self.shape['loops']
                                )
            self.graphProv.edge(hashing, hashing + 'c',
                                style=self.edges['back'],
                                arrowhead=self.edges['none'],
                                color=self.color['notes']
                                )
            return [True, self.graphProv]
        except SystemError:
            return [False, None]

    def assign(self, hashing, text):
        try:
            self.graphProv.node(hashing, label=text,
                                fillcolor=self.color['assign'])
            return [True, self.graphProv]
        except SystemError:
            return [False, None]

    def condition(self, hashing, text, condition):
        try:
            self.graphProv.node(hashing + 'c',
                                label=condition,
                                shape=self.shape['note'],
                                fillcolor='white',
                                color=self.color['notes']
                                )
            self.graphProv.node(hashing,

                                label=text,
                                shape=self.shape['condition']
                                )
            self.graphProv.edge(hashing, hashing + 'c',
                                style=self.edges['back'],
                                arrowhead=self.edges['none'],
                                color=self.color['notes']
                                )
            return [True, self.graphProv]
        except SystemError:
            return [False, None]

    def imports(self, hashing, text):
        try:
            self.graphProv.node(hashing,
                                label=text,
                                fillcolor=self.color['assign']
                                )
            return [True, self.graphProv]
        except SystemError:
            return [False, None]

    def exceptions(self, hashing, text):
        """
        :param hashing: hash of the node
        :param text:  label of the node
        :return:
        """
        try:
            self.graphProv.node(hashing,
                                label=text,
                                shape=self.shape['condition']
                                )
            return [True, self.graphProv]
        except SystemError:
            return [False, None]
