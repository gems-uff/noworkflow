import csv
import sys
import matplotlib.pyplot as plt
from simulator import simulate

def run_simulation(data_a, data_b):
    a = csv_read(data_a)
    b = csv_read(data_b)
    data = simulate(a, b)
    return data

def csv_read(f):
    reader = csv.reader(open(f, 'rU'), delimiter=':')
    data = []
    for row in reader:
        data.append(row)
    return data

def extract_column(data, column):
    col_data = []
    for row in data:
        col_data.append(float(row[column]))
    return col_data

def extract_temperature(data):
    return extract_column(data, 0)

def extract_precipitation(data):
    return extract_column(dat, 1)

def plot(data):
    t = extract_temperature(data)
    p = extract_precipitation(data)
    plt.scatter(t, p, marker='o')
    plt.xlabel('Temperature')
    plt.ylabel('Precipitation')
    plt.savefig("output.png")

#Main Program
data_a = sys.argv[1]
data_b = sys.argv[2]
data = run_simulation(data_a, data_b)
plot(data)
