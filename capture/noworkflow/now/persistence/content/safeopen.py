import io
import builtins
import codecs
import os

from contextlib import contextmanager

std_open = open
io_open = io.open
codecs_open = codecs.open
os_open = os.open

@contextmanager
def restore_open():
    try:
        mock_open = builtins.open
        mock_io_open = io.open
        mock_codecs_open = codecs.open
        mock_os_open = os.open
        builtins.open = std_open
        io.open = io_open
        codecs.open = codecs_open
        os.open = os_open
        yield
    finally:
        builtins.open = mock_open
        io.open = mock_io_open
        codecs.open = mock_codecs_open
        os.open = mock_os_open
