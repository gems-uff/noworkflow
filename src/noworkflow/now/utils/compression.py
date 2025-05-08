# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

import gzip
from io import StringIO as StringIO
from io import BytesIO as IO

def gzip_compress(data):
    gzip_buffer = IO()
    gzip_file = gzip.GzipFile(mode='wb',
                              fileobj=gzip_buffer)
    gzip_file.write(data)
    gzip_file.close()
    return gzip_buffer.getvalue()

def gzip_uncompress(data):
    fakefile=IO(data)
    uncompressed = gzip.GzipFile(fileobj=fakefile, mode='rb')
    return uncompressed.read()