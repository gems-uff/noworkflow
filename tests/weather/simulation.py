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

def plot(data):
    #GetTemperature
    t = extract_column(data, 0)
    #GetPrecipitation
    p = extract_column(data, 1)
    plt.scatter(t, p, marker='o')
    plt.xlabel('Temperature')
    plt.ylabel('Precipitation')
    plt.savefig("output.png")

#Main Program
data_a = sys.argv[1]
data_b = sys.argv[2]
data = run_simulation(data_a, data_b)
plot(data)
