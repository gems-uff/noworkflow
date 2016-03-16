# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now restore' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import argparse
import os
import sys
import time

from future.utils import viewitems

from ..collection.metadata import Metascript
from ..persistence.models import Trial, Module, Dependency, FileAccess
from ..persistence import persistence_config, content
from ..utils.io import print_msg

from .command import Command


class Restore(Command):
    """Restore the files of a trial"""

    def __init__(self, *args, **kwargs):
        super(Restore, self).__init__(*args, **kwargs)
        self.print_msg = True

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial", type=str, nargs="?",
                help="trial id or none for last trial")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")
        add_arg("-s", "--skip-script", action="store_true",
                help="skip main script")
        add_arg("-l", "--skip-local", action="store_true",
                help="skip local modules")
        add_arg("-a", "--skip-access", action="store_true",
                help="skip file access")

        add_arg("-f", "--file", nargs=argparse.REMAINDER,
                type=str,
                help="R|FORMAT: [-h] [-i ID] [-t TARGET] [path] \n"
                     "Restore a file from trial. Without <ID>, it restores \n"
                     "the first access to file. <ID> can be either the \n"
                     "timestamp, the number of access, or the code hash \n"
                     "<TARGET> specifies the target path (default to path)")


    def create_backup(self, metascript, files):
        """Create a backup trial"""
        modules = metascript.modules_store
        dependencies = metascript.dependencies_store
        accesses = metascript.file_accesses_store
        for path, info in viewitems(files):
            if info["type"] == "script":
                metascript.fake_path(path, "")
                metascript.paths[path].code_hash = info["code_hash"]
            elif info["type"] == "module":
                path = os.path.abspath(path)
                version = metascript.deployment.get_version(info["name"])
                mod = (info["name"], version, path, info["code_hash"])
                mid = Module.fast_load_module_id(*mod) or modules.add(*mod)
                dependencies.add(mid)
            elif info["type"] == "access":
                aid = accesses.add(path)
                access = accesses[aid]
                access.content_hash_before = info["code_hash"]
                access.content_hash_after = info["code_hash"]
                access.mode = "a+"

        metascript.trial_id = Trial.store(
            *metascript.create_trial_args(
                args="<restore {}>".format(metascript.trial_id), run=False
            )
        )

        tid, partial = metascript.trial_id, True
        Module.fast_store(tid, modules, partial)
        Dependency.fast_store(tid, dependencies, partial)
        FileAccess.fast_store(tid, accesses, partial)

        print_msg("Backup Trial {} created".format(metascript.trial_id),
                  self.print_msg)

    def restore(self, path, code_hash, trial_id, mode="normal"):
        """Restore file with <code_hash> from <trial_id>"""
        new_code_hash = file_hash(path)
        if code_hash == new_code_hash:
            return False
        if code_hash is None and mode != "script":
            os.remove(path)
            print_msg("File {} removed".format(path), self.print_msg)
            return True
        elif code_hash is not None:
            load_file = content.get(code_hash)
            with open(path, "wb") as fil:
                fil.write(load_file)
            msg = "File {}".format(path)
            if trial_id:
                msg += " from trial {}".format(trial_id)
            msg += " restored"

            print_msg(msg, self.print_msg)
            return True

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
        persistence_config.connect_existing(args.dir or os.getcwd())
        metascript = Metascript().read_restore_args(args)
        self.trial = trial = metascript.trial = Trial(trial_ref=args.trial)
        metascript.trial_id = trial.id
        metascript.name = trial.script
        metascript.fake_path(trial.script, "")
        metascript.paths[trial.script].code_hash = None

        restore_files = trial.versioned_files(**skip_dict(args))
        if not args.file:
            head = Trial.load_parent(trial.script, remove=False)

            last_files = head.versioned_files(**skip_dict(args))
            match, new_files = self.find_differences(last_files)
            if not match:
                self.create_backup(metascript, new_files)

            for path, info in viewitems(restore_files):
                self.restore(path, info["code_hash"], trial.id,
                             mode=info["type"])

            trial.create_head()
        else:
            parser = argparse.ArgumentParser(prog="{} restore {} file".format(
                os.path.basename(sys.argv[0]), trial.id))
            parser.add_argument("path", type=str)
            parser.add_argument(
                "-i", "--id", default="1", type=str,
                help="time ([X|]YYYY-MM-DD HH:MM:SS.ffffff), number of "
                     "access or hash. The optional X in the time, indicates "
                     "if we should get the content before of after the "
                     "access: X = B means before the access, X = A means "
                     "after. Example: 'A|2016-02-27 00:00' will query the "
                     "file accessed at midnight, and get its content after "
                     "the access")
            parser.add_argument(
                "-t", "--target", type=str,
                help="target path (default to path)")

            parsed = parser.parse_args(args.file)

            restore = self.find_file(args.trial, parsed.path, parsed.id)
            if not restore:
                print_msg("File version not found!", self.print_msg)
            else:
                path = parsed.target or parsed.path
                if not self.restore(path, restore[1], None):
                    print_msg("File has not changed!", self.print_msg)

    def find_file(self, tid, path, fid):                                         # pylint: disable=no-self-use
        """Find file according to timestamp, code_hash, and number of access"""
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
            return content.put(fil.read())


def skip_dict(args):
    """Skip specific files"""
    if args.file:
        return {}
    return {
        "skip_script": args.skip_script,
        "skip_local": args.skip_local,
        "skip_access": args.skip_access,
    }
