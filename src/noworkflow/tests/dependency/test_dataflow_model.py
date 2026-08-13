import gc

from ...now.persistence.models import Trial
from ..collection_testcase import CollectionTestCase


class TestDataflowModel(CollectionTestCase):
    def test_export_text_reloads_trial_after_weakref_dies(self):
        self.script("# script.py\n"
                    "x = 1\n"
                    "y = x + 2\n"
                    "print(y)\n")
        self.clean_execution()

        trial = Trial()
        dot = trial.dot

        del trial
        gc.collect()

        text = dot.export_text()

        self.assertIn("digraph", text)
