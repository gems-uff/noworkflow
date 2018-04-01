import time
import csv
from functools import wraps
from os.path import join, isdir, isfile

PROF_DATA = {}


def profile(fn):
    @wraps(fn)
    def with_profiling(*args, **kwargs):
        start_time = time.time()

        ret = fn(*args, **kwargs)

        elapsed_time = time.time() - start_time

        if fn.__name__ not in PROF_DATA:
            PROF_DATA[fn.__name__] = [0, []]
        PROF_DATA[fn.__name__][0] += 1
        PROF_DATA[fn.__name__][1].append(elapsed_time)

        return ret

    return with_profiling


def print_prof_data():
    print('exporting results...')

    csv_file = 'put_time.csv'
    if not isfile(csv_file):
        file = open(csv_file, "w+")
        writer = csv.writer(file, delimiter=';')
        writer.writerow(['function', 'called_times', 'max_time', 'avg_time'])
    else:
        file = open(csv_file, "a")
        writer = csv.writer(file, delimiter=';')

    for fname, data in PROF_DATA.items():
        max_time = max(data[1])
        avg_time = sum(data[1]) / len(data[1])

        writer.writerow([fname, data[0], max_time, avg_time])

    file.close()


def clear_prof_data():
    global PROF_DATA
    PROF_DATA = {}
