# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight ExtendedAnnotation"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
from .base import BaseLW, define_attrs


class ExtendedAnnotationLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """ExtendedAnnotation lightweight object"""

    __slots__, attributes = define_attrs(
        ["relatedTrial","relatedExperiment","annotationLevel","provenanceType","annotationFormat","annotation", "id"]
    )

    def __init__(self, id,annotation,annotationFormat,provenanceType,annotationLevel,relatedExperiment,relatedTrial):
        self.relatedTrial = relatedTrial
        self.relatedExperiment = relatedExperiment
        self.annotationLevel = annotationLevel
        self.provenanceType = provenanceType
        self.annotationFormat = annotationFormat
        self.annotation = annotation
        self.id = id
    
    def __json__(self):
        return {
            'relatedTrial': self.relatedTrial,
            'relatedExperiment': self.relatedExperiment,
            'annotationLevel': self.annotationLevel,
            'provenanceType': self.provenanceType,
            'annotationFormat': self.annotationFormat,
            'annotation': self.annotation,
            'id': self.id
        }
