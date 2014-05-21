#!/usr/bin/env python
from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup
setup(
    name = "noworkflow",
    version = "0.3",
    packages = ['noworkflow'],
    package_data = {'noworkflow': ['resources/*']},
    entry_points = {'console_scripts': ['now = noworkflow.now:main']},
    author = "Leonardo Murta, Vanessa Braganholo, Fernando Chirigati, David Koop, and Juliana Freire",
    author_email = "leomurta@ic.uff.br",
    description = "Supporting infrastructure to run scientific experiments without a scientific workflow management system.",
    license = "MIT",
    keywords = "scientific experiments provenance python",
    url = "https://github.com/gems-uff/noworkflow"
)