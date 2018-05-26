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
        #PROF_DATA[fn.__name__][2].append(len(args[1].encode('utf-8')))

        return ret

    return with_profiling


def print_prof_data(content_database_name):
    print_put_file(content_database_name)
    #print_time_size(content_database_name)


def print_time_size(content_database_name):
    csv_file = 'put_time_size.csv'
    if not isfile(csv_file):
        file = open(csv_file, "w+")
        writer = csv.writer(file, delimiter=';')
        writer.writerow(['content_database', 'function', 'time', 'size'])
    else:
        file = open(csv_file, "a")
        writer = csv.writer(file, delimiter=';')

    print(PROF_DATA)

    calls = PROF_DATA['put'][0]
    times = PROF_DATA['put'][1]
    sizes = PROF_DATA['put'][2]

    for i in xrange(0, calls):
        writer.writerow([str(content_database_name), 'put', times[i], sizes[i]])

    file.close()


def print_put_file(content_database_name):
    csv_file = 'put_time.csv'
    if not isfile(csv_file):
        file = open(csv_file, "w+")
        writer = csv.writer(file, delimiter=';')
        writer.writerow(['function', 'called_times', 'max_time', 'avg_time', 'content_database'])
    else:
        file = open(csv_file, "a")
        writer = csv.writer(file, delimiter=';')

    for fname, data in PROF_DATA.items():
        max_time = max(data[1])
        avg_time = sum(data[1]) / len(data[1])

        writer.writerow([fname, data[0], max_time, avg_time, content_database_name])

    file.close()


def clear_prof_data():
    global PROF_DATA
    PROF_DATA = {}
