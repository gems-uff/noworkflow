# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""External processes a traced script starts: the call boundary and the
files exchanged with them (#202)

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
on the command line and is modified by the process is not seen: with no
hash before it, ``restore`` would delete it. That is the limit of the
``argv`` backend; the optional tracer backend of #206 lifts it.

What is not covered: the children of ``os.fork`` and ``multiprocessing``
(#375, #379), launches made by C code, nested launches (the child's own
children), a launch that failed to start (nothing ran: its accesses are
dropped), and on ``os.exec`` nothing is stored (#377): the pending
launches are only closed in memory. Calls of the standard library that
run a program (``platform.architecture`` runs ``file``) are recorded as
any other launch, which is harmless.
"""

import os
import shlex

# Patches Popen's functions while a collection traces; starts no process
import subprocess  # nosec B404
import sys
import threading
import weakref
from contextlib import contextmanager
from functools import wraps

from ...persistence import content
from ...utils.io import print_error

MODES = ("none", "argv", "strace")
DEFAULT_MODE = "argv"
# The audit events the hook reads.
EVENTS = frozenset(
    {"subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn", "os.exec"}
)
# Entries of the project above which the snapshot is disabled for the trial.
SNAPSHOT_CAP = 20000
# Directories the snapshot does not enter.
SKIPPED_DIRECTORIES = frozenset({".noworkflow", ".git", "__pycache__"})
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
# The messages the tracer prints on stderr, once per trial each.
SNAPSHOT_WARNING = (
    "the project has more than {} entries: files that external processes "
    "create without naming them on the command line are not recorded in "
    "this trial".format(SNAPSHOT_CAP)
)
STRACE_WARNING = (
    "--external-tracer strace is not available yet (#206): falling back to argv"
)


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

    # --- lifecycle ---------------------------------------------------------

    def start(self, metascript):
        """Start tracing for a collection, with the mode of ``metascript``

        ``none`` records nothing; ``strace`` falls back to ``argv`` with a
        warning until #206 lands.
        """
        mode = getattr(metascript, "external_tracer", DEFAULT_MODE) or DEFAULT_MODE
        if mode not in MODES:
            raise ValueError("unknown external tracer {!r}".format(mode))
        if mode == "strace":
            self.warn(STRACE_WARNING)
            mode = "argv"
        self.mode = mode
        self.project_dir = getattr(metascript, "dir", None) or None
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
                self.launch("system", None, None, shell_command=as_text(args[0]))
            elif event == "os.posix_spawn":
                self.launch("posix_spawn", args[1], None)
            elif event == "os.spawn":
                launch = self.launch("spawn", args[2], None)
                if launch is not None:
                    launch.finalize_on_close = args[0] == getattr(os, "P_WAIT", 0)
            elif event == "os.exec":
                self.close_all()
        except Exception as error:  # pylint: disable=broad-except
            self.failures.append(error)
            self.warn(
                "the external process tracer failed and recorded nothing of "
                "a launch: {}: {}".format(type(error).__name__, error)
            )

    def popen_event(self, executable, args, cwd, env):
        """``subprocess.Popen``: an argument list, or the shell's line"""
        # pylint: disable=unused-argument
        if isinstance(args, (str, bytes)):
            # Windows: Popen joins the list into one string, and with
            # shell=True wraps it as `cmd.exe /c "line"`.
            words = split_command_line(as_text(args))
            if len(words) >= 3 and words[1].lower() == "/c":
                return self.launch("popen", None, cwd, shell_command=words[2])
            return self.launch("popen", words, cwd)
        words = [as_text(word) for word in args]
        if (
            len(words) >= 3
            and words[1] == "-c"
            and os.path.basename(words[0]).endswith("sh")
        ):
            return self.launch("popen", None, cwd, shell_command=words[2])
        return self.launch("popen", words, cwd)

    # --- launches ----------------------------------------------------------

    def launch(self, kind, words, cwd, shell_command=None):
        """Record a launch: the files it names now, the candidates and the
        snapshot; returns the ``ExternalProcess``, or None when nothing is
        collecting"""
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
            recorded.add(os.path.normcase(os.path.realpath(resolved)))
        for name, resolved, declared in launch.candidates:
            if not os.path.isfile(resolved):
                continue
            self.add_written(launch, name, resolved, declared or "w")
            recorded.add(os.path.normcase(os.path.realpath(resolved)))
        if launch.before is None:
            return
        after = self.snapshot(launch.cwd)
        if after is None:
            return
        for path in sorted(after - launch.before):
            key = os.path.normcase(os.path.realpath(path))
            if key in recorded or key in self.recorded_since(launch.checkpoint):
                continue
            self.add_written(launch, relative_to_cwd(path), path, "w")

    def add_written(self, launch, name, resolved, mode):
        """An access to a file the process created: no content before"""
        access = self.collector.add_file_access(
            name, launch.activation, launch.checkpoint, path=None
        )
        access.content_hash_after = hash_file(resolved)
        access.mode = mode
        access.done = True
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
    tracer when a launch is bound and when its process ended; nested
    collections patch once"""
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
        _originals = (original_init, original_wait, original_poll)

        @wraps(original_init)
        def __init__(self, *args, **kwargs):
            tracer = _current
            try:
                original_init(self, *args, **kwargs)
            except BaseException:
                if tracer is not None:
                    tracer.launch_failed()
                raise
            if tracer is not None:
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
        popen.__init__, popen.wait, popen.poll = _originals
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


def split_command_line(text):
    """The words of a shell command line, as the shell of the system
    reads them: shlex on POSIX; on Windows the quotes are kept by shlex
    and stripped here, a best effort"""
    posix = os.name != "nt"
    try:
        words = shlex.split(text, posix=posix)
    except ValueError:
        words = text.split()
    if not posix:
        words = [
            word[1:-1] if len(word) > 1 and word[0] == word[-1] == '"' else word
            for word in words
        ]
    return words


def parse_command(args, shell=False):
    """The commands of a launch, each as ``(words, redirections)``

    ``args`` is an argument list (one command) or, with ``shell``, the
    line a shell runs: split into words, cut at ``|``, ``||``, ``&&``,
    ``;`` and ``&``, with the leading ``VAR=value`` words and ``env``
    (with its own assignments) dropped. ``redirections`` are ``(name,
    mode)`` pairs: ``w`` for ``>`` and ``&>``, ``a`` for ``>>``, ``r`` for
    ``<``; the operator may be attached to its target (``>out.txt``,
    ``2>err.txt``) or not.
    """
    if not shell:
        words = [as_text(word) for word in args]
        return [(words, [])] if words else []
    commands = []
    current = []
    for word in split_command_line(as_text(args)):
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
