# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""What the collector records of the processes a script starts (#202)

Each test traces a short script in a throwaway directory, in process,
and reads the file accesses the external process tracer
(``prov_execution/external.py``) attached to the activation of the call
that started the process: the child's script and its input, read with
the same hash before and after; its output, written, with no content
before; a file the child creates without naming it, found by the
snapshot of the directory; the modes inferred from the hashes. The ways
of starting a process (``run``, ``Popen`` and ``wait``, ``communicate``,
``check_output``, ``shell=True`` with redirections, ``os.system``,
``os.popen``, ``os.posix_spawn``) and the ways a launch ends (waited for
inside the call, waited for later, never waited for, finished with the
trial) are each a test. The last tests pin what must not happen: the
program itself is never a file access, a launch made under
``suspended()`` or with ``--external-tracer none`` is not recorded, a
launch that fails to start leaves nothing, and once the collection ends
the hook is inert and ``subprocess.Popen`` has its own functions back.
``TestProgramsAsModules`` (#203) reads the ``module`` rows of the
programs the launches run and of the libraries loaded through ``ctypes``.

``e2e/test_external_processes.py`` pins the same from a real store, for
``now run`` as a process; ``test_external_parsing.py`` the pure functions.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from subprocess import Popen  # noqa: F401  (imported before the script on purpose)

import pytest

from ...now.collection.prov_execution import external
from ...now.persistence.content import safeopen
from ..collection_testcase import CollectionTestCase

SUCCESS = "the execution of trial -1 finished successfully"
INPUT = b"input\n"
OUTPUT = b"child:input\n"
CHILD = """\
import sys
with open(sys.argv[1], encoding="utf-8") as source:
    data = source.read()
with open(sys.argv[2], "w", encoding="utf-8", newline="\\n") as target:
    target.write("child:" + data)
if len(sys.argv) > 3 and sys.argv[3] == "made":
    with open("made.txt", "w", encoding="utf-8", newline="\\n") as made:
        made.write("made\\n")
sys.exit(int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 0)
"""
CHILD_STDIN = """\
import sys
sys.stdout.write("child:" + sys.stdin.read())
"""
CHILD_OPTIONS = """\
import sys
options = dict(word[2:].split("=", 1) for word in sys.argv[1:])
with open(options["in"], encoding="utf-8") as source:
    data = source.read()
with open(options["out"], "w", encoding="utf-8", newline="\\n") as target:
    target.write("child:" + data)
"""
TOOL = '#!/bin/sh\ncat "$1" > /dev/null\n'

POSIX = pytest.mark.skipif(os.name == "nt", reason="the POSIX shell and os.fork")


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def run_script(*words, **options):
    """A script that starts child.py through ``subprocess.run`` with
    ``words`` after it, with the given keyword options"""
    arguments = ", ".join(repr(word) for word in words)
    keywords = "".join(", {}={!r}".format(key, value) for key, value in options.items())
    return (
        "# script.py\n"
        "import subprocess\n"
        "import sys\n"
        "result = subprocess.run([sys.executable, 'child.py'{}]{})\n"
    ).format(", " + arguments if arguments else "", keywords)


class ExternalProcessTestCase(CollectionTestCase):
    """Run each script in a throwaway directory with the children in it"""

    # pylint: disable=invalid-name

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.olddir = os.getcwd()
        os.chdir(self.tmpdir)
        self.write("child.py", CHILD)
        self.write("child_stdin.py", CHILD_STDIN)
        self.write("child_options.py", CHILD_OPTIONS)
        self.write("in.txt", INPUT.decode("utf-8"))
        self.originals = (
            subprocess.Popen.__init__,
            subprocess.Popen.wait,
            subprocess.Popen.poll,
        )

    def tearDown(self):
        super(ExternalProcessTestCase, self).tearDown()
        os.chdir(self.olddir)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write(self, name, text):
        with safeopen.std_open(name, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def read(self, name):
        """The bytes of a file, through the original open: after a
        collection ``open`` is still the collector's wrapper (#250), which
        would record this read as an access of the trial"""
        with safeopen.std_open(name, "rb") as handle:
            return handle.read()

    def collect_ok(self, code, **kwargs):
        """Collect ``code``, which must succeed"""
        self.assertEqual(self.collect(code, **kwargs), SUCCESS)

    def accesses(self, basename=None):
        """The file accesses, in id order, all of them or those of a name"""
        found = [
            access
            for access in self.metascript.file_accesses_store.values()
            if basename is None or os.path.basename(access.name) == basename
        ]
        found.sort(key=lambda access: access.id)
        return found

    def access(self, basename):
        """The one access to a file"""
        found = self.accesses(basename)
        self.assertEqual(
            len(found), 1, "{} accesses to {}".format(len(found), basename)
        )
        return found[0]

    def activation(self, name):
        """The one activation named ``name``"""
        found = [
            activation
            for activation in self.metascript.activations_store.store.values()
            if activation.name == name
        ]
        self.assertEqual(
            len(found), 1, "{} activations named {}".format(len(found), name)
        )
        return found[0]

    def assert_child_files(self, activation_name, prefix=""):
        """The child's three files, recorded as accesses of the named
        activation: the script and the input read, with the same hash
        before and after, the output written, with no content before and
        the child's output after; all done"""
        activation = self.activation(activation_name)
        script = self.access(prefix + "child.py" if prefix else "child.py")
        source = self.access("in.txt")
        target = self.access("out.txt")
        for access in (script, source, target):
            self.assertEqual(access.activation_id, activation.id, access.name)
            self.assertTrue(access.done, access.name)
        self.assertEqual(
            (script.mode, script.content_hash_before, script.content_hash_after),
            ("r", sha1(self.read("child.py")), sha1(self.read("child.py"))),
        )
        self.assertEqual(
            (source.mode, source.content_hash_before, source.content_hash_after),
            ("r", sha1(INPUT), sha1(INPUT)),
        )
        self.assertEqual(
            (target.mode, target.content_hash_before, target.content_hash_after),
            ("w", None, sha1(OUTPUT)),
        )
        return activation


class TestExternalProcessExecution(ExternalProcessTestCase):
    """The files exchanged with a child, by the way it was started"""

    # pylint: disable=invalid-name

    def test_run_with_a_list(self):
        """``subprocess.run`` with an argument list: the three files are
        accesses of the ``run`` activation, named as the command line
        names them; the interpreter, the program, is no access"""
        self.collect_ok(run_script("in.txt", "out.txt"))
        self.assert_child_files("run")
        names = [access.name for access in self.accesses()]
        self.assertEqual(names, ["child.py", "in.txt", "out.txt"])
        self.assertEqual(self.read("out.txt"), OUTPUT)
        self.assertEqual(self.metascript.execution.collector.external.pending, [])

    def test_popen_then_wait(self):
        """``Popen`` and a later ``wait``: the accesses belong to the
        ``Popen`` activation, and the output's hash is taken at the wait,
        after the child wrote it"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "process = subprocess.Popen([sys.executable, 'child.py', 'in.txt', 'out.txt'])\n"
            "same = type(process) is subprocess.Popen\n"
            "patched = hasattr(subprocess.Popen.__init__, '__wrapped__')\n"
            "code = process.wait(60)\n"
        )
        self.assert_child_files("Popen")
        self.assertEqual(self.metascript.namespace["code"], 0)
        self.assertTrue(self.metascript.namespace["same"])
        self.assertTrue(self.metascript.namespace["patched"])

    def test_with_popen_and_communicate(self):
        """``with Popen(...) as p: p.communicate()`` ends the launch inside
        the block"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "with subprocess.Popen([sys.executable, 'child.py', 'in.txt', 'out.txt'],\n"
            "                      stdout=subprocess.PIPE) as process:\n"
            "    out, err = process.communicate(timeout=60)\n"
        )
        self.assert_child_files("Popen")

    def test_check_output(self):
        """``check_output`` waits inside the call"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "output = subprocess.check_output(\n"
            "    [sys.executable, 'child.py', 'in.txt', 'out.txt'], timeout=60)\n"
        )
        self.assert_child_files("check_output")

    def test_popen_polled_until_it_ends(self):
        """A launch driven by ``poll`` ends when a poll sees the return
        code"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "import time\n"
            "process = subprocess.Popen([sys.executable, 'child.py', 'in.txt', 'out.txt'])\n"
            "deadline = time.monotonic() + 60\n"
            "while process.poll() is None and time.monotonic() < deadline:\n"
            "    time.sleep(0.01)\n"
        )
        self.assert_child_files("Popen")

    @POSIX
    def test_shell_with_redirections(self):
        """``shell=True``: the line is parsed, ``<`` names an input and
        ``>`` an output, both declared; the child's script is read"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "result = subprocess.run(\n"
            "    sys.executable + ' child_stdin.py < in.txt > out.txt', shell=True)\n"
        )
        activation = self.activation("run")
        script = self.access("child_stdin.py")
        source = self.access("in.txt")
        target = self.access("out.txt")
        self.assertEqual(
            {a.activation_id for a in (script, source, target)}, {activation.id}
        )
        self.assertEqual(script.mode, "r")
        self.assertEqual((source.mode, source.content_hash_after), ("r", sha1(INPUT)))
        self.assertEqual(
            (target.mode, target.content_hash_before, target.content_hash_after),
            ("w", None, sha1(OUTPUT)),
        )

    @POSIX
    def test_os_system(self):
        """``os.system`` is finalized when its activation closes"""
        self.collect_ok(
            "# script.py\n"
            "import os\n"
            "import sys\n"
            "status = os.system(sys.executable + ' child.py in.txt out.txt')\n"
        )
        self.assert_child_files("system")
        self.assertEqual(self.metascript.namespace["status"], 0)

    @POSIX
    def test_os_popen(self):
        """``os.popen`` goes through ``Popen``; its launch belongs to the
        ``popen`` activation and ends with the pipe's close"""
        self.collect_ok(
            "# script.py\n"
            "import os\n"
            "import sys\n"
            "with os.popen(sys.executable + ' child.py in.txt out.txt') as pipe:\n"
            "    text = pipe.read()\n"
        )
        self.assert_child_files("popen")

    @POSIX
    def test_posix_spawn_is_finalized_when_the_trial_is_stored(self):
        """``os.posix_spawn`` reports no end: its accesses belong to the
        ``posix_spawn`` activation and get their hashes after when the
        trial is stored"""
        self.script(
            "# script.py\n"
            "import os\n"
            "import sys\n"
            "pid = os.posix_spawn(sys.executable,\n"
            "    [sys.executable, 'child.py', 'in.txt', 'out.txt'], os.environ)\n"
            "waited, status = os.waitpid(pid, 0)\n"
        )
        tracer = self.metascript.execution.collector.external
        self.metascript.execution.collect_provenance()
        self.assertEqual(self.metascript.execution.msg, SUCCESS)
        (pending,) = tracer.pending
        self.assertEqual(pending.kind, "posix_spawn")
        # The input was recorded at the launch and waits for its hash
        # after; the output, which did not exist, is not an access yet.
        self.assertFalse(self.access("in.txt").done)
        self.assertEqual(self.accesses("out.txt"), [])
        self.metascript.execution.store_provenance()
        self.assertEqual(tracer.pending, [])
        self.assert_child_files("posix_spawn")

    def test_a_popen_never_waited_for_is_finalized_when_the_trial_is_stored(self):
        """A ``Popen`` the script never waits for keeps its launch pending;
        storing the trial finalizes it with the files as they are then"""
        self.script(
            "# script.py\n"
            "import os\n"
            "import subprocess\n"
            "import sys\n"
            "import time\n"
            "process = subprocess.Popen(\n"
            "    [sys.executable, 'child.py', 'in.txt', 'out.txt', 'made'])\n"
            "deadline = time.monotonic() + 60\n"
            "while not os.path.exists('made.txt') and time.monotonic() < deadline:\n"
            "    time.sleep(0.01)\n"
        )
        tracer = self.metascript.execution.collector.external
        self.metascript.execution.collect_provenance()
        try:
            self.assertEqual(self.metascript.execution.msg, SUCCESS)
            self.assertEqual(len(tracer.pending), 1)
            self.metascript.execution.store_provenance()
            self.assertEqual(tracer.pending, [])
            self.assert_child_files("Popen")
            made = self.access("made.txt")
            self.assertEqual((made.mode, made.content_hash_before), ("w", None))
            self.assertEqual(made.content_hash_after, sha1(b"made\n"))
        finally:
            self.metascript.namespace["process"].wait(60)

    def test_a_file_the_child_creates_without_naming_it_is_found(self):
        """The snapshot of the directory finds ``made.txt``, which no word
        of the command line names: a write with no content before,
        attached to the launch"""
        self.collect_ok(run_script("in.txt", "out.txt", "made"))
        activation = self.assert_child_files("run")
        made = self.access("made.txt")
        self.assertEqual(made.activation_id, activation.id)
        self.assertEqual(
            (made.mode, made.content_hash_before, made.content_hash_after, made.done),
            ("w", None, sha1(b"made\n"), True),
        )

    def test_a_file_the_child_modifies_is_read_and_written(self):
        """An existing output changed by the child: ``r+``, with the old
        content before and the new one after; the unchanged input stays a
        read"""
        self.write("out.txt", "old\n")
        self.collect_ok(run_script("in.txt", "out.txt"))
        target = self.access("out.txt")
        self.assertEqual(
            (target.mode, target.content_hash_before, target.content_hash_after),
            ("r+", sha1(b"old\n"), sha1(OUTPUT)),
        )
        self.assertEqual(self.access("in.txt").mode, "r")

    def test_a_file_the_child_deletes_is_a_read_with_nothing_after(self):
        """A named file the child removes keeps its hash before and has no
        content after"""
        self.write("gone.txt", "gone\n")
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "result = subprocess.run([sys.executable, '-c', 'import os; os.remove(\"gone.txt\")', 'gone.txt'])\n"
        )
        gone = self.access("gone.txt")
        self.assertEqual(
            (gone.mode, gone.content_hash_before, gone.content_hash_after),
            ("r", sha1(b"gone\n"), None),
        )

    @POSIX
    def test_append_redirection(self):
        """``>>`` is a declared append, with the content before and after"""
        self.write("log.txt", "first\n")
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "result = subprocess.run('echo second >> log.txt', shell=True)\n"
        )
        log = self.access("log.txt")
        self.assertEqual(
            (log.mode, log.content_hash_before, log.content_hash_after),
            ("a", sha1(b"first\n"), sha1(b"first\nsecond\n")),
        )

    @POSIX
    def test_a_pipeline_records_the_files_of_each_command(self):
        """``cat in.txt | python child_stdin.py > out.txt``: the input of
        the first command and the script and output of the second"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "result = subprocess.run(\n"
            "    'cat in.txt | ' + sys.executable + ' child_stdin.py > out.txt', shell=True)\n"
        )
        self.assertEqual(
            [(access.name, access.mode) for access in self.accesses()],
            [("in.txt", "r"), ("child_stdin.py", "r"), ("out.txt", "w")],
        )
        self.assertEqual(self.access("out.txt").content_hash_after, sha1(OUTPUT))

    def test_the_file_after_an_equals_sign_is_named(self):
        """``--in=in.txt --out=out.txt`` name the files"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "result = subprocess.run(\n"
            "    [sys.executable, 'child_options.py', '--in=in.txt', '--out=out.txt'])\n"
        )
        self.assertEqual(
            [(access.name, access.mode) for access in self.accesses()],
            [("child_options.py", "r"), ("in.txt", "r"), ("out.txt", "w")],
        )

    def test_cwd_names_the_files_as_the_script_sees_them(self):
        """With ``cwd=``, the files resolve in the child's directory and
        are recorded relative to the script's current directory"""
        os.mkdir("sub")
        shutil.copyfile("child.py", os.path.join("sub", "child.py"))
        shutil.copyfile("in.txt", os.path.join("sub", "in.txt"))
        self.collect_ok(run_script("in.txt", "out.txt", cwd="sub"))
        self.assertEqual(
            [(access.name, access.mode) for access in self.accesses()],
            [
                (os.path.join("sub", "child.py"), "r"),
                (os.path.join("sub", "in.txt"), "r"),
                (os.path.join("sub", "out.txt"), "w"),
            ],
        )
        self.assertEqual(self.read(os.path.join("sub", "out.txt")), OUTPUT)

    def test_depth_1_attaches_the_accesses_to_the_script(self):
        """With the depth at 1 the call is not an active activation, so
        the accesses go to the script's activation, as ``open``'s do"""
        self.collect_ok(run_script("in.txt", "out.txt"), depth=1)
        self.assert_child_files("__main__")

    def test_coarse_granularity_records_the_launch(self):
        """``-cg`` still instruments the calls: the launch is recorded"""
        self.collect_ok(run_script("in.txt", "out.txt"), coarse_granularity=True)
        self.assert_child_files("run")

    def test_a_popen_imported_before_the_script_is_detected(self):
        """``from subprocess import Popen`` made before the script (this
        module did it): the class is patched, not the module's name"""
        self.collect_ok(
            "# script.py\n"
            "import sys\n"
            "from subprocess import Popen\n"
            "code = Popen([sys.executable, 'child.py', 'in.txt', 'out.txt']).wait(60)\n"
        )
        self.assert_child_files("Popen")

    def test_a_launch_that_raises_under_check_is_recorded(self):
        """``run(check=True)`` of a child that exits with 3 raises after the
        wait: the launch is finalized all the same (#378 only loses the
        call's dependencies)"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "try:\n"
            "    subprocess.run([sys.executable, 'child.py', 'in.txt', 'out.txt', '3'],\n"
            "                   check=True, timeout=60)\n"
            "except subprocess.CalledProcessError as error:\n"
            "    status = error.returncode\n"
        )
        self.assert_child_files("run")
        self.assertEqual(self.metascript.namespace["status"], 3)


class TestExternalProcessLimits(ExternalProcessTestCase):
    """What is not recorded, and what the collection leaves behind"""

    # pylint: disable=invalid-name

    @POSIX
    def test_the_program_is_never_a_file_access(self):
        """A program of the project (``./tool.sh``, which reads its
        argument) is argv[0]: no access names it, its argument is read"""
        self.write("tool.sh", TOOL)
        os.chmod("tool.sh", 0o755)
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "result = subprocess.run(['./tool.sh', 'in.txt'])\n"
        )
        self.assertEqual(
            [(access.name, access.mode) for access in self.accesses()],
            [("in.txt", "r")],
        )

    def test_a_launch_that_fails_to_start_leaves_nothing(self):
        """A program that does not exist raises in ``Popen.__init__``
        after the audit event: nothing ran, so the launch and the access
        it had made are dropped"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "try:\n"
            "    subprocess.run(['/no/such/program', 'in.txt'])\n"
            "except FileNotFoundError:\n"
            "    failed = True\n"
        )
        self.assertTrue(self.metascript.namespace["failed"])
        self.assertEqual(self.accesses(), [])
        self.assertEqual(self.metascript.execution.collector.external.pending, [])

    def test_a_launch_under_suspended_is_not_recorded(self):
        """noWorkflow's own launches run under ``suspended()``"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "with __noworkflow__.external.suspended():\n"
            "    subprocess.run([sys.executable, 'child.py', 'in.txt', 'out.txt'])\n"
        )
        self.assertEqual(self.accesses(), [])
        self.assertEqual(self.read("out.txt"), OUTPUT)

    def test_external_tracer_none_records_nothing_of_the_child(self):
        """``--external-tracer none``: the child runs, nothing of it is
        recorded, and Popen is not patched during the script (the patched
        functions carry ``__wrapped__``; the originals do not)"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "patched = hasattr(subprocess.Popen.__init__, '__wrapped__')\n"
            "subprocess.run([sys.executable, 'child.py', 'in.txt', 'out.txt'])\n",
            external_tracer="none",
        )
        self.assertFalse(self.metascript.namespace["patched"])
        self.assertEqual(self.accesses(), [])
        self.assertEqual(self.read("out.txt"), OUTPUT)

    def test_strace_falls_back_to_argv_with_a_warning(self):
        """Until #206 lands, ``strace`` records as ``argv`` does and says
        so once on stderr"""
        self.collect_ok(run_script("in.txt", "out.txt"), external_tracer="strace")
        self.assert_child_files("run")
        tracer = self.metascript.execution.collector.external
        self.assertEqual(tracer.mode, "argv")
        self.assertEqual(tracer.warned, {external.STRACE_WARNING})

    def test_the_snapshot_is_disabled_above_the_cap_with_a_warning(self):
        """A project with more entries than the cap: the files named on the
        command line are still recorded, the new file is not, and one
        warning is printed"""
        self.script(run_script("in.txt", "out.txt", "made"))
        tracer = self.metascript.execution.collector.external
        tracer.snapshot_cap = 3
        self.metascript.execution.collect_provenance()
        self.assertEqual(self.metascript.execution.msg, SUCCESS)
        self.assert_child_files("run")
        self.assertEqual(self.accesses("made.txt"), [])
        self.assertTrue(tracer.snapshot_disabled)
        self.assertEqual(tracer.warned, {external.SNAPSHOT_WARNING})

    def test_after_the_collection_the_hook_is_inert_and_popen_is_itself(self):
        """Once the script ends, ``Popen.__init__``, ``wait`` and ``poll``
        are the originals, no tracer is current, and a process started
        here records nothing, although the audit hook stays installed"""
        self.collect_ok(run_script("in.txt", "out.txt"))
        self.assertTrue(external.hook_installed())
        self.assertIsNone(external.current())
        self.assertFalse(external.popen_patched())
        self.assertEqual(
            (subprocess.Popen.__init__, subprocess.Popen.wait, subprocess.Popen.poll),
            self.originals,
        )
        before = len(self.accesses())
        subprocess.run([sys.executable, "child.py", "in.txt", "later.txt"], timeout=60)
        self.assertEqual(len(self.accesses()), before)
        self.assertEqual(self.accesses("later.txt"), [])
        self.assertEqual(self.read("later.txt"), OUTPUT)

    def test_a_script_that_raises_leaves_popen_itself(self):
        """The patch leaves in the ``finally``, whichever way the script
        ends"""
        msg = self.collect(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "subprocess.run([sys.executable, 'child.py', 'in.txt', 'out.txt'])\n"
            "1 / 0\n"
        )
        self.assertIn("uncaught exception", msg)
        self.assertFalse(external.popen_patched())
        self.assertIsNone(external.current())
        self.assert_child_files("run")


