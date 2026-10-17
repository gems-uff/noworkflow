"""Port of tests/weather/simulation_dummy.py with a file read and a write

Every call site runs once and no user function is called inside another
call's arguments, so all five modes of `now export dataflow` work on it.
"""
import sys


def run_simulation(a, b):
    return a + b


def plot(data):
    return len(data)


with open(sys.argv[1]) as handle:
    data_a = handle.read().strip()
data_b = sys.argv[2]
data = run_simulation(data_a, data_b)
size = plot(data)
with open("result.txt", "w", newline="\n") as handle:
    handle.write(data)
