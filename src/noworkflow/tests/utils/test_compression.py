# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``utils/compression.py``: the gzip streams of push, pull and the vis

``gzip_compress`` and ``gzip_uncompress`` wrap ``gzip.GzipFile`` over a
buffer: ``now push`` compresses what it sends, ``now pull`` uncompresses
what it receives, and the vis server does both, for its responses and for
the requests it is sent. The expected values come
from the standard library's own ``gzip.compress`` and ``gzip.decompress``,
which implement RFC 1952 independently of these wrappers, so a stream one
side writes must be one the other side reads.
"""
import gzip

import pytest

from noworkflow.now.utils.compression import gzip_compress, gzip_uncompress

# Text with a non-ASCII character, repeated so that compression pays off.
DATA = "provenance é\n".encode("utf-8") * 100
# The first two bytes of every gzip member (RFC 1952, section 2.3.1).
GZIP_MAGIC = b"\x1f\x8b"


def test_gzip_compress_writes_a_stream_the_standard_library_reads():
    """The output is a gzip stream, shorter than repetitive input, that
    ``gzip.decompress`` reads back unchanged"""
    compressed = gzip_compress(DATA)
    assert compressed[:2] == GZIP_MAGIC
    assert len(compressed) < len(DATA)
    assert gzip.decompress(compressed) == DATA


def test_gzip_uncompress_reads_a_stream_the_standard_library_wrote():
    """What ``gzip.compress`` wrote comes back unchanged"""
    assert gzip_uncompress(gzip.compress(DATA)) == DATA


def test_gzip_round_trip_of_empty_bytes():
    """Empty input survives the round trip, and an empty stream reads as
    empty bytes, as it does for ``gzip.decompress``"""
    assert gzip_uncompress(gzip_compress(b"")) == b""
    assert gzip.decompress(b"") == b""
    assert gzip_uncompress(b"") == b""


def test_gzip_uncompress_joins_the_members_of_a_multi_member_stream():
    """A stream of several gzip members reads as their concatenation
    (RFC 1952, section 2.2)"""
    stream = gzip.compress(b"first ") + gzip.compress(b"second")
    assert gzip_uncompress(stream) == b"first second"


def test_gzip_compress_rejects_text():
    """Text must be encoded first: ``GzipFile.write`` takes bytes-like
    objects only (``now push`` encodes its JSON before compressing)"""
    # 3.11 words it "memoryview: a bytes-like object is required, ...".
    with pytest.raises(TypeError, match="bytes-like object is required"):
        gzip_compress("text")


def test_gzip_uncompress_rejects_data_that_is_not_gzip():
    """Bytes without the gzip magic number are rejected"""
    with pytest.raises(gzip.BadGzipFile):
        gzip_uncompress(b"not a gzip stream")


def test_gzip_uncompress_rejects_a_truncated_stream():
    """A stream cut before its trailer is rejected instead of being read as
    shorter data"""
    with pytest.raises(EOFError):
        gzip_uncompress(gzip_compress(DATA)[:-4])
