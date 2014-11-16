from __future__ import absolute_import

from datetime import datetime


FORMAT = '%Y-%m-%d %H:%M:%S.%f'


def calculate_duration(activation):
    return int((
        datetime.strptime(activation['finish'], FORMAT) -
        datetime.strptime(activation['start'], FORMAT)
    ).total_seconds() * 1000000)
