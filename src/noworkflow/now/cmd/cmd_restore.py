# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now restore' command"""

from __future__ import absolute_import, division, print_function, unicode_literals

import argparse
import os
import stat
import sys
import time
from datetime import datetime

from future.utils import viewitems

from ..collection.metadata import Metascript
from ..collection.prov_execution.external import is_placeholder
from ..persistence import content, persistence_config
from ..persistence.models import (
    Argument,
    CodeBlock,
    CodeComponent,
    FileAccess,
    Module,
    Tag,
    Trial,
)
from ..utils.cross_version import PY2, PY34, PY35
from ..utils.io import print_error, print_msg
from .command import Command


class Restore(Command):
    """Restore the files of a trial"""

    def __init__(self, *args, **kwargs):
        super(Restore, self).__init__(*args, **kwargs)
        self.print_msg = True
        # Set when a file that was asked for could not be restored; the
        # command goes on with the others and exits with 1 at the end.
        self.failed = False

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial", type=str, nargs="?", help="trial id or none for last trial")
        add_arg(
            "--dir",
            type=str,
            help="set project path where is the database. Default to current directory",
        )
        add_arg("-s", "--skip-script", action="store_true", help="skip main script")
        add_arg("-l", "--skip-local", action="store_true", help="skip local modules")
        add_arg("-a", "--skip-access", action="store_true", help="skip file access")

        add_arg(
            "-f",
            "--file",
            nargs=argparse.REMAINDER,
            type=str,
            help="R|FORMAT: [-h] [-i ID] [-t TARGET] [path] \n"
            "Restore a file from trial. Without <ID>, it restores \n"
            "the first version of the file in the trial (for a \n"
            "file the trial created, the content it wrote first). \n"
            "<ID> can be either the timestamp, the number of \n"
            "access, or the code hash \n"
            "<TARGET> specifies the target path (default to path)",
        )
        add_arg(
            "--message",
            type=str,
            default=None,
            help="add a message to the commit of the trial",
        )
        add_arg("--content-engine", type=str, help="set the content database engine")

    def create_backup(self, metascript, files, args):
        """Create a backup trial"""
        modules = metascript.modules_store
        accesses = metascript.file_accesses_store
        arguments = metascript.arguments_store

        old_id = metascript.trial_id
        metascript.trial_id = Trial.create(*metascript.create_trial_args())
        tid = metascript.trial_id
        metascript.create_arguments(args)
        metascript.arguments_store.add(tid, "restore", repr(old_id))

        for path, info in viewitems(files):
            if info["type"] == "script":
                metascript.path = path
                metascript.definition.create_code_block(
                    None, path, "script", False, True
                )
            elif info["type"] == "module":
                path = os.path.abspath(path)
                cid = metascript.definition.create_code_block(
                    None, path, "module", False, True
                )[1]
                version = None
                try:
                    if PY35:
                        import importlib.util

                        spec = importlib.util.spec_from_file_location(
                            info["name"], path
                        )
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                    elif PY34:
                        from importlib.machinery import SourceFileLoader

                        module = SourceFileLoader(info["name"], path).load_module()
                    elif PY2:
                        import imp

                        module = imp.load_source(info["name"], path)
                    version = metascript.deployment.get_version(module)
                except Exception:
                    pass
                metascript.deployment.add_module(
                    info["name"], version, path, cid, False, None
                )
            elif info["type"] == "access":
                aid = accesses.add(tid, path, info["checkpoint"])
                access = accesses[aid]
                access.content_hash_before = info["code_hash"]
                access.content_hash_after = info["code_hash"]
                access.mode = "a+"

        partial = True
        Trial.fast_update(tid, metascript.main_id, datetime.now(), "backup")
        CodeComponent.store(metascript.code_components_store, partial)
        CodeBlock.store(metascript.code_blocks_store, partial)
        Module.store(modules, partial)
        FileAccess.store(accesses, partial)
        Argument.store(arguments, partial)
        metascript.definition.store_provenance()

        Tag.create_automatic_tag(
            tid, None, None, None, metascript.trial.experiment_id, True
        )  # Adds a X.0.0 tag to the backup trial

        print_msg("Backup Trial {} created".format(metascript.trial_id), self.print_msg)
        content.commit_content(
            metascript.message or "Backup Trial {}".format(metascript.trial_id)
        )

    def restore(self, path, code_hash, trial_id, mode="normal", executable=False):
        """Restore file with <code_hash> from <trial_id>

        ``executable``: the file is a program the trial launched, which
        gets the executable bit when it is written (#205)
        """
        new_code_hash = file_hash(path)
        if code_hash == new_code_hash:
            return False
        if code_hash is None and mode != "script":
            os.remove(path)
            print_msg("File {} removed".format(path), self.print_msg)
            return True
        elif code_hash is not None:
            load_file = content.get(code_hash)
            if is_placeholder(load_file):
                # An executable above the cap of #203: its bytes were never
                # stored, and the placeholder must not replace them
                msg = "Unable to restore file {}".format(path)
                if trial_id:
                    msg += " from trial {}".format(trial_id)
                msg += ": the executable was too large to store. Skipping it"
                print_error(msg)
                self.failed = True
                return False
            try:
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(path, "wb") as fil:
                    fil.write(load_file)
                if executable:
                    make_executable(path)
                msg = "File {}".format(path)
                if trial_id:
                    msg += " from trial {}".format(trial_id)
                msg += " restored"

                print_msg(msg, self.print_msg)
                return True
            except NotADirectoryError as exc:
                msg = "Unable to restore file {}".format(path)
                if trial_id:
                    msg += " from trial {}".format(trial_id)
                msg += " due to {}. Skipping it".format(str(exc))

                print_error(msg)
                self.failed = True
                return False

    def restore_script(self, trial):
        """Restore the main script from <trial>"""
        self.restore(trial.script, trial.code_hash, trial.id)

    def find_differences(self, files):
        """Compare files with existing files
        Return match and dict with the most updated version of files

        match = True if all files match.
        """
        match = True
        new_files = {}

        for path, info in viewitems(files):
            new_code_hash = file_hash(path)
            if info["code_hash"] != new_code_hash:
                info["code_hash"] = new_code_hash
                match = False
                print_msg("{} has changed".format(path), self.print_msg)
            new_files[path] = info
        return match, new_files

    def execute(self, args):
        """Restore the trial, or one of its files with ``-f``

        Returns 1 when something that was asked for was not restored (a
        file version that does not exist, a file that could not be
        written), 0 otherwise; a file that already has the content asked
        for is nothing to do, not a failure.
        """
        metascript = Metascript().read_restore_args(args)
        persistence_config.connect_existing(args.dir or os.getcwd())
        self.trial = trial = metascript.trial = Trial(trial_ref=args.trial)
        metascript.trial_id = trial.id
        metascript.name = trial.script
        metascript.path = trial.path

        restore_files = trial.versioned_files(**skip_dict(args))
        if not args.file:
            head = Trial.load_parent(trial.script, remove=False)

            last_files = head.versioned_files(**skip_dict(args))
            match, new_files = self.find_differences(last_files)
            if not match:
                self.create_backup(metascript, new_files, args)

            programs = launched_programs(trial)
            for path, info in viewitems(restore_files):
                self.restore(
                    path,
                    info["code_hash"],
                    trial.id,
                    mode=info["type"],
                    executable=real_path(path) in programs,
                )

            trial.create_head()
            content.close()
        else:
            parser = argparse.ArgumentParser(
                prog="{} restore {} file".format(
                    os.path.basename(sys.argv[0]), trial.id
                )
            )
            parser.add_argument("path", type=str)
            parser.add_argument(
                "-i",
                "--id",
                default=None,
                type=str,
                help="time ([X|]YYYY-MM-DD HH:MM:SS.ffffff), number of "
                "access or hash. The optional X in the time, indicates "
                "if we should get the content before of after the "
                "access: X = B means before the access, X = A means "
                "after. Example: 'A|2016-02-27 00:00' will query the "
                "file accessed at midnight, and get its content after "
                "the access. Without it, the first version of the file "
                "in the trial: the content before its first access, or, "
                "for a file the trial created, the content after it",
            )
            parser.add_argument(
                "-t", "--target", type=str, help="target path (default to path)"
            )

            parsed = parser.parse_args(args.file)

            restore = self.find_file(args.trial, parsed.path, parsed.id)
            if not restore:
                print_error("File version not found!")
                self.failed = True
            elif restore[1] is None and parsed.target:
                # A version without content (the file did not exist) would
                # delete the target, a file the trial never saw (#246)
                print_error(
                    "File {} did not exist at that point of the trial: "
                    "{} left as it is".format(parsed.path, parsed.target)
                )
                self.failed = True
            else:
                path = parsed.target or parsed.path
                executable = real_path(parsed.path) in launched_programs(trial)
                if (
                    not self.restore(path, restore[1], None, executable=executable)
                    and not self.failed
                ):
                    print_msg("File has not changed!", self.print_msg)
            content.close()
        return 1 if self.failed else 0

    def find_file(self, tid, path, fid):  # pylint: disable=no-self-use
        """Find file according to timestamp, code_hash, and number of access"""
        if sys.version_info < (3, 0):
            if tid:
                tid = tid.decode("utf-8")
            path = path.decode("utf-8")
            fid = fid.decode("utf-8")

        if fid is None:
            if tid:
                return first_version(Trial(tid), path)
            fid = "1"

        splitted = fid.split("|")
        _time = time_str(splitted[-1])
        if _time:
            # timestamp
            text, _ = _time
            trial = Trial.find_by_name_and_time(path, text, trial=tid)
            if trial:
                return trial.script, trial.code_hash
            access = FileAccess.find_by_name_and_time(path, text, trial=tid)
            if access:
                if splitted[0] == "A":
                    return access.name, access.content_hash_after
                return access.name, access.content_hash_before
        if len(fid) >= 6:
            # at least 6 letters to look for code hash
            code_hash = content.find_subhash(fid)
            if code_hash:
                return path, code_hash

        if tid and fid.isnumeric():
            # Count accesses
            fid = int(fid)
            trial = Trial(tid)
            for i, result in enumerate(trial.iterate_accesses(path)):
                if fid == i + 1:
                    return path, result[1]["code_hash"]


