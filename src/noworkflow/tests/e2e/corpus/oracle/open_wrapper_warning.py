"""A warning raised by ``open`` names the code that called it
(#296)

Opening a binary file with line buffering warns that the buffering is
ignored, and the warning names the file of the code that called ``open``:
``toolkit.binlog``, a module of the script's own package that ``now run``
does not rewrite under its default context, so no call of the script's
stands between the two. The script records the warnings and prints where
each one points; the warning that ``toolkit.binlog`` raises itself is the
control.
"""
import os
import warnings

from toolkit import binlog

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    with binlog.open_log("events.bin") as log:
        log.write(b"start\n")
    with binlog.legacy_open_log("legacy.bin") as log:
        log.write(b"start\n")
print([(os.path.basename(warning.filename), warning.category.__name__)
       for warning in caught])
