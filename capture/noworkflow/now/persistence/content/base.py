import io
import codecs
import os
import builtins
import hashlib

from contextlib import contextmanager
from . import safeopen

class ContentDatabaseEngine(object):
    def __init__(self, config):
        self.content_path = None
        self.std_open = open  # Original Python open function.
        self.io_open = io.open  # Original Python open function in Python 3
        self.codecs_open = codecs.open  # Alternative open function
        self.os_open = os.open  # Low level open function
        self.set_path(config)

    def restore_open(self):
        return safeopen.restore_open()

    def mock(self, config):
        self.temp = {}

        def put(content=None, filename="generic"):
            """Mock put"""
            hash_code = hashlib.sha1(content).hexdigest()
            self.temp[hash_code] = content
            return hash_code

        def get(content_hash):
            """Mock get"""
            return self.temp[content_hash]

        self.put = put
        self.get = get

    def connect(self, should_mock=False):
        """Connect to content database"""
        raise NotImplementedError("Implement in subclass")

    def set_path(self, config):
        """Set content path"""
        raise NotImplementedError("Implement in subclass")

    def put(self, content, filename="generic"):  # pylint: disable=method-hidden
        """Put file into database"""
        raise NotImplementedError("Implement in subclass")

    def get(self, content_hash):  # pylint: disable=method-hidden
        """Get file from database"""
        raise NotImplementedError("Implement in subclass")

    def find_subhash(self, content_hash):
        """Find hash in database"""
        raise NotImplementedError("Implement in subclass")

    def gc(self, content_hash):
        """Collect garbage from database"""
        raise NotImplementedError("Implement in subclass")

    def commit_content(self, message):
        """Commit content"""
        raise NotImplementedError("Implement in subclass")

    def close(self):
        """Close connection"""
        pass  # do nothing by default
