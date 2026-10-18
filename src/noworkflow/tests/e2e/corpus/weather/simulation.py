"""Deterministic port of tests/weather/simulation.py

Reads two data files, imports a local module and writes an output file,
without matplotlib and without sleeping.
"""
import csv
import sys

from simulator import simulate


def csv_read(path):
    data = []
    with open(path, newline="") as handle:
        for row in csv.reader(handle, delimiter=":"):
            data.append([float(value) for value in row])
    return data


def extract_column(data, column):
    col_data = []
    for row in data:
        col_data.append(row[column])
    return col_data


def run_simulation(path_a, path_b, scale):
    a = csv_read(path_a)
    b = csv_read(path_b)
    return simulate(a, b, scale)


def write_output(path, data):
    temperature = extract_column(data, 0)
    precipitation = extract_column(data, 1)
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["temperature", "precipitation"])
        for t, p in zip(temperature, precipitation):
            writer.writerow([t, p])
    return len(temperature)


# Main Program
data_a = sys.argv[1]
data_b = sys.argv[2]
scale = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
data = run_simulation(data_a, data_b, scale)
total = write_output("output.csv", data)
print("rows:", total)
