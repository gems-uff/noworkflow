#!/usr/bin/env python
from setuptools import setup, find_packages

import os
import platform

from uuid import getnode

with open("./noworkflow/resources/version.txt", "r") as f:
    __version__ = f.read().strip()


def recursive_path(pack, path):
    matches = []
    for root, _, filenames in os.walk(os.path.join(pack, path)):
        for filename in filenames:
            matches.append(os.path.join(root, filename)[len(pack) + 1:])
    return matches


try:
    with open("../README.md") as f:
        long_description = f.read()
        long_description_content_type="text/markdown"
except (IOError, ImportError):
    long_description = (
        "Supporting infrastructure to run scientific experiments "
        "without a scientific workflow management system.")
    long_description_content_type="text/x-rst"

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
    long_description_content_type="text/markdown",
    license="MIT",
    keywords="scientific experiments provenance python",
    url="https://github.com/gems-uff/noworkflow",
    install_requires=[
        "pyposast", "apted", "future", "SQLAlchemy>=1.4.29,<=1.4.47", "parameterized",
        "requests", "ipykernel", "zipp==3.15", "importlib-metadata==6.4.1", "typing-extensions==4.5.0"
    ],
    extras_require={
        "demo": ["flask", "matplotlib", "numpy", "cython"],
        "notebook": ["pyposast", "ipython", "jupyter"],
        "all": ["pyposast", "ipython", "jupyter", "flask", "pyswip-alt", 
                "matplotlib", "numpy", "cython", "graphviz"],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',

        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3.12',
    ]
)
