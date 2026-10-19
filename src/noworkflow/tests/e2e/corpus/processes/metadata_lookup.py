"""Imports a distribution that noWorkflow does not import before the script

idna, a dependency of requests, which noWorkflow imports only when a
request is sent. Its module row carries its version, which noWorkflow
reads from the distribution's metadata while the script runs. The output
is the modules this import added to sys.modules: under plain Python, what
the script imports, and nothing noWorkflow does on the way.
"""
import sys

before = set(sys.modules)
import idna

print(sorted(set(sys.modules) - before))
