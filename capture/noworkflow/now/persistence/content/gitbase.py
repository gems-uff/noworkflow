import os
import hashlib

from collections import Counter

from ...utils.cross_version import bytes_string
from . import git_system
from .base import ContentDatabaseEngine


GIT_DATABASE_DIR = 'content.git'


class GitContentDatabaseEngine(ContentDatabaseEngine):
    def __init__(self, config):
        super(GitContentDatabaseEngine, self).__init__(config)
        self._commit_name = 'Noworkflow'
        self._commit_email = 'noworkflow@noworkflow.com'
        self._commit_ref = 'refs/heads/master'
        self._initial_message = "Initial Commit"
        self.name_counter = Counter()

    def set_path(self, config):
        """Set content path"""
        self.content_path = os.path.join(config.provenance_path, GIT_DATABASE_DIR)

    def gc(self, aggressive=False):
        git_system.garbage_collection(self.content_path, aggressive)

    def _inc_name(self, filename):
        self.name_counter[filename] += 1
        count = self.name_counter[filename] 
        if count == 1:
            return filename
        return "{} - v{}".format(filename, count)

    def _get_hash_from_content(self, content):
        git_content = bytes_string('blob {}'.format((len(content)))) + b'\0'
        hash = hashlib.sha1(git_content + content).hexdigest()
        return hash


