"""Binary event log, imported by open_wrapper_warning.py"""
import warnings


def open_log(path):
    return open(path, "wb", buffering=1)


def legacy_open_log(path):
    warnings.warn("use open_log", DeprecationWarning, stacklevel=1)
    return open(path, "wb")