PROBED_TOOL = """\
#!/bin/sh
case "$1" in --version|-version) echo probed > probed.txt; exit 0 ;; esac
cat "$1" > /dev/null
"""


class TestProgramsAsModules(ExternalProcessTestCase):
    """The program a launch runs is a module of the trial (#203)"""

    # pylint: disable=invalid-name

    def rows(self, name=None):
        """The module rows, in id order, all of them or those of a name"""
        found = [
            module
            for module in self.metascript.modules_store.store.values()
            if module is not None and (name is None or module.name == name)
        ]
        found.sort(key=lambda module: module.id)
        return found

    def code_hash(self, module):
        return self.metascript.code_blocks_store[module.code_block_id].code_hash

    def test_the_interpreter_of_a_launch_is_a_module_with_its_version(self):
        """``run([sys.executable, ...])``: one row, named as the command
        line names the program, with its real path, the version it prints
        and the hash of its code; the version probe is no launch and opens
        nothing the trial records (its stdin is os.devnull)"""
        self.collect_ok(run_script("in.txt", "out.txt"), bypass_modules=False)
        (row,) = self.rows()
        real = os.path.realpath(sys.executable)
        self.assertEqual(row.name, os.path.basename(sys.executable))
        self.assertEqual(row.path, real)
        self.assertTrue(row.version.startswith("Python "), row.version)
        self.assertEqual(self.code_hash(row), sha1(external.executable_content(real)))
        self.assertFalse(row.transformed)
        self.assert_child_files("run")
        self.assertEqual(len(self.accesses()), 3)
        tracer = self.metascript.execution.collector.external
        self.assertEqual(tracer.pending, [])
        self.assertEqual(list(tracer.versions.values()), [row.version])

    def test_bypass_modules_records_no_program_and_keeps_the_accesses(self):
        """``-b``: no row, the files exchanged as without it"""
        self.collect_ok(run_script("in.txt", "out.txt"), bypass_modules=True)
        self.assertEqual(self.rows(), [])
        self.assert_child_files("run")

    def test_external_tracer_none_records_no_program(self):
        self.collect_ok(
            run_script("in.txt", "out.txt"),
            bypass_modules=False,
            external_tracer="none",
        )
        self.assertEqual(self.rows(), [])

    def test_the_same_program_launched_twice_is_one_row_probed_once(self):
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "subprocess.run([sys.executable, 'child.py', 'in.txt', 'a.txt'])\n"
            "subprocess.run([sys.executable, 'child.py', 'in.txt', 'b.txt'])\n",
            bypass_modules=False,
        )
        self.assertEqual(len(self.rows()), 1)
        tracer = self.metascript.execution.collector.external
        self.assertEqual(len(tracer.versions), 1)

    def test_an_executable_above_the_cap_is_a_placeholder_with_its_sha1(self):
        """Above the cap of the ``Metascript`` (``--executable-cap``, #463),
        which reaches the tracer when it starts, the code is the
        placeholder, whose hash follows the SHA-1 and the size of the
        file"""
        self.script(
            run_script("in.txt", "out.txt"), bypass_modules=False, executable_cap=10
        )
        tracer = self.metascript.execution.collector.external
        self.metascript.execution.collect_provenance()
        self.assertEqual(self.metascript.execution.msg, SUCCESS)
        self.assertEqual(tracer.executable_cap, 10)
        (row,) = self.rows()
        data = self.read(row.path)
        placeholder = external.PLACEHOLDER.format(sha1(data), len(data))
        self.assertEqual(self.code_hash(row), sha1(placeholder.encode("ascii")))

    def test_a_launch_that_fails_to_start_takes_its_row_with_it(self):
        """The program exists but the process never ran (its cwd does not
        exist): no row, no code block for it, and a later launch of the
        same program records it"""
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "import sys\n"
            "try:\n"
            "    subprocess.run([sys.executable, 'child.py'], cwd='no_such_dir')\n"
            "except OSError:\n"
            "    failed = True\n"
            "rows = len([m for m in __noworkflow__.metascript.modules_store.store.values() if m])\n"
            "subprocess.run([sys.executable, 'child.py', 'in.txt', 'out.txt'])\n",
            bypass_modules=False,
        )
        self.assertTrue(self.metascript.namespace["failed"])
        self.assertEqual(self.metascript.namespace["rows"], 0)
        (row,) = self.rows()
        blocks = [
            block
            for block in self.metascript.code_blocks_store.store.values()
            if block is not None and block.id != 1
        ]
        self.assertEqual([block.id for block in blocks], [row.code_block_id])

    @POSIX
    def test_a_program_outside_the_allowlist_is_never_run_to_probe_it(self):
        """``./tool.sh``: a row with its real path and its bytes as code,
        no version, and no run with ``--version`` (it would write
        probed.txt)"""
        self.write("tool.sh", PROBED_TOOL)
        os.chmod("tool.sh", 0o755)
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "result = subprocess.run(['./tool.sh', 'in.txt'])\n",
            bypass_modules=False,
        )
        (row,) = self.rows()
        self.assertEqual(
            (row.name, row.path, row.version),
            ("tool.sh", os.path.realpath("tool.sh"), None),
        )
        self.assertEqual(self.code_hash(row), sha1(PROBED_TOOL.encode("utf-8")))
        self.assertFalse(os.path.exists("probed.txt"))

    @POSIX
    def test_a_program_rewritten_during_the_trial_gets_a_second_row(self):
        """One row per version of the file a trial runs: the program
        rewritten between two launches has two rows, with the two hashes;
        a third launch of the second version adds none"""
        self.write("tool.sh", PROBED_TOOL)
        os.chmod("tool.sh", 0o755)
        self.collect_ok(
            "# script.py\n"
            "import os\n"
            "import subprocess\n"
            "subprocess.run(['./tool.sh', 'in.txt'])\n"
            "with open('tool.sh', 'a', encoding='utf-8') as tool:\n"
            "    tool.write('# rebuilt\\n')\n"
            "subprocess.run(['./tool.sh', 'in.txt'])\n"
            "subprocess.run(['./tool.sh', 'in.txt'])\n",
            bypass_modules=False,
        )
        rows = self.rows("tool.sh")
        self.assertEqual(
            [self.code_hash(row) for row in rows],
            [
                sha1(PROBED_TOOL.encode("utf-8")),
                sha1((PROBED_TOOL + "# rebuilt\n").encode("utf-8")),
            ],
        )

    @POSIX
    def test_a_shell_line_records_the_program_of_each_command(self):
        """``shell=True``: the programs of the commands of the line, not
        the shell that runs them"""
        self.write("tool.sh", PROBED_TOOL)
        os.chmod("tool.sh", 0o755)
        self.collect_ok(
            "# script.py\n"
            "import subprocess\n"
            "subprocess.run('./tool.sh in.txt | cat > copy.txt', shell=True)\n",
            bypass_modules=False,
        )
        self.assertEqual(sorted(row.name for row in self.rows()), ["cat", "tool.sh"])

    @POSIX
    def test_a_bare_name_is_resolved_on_the_path_of_the_env_given(self):
        """``env={"PATH": ...}`` decides where a bare name is found, as it
        decides for subprocess"""
        os.mkdir("bin")
        self.write(os.path.join("bin", "mytool"), PROBED_TOOL)
        os.chmod(os.path.join("bin", "mytool"), 0o755)
        self.collect_ok(
            "# script.py\n"
            "import os\n"
            "import subprocess\n"
            "subprocess.run(['mytool', 'in.txt'], env={'PATH': os.path.abspath('bin')})\n",
            bypass_modules=False,
        )
        (row,) = self.rows()
        self.assertEqual(
            (row.name, row.path),
            ("mytool", os.path.realpath(os.path.join("bin", "mytool"))),
        )

    def test_a_library_is_a_module_only_when_loaded_by_a_path(self):
        """``ctypes.dlopen``: a path (relative to the current directory)
        gives a row with no version and the bytes as code; a bare name,
        which the loader searches, and None (the program itself) give
        none. The event is fed to the tracer directly: loading a real
        library is the e2e test's (test_compiled_modules.py)"""
        self.write("libfake.so", "not really a library")
        self.script("# script.py\nvalue = 1\n", bypass_modules=False)
        tracer = self.metascript.execution.collector.external
        tracer.event("ctypes.dlopen", ("libm.so.6",))
        tracer.event("ctypes.dlopen", (None,))
        self.assertEqual(self.rows(), [])
        tracer.event("ctypes.dlopen", ("./libfake.so",))
        (row,) = self.rows()
        self.assertEqual(
            (row.name, row.path, row.version),
            ("libfake.so", os.path.realpath("libfake.so"), None),
        )
        self.assertEqual(self.code_hash(row), sha1(b"not really a library"))
        self.assertEqual(tracer.failures, [])
