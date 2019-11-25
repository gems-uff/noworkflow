#!/usr/bin/env python
from setuptools import setup, find_packages

import os
import platform

from uuid import getnode

with open("./noworkflow/resources/version.txt", "r") as f:
    __version__ = f.read().strip()


def recursive_path(pack, path):
    matches = []
    for root, dirnames, filenames in os.walk(os.path.join(pack, path)):
        for filename in filenames:
            matches.append(os.path.join(root, filename)[len(pack) + 1:])
    return matches


try:
    import pypandoc
    long_description = pypandoc.convert("../README.md", "rst")
except (IOError, ImportError):
    long_description = (
        "Supporting infrastructure to run scientific experiments "
        "without a scientific workflow management system.")

setup(
    name="noworkflow",
    version=__version__,
    packages=find_packages(),
    package_data={
        "noworkflow": (
            recursive_path("noworkflow", "resources")
            + recursive_path("noworkflow", "jupyter")
            + recursive_path("noworkflow", "now/vis/static")
            + recursive_path("noworkflow", "now/vis/templates")
        ),
    },
    entry_points={
        "console_scripts": ["now=noworkflow:main"]
    },
    author=("Joao Pimentel, Leonardo Murta, Vanessa Braganholo, "
            "Fernando Chirigati, David Koop, and Juliana Freire"),
    author_email="leomurta@ic.uff.br",
    description="Supporting infrastructure to run scientific experiments "
                "without a scientific workflow management system.",
    long_description=long_description,
    license="MIT",
    keywords="scientific experiments provenance python",
    url="https://github.com/gems-uff/noworkflow",
    install_requires=[
        "pyposast>=1.5.0", "apted", "future", "SQLAlchemy"
    ],
    extras_require={
        "vis": ["pyposast", "flask"],
        "notebook": ["pyposast", "ipython", "jupyter", "sphinx"],
        "all": ["pyposast", "ipython", "jupyter", "flask", "pyswip-alt",
                "jsonpickle", "sphinx"],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',

        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ]
)
