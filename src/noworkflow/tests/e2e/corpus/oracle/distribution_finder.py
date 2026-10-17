"""A finder of the script that also answers for distributions (#417)

A program that serves modules or distributions from a place of its own (a
plugin system, a bundled application) puts a finder with
``find_distributions`` in ``sys.meta_path``, and ``importlib.metadata``
asks it whenever the program looks a distribution up. This finder serves
nothing and records each question. Importing modules asks it none.
"""
import importlib.metadata
import sys


class RecordingFinder(importlib.metadata.DistributionFinder):
    """Finds no module and no distribution; records the names asked for"""

    def __init__(self):
        self.asked = []

    def find_spec(self, fullname, path=None, target=None):
        return None

    def find_distributions(self, context=None):
        name = context.name if context is not None else None
        self.asked.append(name)
        return iter(())


finder = RecordingFinder()
sys.meta_path.append(finder)
try:
    # Neither is loaded before the script, with or without noWorkflow.
    import sched
    import wave
finally:
    sys.meta_path.remove(finder)
print("asked for:", finder.asked)
print("imported:", sched.__name__, wave.__name__)
