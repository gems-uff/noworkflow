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

from datetime import datetime
from future.utils import viewitems

from ..collection.metadata import Metascript
from ..persistence.models import Trial, Module, FileAccess, Tag
from ..persistence.models import CodeComponent, CodeBlock, Argument
from ..persistence import persistence_config, content
from ..utils.io import print_msg
from ..utils.cross_version import PY34, PY35, PY2

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
        add_arg("--message", type=str, default=None,
                help="add a message to the commit of the trial")
        add_arg("--content-engine", type=str,
                help="set the content database engine")


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
                        module = SourceFileLoader(
                            info["name"], path
                        ).load_module()
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
        
        Tag.create_automatic_tag(tid, None, None, None, metascript.trial.experiment_id, True) # Adds a X.0.0 tag to the backup trial

        print_msg("Backup Trial {} created".format(metascript.trial_id),
                  self.print_msg)
        content.commit_content(metascript.message or "Backup Trial {}".format(metascript.trial_id))

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
            try:
                with open(path, "wb") as fil:
                    fil.write(load_file)
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

                print_msg(msg, self.print_msg)
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

            for path, info in viewitems(restore_files):
                self.restore(path, info["code_hash"], trial.id,
                             mode=info["type"])

            trial.create_head()
            content.close()
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
            content.close()

    def find_file(self, tid, path, fid):                                         # pylint: disable=no-self-use
        """Find file according to timestamp, code_hash, and number of access"""
        if sys.version_info < (3, 0):
            if tid:
                tid = tid.decode("utf-8")
            path = path.decode("utf-8")
            fid = fid.decode("utf-8")

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
