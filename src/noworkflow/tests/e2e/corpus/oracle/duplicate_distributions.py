"""The distributions the program sees (#420)

``importlib.metadata.distributions()`` lists the distributions on
``sys.path``: a program that loads its plugins, or reports what is
installed, iterates it. ``oracle_marker-1.0.dist-info``, next to the
script, is a distribution that nothing else installs, so plain Python
lists it once.
"""
import importlib.metadata

found = [dist for dist in importlib.metadata.distributions()
         if dist.metadata["Name"] == "oracle-marker"]
print("oracle-marker listed:", len(found))
print("its version:", importlib.metadata.version("oracle-marker"))
