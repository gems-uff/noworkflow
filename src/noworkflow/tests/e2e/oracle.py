# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Compare a script run by plain Python with the same script under ``now run``

Collecting provenance must not change what the script does. ``run_both``
runs a script of the corpus twice in the same project directory, each time
from a fresh copy of the corpus: first with the interpreter that ``now``
runs on, then with ``now run``. ``differences`` lists every way the two
outcomes differ (the return code, stdout, stderr and the SHA-1 of every
file left in the project, the store excluded); no difference is the verdict
"runs like plain Python". ``assert_traced`` then checks that the run was
traced at all: a script that pyposast rejects with a ``SyntaxError`` runs
untransformed and compares equal.

Both runs use the same directory and the same synthetic environment, so a
script may print its own path or write absolute paths and still compare
equal, and nothing is normalized: one character more on either side is a
difference. The plain run drops the variables that start coverage in a
child process, because coverage of a process that never imports noWorkflow
warns on stderr.

A known defect is a ``Defect``: the ``xfail(strict=True)`` mark where it
shows, and the signature of the failure measured today. A test that fails
without that signature fails outright instead of passing as expected, so a
second defect hidden behind the first, or a new regression, cannot hide
behind the mark.
"""
import dataclasses
import difflib
import functools
import os
import shutil
import subprocess
import sys

import pytest

from .harness import CORPUS, PRESERVE_PREFIXES, runs_this_interpreter


@dataclasses.dataclass
class Outcome:
    """What one run of a script left: return code, outputs and files"""

    label: str
    returncode: int
    stdout: str
    stderr: str
    files: dict

    def __str__(self):
        return (
            "--- {} ---\nreturn code: {}\n[stdout]\n{}\n[stderr]\n{}\n"
            "[files]\n{}".format(
                self.label, self.returncode, self.stdout, self.stderr,
                "\n".join("{} {}".format(digest, path)
                          for path, digest in sorted(self.files.items()))
            )
        )


@dataclasses.dataclass(frozen=True)
class Defect:
    """A known defect of one test, on the versions and systems it shows

    ``reason`` starts with the issue that will fix it (``#NNN: ``) and says
    the mechanism; ``signature`` is a piece of text that the failing run
    prints today (an exception and its message, a line of the script's
    output), checked by ``expect_known_failure``. The mark applies on the
    Python versions ``since <= (major, minor) < before`` (each bound
    optional) and, when ``systems`` is given, only on the ``sys.platform``
    values it lists; elsewhere the test must pass. The range is the one
    measured on the matrix, never a guess: ``strict`` turns an unexpected
    pass into a failure.
    """

    reason: str
    signature: str
    since: tuple = None
    before: tuple = None
    systems: tuple = None

    def applies(self):
        version = sys.version_info[:2]
        if self.since is not None and version < tuple(self.since):
            return False
        if self.before is not None and version >= tuple(self.before):
            return False
        return self.systems is None or sys.platform in self.systems


def defect_marks(defects):
    """The ``xfail(strict=True)`` mark of the defects that apply here"""
    current = [defect for defect in defects if defect.applies()]
    if not current:
        return []
    return [pytest.mark.xfail(
        strict=True, raises=AssertionError,
        reason="; ".join(defect.reason for defect in current))]


def expect_known_failure(defects, text):
    """Fail outright unless ``text`` shows a known defect that applies

    Call it once the test knows that it fails, with everything the failing
    run printed. Without a defect that applies, it does nothing and the
    assertion that follows fails as usual. ``pytest.fail`` is not an
    ``AssertionError``, so the xfail mark cannot absorb it.
    """
    current = [defect for defect in defects if defect.applies()]
    if current and not any(defect.signature in text for defect in current):
        pytest.fail(
            "fails, but not with the signature of its known defect ({}); "
            "a second defect or a new regression:\n{}".format(
                " | ".join(repr(defect.signature) for defect in current),
                text),
            pytrace=False)


def plain_python(command):
    """The interpreter that runs the scripts traced by ``command``

    This interpreter under the default command. Under a ``NOW_E2E_CMD``,
    the interpreter its ``#!`` line names (a console script of a virtual
    environment), else the Python next to it (``now.exe`` in ``Scripts``),
    or None when there is none.
    """
    if runs_this_interpreter(command):
        return sys.executable
    try:
        with open(command[0], "rb") as handle:
            first = handle.readline(4096)
    except OSError:
        first = b""
    if first.startswith(b"#!"):
        named = first[2:].decode("utf-8", "replace").strip().split(" ")[0]
        if (os.path.basename(named).startswith("python")
                and os.path.isfile(named)):
            return named
    directory = os.path.dirname(command[0])
    for name in ("python", "python3", "python.exe"):
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate):
            return candidate
    return None


@functools.lru_cache(maxsize=None)
def child_version(command):
    """``(major, minor)`` of the Python that ``command`` traces with, or None
    """
    if runs_this_interpreter(command):
        return sys.version_info[:2]
    python = plain_python(command)
    if python is None:
        return None
    completed = subprocess.run(
        [python, "-c", "import sys; print(*sys.version_info[:2])"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=60)
    if completed.returncode != 0:
        return None
    return tuple(int(part) for part in completed.stdout.split())


def skip_unless_same_python(project):
    """Skip unless ``now`` traces with this interpreter's minor version

    The version gates and the marks of a ``Defect`` read the version of
    the interpreter that runs pytest. Under a ``NOW_E2E_CMD`` on another
    version they would gate the wrong scripts, and a script newer than the
    child's grammar would fail for that reason alone.
    """
    version = child_version(tuple(project.command))
    if version is None:
        pytest.skip("no Python found for {}".format(project.command[0]))
    if version != sys.version_info[:2]:
        pytest.skip("NOW_E2E_CMD traces with Python {}.{}; the version "
                    "gates and the marks follow this interpreter".format(
                        *version))


def fresh_copy(project, corpus):
    """Empty the project directory and copy ``corpus/<corpus>`` into it"""
    for path in project.path.iterdir():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    project.copy_corpus(corpus)


def run_plain(project, script, *args):
    """Run ``python <script> <args>`` in the project, as ``now`` would"""
    python = plain_python(project.command)
    if python is None:
        pytest.skip("no Python found for {}".format(project.command[0]))
    env = {key: value for key, value in project.env.items()
           if not key.startswith(PRESERVE_PREFIXES)}
    completed = subprocess.run(
        [python, script] + [str(arg) for arg in args],
        cwd=str(project.path),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return Outcome("python", completed.returncode, completed.stdout,
                   completed.stderr, project.files())


def run_traced(project, script, *args, flags=()):
    """Run ``now run <flags> <script> <args>`` in the project"""
    result = project.run("run", *flags, script, *args, expect=None,
                         allow_stderr=True)
    label = " ".join(("now run",) + tuple(flags))
    return Outcome(label, result.returncode, result.stdout, result.stderr,
                   project.files())


def run_both(project, corpus, script, *args, flags=()):
    """``(plain, traced)``: the script run by Python, then by ``now run``

    The store of the traced run stays in the project for the caller. A
    missing script fails outright, so that no xfail mark absorbs it.
    """
    if not (CORPUS / corpus / script).is_file():
        pytest.fail("no script {} in corpus/{}".format(script, corpus),
                    pytrace=False)
    fresh_copy(project, corpus)
    plain = run_plain(project, script, *args)
    fresh_copy(project, corpus)
    traced = run_traced(project, script, *args, flags=flags)
    return plain, traced


def differences(plain, traced):
    """Every way two outcomes differ, as readable lines; empty when equal"""
    found = []
    if plain.returncode != traced.returncode:
        found.append("return code: {} {}, {} {}".format(
            plain.label, plain.returncode, traced.label, traced.returncode))
    for stream in ("stdout", "stderr"):
        expected, actual = getattr(plain, stream), getattr(traced, stream)
        if expected != actual:
            diff = difflib.unified_diff(
                [repr(line) + "\n" for line in expected.splitlines(True)],
                [repr(line) + "\n" for line in actual.splitlines(True)],
                plain.label, traced.label, lineterm="\n")
            found.append("{} differs (one repr per line):\n{}".format(
                stream, "".join(diff)))
    for path in sorted(set(plain.files) | set(traced.files)):
        expected, actual = plain.files.get(path), traced.files.get(path)
        if expected == actual:
            continue
        if actual is None:
            found.append("file {}: only {} wrote it".format(path, plain.label))
        elif expected is None:
            found.append("file {}: only {} wrote it".format(
                path, traced.label))
        else:
            found.append("file {}: content differs ({} {}, {} {})".format(
                path, plain.label, expected, traced.label, actual))
    return found


def assert_same_outcome(plain, traced, defects=()):
    """Fail with both outcomes when the two runs differ

    ``defects`` are the known defects of the test: when the runs differ,
    the failure must carry the signature of one that applies.
    """
    found = differences(plain, traced)
    if not found:
        return
    message = "{} does not run like plain Python:\n{}\n\n{}\n\n{}".format(
        traced.label, "\n".join(found), plain, traced)
    expect_known_failure(defects, message)
    raise AssertionError(message)


def assert_traced(project):
    """Fail outright unless the store holds one trial with evaluations

    A script that pyposast rejects with a ``SyntaxError`` runs without the
    transformer (``Skipping transformer.``, printed only under ``-v``) and
    records no evaluation, while its outcome still equals plain Python's.
    """
    trials = project.trials()
    if len(trials) != 1:
        pytest.fail("expected one trial in the store, found {}".format(
            len(trials)), pytrace=False)
    evaluations = project.count("evaluation", trials[0]["id"])
    if evaluations == 0:
        pytest.fail("the trial recorded no evaluation: the script ran "
                    "without the transformer (see `now run -v`)",
                    pytrace=False)
