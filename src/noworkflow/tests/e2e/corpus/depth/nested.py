"""A list comprehension inside a function called from another function"""
import csv


def csv_read(path):
    data = []
    with open(path, newline="") as handle:
        for row in csv.reader(handle, delimiter=":"):
            data.append([float(value) for value in row])
    return data


def outer(path):
    return csv_read(path)


print(outer("data.dat"))
