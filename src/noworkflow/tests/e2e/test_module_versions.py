# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The version ``now run`` records for a module the script imports

``Deployment.get_version`` (``prov_deployment/deployment.py``) records the
version of the installed distribution named after a module, or else the
module's own ``__version__``; ``tests/prov_deployment/test_get_version.py``
covers its cases in process. Here ``now run`` runs as a process on a
project whose script puts ``vendor/`` first on ``sys.path``, as a project
does with what ``pip install --target vendor`` installed there. ``vendor/``
holds two modules declaring ``__version__ = "2.5"``, each with the
metadata directory of a distribution next to it:

- ``helper.py`` and ``helper-1.0.dist-info``, the distribution ``helper``:
  the row records ``1.0``. The lookup reads ``sys.path`` when the module is
  imported. Before PR #186, ``pkg_resources`` read it once, when ``now``
  started, and the row recorded ``2.5`` for a directory added later. The
  script's own directory is such a directory under the ``now`` console
  script, but not under ``python -m noworkflow``, which the harness runs
  and whose ``sys.path`` starts with the current directory.
- ``ns/sub.py`` and ``ns_sub-3.0.dist-info``, the distribution ``ns-sub``:
  the row records ``2.5``. A dotted module is not the distribution whose
  name has a ``-`` in place of the dot, as Flask's ``flask.json`` is not the
  plugin Flask-JSON.
"""

SCRIPT = (
    "import os\n"
    "import sys\n"
    "\n"
    "sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),"
    " 'vendor'))\n"
    "import helper\n"
    "import ns.sub\n"
    "\n"
    "print(helper.__version__, ns.sub.__version__)\n"
)


def test_run_records_the_version_of_a_distribution_on_the_path(project):
    """The ``module`` rows of ``helper`` and ``ns.sub`` hold ``1.0`` and
    ``2.5``"""
    project.write("vendor/helper.py", '__version__ = "2.5"\n')
    project.write("vendor/helper-1.0.dist-info/METADATA",
                  "Metadata-Version: 2.1\nName: helper\nVersion: 1.0\n")
    project.write("vendor/ns/sub.py", '__version__ = "2.5"\n')
    project.write("vendor/ns_sub-3.0.dist-info/METADATA",
                  "Metadata-Version: 2.1\nName: ns-sub\nVersion: 3.0\n")
    project.write("script.py", SCRIPT)
    result = project.run("run", "script.py")
    assert "2.5 2.5" in result.stdout
    trial, = project.trials()
    rows = project.query(
        "SELECT name, version FROM module WHERE trial_id = ? "
        "AND name IN ('helper', 'ns.sub') ORDER BY name", trial["id"])
    assert [(row["name"], row["version"]) for row in rows] == [
        ("helper", "1.0"), ("ns.sub", "2.5")]