def first_version(trial, path):
    """The version ``-f`` restores without ``-i``: the first one the trial
    has of ``path``, its script, a local module or the content before its
    first access; for a file the trial created, whose first access has no
    content before, the content after that access (#246). None when the
    trial never saw the file"""
    versions = trial.iterate_accesses(path)
    first = next(versions, None)
    if first is None:
        return None
    info = first[1]
    if info["type"] == "access" and info["code_hash"] is None:
        # iterate_accesses yields each access before, then after
        after = next(versions, None)
        if after is not None:
            return path, after[1]["code_hash"]
    return path, info["code_hash"]


def launched_programs(trial):
    """The real paths of the programs the trial launched (and of the
    libraries it loaded through ``ctypes``) that lie in the project

    #203 records them in the module table, named as the command line names
    them, beside the modules the script imports; an imported module is
    named after its file (``helper`` for ``helper.py``, ``_dbm`` for
    ``_dbm.cpython-315-darwin.so``, ``pkg`` for ``pkg/__init__.py``), and
    anything else is a program. The store records no file mode: these are
    the files ``restore`` makes executable (#205).
    """
    programs = set()
    # pylint: disable=not-an-iterable
    for module in trial.local_modules:
        stem, dot, _ = os.path.basename(module.path).partition(".")
        imported = dot and stem in (module.name.rpartition(".")[2], "__init__")
        if not imported:
            programs.add(real_path(module.path))
    return programs


def real_path(path):
    """The real path of a project file, for comparisons"""
    return os.path.normcase(
        os.path.realpath(os.path.join(persistence_config.base_path, path))
    )


def make_executable(path):
    """``chmod +x``: execute permission wherever there is read permission;
    Windows has no executable bit"""
    if os.name == "nt":
        return
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | (mode & 0o444) >> 2)


def time_str(arg):
    """Convert arg to time with optional format.
    Return arg, converted time if converted or None, otherwise
    """
    current = ""
    extra = "%Y", "-%m", "-%d", " %H", ":%M", ":%S", ".%f"
    for part in extra:
        current += part
        try:
            converted = time.strptime(arg, current)
            return arg, converted
        except ValueError:
            pass
    return None


def file_hash(path):
    """Return hash of file in path or None"""
    abs_path = os.path.join(persistence_config.base_path, path)
    if not os.path.isfile(abs_path):
        return None
    else:
        with open(abs_path, "rb") as fil:
            return content.put(fil.read(), abs_path)


def skip_dict(args):
    """Skip specific files"""
    if args.file:
        return {}
    return {
        "script": not args.skip_script,
        "local": not args.skip_local,
        "access": not args.skip_access,
    }
