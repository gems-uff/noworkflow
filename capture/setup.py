#!/usr/bin/env python
from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages

import fnmatch
import os

def recursive_path(pack, path):
    matches = []
    for root, dirnames, filenames in os.walk(os.path.join(pack, path)):
        for filename in filenames:
            matches.append(os.path.join(root, filename)[len(pack) + 1:])
    return matches

setup(
    name = "noworkflow",
    version = "0.7.1",
    packages = find_packages(),
    package_data = {
        'noworkflow': [
            'resources/*',
        ] + recursive_path('noworkflow', 'now/vis/static')
          + recursive_path('noworkflow', 'now/vis/templates'),
    },
    entry_points = {'console_scripts': ['now = noworkflow.main:main']},
    author = ("Joao Pimentel, Leonardo Murta, Vanessa Braganholo, "
              "Fernando Chirigati, David Koop, and Juliana Freire"),
    author_email = "leomurta@ic.uff.br",
    description = "Supporting infrastructure to run scientific experiments "
                  "without a scientific workflow management system.",
    license = "MIT",
    keywords = "scientific experiments provenance python",
    url = "https://github.com/gems-uff/noworkflow",
    install_requires=['pyposast'],
    extras_require = {
        'vis': ['flask']
    }
)
