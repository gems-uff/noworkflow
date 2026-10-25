# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""External processes a traced script starts: the call boundary, the
files exchanged with them (#202) and the programs they run (#203)

A script that calls ``subprocess.run(["Rscript", "model.R", "data.csv",
"pred.csv"])`` is recorded, like any call the collector does not trace, as
an activation whose arguments are the command line and whose value is the
``CompletedProcess``. ``ExternalProcessTracer`` adds what the process did
to the project, without a change to the script and without a new table:
every file the command line names, and every file the process creates in
the project, becomes a ``file_access`` of that activation, with the hash
of its content before and after the process and a mode inferred from the
two (``infer_mode``).

**Detection.** One audit hook (PEP 578, ``sys.addaudithook``) is installed
once per process and never removed; it does nothing unless a collection
is tracing (``_current``). It sees ``subprocess.Popen`` (``run``, ``call``,
``check_output``, ``os.popen`` and a ``Popen`` imported before the script
all pass through it), ``os.system``, ``os.posix_spawn`` (and
``posix_spawnp``), ``os.spawn`` (Windows: on POSIX ``os.spawn*`` is a
fork, which is not recorded) and ``os.exec``. A launch made while the
tracer is ``suspended()``, or while the content store runs its own
commands (``safeopen.use_safe_open``), is not recorded.

**Completion.** Audit hooks report the launch, not the end. While a
collection traces, ``subprocess.Popen.__init__``, ``wait`` and ``poll``
are the patched functions of ``patch_popen`` (the class itself is not
replaced: ``type(p) is subprocess.Popen`` stays true); ``__init__`` binds
the launch to its ``Popen`` and ``wait``/``poll`` finalize it once
``returncode`` is set, which covers ``run``, ``check_output``, ``with
Popen`` and ``communicate``. ``os.system`` and a waiting ``os.spawn`` are
finalized when the activation that made the call closes; ``os.posix_spawn``,
a ``Popen`` that is never waited for and a launch whose end the patch did
not see are finalized by ``Collector.store`` at the end of the trial, so
their "after" hashes reflect that moment. The patch is installed by
``Execution.collect_provenance`` around the ``exec`` of the script, next
to the import finder, and removed in the same ``finally``; the Jupyter
kernel installs it around each cell.

**The command line** (``parse_command``, ``classify_tokens``, pure
functions): an argument list, or the string of ``shell=True`` and
``os.system`` split with ``shlex`` and cut at ``|``, ``||``, ``&&``, ``;``
and ``&``, with leading ``VAR=value`` words and ``env`` dropped and the
redirections ``>``, ``>>``, ``2>``, ``&>`` (a declared output) and ``<``
(an input) read, attached or not to their target. The program itself
(``argv[0]``) never becomes a file access: #203 records it in the module
table. Every other word, and the part after ``=`` of ``--opt=file``, that
names an existing regular file (relative to the launch's ``cwd``) is read
and hashed at the launch; a word that looks like a path (a separator, or
an extension) and names no file yet is an output candidate, recorded if
the file exists when the launch is finalized.

**New files.** A process writes files its command line does not name
(``prov.json`` of rdtLite, the binary of ``cc -o``). The set of paths
under the project directory, the current directory and the launch's
``cwd`` is taken at the launch and again at the end (``snapshot``,
skipping ``.noworkflow``, ``.git`` and ``__pycache__``); a file that
appeared is a write with no content before, which is what ``now restore``
needs to remove it. Above ``SNAPSHOT_CAP`` entries the snapshot is
disabled for the trial, with a warning. A file that existed, is not named
on the command line and is modified by the process is not seen: that is
the limit of the ``argv`` backend, which the ``strace`` backend lifts.

**The strace backend** (#206, ``--external-tracer strace``, Linux). A
launch it can rewrite runs under ``strace`` (``external_strace.py`` builds
the command and parses the log): ``Popen.__init__`` replaces the
arguments it was given, and ``os.system``, patched next to it, the line,
before the process starts, and the audit event that follows is read as
the launch the script asked for (``wrapping``). When the launch is
finalized, ``record_trace`` adds, besides what ``argv`` records, every
regular file under the project directory or the launch's directory that
the process or its children opened (not inside ``SKIPPED_DIRECTORIES``
or ``LIBRARY_DIRECTORIES``): a read is an access with the content at the
end before and after; a write to a file the snapshot did not have at the
launch is a file the process created (no content before, ``w``); a write
to a file that existed, or that a disabled snapshot cannot place, is an
access whose content before is unknown, with mode ``r+`` and no content
before, which ``now restore`` leaves in place instead of deleting
(``UNRECORDED_MODE``). A program executed under those directories is a
module, like the program of the launch. Not rewritten, and recorded as
``argv`` does: ``os.posix_spawn``, ``os.spawn``, ``os.exec``, a launch
made while the tracer is suspended, a ``Popen`` given its own
``executable`` without ``shell`` (strace would lose the ``argv[0]``) or
another ``user`` or ``group`` (strace could not write its log), and a
system without Linux or without a usable ``strace``, where the trial
falls back to ``argv`` with a warning (``prepare_strace``, which runs
``strace`` once per process to see that it can trace).

**R provenance tools** (#207). An R script run under rdtLite
(``Rscript -e 'rdtLite::prov.run("model.R", prov.dir = ".")'``) leaves a
PROV-JSON document, ``prov_model/prov.json``, that names the files the
script read and wrote, the script and what it sourced, none of them on
the command line. When a launch wrote such a document (``prov.json`` in
a directory whose name starts with ``prov``; ``external_provjson.py``
finds and reads it), ``link_prov_json`` adds each file it names, under
the project directory or the launch's directory, as an access of the
launch, as ``record_trace`` does with the files of a strace log: a read
with the content at the end before and after, a write to a new file
with no content before, a write to a file that existed as
``UNRECORDED_MODE``; a file the launch already accounts for keeps its
access. A document is found whichever backend runs: a new one by the
snapshot or the strace log, a rewritten one (rdtLite deletes and
recreates its directory on each run) by the inode, size and mtime that
the launch noted of every document the snapshot held, which also makes
the document itself an ``UNRECORDED_MODE`` access. A document that is no
PROV-JSON is reported on stderr and read no further; a document written
outside the project (rdtLite's default ``prov.dir`` is R's temporary
directory) is not seen.

**The programs** (#203). The program a launch runs is a deployment
dependency of the trial, like an imported module: ``record_programs``
resolves it as the system does (``resolve_program``: the ``PATH`` of the
``env`` given to the process, or of the script's environment, and the
launch's ``cwd`` for a name with a separator, then the real path) and
adds a ``module`` row named as the command line names it, with that path
and a binary code block, so that ``code_hash`` is the hash of the
executable's bytes; above the cap (``--executable-cap`` of ``now run``,
``EXECUTABLE_CAP`` by default, #463) the code block is a placeholder
that carries the SHA-1 of the file, computed by streaming, so the hash
still changes when the binary does. For an argument list the
program is the executable ``Popen`` runs (``executable=``, or the first
word); for a line run through a shell, the program of each of its
commands, not the shell. One row per ``(real path, size, mtime)`` per
trial: a binary rebuilt in the middle of a trial gets a second row with
its new hash. An interpreter or a compiler of ``PROBED`` (or a
``python*``) gets a version, the first line of what ``<program>
--version`` (``-version`` for ``java``) prints, probed once per path per
trial under ``suspended()``, with no input and a timeout; any other
program is never run to probe it, and has no version. A shared library
loaded through ``ctypes`` (the ``ctypes.dlopen`` audit event), which no
import finder sees, gets a row the same way, without a version, when the
name it is loaded by is a path (absolute, or relative to the current
directory); a bare name (``libm.so.6``) is found by the loader's own
search, which is not reproduced here. ``-b`` (``bypass_modules``) skips
all of this and keeps the file accesses; a launch that fails to start
takes its rows with it.

What is not covered: the children of ``os.fork`` and ``multiprocessing``
(#375, #379), launches made by C code, nested launches (the child's own
children) as launches of their own (under strace, their files and the
programs they run in the project are the launch's), a launch that failed
to start (nothing ran: its accesses are
dropped), and on ``os.exec`` nothing is stored (#377): the pending
launches are only closed in memory. Calls of the standard library that
run a program (``platform.architecture`` runs ``file``) are recorded as
any other launch, which is harmless.
"""

import hashlib
import inspect
import os
import re
import shlex
import shutil

# Patches Popen's functions while a collection traces; starts no process
import subprocess  # nosec B404
import sys
import tempfile
import threading
import weakref
from contextlib import contextmanager
from functools import wraps

from ...persistence import content
from ...utils.io import print_error
from .external_provjson import (
    changed_documents,
    documents_in,
    is_prov_json,
    read_prov_json,
)
from .external_strace import parse_log, strace_command

MODES = ("none", "argv", "strace")
DEFAULT_MODE = "argv"
# The audit events the hook reads.
EVENTS = frozenset(
    {
        "subprocess.Popen",
        "os.system",
        "os.posix_spawn",
        "os.spawn",
        "os.exec",
        "ctypes.dlopen",
    }
)
# Entries of the project above which the snapshot is disabled for the trial.
SNAPSHOT_CAP = 20000
# Directories the snapshot does not enter.
SKIPPED_DIRECTORIES = frozenset({".noworkflow", ".git", "__pycache__"})
# Directories of installed libraries: what a process loads from them (a
# virtual environment inside the project) is no file the trace records.
LIBRARY_DIRECTORIES = frozenset({"site-packages", "dist-packages"})
# The mode of an access to a file that existed and that a process changed
# without naming it (strace backend): its content before is unknown, and
# `now restore` must not take the missing hash for a file that did not
# exist (`unrecorded_before`).
UNRECORDED_MODE = "r+"
# Shell words that separate two commands.
SEPARATORS = frozenset({"|", "||", "&&", ";", "&"})
# Redirections: the operator and the mode of the file it names.
REDIRECTIONS = (
    ("&>>", "a"),
    ("&>", "w"),
    (">>", "a"),
    (">", "w"),
    ("<", "r"),
)
# Executables above this size are not stored: their code block is a
# placeholder with the SHA-1 of the file (#203). The default of
# `now run --executable-cap` (#463).
EXECUTABLE_CAP = 16 * 1024 * 1024
# The programs whose version is probed (#203), by the name the command
# line gives them; any other program is never run to probe it. On Windows
# the comparison ignores case and a trailing ".exe".
PROBED = frozenset(
    {
        "Rscript",
        "R",
        "julia",
        "bash",
        "perl",
        "node",
        "ruby",
        "java",
        "gcc",
        "cc",
        "clang",
        "g++",
        "make",
        "octave",
    }
)
# python, python3, python3.15, pythonw: probed as well.
PYTHON_NAME = re.compile(r"python[0-9.]*w?\Z")
# The code block of an executable above EXECUTABLE_CAP: not its bytes,
# which `now restore` must never write in its place.
PLACEHOLDER = "<noWorkflow: executable not stored; sha1={}; size={}>"
PLACEHOLDER_PREFIX = PLACEHOLDER.split("{")[0].encode("ascii")
# Seconds a version probe may take, and the length of the version kept.
PROBE_TIMEOUT = 5
VERSION_LENGTH = 200
# The messages the tracer prints on stderr, once per trial each.
SNAPSHOT_WARNING = (
    "the project has more than {} entries: files that external processes "
    "create without naming them on the command line are not recorded in "
    "this trial".format(SNAPSHOT_CAP)
)
STRACE_WARNING = "--external-tracer strace {}: falling back to argv"
STRACE_NOT_LINUX = "runs on Linux only"
STRACE_MISSING = "needs strace on the PATH"
STRACE_FAILS = "cannot trace here ({})"
STRACE_EMPTY_LOG = "its log shows no process"
PROV_JSON_WARNING = "the PROV-JSON {} was not read: {}"
# The program of the strace backend, looked up in the PATH.
STRACE_PROGRAM = "strace"
# The shell of `shell=True` and of os.system on POSIX.
POSIX_SHELL = "/bin/sh"
# Arguments of Popen with which a launch is not run under strace: the
# process would run as another user, who cannot write the log.
UNWRAPPED_POPEN = ("user", "group", "extra_groups")


class ExternalProcess:
    """One launch: its command line, where it is attached and what it
    exchanged

    ``accesses`` are the ``FileAccessLW`` created at the launch, for the
    files that existed then; ``candidates`` the output candidates, as
    ``(name, resolved path, declared mode or None)``, which become
    accesses if the file exists at the end; ``before`` the snapshot of the
    project, or None. ``activation`` is the closest active activation at
    the launch, where the accesses go; ``call_activation`` the innermost
    one, which closing finalizes a launch that ``finalize_on_close``.
    """

    # pylint: disable=too-many-instance-attributes, too-few-public-methods

    def __init__(self, kind, command, cwd, activation, call_activation, checkpoint):
        # pylint: disable=too-many-arguments
        self.kind = kind
        self.command = command
        self.cwd = cwd
        self.activation = activation
        self.call_activation = call_activation
        self.checkpoint = checkpoint
        self.accesses = []
        self.candidates = []
        self.before = None
        self.finalize_on_close = kind == "system"
        self.popen = None
        self.finished = False
        self.returncode = None
        # The keys of the executables this launch added to the module
        # table (#203), which a launch that fails to start takes back.
        self.executables = []
        # The directory relative paths of the launch resolve against, and
        # the log of the strace backend (#206), or None.
        self.base = cwd or os.getcwd()
        self.log = None
        # The real paths of the files the launch wrote, and the documents
        # of R provenance tools in the project at the launch, with their
        # signature (#207).
        self.written = []
        self.documents = {}


class ExternalProcessTracer:
    """Records the launches of one collector (``Collector.external``)"""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, collector):
        self.collector = collector
        self.mode = DEFAULT_MODE
        self.project_dir = None
        self.started = False
        self.pending = []
        self.by_popen = weakref.WeakKeyDictionary()
        self.unbound = {}
        self.waiting_close = set()
        self.suspend_depth = 0
        self.snapshot_cap = SNAPSHOT_CAP
        self.snapshot_disabled = False
        self.warned = set()
        self.failures = []
        self.lock = threading.RLock()
        # (real path, size, mtime_ns) -> (module id, code block id) of the
        # executables recorded in this trial, and the probed versions by
        # path (#203).
        self.executables = {}
        self.versions = {}
        self.executable_cap = EXECUTABLE_CAP
        # The strace backend (#206): the program, the directory of the
        # logs and the launches rewritten on each thread whose audit event
        # has not come yet.
        self.strace = None
        self.log_dir = None
        self.log_count = 0
        self.wrapping = {}

    # --- lifecycle ---------------------------------------------------------

    def start(self, metascript):
        """Start tracing for a collection, with the mode of ``metascript``

        ``none`` records nothing; ``strace`` falls back to ``argv`` with a
        warning where it cannot trace (``prepare_strace``).
        """
        mode = getattr(metascript, "external_tracer", DEFAULT_MODE) or DEFAULT_MODE
        if mode not in MODES:
            raise ValueError("unknown external tracer {!r}".format(mode))
        if mode == "strace":
            reason = self.prepare_strace()
            if reason is not None:
                self.warn(STRACE_WARNING.format(reason))
                mode = "argv"
        self.mode = mode
        self.project_dir = getattr(metascript, "dir", None) or None
        self.executable_cap = getattr(metascript, "executable_cap", EXECUTABLE_CAP)
        if mode == "none" or self.started:
            return
        install_hook()
        _push(self)
        patch_popen()
        self.started = True

    def stop(self):
        """Stop tracing: the patch leaves, the hook goes inert

        The launches still pending are finalized by ``finalize_pending``
        when the trial is stored.
        """
        if not self.started:
            return
        self.started = False
        unpatch_popen()
        _pop(self)

    def prepare_strace(self):
        """Find a ``strace`` that can trace here: None when there is one,
        the reason to fall back to ``argv`` otherwise"""
        if not sys.platform.startswith("linux"):
            return STRACE_NOT_LINUX
        strace = shutil.which(STRACE_PROGRAM)
        if strace is None:
            return STRACE_MISSING
        strace = os.path.abspath(strace)
        with self.suspended(), content.use_safe_open():
            detail = strace_support(strace)
        if detail is not None:
            return STRACE_FAILS.format(detail)
        self.strace = strace
        return None

    @contextmanager
    def suspended(self):
        """Launches made inside are noWorkflow's own and are not recorded"""
        with self.lock:
            self.suspend_depth += 1
        try:
            yield
        finally:
            with self.lock:
                self.suspend_depth -= 1

    def warn(self, message):
        """Print a warning on stderr once per tracer"""
        if message not in self.warned:
            self.warned.add(message)
            print_error(message)

    # --- the hook ----------------------------------------------------------

    def event(self, event, args):
        """An audit event of ``EVENTS``, while this tracer is current

        A failure of the tracer never reaches the script: it is reported
        on stderr and kept in ``failures``.
        """
        if self.suspend_depth or content.should_use_safe_open():
            return
        try:
            if event == "subprocess.Popen":
                self.popen_event(*args)
            elif event == "os.system":
                wrap = self.unwrap()
                if wrap is not None:
                    launch = self.launch("system", None, None, shell_command=wrap[0])
                    self.attach_log(launch, wrap[2])
                else:
                    self.launch("system", None, None, shell_command=as_text(args[0]))
            elif event == "os.posix_spawn":
                self.launch("posix_spawn", args[1], None, program=args[0], env=args[2])
            elif event == "os.spawn":
                launch = self.launch(
                    "spawn", args[2], None, program=args[1], env=args[3]
                )
                if launch is not None:
                    launch.finalize_on_close = args[0] == getattr(os, "P_WAIT", 0)
            elif event == "os.exec":
                self.close_all()
            elif event == "ctypes.dlopen":
                self.library_loaded(args[0])
        except Exception as error:  # pylint: disable=broad-except
            self.failures.append(error)
            self.warn(
                "the external process tracer failed and recorded nothing of "
                "a launch: {}: {}".format(type(error).__name__, error)
            )

    def popen_event(self, executable, args, cwd, env):
        """``subprocess.Popen``: an argument list, or the shell's line

        ``executable`` is what the process runs: ``executable=`` when given,
        the first word otherwise (POSIX; None on Windows). A launch the
        strace backend rewrote is read as the script gave it.
        """
        wrap = self.unwrap()
        if wrap is not None:
            line, words, log = wrap
            if line is not None:
                launch = self.launch("popen", None, cwd, shell_command=line, env=env)
            else:
                launch = self.launch("popen", words, cwd, env=env)
            self.attach_log(launch, log)
            return launch
        if isinstance(args, (str, bytes)):
            # Windows: Popen joins the list into one string (list2cmdline),
            # and with shell=True wraps it as `cmd.exe /c "line"`.
            line = as_text(args)
            inner = windows_shell_command(line)
            if inner is not None:
                return self.launch("popen", None, cwd, shell_command=inner, env=env)
            return self.launch(
                "popen",
                split_windows_command_line(line),
                cwd,
                program=executable,
                env=env,
            )
        words = [as_text(word) for word in args]
        if (
            len(words) >= 3
            and words[1] == "-c"
            and os.path.basename(words[0]).endswith("sh")
        ):
            return self.launch("popen", None, cwd, shell_command=words[2], env=env)
        return self.launch("popen", words, cwd, program=executable, env=env)

    # --- the strace backend (#206) -----------------------------------------

    def can_wrap(self):
        """Whether a launch made now runs under strace"""
        return (
            self.mode == "strace"
            and self.strace is not None
            and not self.suspend_depth
            and not content.should_use_safe_open()
            and self.collector.current_activation() is not None
        )

    def wrap_popen(self, bound):
        """Rewrite the bound arguments of a ``Popen.__init__`` to run under
        strace, and keep what the script gave for the audit event; False
        when the launch is left as it is"""
        if not self.can_wrap():
            return False
        arguments = bound.arguments
        if any(arguments.get(name) is not None for name in UNWRAPPED_POPEN):
            return False
        args = arguments.get("args")
        executable = arguments.get("executable")
        shell = arguments.get("shell", False)
        parts = [args] if isinstance(args, (str, bytes, os.PathLike)) else list(args)
        if not parts:
            return False
        if shell:
            line = as_text(parts[0])
            argv = [executable or POSIX_SHELL, "-c"] + parts
            words = None
        elif executable is not None:
            return False
        else:
            line = None
            argv = parts
            words = [as_text(word) for word in parts]
        log = self.new_log()
        arguments["args"] = strace_command(self.strace, log, argv)
        arguments["shell"] = False
        arguments["executable"] = None
        self.wrapping[threading.get_ident()] = (line, words, log)
        return True

    def wrap_system(self, command):
        """The line ``os.system`` runs instead of ``command``, under
        strace, or None when the launch is left as it is"""
        if not self.can_wrap():
            return None
        line = as_text(command)
        log = self.new_log()
        # `exec`: the shell becomes strace, whose status is the command's
        wrapped = "exec " + shlex.join(
            strace_command(self.strace, log, [POSIX_SHELL, "-c", line])
        )
        self.wrapping[threading.get_ident()] = (line, None, log)
        return wrapped

    def unwrap(self):
        """The launch this thread rewrote, ``(line, words, log)``, which
        the audit event that follows reads; None when there is none"""
        return self.wrapping.pop(threading.get_ident(), None)

    def new_log(self):
        """A path for the log of one launch, in a directory of this
        tracer, created on the first launch"""
        with self.lock:
            if self.log_dir is None:
                # tempfile opens a file to test the directory: not the
                # script's, so the collector's os.open steps aside
                with content.use_safe_open():
                    self.log_dir = tempfile.mkdtemp(prefix="now-strace-")
            self.log_count += 1
            return os.path.join(self.log_dir, "{}.log".format(self.log_count))

    def attach_log(self, launch, log):
        """Give the launch its log; a launch that is not recorded (no
        activation) has its log removed"""
        if launch is None:
            remove_file(log)
            return
        launch.log = log

    def remove_logs(self):
        """Remove the directory of the logs, when every log was read"""
        with self.lock:
            log_dir, self.log_dir = self.log_dir, None
        if log_dir is not None:
            # rmtree opens the directory through os.open
            with content.use_safe_open():
                shutil.rmtree(log_dir, ignore_errors=True)

    def record_trace(self, launch, recorded):
        """Add the files the strace log of a launch shows, under the
        project directory and the launch's directory, that ``recorded``
        (the real paths the launch already accounts for) does not have;
        the programs it executed there become modules"""
        log, launch.log = launch.log, None
        try:
            with content.std_open(log, "rb") as handle:
                text = handle.read().decode("utf-8", "surrogateescape")
        except OSError:
            return
        finally:
            remove_file(log)
        trace = parse_log(text, launch.base)
        roots = [
            os.path.realpath(root) for root in (self.project_dir, launch.base) if root
        ]
        executed = set()
        for path in trace.executed:
            real = os.path.realpath(path)
            executed.add(os.path.normcase(real))
            if (
                self.records_modules()
                and traced_file(real, roots)
                and is_regular_file(real)
            ):
                self.add_executable(program_name(path), real, probe=False)
        self.record_opened(launch, trace.opened, recorded, roots, executed)

    def record_opened(self, launch, opened, recorded, roots, executed=frozenset()):
        """Add the files of ``opened`` (``{path: written}``, from a strace
        log or a PROV-JSON document) under ``roots`` that ``recorded`` does
        not have: a read with the content at the end before and after; a
        write to a file the snapshot did not have at the launch, a file
        the process created; a write to any other, a file whose content
        before is unknown (``UNRECORDED_MODE``)"""
        # pylint: disable=too-many-arguments
        before = None
        if launch.before is not None:
            before = {os.path.normcase(path) for path in launch.before}
        collector = self.collector
        for path, write in opened.items():
            real = os.path.realpath(path)
            key = os.path.normcase(real)
            if key in recorded or key in executed:
                continue
            if not traced_file(real, roots) or not is_regular_file(real):
                continue
            recorded.add(key)
            name = relative_to_cwd(real)
            if write and before is not None and key not in before:
                self.add_written(launch, name, real, "w")
                continue
            if write:
                self.add_unrecorded(launch, name, real)
            else:
                access = collector.add_file_access(
                    name, launch.activation, launch.checkpoint, path=real
                )
                access.content_hash_after = access.content_hash_before
                access.mode = "r"
                access.done = True

    def add_unrecorded(self, launch, name, real):
        """An access to a file that existed and that the process changed,
        whose content before is unknown"""
        access = self.collector.add_file_access(
            name, launch.activation, launch.checkpoint, path=None
        )
        access.content_hash_after = hash_file(real)
        access.mode = UNRECORDED_MODE
        access.done = True
        launch.written.append(real)
        return access

    # --- R provenance tools (#207) -----------------------------------------

    def link_prov_json(self, launch, recorded):
        """Read the PROV-JSON documents the launch wrote and add the files
        they name, under the project directory or the launch's directory,
        as accesses of the launch; a document that cannot be read is
        reported on stderr, never raised"""
        documents = [path for path in launch.written if is_prov_json(path)]
        if not documents:
            return
        roots = [
            os.path.realpath(root) for root in (self.project_dir, launch.base) if root
        ]
        for document in dict.fromkeys(documents):
            try:
                with content.std_open(document, "rb") as handle:
                    text = handle.read().decode("utf-8", "surrogateescape")
                opened = read_prov_json(text, launch.base)
            except (OSError, ValueError) as error:
                self.warn(PROV_JSON_WARNING.format(relative_to_cwd(document), error))
                continue
            self.record_opened(launch, opened, recorded, roots)

    # --- launches ----------------------------------------------------------

    def launch(self, kind, words, cwd, shell_command=None, program=None, env=None):
        """Record a launch: the files it names now, the candidates, the
        snapshot and the programs it runs (``program``, or the first word;
        for a shell line, the first word of each command), resolved with
        ``env``; returns the ``ExternalProcess``, or None when nothing is
        collecting"""
        # pylint: disable=too-many-arguments
        collector = self.collector
        activation = collector.current_activation()
        if activation is None:
            return None
        cwd = os.path.abspath(as_text(cwd)) if cwd else None
        base = cwd or os.getcwd()
        if shell_command is not None:
            # A keyword of parse_command, which reads the line: no shell runs here
            commands = parse_command(shell_command, shell=True)  # nosec B604
        else:
            commands = parse_command(words)
        launch = ExternalProcess(
            kind,
            shell_command if shell_command is not None else words,
            cwd,
            activation,
            collector.last_activation,
            collector.get_time(),
        )
        seen = set()
        for command in commands:
            for name, mode in classify_tokens(command, base):
                resolved = os.path.join(base, name)
                key = os.path.normcase(os.path.realpath(resolved))
                if key in seen:
                    continue
                seen.add(key)
                recorded = self.recorded_name(name, cwd)
                if os.path.isfile(resolved):
                    access = collector.add_file_access(
                        recorded, activation, launch.checkpoint, path=resolved
                    )
                    launch.accesses.append((access, resolved, mode))
                else:
                    launch.candidates.append((recorded, resolved, mode))
        launch.before = self.snapshot(cwd)
        if launch.before is not None:
            launch.documents = documents_in(launch.before)
        if shell_command is not None:
            programs = [command[0][0] for command in commands if command[0]]
        else:
            programs = [program or (words[0] if words else None)]
        # Before the launch is bound: a version probe starts a process of
        # its own, whose Popen must find nothing to bind on this thread.
        self.record_programs(launch, programs, base, env)
        with self.lock:
            self.pending.append(launch)
            if kind == "popen":
                self.unbound[threading.get_ident()] = launch
            if launch.finalize_on_close:
                self.waiting_close.add(id(launch.call_activation))
        return launch

    def recorded_name(self, name, cwd):
        """The name an access gets: the word as the command line gives it,
        or, for a launch with its own ``cwd``, the path as the script's
        own directory sees it"""
        if cwd is None:
            return name
        resolved = os.path.join(cwd, name)
        return relative_to_cwd(resolved)

    def bind(self, popen):
        """Attach the launch of the ``Popen.__init__`` that just returned
        on this thread to its ``Popen``"""
        with self.lock:
            launch = self.unbound.pop(threading.get_ident(), None)
            if launch is None:
                return
            launch.popen = popen
            self.by_popen[popen] = launch

    def launch_failed(self):
        """``Popen.__init__`` raised on this thread: the process never ran,
        so the launch and its accesses are dropped"""
        with self.lock:
            launch = self.unbound.pop(threading.get_ident(), None)
            if launch is None:
                return
            self.discard(launch)

    def discard(self, launch):
        """Forget a launch and the accesses it created"""
        with self.lock:
            launch.finished = True
            if launch in self.pending:
                self.pending.remove(launch)
            self.waiting_close.discard(id(launch.call_activation))
        store = self.collector.file_accesses
        for access, _, _ in launch.accesses:
            del store[access.id]
        launch.accesses = []
        if launch.log is not None:
            remove_file(launch.log)
            launch.log = None
        metascript = self.collector.metascript
        for key in launch.executables:
            with self.lock:
                ids = self.executables.pop(key, None)
            if ids is None:
                continue
            module_id, code_id = ids
            del metascript.modules_store[module_id]
            del metascript.code_components_store[code_id]
            del metascript.code_blocks_store[code_id]
        launch.executables = []

    # --- the programs (#203) -------------------------------------------------

    def records_modules(self):
        """Whether the programs go to the module table: not under ``-b``"""
        return not getattr(self.collector.metascript, "bypass_modules", True)

    def record_programs(self, launch, programs, base, env):
        """Add the programs of a launch to the module table; a program
        that resolves to no file (a shell builtin, a missing program) is
        skipped, and a failure is reported, never raised"""
        if not self.records_modules():
            return
        for program in programs:
            try:
                path = resolve_program(program, base, env)
                if path is None:
                    continue
                key = self.add_executable(program_name(program), path, probe=True)
            except Exception as error:  # pylint: disable=broad-except
                self.failures.append(error)
                self.warn(
                    "the external process tracer recorded no module for a "
                    "program: {}: {}".format(type(error).__name__, error)
                )
                continue
            if key is not None:
                launch.executables.append(key)

    def library_loaded(self, name):
        """``ctypes.dlopen``: a library loaded by a path is a module"""
        if not self.records_modules():
            return
        name = as_text(name)
        if not name or not os.path.dirname(name):
            return
        path = os.path.realpath(os.path.join(os.getcwd(), name))
        if is_regular_file(path):
            self.add_executable(os.path.basename(name), path, probe=False)

    def add_executable(self, name, path, probe):
        """A ``module`` row for the file at ``path`` (a real path), with a
        binary code block and, when ``probe`` and the name is in the
        allowlist, a version; returns its key, or None when this file, as
        it is now, already has a row in the trial"""
        info = os.stat(path)
        key = (os.path.normcase(path), info.st_size, info.st_mtime_ns)
        with self.lock:
            if key in self.executables:
                return None
            self.executables[key] = None
        try:
            version = self.version_of(name, path) if probe else None
            data = executable_content(path, self.executable_cap)
            metascript = self.collector.metascript
            _, code_id = metascript.definition.create_code_block(
                data, path, "module", True, False
            )
            module_id = metascript.deployment.add_module(
                name, version, path, code_id, False, None
            )
        except BaseException:
            with self.lock:
                self.executables.pop(key, None)
            raise
        with self.lock:
            self.executables[key] = (module_id, code_id)
        return key

    def version_of(self, name, path):
        """The probed version of a program of the allowlist, once per path
        per trial; None for any other program, which is not run"""
        flag = probe_flag(name)
        if flag is None:
            return None
        cache_key = os.path.normcase(path)
        if cache_key not in self.versions:
            # The probe's own opens (os.devnull for its stdin) are not the
            # script's: safe open makes the collector's wrappers step aside
            with self.suspended(), content.use_safe_open():
                self.versions[cache_key] = probe_version(path, flag)
        return self.versions[cache_key]

    def completed(self, popen):
        """``wait`` or ``poll`` saw the process end"""
        launch = self.by_popen.pop(popen, None)
        if launch is not None and not launch.finished:
            self.finalize(launch, popen.returncode)

    def activation_closed(self, activation):
        """Finalize the launches made by a call that just returned
        (``os.system``, a waiting ``os.spawn``)"""
        if id(activation) not in self.waiting_close:
            return
        with self.lock:
            self.waiting_close.discard(id(activation))
            launches = [
                launch
                for launch in self.pending
                if launch.finalize_on_close and launch.call_activation is activation
            ]
        for launch in launches:
            self.finalize(launch)

    def finalize_pending(self, final):
        """Finalize what is still pending: everything when the trial is
        stored (``final``), on a partial save only the launches whose
        process is known to have ended"""
        with self.lock:
            launches = [
                launch
                for launch in self.pending
                if final
                or (launch.popen is not None and launch.popen.returncode is not None)
            ]
        for launch in launches:
            returncode = launch.popen.returncode if launch.popen is not None else None
            self.finalize(launch, returncode)
        if final:
            self.remove_logs()

    def close_all(self):
        """``os.exec``: the image is about to be replaced, nothing will be
        stored (#377); the pending launches are closed in memory"""
        with self.lock:
            launches = list(self.pending)
        for launch in launches:
            self.finalize(launch)

    def finalize(self, launch, returncode=None):
        """The process ended (or the trial did): hash the files after it,
        infer the modes, record the candidates and the new files"""
        with self.lock:
            if launch.finished:
                return
            launch.finished = True
            launch.returncode = returncode
            if launch in self.pending:
                self.pending.remove(launch)
            self.waiting_close.discard(id(launch.call_activation))
        recorded = set()
        for access, resolved, declared in launch.accesses:
            after = hash_file(resolved)
            access.content_hash_after = after
            access.mode = infer_mode(access.content_hash_before, after, declared)
            access.done = True
            real = os.path.realpath(resolved)
            recorded.add(os.path.normcase(real))
            if access.mode != "r":
                launch.written.append(real)
        for name, resolved, declared in launch.candidates:
            if not os.path.isfile(resolved):
                continue
            self.add_written(launch, name, resolved, declared or "w")
            recorded.add(os.path.normcase(os.path.realpath(resolved)))
        # A document an R provenance tool rewrote: rdtLite deletes and
        # recreates its directory, which the set of paths does not show.
        for path in changed_documents(launch.documents):
            key = os.path.normcase(os.path.realpath(path))
            if key in recorded or key in self.recorded_since(launch.checkpoint):
                continue
            recorded.add(key)
            self.add_unrecorded(launch, relative_to_cwd(path), path)
        if launch.log is not None:
            self.record_trace(launch, recorded)
        after = self.snapshot(launch.cwd) if launch.before is not None else None
        for path in sorted(after - launch.before) if after is not None else ():
            key = os.path.normcase(os.path.realpath(path))
            if key in recorded or key in self.recorded_since(launch.checkpoint):
                continue
            recorded.add(key)
            self.add_written(launch, relative_to_cwd(path), path, "w")
        # Last, once every file the launch wrote is known.
        try:
            self.link_prov_json(launch, recorded)
        except Exception as error:  # pylint: disable=broad-except
            self.failures.append(error)
            self.warn(
                "the external process tracer recorded no file of a PROV-JSON "
                "document: {}: {}".format(type(error).__name__, error)
            )

    def add_written(self, launch, name, resolved, mode):
        """An access to a file the process created: no content before"""
        access = self.collector.add_file_access(
            name, launch.activation, launch.checkpoint, path=None
        )
        access.content_hash_after = hash_file(resolved)
        access.mode = mode
        access.done = True
        launch.written.append(os.path.realpath(resolved))
        return access

    def recorded_since(self, checkpoint):
        """The real paths of the accesses recorded since ``checkpoint``,
        by the script's own opens or by other launches: a file they
        account for is not a file this launch created"""
        found = set()
        for access in self.collector.file_accesses.values():
            if access.checkpoint >= checkpoint:
                found.add(os.path.normcase(os.path.realpath(access.name)))
        return found

    # --- the snapshot ------------------------------------------------------

    def snapshot(self, cwd):
        """The files under the project, the current directory and ``cwd``,
        or None when the snapshot is disabled"""
        if self.snapshot_disabled:
            return None
        roots = [self.project_dir, os.getcwd(), cwd]
        found = snapshot(roots, self.snapshot_cap)
        if found is None:
            self.snapshot_disabled = True
            self.warn(SNAPSHOT_WARNING)
        return found


# --- the hook and the patch, once per process --------------------------------

_installed = False
_stack = []
_current = None
_originals = None
_patch_depth = 0
_lock = threading.Lock()
# strace path -> why it cannot trace, or None, measured once (#206).
_strace_support = {}


def _audit(event, args):
    """The audit hook: inert unless a tracer is current"""
    tracer = _current
    if tracer is None or event not in EVENTS:
        return
    tracer.event(event, args)


@contextmanager
def suspended():
    """Launches made inside are noWorkflow's own and are not recorded by
    the tracer that is tracing now, if any (the ``now_vis()`` and
    ``now_notebook()`` builtins of the debugger start a process)"""
    tracer = _current
    if tracer is None:
        yield
        return
    with tracer.suspended():
        yield


def install_hook():
    """Install the audit hook, once per process (it cannot be removed)"""
    global _installed  # pylint: disable=global-statement
    with _lock:
        if not _installed:
            sys.addaudithook(_audit)
            _installed = True


def hook_installed():
    """Whether the audit hook is installed in this process"""
    return _installed


def current():
    """The tracer that is tracing now, or None"""
    return _current


def _push(tracer):
    global _current  # pylint: disable=global-statement
    with _lock:
        _stack.append(tracer)
        _current = tracer


def _pop(tracer):
    global _current  # pylint: disable=global-statement
    with _lock:
        if tracer in _stack:
            _stack.remove(tracer)
        _current = _stack[-1] if _stack else None


def patch_popen():
    """Patch ``Popen.__init__``, ``wait`` and ``poll`` to tell the current
    tracer when a launch is bound and when its process ended, and
    ``__init__`` and ``os.system`` to let the strace backend rewrite a
    launch (#206); nested collections patch once"""
    global _originals, _patch_depth  # pylint: disable=global-statement
    with _lock:
        _patch_depth += 1
        if _patch_depth > 1:
            return
        popen = subprocess.Popen
        original_init, original_wait, original_poll = (
            popen.__init__,
            popen.wait,
            popen.poll,
        )
        original_system = getattr(os, "system", None)
        _originals = (original_init, original_wait, original_poll, original_system)
        signature = inspect.signature(original_init)

        @wraps(original_init)
        def __init__(self, *args, **kwargs):
            tracer = _current
            wrapped = False
            if tracer is not None:
                try:
                    bound = signature.bind(self, *args, **kwargs)
                except TypeError:
                    # The original raises the error the script expects
                    pass
                else:
                    wrapped = tracer.wrap_popen(bound)
                    if wrapped:
                        args, kwargs = bound.args[1:], bound.kwargs
            try:
                original_init(self, *args, **kwargs)
            except BaseException:
                if tracer is not None:
                    if wrapped:
                        tracer.unwrap()
                    tracer.launch_failed()
                raise
            if tracer is not None:
                if wrapped:
                    tracer.unwrap()
                tracer.bind(self)

        @wraps(original_wait)
        def wait(self, timeout=None):
            result = original_wait(self, timeout)
            tracer = _current
            if tracer is not None and self.returncode is not None:
                tracer.completed(self)
            return result

        @wraps(original_poll)
        def poll(self):
            result = original_poll(self)
            tracer = _current
            if tracer is not None and self.returncode is not None:
                tracer.completed(self)
            return result

        popen.__init__ = __init__
        popen.wait = wait
        popen.poll = poll
        if original_system is not None:

            @wraps(original_system)
            def system(command):
                tracer = _current
                line = tracer.wrap_system(command) if tracer is not None else None
                if line is None:
                    return original_system(command)
                try:
                    return original_system(line)
                finally:
                    tracer.unwrap()

            os.system = system


def unpatch_popen():
    """Put the original functions back when the last collection stops"""
    global _originals, _patch_depth  # pylint: disable=global-statement
    with _lock:
        if _patch_depth == 0:
            return
        _patch_depth -= 1
        if _patch_depth > 0:
            return
        popen = subprocess.Popen
        popen.__init__, popen.wait, popen.poll, original_system = _originals
        if original_system is not None:
            os.system = original_system
        _originals = None


def popen_patched():
    """Whether ``subprocess.Popen`` carries the tracer's patch now"""
    return _patch_depth > 0


# --- pure functions -----------------------------------------------------------


def as_text(value):
    """A command-line word as text: bytes and path-like objects decoded"""
    if value is None:
        return None
    if isinstance(value, bytes):
        return os.fsdecode(value)
    if isinstance(value, str):
        return value
    try:
        return os.fsdecode(os.fspath(value))
    except TypeError:
        return str(value)


def program_name(program):
    """The name of a program's module row: the last part of the word
    that names it, as the command line gives it (``./metrics`` is
    ``metrics``; a link keeps its own name, ``cc`` and not ``gcc``)"""
    program = as_text(program)
    return os.path.basename(program.rstrip("/" + os.sep)) or program


def resolve_program(program, cwd=None, env=None):
    """The real path of the program a launch runs, or None

    A name with a separator is relative to the launch's ``cwd`` (the
    current directory when None); a bare name is searched in the ``PATH``
    of ``env`` (the environment given to the process, the script's when
    None), as ``subprocess`` does; on Windows ``shutil.which`` adds the
    ``PATHEXT`` extensions. Only a regular file is a program.
    """
    program = as_text(program)
    if not program:
        return None
    if os.path.dirname(program):
        found = shutil.which(os.path.join(cwd or os.getcwd(), program))
    else:
        found = shutil.which(program, path=os.pathsep.join(os.get_exec_path(env)))
    if found is None:
        return None
    real = os.path.realpath(found)
    return real if is_regular_file(real) else None


def probe_flag(name, windows=None):
    """The flag that makes a program of the allowlist print its version
    (``-version`` for ``java``, ``--version`` otherwise), or None for a
    program outside it, which is never run to probe it"""
    if windows is None:
        windows = os.name == "nt"
    base = name
    known = name in PROBED
    if windows:
        base = name.lower()
        if base.endswith(".exe"):
            base = base[: -len(".exe")]
        known = base in {probed.lower() for probed in PROBED}
    if not known and not PYTHON_NAME.match(base):
        return None
    return "-version" if base == "java" else "--version"


def probe_version(path, flag, timeout=PROBE_TIMEOUT):
    """The first non-empty line of what ``path flag`` prints, on stdout
    or stderr, cut at ``VERSION_LENGTH``; None when it fails, times out
    or exits with another status than 0"""
    try:
        # A program of the allowlist, by its real path, with one flag and
        # no shell (probe_flag): the version probe of #203
        completed = subprocess.run(  # nosec B603
            [path, flag],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return first_line(completed.stdout)


def strace_support(strace, timeout=PROBE_TIMEOUT):
    """Why a ``strace`` cannot trace a process here, or None when it can;
    measured once per path per process

    It runs this interpreter on an empty program under ``strace``, which
    must exit with 0 and log the interpreter's ``execve``: in a container
    without ptrace strace fails, and under an emulator (Rosetta in a Linux
    VM on Apple silicon) it may exit with 0, an empty log and a program
    that did not run as asked.
    """
    if strace in _strace_support:
        return _strace_support[strace]
    # tempfile and rmtree open through os.open, which is not the script's
    with content.use_safe_open():
        log_dir = tempfile.mkdtemp(prefix="now-strace-")
    try:
        detail = probe_strace(strace, os.path.join(log_dir, "probe.log"), timeout)
    finally:
        with content.use_safe_open():
            shutil.rmtree(log_dir, ignore_errors=True)
    _strace_support[strace] = detail
    return detail


def probe_strace(strace, log, timeout):
    """Run the probe of ``strace_support``"""
    command = strace_command(strace, log, [sys.executable, "-c", ""])
    try:
        # strace by its path from shutil.which, running this interpreter
        # on an empty program: the probe of #206
        completed = subprocess.run(  # nosec B603
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return "{}: {}".format(type(error).__name__, error)
    if completed.returncode != 0:
        return first_line(completed.stderr) or "exit status {}".format(
            completed.returncode
        )
    try:
        with content.std_open(log, "rb") as handle:
            text = handle.read().decode("utf-8", "surrogateescape")
    except OSError:
        text = ""
    if not parse_log(text, os.getcwd()).executed:
        return STRACE_EMPTY_LOG
    return None


def traced_file(real, roots):
    """Whether a real path the strace log shows is one the trial records:
    under one of ``roots`` (real paths), outside ``SKIPPED_DIRECTORIES``
    and ``LIBRARY_DIRECTORIES``"""
    for root in roots:
        if real != root and not real.startswith(root.rstrip(os.sep) + os.sep):
            continue
        parts = os.path.relpath(real, root).split(os.sep)
        return not any(
            part in SKIPPED_DIRECTORIES or part in LIBRARY_DIRECTORIES
            for part in parts[:-1]
        )
    return False


def unrecorded_before(access):
    """Whether an access is to a file that existed and whose content
    before was not recorded (#206): ``UNRECORDED_MODE``, no content
    before and a content after. An open of the script that fails leaves
    no content before or after (a file that did not exist), whatever its
    mode"""
    return (
        access.mode == UNRECORDED_MODE
        and access.content_hash_before is None
        and access.content_hash_after is not None
    )


def remove_file(path):
    """Remove a file, if it is there"""
    try:
        os.remove(path)
    except OSError:
        pass


def first_line(output):
    """The first non-empty line of a program's output, cut at
    ``VERSION_LENGTH``, or None"""
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    for line in (output or "").splitlines():
        line = line.strip()
        if line:
            return line[:VERSION_LENGTH]
    return None


def executable_content(path, cap=EXECUTABLE_CAP):
    """The bytes of an executable for its code block: the file up to
    ``cap`` bytes; above it, or always when ``cap`` is 0, a placeholder
    with the size and the SHA-1 of the file, read in chunks, so that the
    code hash still follows the binary"""
    size = os.path.getsize(path)
    if 0 < cap and size <= cap:
        with content.std_open(path, "rb") as handle:
            return handle.read()
    digest = hashlib.sha1(usedforsecurity=False)
    with content.std_open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return PLACEHOLDER.format(digest.hexdigest(), size).encode("ascii")


def is_placeholder(data):
    """Whether stored content is the placeholder of an executable that was
    too large to store, rather than its bytes"""
    return isinstance(data, bytes) and data.startswith(PLACEHOLDER_PREFIX)


def split_command_line(text, windows=None):
    """The words of a shell command line, as the shell of the system
    reads them: shlex on POSIX (a line it rejects, an unbalanced quote,
    is split on spaces); on Windows, what cmd.exe runs for ``/c`` with
    the line (``strip_cmd_quotes``), split as the C runtime builds argv
    (``split_windows_command_line``). ``windows`` forces either system,
    for the tests."""
    if windows is None:
        windows = os.name == "nt"
    if windows:
        return split_windows_command_line(strip_cmd_quotes(text))
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return text.split()


def split_windows_command_line(text):
    """The words of a Windows command line, as the C runtime builds argv
    (the inverse of ``subprocess.list2cmdline``): whitespace separates
    the words, a quote opens or closes a span where it does not, ``2n``
    backslashes before a quote are ``n`` backslashes, ``2n+1`` are ``n``
    and a literal quote, two quotes inside a span are a literal quote,
    and backslashes elsewhere are literal"""
    words, current, in_quotes, started = [], [], False, False
    index, length = 0, len(text)
    while index < length:
        char = text[index]
        if char == "\\":
            end = index
            while end < length and text[end] == "\\":
                end += 1
            count = end - index
            started = True
            if end < length and text[end] == '"':
                current.append("\\" * (count // 2))
                if count % 2:
                    current.append('"')
                    index = end + 1
                else:
                    index = end
                continue
            current.append("\\" * count)
            index = end
            continue
        if char == '"':
            started = True
            if in_quotes and index + 1 < length and text[index + 1] == '"':
                current.append('"')
                index += 2
                continue
            in_quotes = not in_quotes
            index += 1
            continue
        if char in " \t" and not in_quotes:
            if started:
                words.append("".join(current))
                current, started = [], False
            index += 1
            continue
        current.append(char)
        started = True
        index += 1
    if started:
        words.append("".join(current))
    return words


# The characters cmd.exe treats specially between the two quotes of a line.
CMD_SPECIAL = frozenset("&<>()@^|")


def strip_cmd_quotes(line):
    """What cmd.exe runs for ``/c <line>`` (``os.system``, ``shell=True``):
    the quotes stay when the line has exactly two, with whitespace and no
    special character between them and the quoted text naming an
    executable file; otherwise, when the line starts with a quote, the
    first quote and the last one leave (the rule ``cmd /?`` states)"""
    if not line.startswith('"'):
        return line
    last = line.rfind('"')
    if last == 0:
        return line
    if line.count('"') == 2:
        inner = line[1:last]
        if (
            any(char.isspace() for char in inner)
            and not CMD_SPECIAL & set(inner)
            and is_regular_file(inner)
        ):
            return line
    return line[1:last] + line[last + 1 :]


def windows_shell_command(line):
    """The line a ``cmd.exe /c`` (or ``/k``) command line runs, or None
    when the line is not one: what ``Popen(shell=True)`` builds on
    Windows, ``COMSPEC /c "line"``"""
    words = split_windows_command_line(line)
    if len(words) < 3 or words[1].lower() not in ("/c", "/k"):
        return None
    marker = line.lower().find(words[1].lower() + " ")
    if marker < 0:
        return None
    return line[marker + len(words[1]) + 1 :].lstrip()


def parse_command(args, shell=False, windows=None):
    """The commands of a launch, each as ``(words, redirections)``

    ``args`` is an argument list (one command) or, with ``shell``, the
    line a shell runs: split into words, cut at ``|``, ``||``, ``&&``,
    ``;`` and ``&``, with the leading ``VAR=value`` words and ``env``
    (with its own assignments) dropped. ``redirections`` are ``(name,
    mode)`` pairs: ``w`` for ``>`` and ``&>``, ``a`` for ``>>``, ``r`` for
    ``<``; the operator may be attached to its target (``>out.txt``,
    ``2>err.txt``) or not. ``windows`` forces the system's rules for the
    line (``split_command_line``).
    """
    if not shell:
        words = [as_text(word) for word in args]
        return [(words, [])] if words else []
    commands = []
    current = []
    for word in split_command_line(as_text(args), windows):
        if word in SEPARATORS:
            commands.append(current)
            current = []
            continue
        if word.endswith(";") and len(word) > 1:
            current.append(word[:-1])
            commands.append(current)
            current = []
            continue
        current.append(word)
    commands.append(current)
    result = []
    for words in commands:
        parsed = parse_shell_words(words)
        if parsed is not None:
            result.append(parsed)
    return result


def parse_shell_words(words):
    """One shell command: its words without the environment prefix, and
    its redirections; None for an empty command"""
    words = list(words)
    while words and is_assignment(words[0]):
        words.pop(0)
    if words and words[0] == "env":
        words.pop(0)
        while words and is_assignment(words[0]):
            words.pop(0)
    kept = []
    redirections = []
    pending = None
    for word in words:
        if pending is not None:
            redirections.append((word, pending))
            pending = None
            continue
        operator, target, mode = redirection(word)
        if operator is None:
            kept.append(word)
        elif target:
            redirections.append((target, mode))
        else:
            pending = mode
    if not kept and not redirections:
        return None
    return (kept, redirections)


def is_assignment(word):
    """Whether a shell word is ``NAME=value``"""
    name, separator, _ = word.partition("=")
    return bool(separator) and name.isidentifier()


def redirection(word):
    """``(operator, target, mode)`` of a redirection word, or ``(None,
    None, None)``; the target is empty when it is the next word"""
    text = word
    descriptor = ""
    while text and text[0].isdigit():
        descriptor += text[0]
        text = text[1:]
    for operator, mode in REDIRECTIONS:
        if text.startswith(operator):
            target = text[len(operator) :]
            if operator == "<" and descriptor:
                return None, None, None
            if target.startswith("&"):
                # `2>&1`: a descriptor, not a file
                return None, None, None
            return descriptor + operator, target, mode
    return None, None, None


def looks_like_path(word):
    """Whether a word that names no file yet may name one the process
    creates: a separator, or an extension that is not a number"""
    if not word or word.startswith("-") or word in (".", "..") or "\0" in word:
        return False
    if "/" in word or os.sep in word or (os.altsep and os.altsep in word):
        return True
    root, extension = os.path.splitext(word)
    return bool(root) and len(extension) > 1 and not extension[1:].isdigit()


def classify_tokens(command, base):
    """The files a command names: ``[(name, declared mode or None)]``

    ``command`` is ``(words, redirections)`` of ``parse_command``; the
    program (``words[0]``) is never a file access (#203 records it as a
    module). A word, or the part after ``=`` of a ``--opt=file`` word,
    that names an existing regular file relative to ``base`` is a file,
    with no declared mode (inferred at the end); one that only looks like
    a path is an output candidate. A redirection target is a declared
    output (``w``, ``a``) or input (``r``).
    """
    words, redirections = command
    found = []
    seen = set()

    def add(name, mode):
        if name and name not in seen:
            seen.add(name)
            found.append((name, mode))

    for word in words[1:]:
        names = word_candidates(word)
        existing = [name for name in names if is_regular_file(os.path.join(base, name))]
        if existing:
            add(existing[0], None)
            continue
        # A candidate: what follows `=` before the whole word, so that
        # `OUT=f.txt` names f.txt and not `OUT=f.txt`.
        for name in reversed(names):
            if looks_like_path(name):
                add(name, None)
                break
    for name, mode in redirections:
        add(name, mode)
    return found


def word_candidates(word):
    """The names a word may carry: itself, and what follows ``=``"""
    names = [word]
    if "=" in word and not word.startswith("="):
        names.append(word.split("=", 1)[1])
    return [name for name in names if name and not name.startswith("-")]


def is_regular_file(path):
    """``os.path.isfile`` that never raises (a NUL in a word, a path too
    long)"""
    try:
        return os.path.isfile(path)
    except (OSError, ValueError):
        return False


def infer_mode(before, after, declared=None):
    """The mode of an access from the hashes around the process

    A declared mode (a redirection) wins. Otherwise: no content before, a
    file now: ``w``; the same content: ``r``; another content: ``r+``
    (the dataflow draws a read and a write edge for ``+``); gone: ``r``
    with no content after.
    """
    if declared:
        return declared
    if before is None:
        return "w"
    if after is None or after == before:
        return "r"
    return "r+"


def hash_file(path):
    """The hash of a regular file's content, put in the content store, or
    None when there is no such file"""
    if not is_regular_file(path):
        return None
    with content.std_open(path, "rb") as handle:
        return content.put(handle.read(), path)


def relative_to_cwd(path):
    """A path as the script's own directory sees it: relative to the
    current directory when under it, absolute otherwise"""
    cwd = os.getcwd()
    real = os.path.realpath(path)
    try:
        relative = os.path.relpath(real, os.path.realpath(cwd))
    except ValueError:
        # Windows: another drive
        return path
    if relative.startswith(os.pardir):
        return path if os.path.isabs(path) else real
    return relative


def snapshot(roots, cap=SNAPSHOT_CAP):
    """The regular files under ``roots`` (real paths, each root once),
    or None when they exceed ``cap`` entries

    Symbolic links are not followed, and ``SKIPPED_DIRECTORIES`` are not
    entered. A root that does not exist is skipped.
    """
    found = set()
    seen_roots = set()
    budget = cap
    for root in roots:
        if not root:
            continue
        real = os.path.realpath(root)
        if real in seen_roots or not os.path.isdir(real):
            continue
        seen_roots.add(real)
        stack = [real]
        while stack:
            directory = stack.pop()
            try:
                entries = list(os.scandir(directory))
            except OSError:
                continue
            for entry in entries:
                budget -= 1
                if budget < 0:
                    return None
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIPPED_DIRECTORIES:
                            stack.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        found.add(entry.path)
                except OSError:
                    continue
    return found
