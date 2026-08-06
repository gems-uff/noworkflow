# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Proxy that captures content_hash_after when a write-mode file is closed"""

import os
import io

from ...persistence import content


class FileAccessProxy(object):
    """Proxy around a real file object.

    Delegates every operation to the wrapped file and captures
    ``content_hash_after`` at the moment the file is closed (explicit
    ``close()`` or ``with`` block exit). This is required because the
    ``open`` call is itself a noWorkflow activation that closes right after
    returning the (just-truncated) file object; capturing the "after" hash
    when that activation closes would always hash an empty file.
    """
    # pylint: disable=protected-access

    def __init__(self, file, file_access, collector):
        object.__setattr__(self, "_f", file)
        object.__setattr__(self, "_fa", file_access)
        object.__setattr__(self, "_collector", collector)

    def _capture_after(self):
        """Re-read the file from disk and store its content_hash_after once"""
        file_access = self._fa
        # The file is no longer open for the never-closed fallback in store().
        self._collector.open_write_files.pop(file_access, None)
        if (file_access.content_hash_after is None
                and os.path.exists(file_access.name)):
            with content.std_open(file_access.name, "rb") as fil:
                file_access.content_hash_after = content.put(
                    fil.read(), file_access.name
                )
        file_access.done = True

    def close(self):
        """Close the real file (flushing it) before capturing the hash"""
        result = self._f.close()
        self._capture_after()
        return result

    def __enter__(self):
        self._f.__enter__()
        return self

    def __exit__(self, *exc):
        result = self._f.__exit__(*exc)
        self._capture_after()
        return result

    # Dunders that bypass __getattr__ must be delegated explicitly:
    def __iter__(self):
        return iter(self._f)

    def __next__(self):
        return next(self._f)

    def write(self, *args, **kwargs):
        return self._f.write(*args, **kwargs)

    def read(self, *args, **kwargs):
        return self._f.read(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._f, name)

    def __setattr__(self, name, value):
        setattr(self._f, name, value)


class TextFileProxy(FileAccessProxy):
    """FileAccessProxy for text files (io.TextIOBase)"""


class BufferedFileProxy(FileAccessProxy):
    """FileAccessProxy for buffered binary files (io.BufferedIOBase)"""


class RawFileProxy(FileAccessProxy):
    """FileAccessProxy for raw/unbuffered binary files (io.RawIOBase)"""


# Register one proxy class per io category so that isinstance(proxy, io.*)
# keeps reporting the real file category without breaking attribute
# delegation (subclassing io.* directly would resolve methods on the base
# before __getattr__, hiding the real file's state).
io.TextIOBase.register(TextFileProxy)
io.BufferedIOBase.register(BufferedFileProxy)
io.RawIOBase.register(RawFileProxy)


def wrap_file_access(file, file_access, collector):
    """Wrap a write-mode file object in the proxy matching its io category"""
    if isinstance(file, io.TextIOBase):
        return TextFileProxy(file, file_access, collector)
    if isinstance(file, io.BufferedIOBase):
        return BufferedFileProxy(file, file_access, collector)
    if isinstance(file, io.RawIOBase):
        return RawFileProxy(file, file_access, collector)
    return FileAccessProxy(file, file_access, collector)
