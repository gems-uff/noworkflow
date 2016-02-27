# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now restore' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

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
        add_arg("-b", "--bypass-modules", action="store_true",
                help="bypass module dependencies analysis, assuming that no "
                     "module changes occurred since last execution")
        add_arg("-s", "--skip-script", action="store_true",
                help="skip main script")
        add_arg("-l", "--skip-local", action="store_true",
                help="skip local modules")
        add_arg("-a", "--skip-access", action="store_true",
                help="skip file access")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")

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
            return
        if code_hash is None and mode != "script":
            os.remove(path)
            print_msg("File {} removed".format(path), self.print_msg)
        elif code_hash is not None:
            load_file = content.get(code_hash)
            with open(path, "wb") as fil:
                fil.write(load_file)
            print_msg("File {} from trial {} restored".format(path, trial_id),
                      self.print_msg)

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
        trial = metascript.trial = Trial(trial_ref=args.trial)
        metascript.trial_id = trial.id
        metascript.name = trial.script
        metascript.fake_path(trial.script, "")
        metascript.paths[trial.script].code_hash = None

        restore_files = trial.versioned_files(**skip_dict(args))
        head = Trial.load_parent(trial.script, remove=False)

        last_files = head.versioned_files(**skip_dict(args))
        match, new_files = self.find_differences(last_files)
        if not match:
            self.create_backup(metascript, new_files)

        for path, info in viewitems(restore_files):
            self.restore(path, info["code_hash"], trial.id, mode=info["type"])

        trial.create_head()


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
    return {
        "skip_script": args.skip_script,
        "skip_local": args.skip_local,
        "skip_access": args.skip_access,
    }
