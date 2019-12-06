import io
import builtins
import codecs
import os
import threading

from contextlib import contextmanager

open_usage = {}

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
        try:
            mock_builtins = __builtins__["open"]
            __builtins__["open"] = std_open
        except:
            mock_builtins = __builtins__.open
            __builtins__.open = std_open
        yield
    finally:
        builtins.open = mock_open
        io.open = mock_io_open
        codecs.open = mock_codecs_open
        os.open = mock_os_open
        try:
            __builtins__["open"] = mock_builtins
        except:
            __builtins__.open = mock_builtins

def print_open():
    print(std_open)
    print(io_open)
    print(codecs_open.__code__.co_filename)
    print(os_open)

@contextmanager
def use_safe_open():
    try:
        ident = threading.current_thread().ident
        old = open_usage.get(ident, False)
        open_usage[ident] = True
        yield
    finally:
        open_usage[ident] = old

def should_use_safe_open():
    ident = threading.current_thread().ident
    return open_usage.get(ident, False)
