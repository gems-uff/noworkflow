import hashlib
import os
from os.path import join, isdir, isfile

from .base import ContentDatabaseEngine
from .parallel import create_distributed, create_pool, create_threading
from . import safeopen

STANDARD_DATABASE_DIR = 'content'


class PlainEngine(ContentDatabaseEngine):
    def __init__(self, config):
        super(PlainEngine, self).__init__(config)

    def connect(self, should_mock=False):
        """Create content directory"""
        if not should_mock and not isdir(self.content_path):
            os.makedirs(self.content_path)

    def set_path(self, config):
        """Set content path"""
        self.content_path = os.path.join(config.provenance_path, STANDARD_DATABASE_DIR)

    @staticmethod
    def do_put(content_path, content):
        """Perform put operation. This is used in the distributed wrapper"""
        content_hash = hashlib.sha1(content).hexdigest()
        content_dirname = join(content_path, content_hash[:2])
        if not isdir(content_dirname):
            os.makedirs(content_dirname)
        content_filename = join(content_dirname, content_hash[2:])
        if not isfile(content_filename):
            with safeopen.std_open(content_filename, "wb") as content_file:
                content_file.write(content)
        return content_hash

    def put_attr(self, content, filename):
        """Return attributes for the do_put operation"""
        return (self.content_path, content)

    def put(self, content, filename):  # pylint: disable=method-hidden
        """Put content in the content database"""
        return self.do_put(*self.put_attr(content, filename))

    def get(self, content_hash):  # pylint: disable=method-hidden
        """Get content from the content database"""
        content_filename = join(self.content_path,
                                content_hash[:2],
                                content_hash[2:])
        with self.std_open(content_filename, "rb") as content_file:
            return content_file.read()

    def find_subhash(self, content_hash):
        """Get hash that starts by content_hash"""
        content_dirname = content_hash[:2]
        content_filename = content_hash[2:]
        content_dir = join(self.content_path, content_dirname)
        if not isdir(content_dir):
            return None
        for _, _, filenames in os.walk(content_dir):
            for name in filenames:
                if name.startswith(content_filename):
                    return content_dirname + name
        return None

    def gc(self, content_hash):
        """Do nothing for plain storage"""
        pass

    def commit_content(self, message):
        """Do nothing for plain storage"""
        pass


DistributedPlainEngine = create_distributed(PlainEngine)
PoolPlainEngine = create_pool(PlainEngine)
ThreadingPlainEngine = create_threading(PlainEngine)
